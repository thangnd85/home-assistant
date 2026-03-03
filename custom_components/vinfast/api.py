import requests
import json
import time
import datetime
import hashlib
import hmac
import base64
import urllib.parse
import threading
import logging
import uuid
import random
import paho.mqtt.client as mqtt

from .const import (
    AUTH0_DOMAIN, AUTH0_CLIENT_ID, API_BASE, 
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID, 
    BASE_SENSORS, VF3_SENSORS, VF567_SENSORS, VF89_SENSORS, VEHICLE_SPECS
)

_LOGGER = logging.getLogger(__name__)

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError): return default

class VinFastAPI:
    def __init__(self, email, password, vin=None, vehicle_name="Xe VinFast", options=None):
        self.email = email
        self.password = password
        self.access_token = None
        self.vin = vin
        self.user_id = None
        self.vehicle_name = vehicle_name
        self.vehicle_model_display = "Unknown" 
        self.options = options or {}
        
        self.client = None
        self.callbacks = []
        self._running = False
        
        CHARS = "0123456789qwertyuiopasdfghjklzxcvbnm"
        self._mqtt_client_id_rand = "".join(random.choice(CHARS) for _ in range(20))
        
        self._last_data = {
            "api_vehicle_status": "Đang khởi động...",
            "api_current_address": "Đang kết nối...",
        }  
        
        self.cost_per_kwh = safe_float(self.options.get("cost_per_kwh", 4000), 4000)
        self.gas_price = safe_float(self.options.get("gas_price", 20000), 20000)
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", 0.15), 0.15)
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", 15.0), 15.0)

        # Trạng thái thiết yếu
        self._is_moving = False
        self._is_charging = False
        self._last_is_charging = False 
        self._last_gear = "1"
        self._last_lat_lon = None
        
        self._last_activity_time = time.time()
        self._force_full_scan = False
        
        # Biến quản lý Trip 30 phút
        self._is_trip_active = False
        self._last_move_time = time.time()
        self._trip_start_odo = None
        self._trip_start_time = None
        self._trip_start_soc = None
        
        # Biến phân tích Smart Profiling (Dải tốc độ)
        self._eff_soc = None
        self._eff_odo = None
        self._eff_speeds = []
        self._eff_stats = {}

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            if self._last_data: cb(self._last_data)

    def stop(self):
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def login(self):
        url = f"https://{AUTH0_DOMAIN}/oauth/token"
        res = requests.post(url, json={
            "client_id": AUTH0_CLIENT_ID, "grant_type": "password",
            "username": self.email, "password": self.password,
            "scope": "openid profile email offline_access", "audience": API_BASE
        }, timeout=15)
        res.raise_for_status()
        self.access_token = res.json()["access_token"]
        return self.access_token

    def _update_dynamic_costs(self):
        model = self.vehicle_model_display.upper()
        target_spec = {"ev_kwh_per_km": 0.15, "gas_km_per_liter": 15.0} 
        for k, v in VEHICLE_SPECS.items():
            if k.replace(" ", "") in model.replace(" ", ""):
                target_spec = v
                break
        fallback_ev = target_spec.get("ev_kwh_per_km", 0.15)
        fallback_gas = target_spec.get("gas_km_per_liter", 15.0)
        
        ev_opt = self.options.get("ev_kwh_per_km")
        self.ev_kwh_per_km = fallback_ev if ev_opt is None else safe_float(ev_opt, fallback_ev)
        gas_opt = self.options.get("gas_km_per_liter")
        self.gas_km_per_liter = fallback_gas if gas_opt is None else safe_float(gas_opt, fallback_gas)

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        headers = {"Authorization": f"Bearer {self.access_token}", "x-service-name": "CAPP", "x-app-version": "2.17.5", "x-device-platform": "android"}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        vehicles = res.json().get("data", [])
        if vehicles:
            v = vehicles[0]
            self.user_id = str(v.get("userId", ""))
            if not self.vin: self.vin = v.get("vinCode", "")
            self.vehicle_name = v.get("customizedVehicleName") or v.get("vehicleName") or "Xe VinFast"
            self.vehicle_model_display = v.get("marketingName") or v.get("dmsVehicleModel") or "VF"
            
            self._last_data["api_vehicle_name"] = self.vehicle_name
            self._last_data["api_vehicle_model"] = self.vehicle_model_display
            
            self._update_dynamic_costs() 
            self._calculate_advanced_stats()
            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)
        return vehicles

    def send_remote_command(self, command_type, params=None):
        payload = {"commandType": command_type, "vinCode": self.vin, "params": params or {}}
        res = self._post_api("ccaraccessmgmt/api/v2/remote/app/command", payload)
        if res and res.status_code == 200:
            _LOGGER.info(f"VinFast: [Remote] Lệnh {command_type} thành công!")
            return True
        return False

    def _calculate_advanced_stats(self):
        try:
            model = self.vehicle_model_display.upper()
            target_spec = {"capacity": 0, "range": 0}
            for k, v in VEHICLE_SPECS.items():
                if k.replace(" ", "") in model.replace(" ", ""):
                    target_spec = v
                    break
                    
            cap = target_spec["capacity"]
            ran = target_spec["range"]
            if cap > 0:
                self._last_data["api_static_capacity"] = cap
                self._last_data["api_static_range"] = ran
                
                soh = safe_float(self._last_data.get("34220_00001_00001", 100))
                if 0 < soh <= 100:
                    self._last_data["api_battery_degradation"] = round(cap * (100 - soh) / 100, 2)
                    
                total_kwh = self._last_data.get("api_total_energy_charged", 0)
                odo = safe_float(self._last_data.get("34183_00001_00003", 0))
                if odo == 0: odo = safe_float(self._last_data.get("34199_00000_00000", 0))
                
                eff = 0
                if total_kwh > 0 and odo > 0:
                    eff = (total_kwh / odo) * 100
                    self._last_data["api_lifetime_efficiency"] = round(eff, 2)

                soc = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 0)))
                if eff > 0:
                    calc_max_range = cap / (eff / 100)
                    self._last_data["api_calc_max_range"] = round(calc_max_range, 1)
                    self._last_data["api_calc_range_per_percent"] = round(calc_max_range / 100, 2)
                    if soc > 0:
                        self._last_data["api_calc_remain_range"] = round(calc_max_range * (soc / 100), 1)
                    if ran > 0 and calc_max_range > 0:
                        deg_range = (1 - (calc_max_range / ran)) * 100
                        self._last_data["api_est_range_degradation"] = max(round(deg_range, 2), 0.0)
        except Exception: pass

    def _generate_x_hash(self, method, api_path, vin, timestamp_ms, secret_key="Vinfast@2025"):
        path_without_query = api_path.split("?")[0]
        normalized_path = path_without_query if path_without_query.startswith("/") else "/" + path_without_query
        parts = [method, normalized_path, vin, secret_key, str(timestamp_ms)] if vin else [method, normalized_path, secret_key, str(timestamp_ms)]
        return base64.b64encode(hmac.new(secret_key.encode('utf-8'), "_".join(parts).lower().encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

    def _generate_x_hash_2(self, platform, vin_code, identifier, path, method, timestamp_ms, hash2_key="ConnectedCar@6521"):
        normalized_path = path.split("?")[0]
        if normalized_path.startswith("/"): normalized_path = normalized_path[1:]
        normalized_path = normalized_path.replace("/", "_")
        parts = [platform, vin_code, identifier, normalized_path, method, str(timestamp_ms)] if vin_code else [platform, identifier, normalized_path, method, str(timestamp_ms)]
        return base64.b64encode(hmac.new(hash2_key.encode('utf-8'), "_".join(parts).lower().encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

    def _get_base_headers(self, vin_override=None):
        request_vin = vin_override or self.vin
        headers = {
            "Authorization": f"Bearer {self.access_token}", "x-service-name": "CAPP",
            "x-app-version": "2.17.5", "x-device-platform": "android", "x-device-identifier": DEVICE_ID,
            "Content-Type": "application/json"
        }
        if request_vin: headers["x-vin-code"] = request_vin
        if self.user_id: headers["x-player-identifier"] = self.user_id
        return headers

    def _post_api(self, path, payload, max_retries=1, vin_override=None):
        for _ in range(max_retries + 1):
            ts = int(time.time() * 1000)
            request_vin = vin_override or self.vin
            headers = self._get_base_headers(request_vin)
            headers.update({
                "X-HASH": self._generate_x_hash("POST", path, request_vin, ts),
                "X-HASH-2": self._generate_x_hash_2("android", request_vin, DEVICE_ID, path, "POST", ts),
                "X-TIMESTAMP": str(ts)
            })
            try:
                res = requests.post(f"{API_BASE}/{path}", headers=headers, json=payload, timeout=15)
                if res.status_code == 401:
                    self.login() 
                    continue
                return res
            except Exception:
                return None
        return None

    def _register_device_trust(self):
        try:
            method, api_path = "PUT", "ccarusermgnt/api/v1/device-trust/fcm-token"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), "X-TIMESTAMP": str(ts)})
            requests.put(f"{API_BASE}/{api_path}", headers=headers, json={"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"}, timeout=10)
        except Exception: pass

    def get_address_from_osm(self, lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            res = requests.get(url, headers={"User-Agent": "HA-VinFast/1.0"}, timeout=5)
            if res.status_code == 200: return res.json().get("display_name", f"{lat}, {lon}")
        except Exception: pass
        return f"{lat}, {lon}"

    def _update_location_async(self, lat, lon):
        try:
            addr = self.get_address_from_osm(lat, lon)
            if addr:
                self._last_data["api_current_address"] = addr
                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def register_resources(self):
        try:
            self._post_api("ccarusermgnt/api/v1/user-vehicle/set-primary-vehicle", {"vinCode": self.vin})
            self._post_api("ccaraccessmgmt/api/v1/remote/app/wakeup", {})

            active_dict = BASE_SENSORS.copy()
            model = self.vehicle_model_display.upper()
            if "VF 3" in model or "VF3" in model: active_dict.update(VF3_SENSORS)
            elif any(m in model for m in ["VF 5", "VF 6", "VF 7", "VF5", "VF6", "VF7"]): active_dict.update(VF3_SENSORS), active_dict.update(VF567_SENSORS)
            elif any(m in model for m in ["VF 8", "VF 9", "VF8", "VF9"]): active_dict.update(VF89_SENSORS)
            else: active_dict.update(VF3_SENSORS)

            request_objects = [
                {"objectId": str(int(k.split("_")[0])), "instanceId": str(int(k.split("_")[1])), "resourceId": str(int(k.split("_")[2]))} 
                for k in active_dict.keys() if "_" in k and not k.startswith("api_")
            ]
            
            self._post_api("ccaraccessmgmt/api/v1/telemetry/app/ping", request_objects)
            res = self._post_api(f"ccaraccessmgmt/api/v1/telemetry/{self.vin}/list_resource", request_objects)
            if res and res.status_code == 404:
                self._post_api("ccaraccessmgmt/api/v1/telemetry/list_resource", request_objects)
                
            _LOGGER.info(f"VinFast: [Giả lập App] Đã bắn API đánh thức T-Box thành công.")
        except Exception: pass

    def fetch_charging_history(self):
        try:
            method, api_path = "POST", "ccarcharging/api/v1/charging-sessions/search"
            all_sessions = []
            page, size = 0, 50 
            while self._running:
                ts = int(time.time() * 1000)
                headers = self._get_base_headers()
                headers.update({
                    "X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), 
                    "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), 
                    "X-TIMESTAMP": str(ts)
                })
                payload = {"orderStatus": [3, 5, 7], "startTime": 1609459200000, "endTime": int(time.time() * 1000)}
                res = requests.post(f"{API_BASE}/{api_path}?page={page}&size={size}", headers=headers, json=payload, timeout=15)
                if res.status_code == 401:
                    self.login() 
                    continue
                if res.status_code != 200: break
                data = res.json()
                sessions = []
                if isinstance(data.get("data"), list): sessions = data["data"]
                elif isinstance(data.get("data"), dict) and "content" in data["data"]: sessions = data["data"]["content"]
                elif "content" in data: sessions = data["content"]
                if not sessions: break
                all_sessions.extend(sessions)
                if len(sessions) < size: break
                page += 1
                time.sleep(0.5) 
                
            unique_sessions = {s.get("id") or f"noid_{s.get('pluggedTime')}": s for s in all_sessions}
            t_sessions = sum(1 for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0)
            t_kwh = sum(safe_float(s.get("totalKWCharged", 0)) for s in unique_sessions.values())
            self._last_data["api_total_charge_sessions"] = t_sessions
            self._last_data["api_total_energy_charged"] = round(t_kwh, 2)
            self._last_data["api_total_charge_cost_est"] = round(t_kwh * self.cost_per_kwh, 0)
            
            valid_sessions = [s for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0]
            if valid_sessions:
                sorted_sessions = sorted(valid_sessions, key=lambda x: safe_float(x.get("pluggedTime", 0)), reverse=True)
                last_session = sorted_sessions[0]
                start_soc = safe_float(last_session.get("startBatteryLevel", 0))
                end_soc = safe_float(last_session.get("endBatteryLevel", 0))
                energy_grid = safe_float(last_session.get("totalKWCharged", 0))
                
                self._last_data["api_last_charge_start_soc"] = start_soc
                self._last_data["api_last_charge_end_soc"] = end_soc
                self._last_data["api_last_charge_energy"] = round(energy_grid, 2)
                
                p_time = safe_float(last_session.get("pluggedTime", 0))
                u_time = safe_float(last_session.get("unpluggedTime", 0))
                duration_min = 0
                if u_time > p_time:
                    duration_min = (u_time - p_time) / 60000
                    self._last_data["api_last_charge_duration"] = round(duration_min, 0)
                if duration_min > 0:
                    self._last_data["api_last_charge_power"] = round((energy_grid / (duration_min / 60)), 1)
                
                cap = safe_float(self._last_data.get("api_static_capacity", 0))
                if cap > 0 and energy_grid > 0:
                    energy_added_to_battery = ((end_soc - start_soc) / 100.0) * cap
                    if energy_added_to_battery > 0:
                        charge_eff = (energy_added_to_battery / energy_grid) * 100
                        self._last_data["api_last_charge_efficiency"] = min(round(charge_eff, 1), 100.0)

            self._calculate_advanced_stats()
            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _delayed_fetch_charging_history(self):
        time.sleep(60)
        self.fetch_charging_history()

    def _send_heartbeat(self, state="1"):
        if not self.client or not self.client.is_connected() or not self.vin: return
        topic = f"/vehicles/{self.vin}/push/connected/heartbeat"
        payload = {
            "version": "1.2", 
            "timestamp": int(time.time() * 1000), 
            "trans_id": str(uuid.uuid4()), 
            "content": {"34183": { "1": { "54": str(state) } }}
        }
        try: 
            self.client.publish(topic, json.dumps(payload), qos=1)
        except Exception: pass

    def _get_aws_mqtt_url(self):
        res_id = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15)
        identity_id = res_id.json()["IdentityId"]
        creds_res = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": identity_id, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15)
        creds = creds_res.json()["Credentials"]
        try:
            requests.post(f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": identity_id}, timeout=15)
        except Exception: pass

        def sign(k, m): return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()
        amz_date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
        cred_scope = f"{date_stamp}/{AWS_REGION}/iotdevicegateway/aws4_request"
        qs = f"X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={urllib.parse.quote(creds['AccessKeyId'] + '/' + cred_scope, safe='')}&X-Amz-Date={amz_date}&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
        req = f"GET\n/mqtt\n{qs}\nhost:{IOT_ENDPOINT}\n\nhost\n" + hashlib.sha256("".encode('utf-8')).hexdigest()
        sts = f"AWS4-HMAC-SHA256\n{amz_date}\n{cred_scope}\n" + hashlib.sha256(req.encode('utf-8')).hexdigest()
        sig = hmac.new(sign(sign(sign(sign(('AWS4' + creds['SecretKey']).encode('utf-8'), date_stamp), AWS_REGION), 'iotdevicegateway'), 'aws4_request'), sts.encode('utf-8'), hashlib.sha256).hexdigest()
        return f"wss://{IOT_ENDPOINT}/mqtt?{qs}&X-Amz-Signature={sig}&X-Amz-Security-Token={urllib.parse.quote(creds['SessionToken'], safe='')}"

    def _renew_aws_connection(self):
        try:
            self.login()
            self._register_device_trust()
            new_url = self._get_aws_mqtt_url()
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.client.ws_set_options(path=new_url.split(IOT_ENDPOINT)[1])
                self.client.connect(IOT_ENDPOINT, 443, 60)
                self.client.loop_start()
                self.register_resources()
        except Exception: pass

    def _api_polling_loop(self):
        start_time = time.time()
        last_heartbeat = start_time
        last_charge_fetch = start_time
        last_token_renew = start_time
        last_app_sim = start_time
        
        time.sleep(3) 
        if self.client:
            _LOGGER.info("VinFast: [Khởi động] Đang thực hiện giả lập mở App lần đầu...")
            self.register_resources()
            self.fetch_charging_history()

        while self._running:
            try:
                time.sleep(1)
                now = time.time()
                
                if now - last_heartbeat >= 120:
                    last_heartbeat = now
                    self._send_heartbeat("1")
                
                if now - last_charge_fetch >= 3600:
                    last_charge_fetch = now
                    self.fetch_charging_history()

                if now - last_token_renew >= 3000:
                    last_token_renew = now
                    self._renew_aws_connection()

                if now - last_app_sim >= 900:
                    last_app_sim = now
                    if not self._is_moving and not self._is_charging:
                        self.register_resources()

                if getattr(self, '_force_full_scan', False):
                    self._force_full_scan = False
                    last_app_sim = now
                    self.register_resources()
                        
            except Exception: pass

    def start_mqtt(self):
        if self._running: return
        self._running = True
        if not self.user_id: self.get_vehicles()
        self._register_device_trust()
        
        client_id = f"Android_{self.vin}_{self._mqtt_client_id_rand}"
        wss_url = self._get_aws_mqtt_url()
        self.client = mqtt.Client(client_id=client_id, transport="websockets", protocol=mqtt.MQTTv311)
        self.client.username_pw_set("?SDK=Android&Version=2.81.0")
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.ws_set_options(path=wss_url.split(IOT_ENDPOINT)[1])
        self.client.tls_set()
        
        self.client.connect(IOT_ENDPOINT, 443, 60)
        self.client.loop_start()

        self._polling_thread = threading.Thread(target=self._api_polling_loop, daemon=True)
        self._polling_thread.start()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0: 
            _LOGGER.info("VinFast: [MQTT] Đã kết nối AWS IoT.")
            client.subscribe(f"/mobile/{self.vin}/push", qos=1)
            client.subscribe(f"monitoring/server/{self.vin}/push", qos=1)
            client.subscribe(f"/server/{self.vin}/remctrl", qos=1)
            self._send_heartbeat("2")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0 and self._running: pass

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            data_dict = {}
            for item in payload:
                obj, inst, res = str(item.get("objectId", "0")).zfill(5), str(item.get("instanceId", "0")).zfill(5), str(item.get("resourceId", "0")).zfill(5)
                key = item.get("deviceKey") if "deviceKey" in item else f"{obj}_{inst}_{res}"
                val = item.get("value")
                if key and val is not None: data_dict[key] = val
            
            if data_dict:
                current_time = time.time()
                if str(data_dict.get("34183_00001_00055", "0")) == "1":
                    self._send_heartbeat("1")

                time_since_last = current_time - getattr(self, '_last_activity_time', current_time)
                self._last_activity_time = current_time
                
                if not self._is_moving and not self._is_charging and time_since_last > 180:
                    self._force_full_scan = True
                
                self._last_data.update(data_dict)
                current_soc = safe_float(data_dict.get("34183_00001_00009", data_dict.get("34180_00001_00011", self._last_data.get("34183_00001_00009", 0))))
                
                # --- PHÂN TÍCH SẠC PIN ---
                c_status_1 = str(data_dict.get("34193_00001_00005", self._last_data.get("34193_00001_00005", "0")))
                c_status_2 = str(data_dict.get("34183_00000_00001", self._last_data.get("34183_00000_00001", "0")))
                self._is_charging = (c_status_1 == "1") or (c_status_2 == "1")

                if self._is_charging and not self._last_is_charging:
                    self._last_is_charging = True
                elif not self._is_charging and self._last_is_charging:
                    self._last_is_charging = False
                    threading.Thread(target=self._delayed_fetch_charging_history, daemon=True).start()

                self._calculate_advanced_stats()
                
                speed = safe_float(data_dict.get("34183_00001_00002", self._last_data.get("34183_00001_00002", 0)))
                gear = str(data_dict.get("34183_00001_00001", self._last_data.get("34183_00001_00001", "1"))) 
                odo = safe_float(data_dict.get("34183_00001_00003", self._last_data.get("34183_00001_00003", 0))) 
                if odo == 0: odo = safe_float(data_dict.get("34199_00000_00000", self._last_data.get("34199_00000_00000", 0)))
                
                # --- PHÂN TÍCH DẢI TỐC ĐỘ TỐI ƯU KHI ĐANG CHẠY (SMART PROFILING) ---
                if odo > 0 and current_soc > 0:
                    if getattr(self, '_eff_soc', None) is None or current_soc > self._eff_soc:
                        self._eff_soc = current_soc
                        self._eff_odo = odo
                        self._eff_speeds = []
                        
                    if speed > 0:
                        self._eff_speeds.append(speed)
                        
                    if current_soc < self._eff_soc:
                        drop_amount = self._eff_soc - current_soc
                        if getattr(self, '_eff_odo', None) is not None and len(self._eff_speeds) > 0:
                            dist = odo - self._eff_odo
                            if dist > 0:
                                sorted_speeds = sorted(self._eff_speeds)
                                median_speed = sorted_speeds[len(sorted_speeds) // 2]
                                band_lower = int(median_speed / 10) * 10
                                band_key = f"{band_lower}-{band_lower+10}"
                                
                                if not hasattr(self, '_eff_stats'):
                                    self._eff_stats = {}
                                if band_key not in self._eff_stats:
                                    self._eff_stats[band_key] = {"dist": 0.0, "drops": 0.0}
                                    
                                self._eff_stats[band_key]["dist"] += dist
                                self._eff_stats[band_key]["drops"] += drop_amount
                                
                                best_band = "Đang thu thập..."
                                best_eff = 0
                                for k, v in self._eff_stats.items():
                                    if v["drops"] > 0:
                                        eff = v["dist"] / v["drops"]
                                        if eff > best_eff:
                                            best_eff = eff
                                            best_band = k
                                if best_eff > 0:
                                    self._last_data["api_best_efficiency_band"] = f"{best_band} km/h ({round(best_eff, 2)} km/1%)"
                                    
                        # Reset vòng mới
                        self._eff_soc = current_soc
                        self._eff_odo = odo
                        self._eff_speeds = []
                # -----------------------------------------------------------------

                if odo > 0 and self.gas_km_per_liter > 0:
                    self._last_data["api_total_gas_cost"] = round((odo / self.gas_km_per_liter) * self.gas_price, 0)

                self._is_moving = (speed > 0) or (gear not in ["1", 1]) 
                if self._is_moving: self._last_data["api_vehicle_status"] = "Đang di chuyển"
                elif self._is_charging: self._last_data["api_vehicle_status"] = "Đang sạc"
                else: self._last_data["api_vehicle_status"] = "Đang đỗ"

                # --- CHUYẾN ĐI (TRIP 30 PHÚT) ---
                if self._is_moving:
                    self._last_move_time = current_time

                if not self._is_moving and (current_time - getattr(self, '_last_move_time', current_time) > 1800):
                    if getattr(self, '_is_trip_active', False):
                        self._is_trip_active = False

                if self._is_moving and not getattr(self, '_is_trip_active', False) and odo > 0:
                    self._trip_start_odo = odo
                    self._trip_start_time = current_time
                    self._trip_start_soc = current_soc
                    self._is_trip_active = True
                    
                    self._last_data["api_trip_distance"] = 0.0
                    self._last_data["api_trip_gas_cost"] = 0
                    self._last_data["api_trip_charge_cost"] = 0
                    self._last_data["api_trip_avg_speed"] = 0.0
                    self._last_data["api_trip_energy_used"] = 0.0
                    self._last_data["api_trip_efficiency"] = 0.0

                if getattr(self, '_is_trip_active', False) and self._trip_start_odo is not None and odo >= self._trip_start_odo:
                    trip_dist = odo - self._trip_start_odo
                    self._last_data["api_trip_distance"] = round(trip_dist, 1)
                    if self.gas_km_per_liter > 0:
                        self._last_data["api_trip_gas_cost"] = round((trip_dist / self.gas_km_per_liter) * self.gas_price, 0)
                    self._last_data["api_trip_charge_cost"] = round(trip_dist * self.ev_kwh_per_km * self.cost_per_kwh, 0)
                    
                    if self._trip_start_time and self._trip_start_time > 0:
                        trip_hrs = (current_time - self._trip_start_time) / 3600.0
                        if trip_hrs > 0 and trip_dist > 0:
                            self._last_data["api_trip_avg_speed"] = round(trip_dist / trip_hrs, 1)

                    if self._trip_start_soc is not None and self._trip_start_soc >= current_soc and trip_dist > 0:
                        cap = safe_float(self._last_data.get("api_static_capacity", 0))
                        if cap > 0:
                            energy_used = ((self._trip_start_soc - current_soc) / 100.0) * cap
                            self._last_data["api_trip_energy_used"] = round(energy_used, 2)
                            self._last_data["api_trip_efficiency"] = round((energy_used / trip_dist) * 100, 2)

                lat = data_dict.get("00006_00001_00000", self._last_data.get("00006_00001_00000"))
                lon = data_dict.get("00006_00001_00001", self._last_data.get("00006_00001_00001"))
                if lat and lon:
                    curr_coord = f"{lat},{lon}"
                    if curr_coord != self._last_lat_lon: 
                        self._last_lat_lon = curr_coord
                        self._last_data["api_current_address"] = f"Đang định vị GPS ({curr_coord})..."
                        threading.Thread(target=self._update_location_async, args=(lat, lon), daemon=True).start()

                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
        except Exception: pass
