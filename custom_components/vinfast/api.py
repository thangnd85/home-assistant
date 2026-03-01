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
import math
import paho.mqtt.client as mqtt

from .const import (
    AUTH0_DOMAIN, AUTH0_CLIENT_ID, API_BASE, 
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID, 
    BASE_SENSORS, VF3_SENSORS, VF567_SENSORS, VF89_SENSORS,
    DEFAULT_COST_PER_KWH, DEFAULT_EV_KWH_PER_KM, 
    DEFAULT_GAS_PRICE, DEFAULT_GAS_KM_PER_LITER
)

_LOGGER = logging.getLogger(__name__)

def safe_float(val, default=0.0):
    """Hàm bảo vệ vòng lặp không bị sập khi dữ liệu MQTT trả về None hoặc String lỗi"""
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError):
        return default

class VinFastAPI:
    def __init__(self, email, password, vin=None, vehicle_name="Xe VinFast", options=None):
        self.email = email
        self.password = password
        self.access_token = None
        self.vin = vin
        self.user_id = None
        self.vehicle_name = vehicle_name
        self.vehicle_model = "Unknown" # Sẽ dùng cái này để nhận diện xe chính xác 100%
        self.options = options or {}
        self.client = None
        self.callbacks = []
        self._running = False
        self._polling_thread = None
        
        # Khởi tạo mặc định để các cảm biến không bị "Chưa xác định" khi vừa bật HA
        self._last_data = {
            "api_trip_distance": 0,
            "api_trip_charge_cost": 0,
            "api_trip_gas_cost": 0,
            "api_total_gas_cost": 0,
            "api_total_charge_cost_est": 0
        }  
        
        self.cost_per_kwh = safe_float(self.options.get("cost_per_kwh", DEFAULT_COST_PER_KWH), 4000)
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", DEFAULT_EV_KWH_PER_KM), 0.12)
        self.gas_price = safe_float(self.options.get("gas_price", DEFAULT_GAS_PRICE), 20000)
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", DEFAULT_GAS_KM_PER_LITER), 25)

        self._last_moved_time = time.time()
        self._is_moving = False
        self._trip_start_odo = None
        self._last_gear = "1" # Gear 1 = Park
        self._last_lat_lon = None
        self._last_address = "Đang tải vị trí..."

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            if self._last_data:
                cb(self._last_data)

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
        })
        res.raise_for_status()
        self.access_token = res.json()["access_token"]
        return self.access_token

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        headers = {"Authorization": f"Bearer {self.access_token}", "x-service-name": "CAPP", "x-app-version": "2.17.5", "x-device-platform": "android"}
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        vehicles = res.json().get("data", [])
        if vehicles:
            v = vehicles[0]
            self.user_id = str(v.get("userId", ""))
            if not self.vin: self.vin = v.get("vinCode")
            # FIX LỖI 1: Bắt chuẩn Model xe để tránh trùng lặp cảm biến
            self.vehicle_model = str(v.get("vehicleModel") or v.get("dmsVehicleModel") or "Unknown").upper()
        return vehicles

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

    def _get_base_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}", "x-vin-code": self.vin, "x-service-name": "CAPP",
            "x-app-version": "2.17.5", "x-device-platform": "android", "x-device-identifier": DEVICE_ID,
            "x-player-identifier": self.user_id, "Content-Type": "application/json"
        }

    def _register_device_trust(self):
        try:
            method, api_path = "PUT", "ccarusermgnt/api/v1/device-trust/fcm-token"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), "X-TIMESTAMP": str(ts)})
            requests.put(f"{API_BASE}/{api_path}", headers=headers, json={"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"})
        except Exception: pass

    def get_address_from_osm(self, lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            res = requests.get(url, headers={"User-Agent": "HomeAssistant-VinFast-Integration/1.0"}, timeout=5)
            if res.status_code == 200:
                return res.json().get("display_name", f"{lat}, {lon}")
        except Exception: pass
        return f"{lat}, {lon}"

    def wake_up_vehicle(self):
        try:
            ping_path = "ccaraccessmgmt/api/v1/telemetry/app/ping"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash("POST", ping_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, ping_path, "POST", ts), "X-TIMESTAMP": str(ts)})
            requests.post(f"{API_BASE}/{ping_path}", headers=headers, json=[])
            
            master_dict = {**BASE_SENSORS, **VF3_SENSORS, **VF567_SENSORS, **VF89_SENSORS}
            payload = []
            for key in master_dict.keys():
                if "_" in key and not key.startswith("api_"):
                    parts = key.split("_")
                    if len(parts) == 3: payload.append({"objectId": str(int(parts[0])), "instanceId": str(int(parts[1])), "resourceId": str(int(parts[2]))})

            lr_path = f"ccaraccessmgmt/api/v1/telemetry/{self.vin}/list_resource"
            ts2 = int(time.time() * 1000)
            headers2 = self._get_base_headers()
            headers2.update({"X-HASH": self._generate_x_hash("POST", lr_path, self.vin, ts2), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, lr_path, "POST", ts2), "X-TIMESTAMP": str(ts2)})
            res = requests.post(f"{API_BASE}/{lr_path}", headers=headers2, json=payload)

            if res.status_code == 404:
                lr_path_2 = "ccaraccessmgmt/api/v1/telemetry/list_resource"
                ts3 = int(time.time() * 1000)
                headers3 = self._get_base_headers()
                headers3.update({"X-HASH": self._generate_x_hash("POST", lr_path_2, self.vin, ts3), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, lr_path_2, "POST", ts3), "X-TIMESTAMP": str(ts3)})
                requests.post(f"{API_BASE}/{lr_path_2}", headers=headers3, json=payload)

        except Exception as e: _LOGGER.error(f"VinFast Wakeup Error: {e}")

    def fetch_charging_history(self):
        try:
            method, api_path = "POST", "ccarcharging/api/v1/charging-sessions/search"
            all_sessions = []
            page, size, total_pages = 0, 100, 1
            while page < total_pages and self._running:
                ts = int(time.time() * 1000)
                headers = self._get_base_headers()
                headers.update({"X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), "X-TIMESTAMP": str(ts)})
                res = requests.post(f"{API_BASE}/{api_path}?page={page}&size={size}", headers=headers, json={"orderStatus": [3, 5, 7]})
                if res.status_code == 401:
                    self.login()
                    continue
                if res.status_code != 200: break
                data = res.json()
                sessions = data.get("data", []) if isinstance(data.get("data"), list) else (data.get("data", {}).get("content", []) if isinstance(data.get("data"), dict) else data.get("content", []))
                all_sessions.extend(sessions)
                if page == 0:
                    meta = data.get("metadata", {})
                    if not meta and isinstance(data.get("data"), dict): meta = data.get("data", {}).get("metadata", {})
                    total_records = meta.get("totalRecords") or len(sessions)
                    if total_records > 0: total_pages = math.ceil(total_records / size)
                page += 1
                
            unique_sessions = {s.get("id") or f"noid_{s.get('pluggedTime')}": s for s in all_sessions}
            t_sessions = sum(1 for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0)
            t_kwh = sum(safe_float(s.get("totalKWCharged", 0)) for s in unique_sessions.values())
            t_cost = sum(safe_float(s.get("finalAmount", 0)) for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0)

            self._last_data.update({
                "api_total_charge_sessions": t_sessions,
                "api_total_energy_charged": round(t_kwh, 2),
                "api_total_charge_cost": round(t_cost, 0),
                "api_total_charge_cost_est": round(t_kwh * self.cost_per_kwh, 0)
            })
            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)
        except Exception as e: _LOGGER.error(f"VinFast Charging Fetch Error: {e}")

    def _get_aws_mqtt_url(self):
        res_id = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}})
        identity_id = res_id.json()["IdentityId"]
        creds_res = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": identity_id, "Logins": {AUTH0_DOMAIN: self.access_token}})
        creds = creds_res.json()["Credentials"]
        requests.post(f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": identity_id})

        def sign(k, m): return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()
        amz_date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
        cred_scope = f"{date_stamp}/{AWS_REGION}/iotdevicegateway/aws4_request"
        qs = f"X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={urllib.parse.quote(creds['AccessKeyId'] + '/' + cred_scope, safe='')}&X-Amz-Date={amz_date}&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
        req = f"GET\n/mqtt\n{qs}\nhost:{IOT_ENDPOINT}\n\nhost\n" + hashlib.sha256("".encode('utf-8')).hexdigest()
        sts = f"AWS4-HMAC-SHA256\n{amz_date}\n{cred_scope}\n" + hashlib.sha256(req.encode('utf-8')).hexdigest()
        sig = hmac.new(sign(sign(sign(sign(('AWS4' + creds['SecretKey']).encode('utf-8'), date_stamp), AWS_REGION), 'iotdevicegateway'), 'aws4_request'), sts.encode('utf-8'), hashlib.sha256).hexdigest()
        return f"wss://{IOT_ENDPOINT}/mqtt?{qs}&X-Amz-Signature={sig}&X-Amz-Security-Token={urllib.parse.quote(creds['SessionToken'], safe='')}"

    def _api_polling_loop(self):
        counter = 0
        last_ping_time = time.time() - 300 
        
        while self._running:
            try:
                current_time = time.time()
                
                if self._is_moving: poll_interval = 60 
                else:
                    if (current_time - self._last_moved_time) > 1800: poll_interval = 900 
                    else: poll_interval = 300 
                
                if current_time - last_ping_time >= poll_interval:
                    if self.client and self.client.is_connected():
                        self.wake_up_vehicle()
                        last_ping_time = current_time

                if counter == 0 or (counter > 0 and counter % 3600 == 0):
                    self.fetch_charging_history()

                if counter > 0 and counter % 43200 == 0:
                    self.login()
                    self._register_device_trust()
                    new_url = self._get_aws_mqtt_url()
                    self.client.ws_set_options(path=new_url.split(IOT_ENDPOINT)[1])
                    self.client.reconnect()
                    counter = 0

            except Exception as e: _LOGGER.error(f"VinFast Polling Loop Error: {e}")
            time.sleep(1)
            counter += 1

    def start_mqtt(self):
        if self._running: return
        self._running = True
        
        if not self.user_id: self.get_vehicles()
        self._register_device_trust()
        
        wss_url = self._get_aws_mqtt_url()
        self.client = mqtt.Client(client_id=f"HA-VFDash-{int(time.time())}", transport="websockets", protocol=mqtt.MQTTv311)
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
        if rc == 0: client.subscribe(f"/mobile/{self.vin}/push", qos=1)

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
                self._last_data.update(data_dict)
                
                # --- FIX LỖI 2: TOÁN HỌC AN TOÀN (SAFE FLOAT) ---
                speed = safe_float(data_dict.get("34183_00001_00002", self._last_data.get("34183_00001_00002", 0)))
                if speed == 0: speed = safe_float(data_dict.get("34188_00000_00000", self._last_data.get("34188_00000_00000", 0)))
                
                gear = str(data_dict.get("34183_00001_00001", self._last_data.get("34183_00001_00001", "1"))) 
                if gear == "1": gear = str(data_dict.get("34187_00000_00000", self._last_data.get("34187_00000_00000", "1")))
                
                odo = safe_float(data_dict.get("34183_00001_00003", self._last_data.get("34183_00001_00003", 0))) 
                if odo == 0: odo = safe_float(data_dict.get("34199_00000_00000", self._last_data.get("34199_00000_00000", 0)))
                
                if odo > 0 and self.gas_km_per_liter > 0:
                    self._last_data["api_total_gas_cost"] = round(odo * (self.gas_price / self.gas_km_per_liter), 0)

                self._is_moving = (speed > 0) or (gear not in ["1", 1]) 
                if self._is_moving:
                    self._last_moved_time = time.time()
                    self._last_data["api_vehicle_status"] = "Đang di chuyển"
                else:
                    self._last_data["api_vehicle_status"] = "Đang đỗ"

                # --- FIX LOGIC TRIP: RESET KHI CHUYỂN TỪ P (1) SANG D (4) ---
                if gear != "1" and self._last_gear == "1" and odo > 0:
                    self._trip_start_odo = odo # Bắt đầu chuyến đi mới
                
                self._last_gear = gear

                if self._trip_start_odo is not None and odo >= self._trip_start_odo:
                    trip_dist = odo - self._trip_start_odo
                    self._last_data["api_trip_distance"] = round(trip_dist, 1)
                    
                    if self.gas_km_per_liter > 0:
                        self._last_data["api_trip_gas_cost"] = round(trip_dist * (self.gas_price / self.gas_km_per_liter), 0)
                    self._last_data["api_trip_charge_cost"] = round(trip_dist * self.ev_kwh_per_km * self.cost_per_kwh, 0)

                lat = data_dict.get("00006_00001_00000")
                lon = data_dict.get("00006_00001_00001")
                if lat and lon:
                    curr_coord = f"{lat},{lon}"
                    if curr_coord != self._last_lat_lon: 
                        self._last_lat_lon = curr_coord
                        self._last_address = self.get_address_from_osm(lat, lon)
                        self._last_data["api_current_address"] = self._last_address

                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
        except Exception as e: _LOGGER.error(f"VinFast MQTT Logic Error: {e}")
