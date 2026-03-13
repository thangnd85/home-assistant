import requests
from requests.exceptions import RequestException
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
import os
import math

from .const import (
    AUTH0_DOMAIN, AUTH0_CLIENT_ID, API_BASE, 
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID, 
    VIRTUAL_SENSORS, VF3_SENSORS, VF5_SENSORS, VFE34_SENSORS, VF67_SENSORS, VF89_SENSORS, VEHICLE_SPECS
)
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HA_CONFIG_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
WWW_DIR = os.path.join(HA_CONFIG_DIR, "www")
MOCK_FILE = os.path.join(WWW_DIR, "mock_console_cmd.txt")

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except Exception: return default

class VinFastAPI:
    def __init__(self, email, password, vin=None, vehicle_name="Xe VinFast", options=None, gemini_api_key=""):
        self.email = email
        self.password = password
        self.gemini_api_key = gemini_api_key
        self.access_token = None
        self.vin = vin
        self.user_id = None
        self.vehicle_name = vehicle_name
        self.vehicle_model_display = "Unknown" 
        self._model_group = "UNKNOWN"
        self.options = options or {}
        
        self.client = None
        self.callbacks = []
        self._running = False
        self._needs_mqtt_renew = False 
        self._mqtt_client_id_rand = "".join(random.choice("0123456789qwertyuiop") for _ in range(15))
        
        self._last_data = {
            "api_vehicle_status": "Đang kết nối...",
            "api_current_address": "Đang tải...",
            "api_trip_route": "[]",
            "api_nearby_stations": "[]",
            "api_trip_distance": 0.0,
            "api_trip_avg_speed": 0.0,
            "api_trip_energy_used": 0.0,
            "api_trip_efficiency": 0.0,
            "api_live_charge_power": 0.0,
            "api_last_lat": None, 
            "api_last_lon": None,
            "api_total_charge_sessions": 0,
            "api_total_energy_charged": 0.0,
            "api_vehicle_name": self.vehicle_name,
            "api_charge_history_list": "[]", 
            "api_ai_advisor": "Hệ thống AI đang chờ phân tích...",
            "api_best_efficiency_band": "Chưa đủ dữ liệu"
        }  
        
        self.cost_per_kwh = safe_float(self.options.get("cost_per_kwh", 4000), 4000)
        self.gas_price = safe_float(self.options.get("gas_price", 20000), 20000)
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", 0.15), 0.15)
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", 15.0), 15.0)

        self._is_moving = False
        self._is_charging = False
        self._last_is_charging = False 
        self._last_actual_move_time = time.time()
        self._last_lat_lon = ""
        
        self._vehicle_offline = False
        self._last_auto_wakeup_time = 0
        
        self._is_trip_active = False
        self._trip_start_odo = 0.0
        self._trip_start_time = time.time()
        self._trip_start_soc = 100.0
        self._trip_start_address = "Không xác định"
        self._route_coords = []
        self._last_gps_time = time.time()
        self._trip_accumulated_distance_m = 0.0
        
        self._eff_soc = None
        self._eff_gps_dist = 0.0 
        self._eff_time = None
        self._eff_speeds = []
        self._eff_stats = {}
        
        # Biến đếm thời gian chống Spam AI
        self._last_ai_anomaly_time = 0
        self._last_ai_weather_time = 0
        
        self._charge_start_time = time.time()
        self._charge_start_soc = 0.0
        self._charge_calc_soc = 0.0
        self._charge_calc_time = time.time()
        self._current_charge_max_power = 0.0 

        self._last_geocoded_grid = None
        self._last_weather_fetch_time = 0 
        self._last_mqtt_msg_time = time.time() 
        self._geocode_lock = threading.Lock()

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            if self._last_data: cb(self._last_data)

    def stop(self):
        self._running = False
        if self.client:
            self.client.loop_stop()
            try: self.client.disconnect()
            except: pass

    def _update_vehicle_name(self, candidate_name):
        if not candidate_name: return
        candidate = str(candidate_name).strip()
        if len(candidate) < 2 or candidate.isnumeric() or candidate in ["0", "1"]: return
        if candidate.lower() in ["none", "null", "unknown", "xevinfast"] or "profile_email" in candidate.lower(): return
        if candidate.upper().replace(" ", "") in ["VF3", "VF5", "VF6", "VF7", "VF8", "VF9", "VFE34"]: return 
        self._last_data["api_vehicle_name"] = candidate

    def inject_mock_data(self, payload_list):
        class MockMsg:
            def __init__(self, data): self.payload = json.dumps(data).encode('utf-8')
        self._on_message(None, None, MockMsg(payload_list))

    def _process_console_command(self, cmd):
        parts = cmd.lower().split()
        if not parts: return
        action = parts[0]
        
        if action == "cs": self.inject_mock_data([{"deviceKey": "34193_00001_00005", "value": "1"}, {"deviceKey": "34183_00000_00001", "value": "1"}])
        elif action == "rs": self.inject_mock_data([{"deviceKey": "34193_00001_00005", "value": "2"}, {"deviceKey": "34183_00000_00001", "value": "2"}])
        elif action == "p": self.inject_mock_data([{"deviceKey": "34183_00001_00001", "value": "1"}, {"deviceKey": "34187_00000_00000", "value": "1"}, {"deviceKey": "34183_00001_00002", "value": "0"}, {"deviceKey": "34188_00000_00000", "value": "0"}])
        elif action == "d": self.inject_mock_data([{"deviceKey": "34183_00001_00001", "value": "4"}, {"deviceKey": "34187_00000_00000", "value": "4"}])
        elif action == "v":
            speed = 40
            if len(parts) > 1:
                try: speed = int(parts[1])
                except: pass
            current_lat = safe_float(self._last_data.get("00006_00001_00000", 11.555))
            current_lon = safe_float(self._last_data.get("00006_00001_00001", 106.172))
            if speed > 0:
                self.inject_mock_data([
                    {"deviceKey": "34183_00001_00002", "value": str(speed)}, {"deviceKey": "34188_00000_00000", "value": str(speed)},
                    {"deviceKey": "00006_00001_00000", "value": str(current_lat + 0.001)}, {"deviceKey": "00006_00001_00001", "value": str(current_lon + 0.001)}
                ])
            else:
                self.inject_mock_data([{"deviceKey": "34183_00001_00002", "value": "0"}, {"deviceKey": "34188_00000_00000", "value": "0"}])
        elif action == "soc":
            if len(parts) > 1:
                soc_val = parts[1]
                self.inject_mock_data([{"deviceKey": "34183_00001_00009", "value": soc_val}, {"deviceKey": "34180_00001_00011", "value": soc_val}])
        elif action == "ai":
            trip_data = {"dist": 15.5, "drop": 6.0}
            threading.Thread(target=self._run_ai_advisor_async, args=("trip", trip_data), daemon=True).start()

    def _get_base_headers(self, vin_override=None):
        request_vin = vin_override or self.vin
        headers = {
            "Authorization": f"Bearer {self.access_token}", 
            "x-service-name": "CAPP",
            "x-app-version": "2.17.5", 
            "x-device-platform": "android", 
            "x-device-identifier": DEVICE_ID,
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-G998B Build/TP1A.220624.014)",
            "Content-Type": "application/json"
        }
        if request_vin and request_vin != "none": headers["x-vin-code"] = request_vin
        if self.user_id: headers["x-player-identifier"] = self.user_id
        return headers

    def _safe_request(self, method, url, max_retries=3, delay=5, **kwargs):
        for attempt in range(max_retries):
            try:
                if method.upper() == "POST": return requests.post(url, **kwargs)
                elif method.upper() == "PUT": return requests.put(url, **kwargs)
                else: return requests.get(url, **kwargs)
            except Exception as e:
                _LOGGER.debug(f"HTTP Request Error: {e}")
                if attempt < max_retries - 1: time.sleep(delay)
        return None

    def login(self):
        url = f"https://{AUTH0_DOMAIN}/oauth/token"
        res = self._safe_request("POST", url, json={
            "client_id": AUTH0_CLIENT_ID, "grant_type": "password",
            "username": self.email, "password": self.password,
            "scope": "openid profile email offline_access", "audience": API_BASE
        }, timeout=15) 
        if res and res.status_code == 200:
            self.access_token = res.json()["access_token"]
            return self.access_token
        return None

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        res = self._safe_request("GET", url, headers=self._get_base_headers(vin_override="none"), timeout=15)
        if res and res.status_code == 200:
            vehicles = res.json().get("data", [])
            if vehicles:
                v = vehicles[0]
                self.user_id = str(v.get("userId", ""))
                if not self.vin: self.vin = v.get("vinCode", "")
                self._load_state()

                self.vehicle_model_display = v.get("marketingName") or v.get("dmsVehicleModel") or "VF"
                self._last_data["api_vehicle_model"] = self.vehicle_model_display
                
                custom_name = v.get("customizedVehicleName")
                if custom_name and len(custom_name) > 1:
                    self.vehicle_name = custom_name
                    self._last_data["api_vehicle_name"] = custom_name
                
                model_str = self.vehicle_model_display.upper()
                if "VF 3" in model_str or "VF3" in model_str: self._model_group = "VF3"
                elif "VF 5" in model_str or "VF5" in model_str: self._model_group = "VF5"
                elif any(m in model_str for m in ["VFE34", "VF E34", "VFE 34"]): self._model_group = "VFE34"
                elif any(m in model_str for m in ["VF 6", "VF 7", "VF6", "VF7"]): self._model_group = "VF67"
                elif any(m in model_str for m in ["VF 8", "VF 9", "VF8", "VF9"]): self._model_group = "VF89"
                else: self._model_group = "UNKNOWN"
                
                self._update_dynamic_costs()
                self._calculate_advanced_stats()
                lat_start = self._last_data.get("api_last_lat")
                lon_start = self._last_data.get("api_last_lon")
                if lat_start and lon_start:
                    threading.Thread(target=self._update_location_async, args=(lat_start, lon_start), daemon=True).start()
            return vehicles
        return []

    def _update_dynamic_costs(self):
        model = self.vehicle_model_display.upper()
        target_spec = {"ev_kwh_per_km": 0.15, "gas_km_per_liter": 15.0} 
        for k, v in VEHICLE_SPECS.items():
            if k.replace(" ", "") in model.replace(" ", ""):
                target_spec = v
                break
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", target_spec.get("ev_kwh_per_km", 0.15)))
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", target_spec.get("gas_km_per_liter", 15.0)))

    def _calculate_advanced_stats(self):
        try:
            model = self.vehicle_model_display.upper()
            target_spec = {"capacity": 0, "range": 0}
            for k, v in VEHICLE_SPECS.items():
                if k.replace(" ", "") in model.replace(" ", ""):
                    target_spec = v
                    break
            cap, ran = target_spec["capacity"], target_spec["range"]
            soc = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 0)))
            cur_ran = safe_float(self._last_data.get("34183_00001_00011", self._last_data.get("34180_00001_00007", 0)))
            
            if cap > 0:
                self._last_data["api_static_capacity"] = cap
                self._last_data["api_static_range"] = ran
                if ran > 0 and soc > 0 and cur_ran > 0:
                    theoretical_range_at_current_soc = (ran / 100.0) * soc
                    soh_calc = (current_range / theoretical_range_at_current_soc) * 100.0
                    soh_calc = min(soh_calc, 100.0) 
                    self._last_data["api_soh_calculated"] = round(soh_calc, 1)
                else:
                    self._last_data["api_soh_calculated"] = safe_float(self._last_data.get("34220_00001_00001", 100))
                
                total_kwh = safe_float(self._last_data.get("api_total_energy_charged", 0))
                odo = safe_float(self._last_data.get("34183_00001_00003", self._last_data.get("34199_00000_00000", 0)))
                if total_kwh > 0 and odo > 0:
                    self._last_data["api_lifetime_efficiency"] = round((total_kwh / odo) * 100, 2)
        except Exception: pass

    def _generate_x_hash(self, method, api_path, vin, timestamp_ms, secret_key="Vinfast@2025"):
        path = api_path.split("?")[0]
        if not path.startswith("/"): path = "/" + path
        parts = [method, path, vin, secret_key, str(timestamp_ms)] if vin else [method, path, secret_key, str(timestamp_ms)]
        return base64.b64encode(hmac.new(secret_key.encode('utf-8'), "_".join(parts).lower().encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

    def _generate_x_hash_2(self, platform, vin_code, identifier, path, method, timestamp_ms, hash2_key="ConnectedCar@6521"):
        norm_path = path.split("?")[0].strip("/").replace("/", "_")
        parts = [platform, vin_code, identifier, norm_path, method, str(timestamp_ms)] if vin_code else [platform, identifier, norm_path, method, str(timestamp_ms)]
        return base64.b64encode(hmac.new(hash2_key.encode('utf-8'), "_".join(parts).lower().encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

    def _post_api(self, path, payload):
        ts = int(time.time() * 1000)
        headers = self._get_base_headers()
        headers.update({
            "X-HASH": self._generate_x_hash("POST", path, self.vin, ts),
            "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, path, "POST", ts),
            "X-TIMESTAMP": str(ts)
        })
        try: return requests.post(f"{API_BASE}/{path}", headers=headers, json=payload, timeout=15)
        except Exception: return None

    def _register_device_trust(self):
        try:
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash("PUT", "ccarusermgnt/api/v1/device-trust/fcm-token", self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, "ccarusermgnt/api/v1/device-trust/fcm-token", "PUT", ts), "X-TIMESTAMP": str(ts)})
            self._safe_request("PUT", f"{API_BASE}/ccarusermgnt/api/v1/device-trust/fcm-token", headers=headers, json={"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"}, timeout=10)
        except Exception: pass

    def register_resources(self):
        try:
            self._post_api("ccarusermgnt/api/v1/user-vehicle/set-primary-vehicle", {"vinCode": self.vin})
            self._post_api("ccaraccessmgmt/api/v1/remote/app/wakeup", {})
            active_dict = VF3_SENSORS if self._model_group == "VF3" else VF5_SENSORS
            reqs = [{"objectId": str(int(k.split("_")[0])), "instanceId": str(int(k.split("_")[1])), "resourceId": str(int(k.split("_")[2]))} for k in active_dict.keys() if "_" in k and not k.startswith("api_")]
            for name_id in ["34180", "34181", "34183"]: reqs.append({"objectId": name_id, "instanceId": "00001", "resourceId": "00010"})
            self._post_api("ccaraccessmgmt/api/v1/telemetry/app/ping", reqs)
            self._post_api(f"ccaraccessmgmt/api/v1/telemetry/{self.vin}/list_resource", reqs)
            self._last_auto_wakeup_time = time.time()
            _LOGGER.debug("VinFast: Đã gửi lệnh HTTP WAKEUP toàn diện tới xe.")
        except Exception as e: pass

    def send_remote_command(self, command_type, params=None):
        payload = {"commandType": command_type, "vinCode": self.vin, "params": params or {}}
        res = self._post_api("ccaraccessmgmt/api/v2/remote/app/command", payload)
        if res and res.status_code == 200:
            threading.Thread(target=self.register_resources, daemon=True).start()
            return True
        return False

    def get_address_from_osm(self, lat, lon):
        try:
            res = requests.get(f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18", headers={"User-Agent": f"HA-VinFast"}, timeout=5)
            if res.status_code == 200: return res.json().get("display_name", f"{lat}, {lon}")
        except Exception: pass
        return f"{lat}, {lon}"

    def _fetch_weather_and_hvac(self, lat, lon):
        try:
            now = time.time()
            if now - self._last_weather_fetch_time < 900: return
            res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true", timeout=10)
            if res.status_code == 200:
                data = res.json()
                current = data.get("current_weather", {})
                temp = current.get("temperature")
                wind = current.get("windspeed")
                code = current.get("weathercode", 0)
                
                if temp is not None:
                    self._last_weather_fetch_time = now
                    self._last_data["api_outside_temp"] = temp
                    condition = "Trời quang"
                    if code in [1, 2, 3]: condition = "Có mây"
                    elif code in [45, 48]: condition = "Sương mù"
                    elif code in [51, 53, 55, 61, 63, 65]: condition = "Mưa nhẹ"
                    elif code in [80, 81, 82, 95, 96, 99]: condition = "Mưa rào/Giông"
                    self._last_data["api_weather_condition"] = f"{condition} (Gió {wind}km/h)"

                    if temp > 35: hvac = "Làm mát Tối đa (Tốn Pin)"
                    elif temp > 28: hvac = "Làm mát Trung bình"
                    elif temp < 15: hvac = "Sưởi ấm Tối đa (Rất tốn Pin)"
                    elif temp < 22: hvac = "Sưởi ấm Nhẹ"
                    else: hvac = "Lý tưởng (Tiết kiệm Pin)"
                    self._last_data["api_hvac_load_estimate"] = hvac
                    
                    # ==============================================================
                    # AI ADVISOR: CẢNH BÁO THỜI TIẾT CỰC ĐOAN (Cooldown 30 phút)
                    # ==============================================================
                    if now - getattr(self, '_last_ai_weather_time', 0) > 1800:
                        if temp >= 38 or temp <= 15 or code in [80, 81, 82, 95, 96, 99]:
                            self._last_ai_weather_time = now
                            weather_data = {"temp": temp, "cond": condition}
                            threading.Thread(target=self._run_ai_advisor_async, args=("weather", weather_data), daemon=True).start()

                    self._save_state()
                    if self.callbacks:
                        for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _update_location_async(self, lat, lon):
        try:
            grid_coord = f"{round(float(lat), 3)},{round(float(lon), 3)}"
            curr_addr = self._last_data.get("api_current_address", "")
            threading.Thread(target=self._fetch_weather_and_hvac, args=(lat, lon), daemon=True).start()
            with self._geocode_lock:
                if getattr(self, '_last_geocoded_grid', None) != grid_coord or "Tọa độ" in curr_addr or "Đang kết nối" in curr_addr:
                    addr = self.get_address_from_osm(lat, lon)
                    if addr:
                        self._last_data["api_current_address"] = addr
                        self._last_geocoded_grid = grid_coord
                        
                        threading.Thread(target=self.fetch_nearby_stations, daemon=True).start()
                        
                        self._save_state()
                        if self.callbacks:
                            for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _load_state(self):
        if not self.vin: return
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        charge_history_file = os.path.join(WWW_DIR, f"vinfast_charge_history_{self.vin.lower()}.json")
        if os.path.exists(charge_history_file):
            try:
                with open(charge_history_file, 'r', encoding='utf-8') as f:
                    self._last_data["api_charge_history_list"] = json.dumps(json.load(f))
            except: pass
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    if "last_data" in saved_data:
                        self._last_data.update(saved_data["last_data"])
                    if "internal_memory" in saved_data:
                        mem = saved_data["internal_memory"]
                        self._is_trip_active = mem.get("is_trip_active", False)
                        self._trip_start_odo = mem.get("trip_start_odo", 0.0)
                        self._trip_start_time = mem.get("trip_start_time", time.time())
                        self._trip_start_soc = mem.get("trip_start_soc", 100.0)
                        self._trip_accumulated_distance_m = mem.get("trip_accumulated_distance_m", 0.0)
                        self._eff_soc = mem.get("eff_soc", None)
                        self._eff_gps_dist = mem.get("eff_gps_dist", 0.0)
                        self._eff_time = mem.get("eff_time", None)
                        self._eff_stats = mem.get("eff_stats", {})
                        self._last_ai_anomaly_time = mem.get("last_ai_anomaly_time", 0)
                        self._last_ai_weather_time = mem.get("last_ai_weather_time", 0)
                        
                        lat_start = self._last_data.get("api_last_lat")
                        lon_start = self._last_data.get("api_last_lon")
                        if lat_start and lon_start:
                            self._last_lat_lon = f"{lat_start},{lon_start}"
            except Exception: pass

    def _save_state(self):
        if not self.vin: return
        os.makedirs(WWW_DIR, exist_ok=True)
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        try:
            data_to_save = {
                "last_data": self._last_data.copy(),
                "internal_memory": {
                    "is_trip_active": getattr(self, '_is_trip_active', False),
                    "trip_start_odo": getattr(self, '_trip_start_odo', 0.0),
                    "trip_start_time": getattr(self, '_trip_start_time', time.time()),
                    "trip_start_soc": getattr(self, '_trip_start_soc', 100.0),
                    "trip_accumulated_distance_m": getattr(self, '_trip_accumulated_distance_m', 0.0), 
                    "eff_soc": getattr(self, '_eff_soc', None),
                    "eff_gps_dist": getattr(self, '_eff_gps_dist', 0.0),
                    "eff_time": getattr(self, '_eff_time', None),
                    "eff_stats": getattr(self, '_eff_stats', {}),
                    "last_ai_anomaly_time": getattr(self, '_last_ai_anomaly_time', 0),
                    "last_ai_weather_time": getattr(self, '_last_ai_weather_time', 0)
                },
                "unix_time": time.time()
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False)
        except Exception: pass

    def _save_trip_history(self):
        if not self.vin: return
        try:
            os.makedirs(WWW_DIR, exist_ok=True)
            trip_file = os.path.join(WWW_DIR, f"vinfast_trips_{self.vin.lower()}.json")
            trips = []
            if os.path.exists(trip_file):
                try:
                    with open(trip_file, 'r', encoding='utf-8') as f: trips = json.load(f)
                except: pass
            
            dist = float(self._last_data.get("api_trip_distance", 0))
            if dist > 0.05 or len(self._route_coords) > 2: 
                start_dt = datetime.datetime.fromtimestamp(self._trip_start_time)
                end_dt = datetime.datetime.now()
                dur_mins = int((end_dt.timestamp() - self._trip_start_time) / 60)

                start_addr = f"{self._route_coords[0][0]}, {self._route_coords[0][1]}" if self._route_coords else "Unknown"
                end_addr = f"{self._route_coords[-1][0]}, {self._route_coords[-1][1]}" if self._route_coords else "Unknown"

                new_trip = {
                    "id": int(end_dt.timestamp()),
                    "date": start_dt.strftime("%d/%m/%Y"),
                    "start_time": start_dt.strftime("%H:%M"),
                    "end_time": end_dt.strftime("%H:%M"),
                    "duration": dur_mins if dur_mins > 0 else 1,
                    "distance": round(dist, 2),
                    "start_address": start_addr,
                    "end_address": end_addr,
                    "route": self._route_coords
                }
                
                trips.insert(0, new_trip) 
                trips = trips[:50] 
                with open(trip_file, 'w', encoding='utf-8') as f:
                    json.dump(trips, f, ensure_ascii=False)
        except Exception: pass

    # =========================================================================
    # AI ADVISOR TỐI ƯU VỚI THUẬT TOÁN MỚI (km / 1% Pin)
    # =========================================================================
    def _run_ai_advisor_async(self, mode="trip", data_payload=None):
        try:
            if not getattr(self, 'gemini_api_key', None) or self.gemini_api_key.strip() == "":
                self._last_data["api_ai_advisor"] = "Vui lòng nhập Google Gemini API Key trong phần Cấu hình Integration (Config Flow) để AI có thể đánh giá."
                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
                return 

            temp = self._last_data.get("api_outside_temp", "Không rõ")
            cond = self._last_data.get("api_weather_condition", "Không rõ")
            hvac = self._last_data.get("api_hvac_load_estimate", "Bình thường")
            soc_end = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 50)))
            std_range = safe_float(self._last_data.get("api_static_range", 210))
            expected_km_per_1 = round(std_range / 100.0, 2) if std_range > 0 else 2.1

            prompt = ""

            if mode == "weather" and data_payload:
                w_temp = data_payload.get('temp', temp)
                w_cond = data_payload.get('cond', cond)
                prompt = (
                    f"CẢNH BÁO THỜI TIẾT CỰC ĐOAN: Nhiệt độ ngoài trời đang là {w_temp} độ C, thời tiết: {w_cond}. "
                    f"Đóng vai chuyên gia AI của xe VinFast, viết MỘT câu tiếng Việt cực kỳ ngắn gọn (dưới 40 từ) "
                    "khuyên tài xế cách chỉnh điều hòa và lái xe để an toàn và tiết kiệm pin nhất lúc này."
                )
                self._last_data["api_ai_advisor"] = f"☁️ Thời tiết khắc nghiệt ({w_temp}°C). Đang gọi AI tư vấn..."
                
            elif mode == "anomaly" and data_payload:
                dist = round(data_payload.get('dist', 0), 2)
                spd = round(data_payload.get('speed', 0), 1)
                prompt = (
                    f"CẢNH BÁO HAO PIN: Xe điện vừa sụt 1% pin nhưng chỉ đi được {dist}km "
                    f"(mức chuẩn lý tưởng của nhà sản xuất công bố là {expected_km_per_1} km/1%). "
                    f"Tốc độ chạy trung bình lúc này: {spd}km/h. Tải điều hòa: {hvac}. "
                    "Bạn hãy đóng vai Cố vấn AI trên xe, viết MỘT câu tiếng Việt cực kỳ ngắn gọn (dưới 40 từ) "
                    "nhận xét nguyên nhân gây tốn pin (do tốc độ hay điều hòa) và đưa ra lời khuyên khẩn cấp."
                )
                self._last_data["api_ai_advisor"] = f"⚠️ Sụt pin nhanh! (1% đi được {dist}km). Đang chờ AI phân tích..."

            else:
                dist = data_payload.get('dist', 0) if data_payload else float(self._last_data.get("api_trip_distance", 0.0))
                drop = data_payload.get('drop', 0) if data_payload else 0
                
                if dist < 0.05: 
                    self._last_data["api_ai_advisor"] = f"Hệ thống đang đợi... Chuyến đi hiện tại ({dist}km) quá ngắn để phân tích."
                    if self.callbacks:
                        for cb in self.callbacks: cb(self._last_data)
                    return 

                actual_km_per_1 = round(dist / drop, 2) if drop > 0 else dist
                spd = self._last_data.get("api_trip_avg_speed", 0)
                
                prompt = (
                    f"Đóng vai kỹ sư phân tích xe điện. Chuyến đi vừa hoàn thành dài {round(dist,2)}km, tiêu hao {round(drop,1)}% pin. "
                    f"Hiệu suất thực tế đạt: {actual_km_per_1} km / 1% pin. (Thông số chuẩn của hãng là {expected_km_per_1} km / 1%). "
                    f"Tốc độ trung bình {spd}km/h. Môi trường: {temp}°C, {cond}. Tải điều hòa: {hvac}. "
                    "Hãy viết 1 đoạn văn tiếng Việt ngắn gọn (dưới 50 từ), đánh giá xem hiệu suất chuyến đi này là xuất sắc, bình thường hay kém "
                    "và đưa ra 1 lời khuyên."
                )
                self._last_data["api_ai_advisor"] = "🔄 Đang tổng kết chuyến đi. Gửi dữ liệu cho AI phân tích..."

            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)

            # Cập nhật dùng model gemini-1.5-flash chuẩn nhất hiện nay
            clean_key = self.gemini_api_key.strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={clean_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            for attempt in range(2):
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                if res.status_code == 200:
                    ai_text = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if ai_text:
                        self._last_data["api_ai_advisor"] = ai_text.replace("*", "").strip()
                    break 
                elif res.status_code == 403:
                    # BẢN VÁ: Giải thích rõ lỗi 403 cho người dùng
                    self._last_data["api_ai_advisor"] = "❌ Lỗi 403: API Key bị sai hoặc chưa được cấp quyền. Hãy kiểm tra lại Google AI Studio."
                    break
                elif res.status_code == 400:
                    self._last_data["api_ai_advisor"] = "❌ Lỗi 400: API Key không hợp lệ."
                    break
                elif res.status_code in [503, 429]:
                    if attempt < 1: time.sleep(2.5); continue
                    else: self._last_data["api_ai_advisor"] = f"⏳ Google AI hiện đang quá tải (Lỗi {res.status_code})."
                else:
                    self._last_data["api_ai_advisor"] = f"❌ Google báo lỗi {res.status_code}"
                    break
                
            self._save_state()
            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)
        except Exception as e: 
            self._last_data["api_ai_advisor"] = f"❌ Lỗi kết nối đến Google AI: {e}"
            if self.callbacks:
                for cb in self.callbacks: cb(self._last_data)

    def fetch_charging_history(self):
        max_retries = 5 
        attempt = 0
        
        while self._running and attempt < max_retries:
            attempt += 1
            try:
                if not self.vin or not self.access_token: 
                    time.sleep(5)
                    continue
                    
                api_path = "ccarcharging/api/v1/charging-sessions/search"
                ts = int(time.time() * 1000)
                headers = self._get_base_headers()
                headers.update({
                    "X-HASH": self._generate_x_hash("POST", api_path, self.vin, ts), 
                    "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, "POST", ts), 
                    "X-TIMESTAMP": str(ts)
                })
                
                payload = {"orderStatus": [3, 5, 7], "startTime": 1704067200000, "endTime": ts}
                
                all_sessions = []
                page = 0
                size = 50
                success_fetch = False
                
                while page < 50: 
                    res = requests.post(f"{API_BASE}/{api_path}?page={page}&size={size}", headers=headers, json=payload, timeout=20)
                    
                    if res and res.status_code == 200:
                        data = res.json().get("data", {})
                        content = []
                        if isinstance(data, dict):
                            content = data.get("content", [])
                        elif isinstance(data, list):
                            content = data
                            
                        all_sessions.extend(content)
                        if len(content) < size:
                            success_fetch = True
                            break 
                        page += 1
                        time.sleep(0.5) 
                    else:
                        break 
                        
                if success_fetch:
                    valid_sessions = sorted([s for s in all_sessions if safe_float(s.get("totalKWCharged", 0)) > 0], key=lambda x: safe_float(x.get("pluggedTime", 0)), reverse=True)
                    actual_public_sessions = len(valid_sessions)
                    prev_public_count = int(self._last_data.get("api_public_charge_sessions", 0))
                    
                    if actual_public_sessions >= prev_public_count or prev_public_count == 0:
                        detailed_history = []
                        for s in valid_sessions[:10]:
                            addr = s.get("chargingStationAddress", "Trạm sạc VinFast")
                            kwh = safe_float(s.get("totalKWCharged", 0))
                            p_time = safe_float(s.get("pluggedTime", 0))
                            u_time = safe_float(s.get("unpluggedTime", 0))
                            dur = round((u_time - p_time) / 60000) if u_time > p_time else 0
                            date_str = datetime.datetime.fromtimestamp(p_time/1000).strftime('%d/%m/%Y %H:%M') if p_time > 0 else ""
                            detailed_history.append({"date": date_str, "address": addr, "kwh": kwh, "duration": dur})
                        
                        self._last_data["api_charge_history_list"] = json.dumps(detailed_history)
                        self._last_data["api_public_charge_sessions"] = actual_public_sessions
                        home_sessions = int(self._last_data.get("api_home_charge_sessions", 0))
                        self._last_data["api_total_charge_sessions"] = actual_public_sessions + home_sessions
                        
                        public_energy = sum(safe_float(s.get("totalKWCharged", 0)) for s in valid_sessions)
                        self._last_data["api_public_charge_energy"] = round(public_energy, 2)
                        home_kwh = safe_float(self._last_data.get("api_home_charge_kwh", 0.0))
                        self._last_data["api_total_energy_charged"] = round(public_energy + home_kwh, 2)
                        
                        if valid_sessions:
                            last_session = valid_sessions[0]
                            self._last_data["api_last_charge_start_soc"] = safe_float(last_session.get("startBatteryLevel", 0))
                            self._last_data["api_last_charge_end_soc"] = safe_float(last_session.get("endBatteryLevel", 0))
                            energy_grid = safe_float(last_session.get("totalKWCharged", 0))
                            self._last_data["api_last_charge_energy"] = round(energy_grid, 2)
                            p_time = safe_float(last_session.get("pluggedTime", 0))
                            u_time = safe_float(last_session.get("unpluggedTime", 0))
                            duration_min = (u_time - p_time) / 60000 if u_time > p_time else 0
                            if duration_min > 0:
                                self._last_data["api_last_charge_duration"] = round(duration_min, 0)
                                self._last_data["api_last_charge_power"] = round((energy_grid / (duration_min / 60)), 1)
                        
                        self._calculate_advanced_stats()
                        self._save_state()
                        if self.callbacks:
                            for cb in self.callbacks: cb(self._last_data)
                        break 
                    else:
                        time.sleep(10)
                        continue
                else:
                    time.sleep(10)
                    continue
                    
            except Exception as e:
                time.sleep(10)

    def fetch_nearby_stations(self):
        try:
            if not self._last_lat_lon: return
            lat_str, lon_str = self._last_lat_lon.split(',')
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash("POST", "ccarcharging/api/v1/stations/search", self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, "ccarcharging/api/v1/stations/search", "POST", ts), "X-TIMESTAMP": str(ts)})
            payload = {"latitude": float(lat_str), "longitude": float(lon_str), "radius": 50000, "excludeFavorite": False, "stationType": [], "status": [], "brandIds": []}
            
            res = requests.post(f"{API_BASE}/ccarcharging/api/v1/stations/search?page=0&size=50", headers=headers, json=payload, timeout=15)
            if res and res.status_code == 200:
                data = res.json().get("data", [])
                if isinstance(data, dict) and "content" in data: data = data.get("content", [])
                stations = []
                for st in data:
                    st_lat = safe_float(st.get("latitude"))
                    st_lng = safe_float(st.get("longitude"))
                    if not st_lat or not st_lng: continue
                    dist = round(safe_float(st.get("distance", 0))/1000, 1)
                    if dist > 80.0: continue
                    max_power, avail, total = 0, 0, 0
                    for evse in st.get("evsePowers", []):
                        avail += int(evse.get("numberOfAvailableEvse", 0))
                        total += int(evse.get("totalEvse", 0))
                        power_kw = int(evse.get("type", 0)) / 1000 if int(evse.get("type", 0)) >= 1000 else int(evse.get("type", 0))
                        if power_kw > max_power: max_power = int(power_kw)
                    stations.append({"id": st.get("locationId", ""), "name": st.get("stationName", "Trạm sạc VinFast").strip(), "lat": st_lat, "lng": st_lng, "power": max_power, "avail": avail, "total": total, "dist": dist})
                
                stations = sorted(stations, key=lambda x: x["dist"])
                self._last_data["api_nearby_stations"] = json.dumps(stations)
                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _sign(self, key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def _get_signature_key(self, key, date_stamp, regionName, serviceName):
        kDate = self._sign(('AWS4' + key).encode('utf-8'), date_stamp)
        kRegion = self._sign(kDate, regionName)
        kService = self._sign(kRegion, serviceName)
        kSigning = self._sign(kService, 'aws4_request')
        return kSigning

    def _get_aws_mqtt_url(self):
        try:
            url_id = f"https://cognito-identity.{AWS_REGION}.amazonaws.com/"
            res_id = self._safe_request("POST", url_id, headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15)
            if not res_id or res_id.status_code != 200: return None
            identity_id = res_id.json()["IdentityId"]
            
            res_cred = self._safe_request("POST", url_id, headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": identity_id, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15)
            if not res_cred or res_cred.status_code != 200: return None
            creds = res_cred.json()["Credentials"]
            
            self._safe_request("POST", f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": identity_id}, timeout=15)
            
            t = datetime.datetime.now(datetime.timezone.utc)
            amz_date = t.strftime('%Y%m%dT%H%M%SZ')
            datestamp = t.strftime('%Y%m%d')
            credential_scope = f"{datestamp}/{AWS_REGION}/iotdevicegateway/aws4_request"
            query_params = f"X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={urllib.parse.quote(creds['AccessKeyId'] + '/' + credential_scope, safe='')}&X-Amz-Date={amz_date}&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
            canonical_request = f"GET\n/mqtt\n{query_params}\nhost:{IOT_ENDPOINT}\n\nhost\n" + hashlib.sha256("".encode('utf-8')).hexdigest()
            
            string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n" + hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
            signing_key = self._get_signature_key(creds['SecretKey'], datestamp, AWS_REGION, 'iotdevicegateway')
            signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            
            return f"wss://{IOT_ENDPOINT}/mqtt?{query_params}&X-Amz-Signature={signature}&X-Amz-Security-Token={urllib.parse.quote(creds['SessionToken'], safe='')}"
        except Exception: return None

    def _renew_aws_connection(self):
        try:
            if self.client:
                self.client.loop_stop()
                try: self.client.disconnect()
                except: pass
                self.client = None 
                
            self.client = mqtt.Client(client_id=f"Android_{self.vin}_{self._mqtt_client_id_rand}", transport="websockets")
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.tls_set()
            
            self.login()
            self._register_device_trust()
            new_url = self._get_aws_mqtt_url()
            if new_url:
                self.client.ws_set_options(path=new_url.split(IOT_ENDPOINT)[1])
                self.client.connect(IOT_ENDPOINT, 443, 30)
                self.client.loop_start()
                self._needs_mqtt_renew = False 
        except Exception as e: pass

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0: 
            client.subscribe(f"/mobile/{self.vin}/push", qos=1)
            client.subscribe(f"monitoring/server/{self.vin}/push", qos=1)
            client.subscribe(f"/server/{self.vin}/remctrl", qos=1)
            self._last_mqtt_msg_time = time.time()

    def _on_disconnect(self, client, userdata, rc):
        self._needs_mqtt_renew = True

    def _send_heartbeat(self, state="1"):
        if not self.client or not self.client.is_connected() or not self.vin: return
        topic = f"/vehicles/{self.vin}/push/connected/heartbeat"
        payload = {"version": "1.2", "timestamp": int(time.time() * 1000), "trans_id": str(uuid.uuid4()), "content": {"34183": { "1": { "54": str(state) } }}}
        try: self.client.publish(topic, json.dumps(payload), qos=1)
        except Exception: pass

    def _api_polling_loop(self):
        time.sleep(5) 
        if not self.user_id: self.get_vehicles()
        self._renew_aws_connection()
        self.register_resources()
        
        last_heartbeat = time.time()
        last_state_save = time.time()
        last_aws_renew = time.time()
        
        while self._running:
            try:
                time.sleep(1)
                now = time.time()
                
                try:
                    if os.path.exists(MOCK_FILE):
                        with open(MOCK_FILE, "r", encoding="utf-8") as f: cmd = f.read().strip()
                        os.remove(MOCK_FILE)
                        if cmd: self._process_console_command(cmd)
                except Exception: pass

                if now - last_heartbeat >= 60:
                    last_heartbeat = now
                    state = "2" if getattr(self, '_is_moving', False) else "1"
                    self._send_heartbeat(state)

                if now - last_aws_renew >= 3000 or self._needs_mqtt_renew:
                    last_aws_renew = now
                    self._renew_aws_connection()

                time_since_last_msg = now - getattr(self, '_last_mqtt_msg_time', now)
                if getattr(self, '_is_moving', False) and time_since_last_msg > 180:
                    self._needs_mqtt_renew = True
                    self._last_mqtt_msg_time = now 

                if getattr(self, '_vehicle_offline', False):
                    time_since_last_wakeup = now - getattr(self, '_last_auto_wakeup_time', 0)
                    if time_since_last_wakeup > 180:
                        _LOGGER.warning("VinFast: Xe đang Offline (Ngủ sâu). Tiến hành gọi HTTP PING Wakeup T-Box...")
                        self.register_resources() 

                # =====================================================================
                # BẢN VÁ: TỰ ĐỘNG CHỐT CHUYẾN ĐI CHỈ KHI DỪNG HẲN (SPEED=0) QUÁ 5 PHÚT
                # =====================================================================
                time_since_move = now - getattr(self, '_last_actual_move_time', now)
                if getattr(self, '_is_trip_active', False) and not getattr(self, '_is_moving', False) and time_since_move >= 300:
                    self._is_trip_active = False 
                    self._save_trip_history()
                    
                    trip_dist = float(self._last_data.get("api_trip_distance", 0))
                    soc_start = getattr(self, '_trip_start_soc', 100.0)
                    soc_end = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 50)))
                    soc_drop = soc_start - soc_end
                    
                    # Gọi AI Phân tích Trip (Bằng dữ liệu hiệu suất mới)
                    if trip_dist >= 0.5: 
                        trip_data = {"dist": trip_dist, "drop": soc_drop}
                        threading.Thread(target=self._run_ai_advisor_async, args=("trip", trip_data), daemon=True).start()
                        
                    self._trip_start_odo = 0.0
                    self._trip_start_time = time.time()
                    self._route_coords = []
                    self._trip_accumulated_distance_m = 0.0 
                    self._save_state() 

                if now - last_state_save >= 60:
                    last_state_save = now
                    self._save_state()
            except Exception: pass

    def start_mqtt(self):
        if self._running: return
        self._running = True
        self._polling_thread = threading.Thread(target=self._api_polling_loop, daemon=True)
        self._polling_thread.start()
        threading.Thread(target=self.fetch_charging_history, daemon=True).start()

    def _filter_critical_data(self, key, current_val, fallback_val):
        if current_val is None: return fallback_val
        if key in ["34183_00001_00009", "34180_00001_00011", "34183_00001_00003", "34199_00000_00000", "34183_00001_00004", "34180_00001_00007", "34193_00001_00012", "34193_00001_00014", "34193_00001_00019"]:
            try:
                if float(current_val) <= 0.0 and fallback_val is not None and float(fallback_val) > 0:
                    return fallback_val
            except Exception: pass
        return current_val

    def _on_message(self, client, userdata, msg):
        current_time = time.time()
        self._last_mqtt_msg_time = current_time 
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            data_dict = {}
            items = []
            if isinstance(payload, list): items = payload
            elif isinstance(payload, dict):
                if "data" in payload and isinstance(payload["data"], list): items = payload["data"]
                elif "content" in payload and isinstance(payload["content"], list): items = payload["content"]
            
            for item in items:
                if not isinstance(item, dict): continue
                obj, inst, res = str(item.get("objectId", "0")).zfill(5), str(item.get("instanceId", "0")).zfill(5), str(item.get("resourceId", "0")).zfill(5)
                key = item.get("deviceKey") if "deviceKey" in item else f"{obj}_{inst}_{res}"
                val = item.get("value")
                
                if key == "56789_00001_00007":
                    if str(val) == "CONNECTION_LOST":
                        self._vehicle_offline = True
                    elif str(val) == "NONE":
                        self._vehicle_offline = False
                
                if key == "34180_00001_00011" and isinstance(val, str) and "profile_email" in val: continue 
                if key and val is not None: 
                    data_dict[key] = self._filter_critical_data(key, val, self._last_data.get(key))
            
            if not data_dict: return
            
            t1 = data_dict.get("34193_00001_00012")
            t2 = data_dict.get("34193_00001_00014")
            t3 = data_dict.get("34193_00001_00019")
            target_val = t1 if t1 is not None else (t2 if t2 is not None else t3)
            if target_val is not None:
                try:
                    v_num = float(target_val)
                    if v_num > 0: self._last_data["api_target_charge_limit"] = v_num
                except: pass

            self._last_data.update(data_dict)
            
            for k in ["34180_00001_00010", "34183_00001_00010", "34181_00001_00007"]:
                if k in data_dict and isinstance(data_dict[k], str):
                    self._update_vehicle_name(data_dict[k])
                
        except Exception: return

        current_soc = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 0)))
        
        try:
            if self._model_group == "VF89":
                gear = str(self._last_data.get("34187_00000_00000", "1"))
                speed = safe_float(self._last_data.get("34188_00000_00000", 0))
            else: 
                gear = str(self._last_data.get("34183_00001_00001", "1"))
                speed = safe_float(self._last_data.get("34183_00001_00002", 0))

            # =====================================================================
            # BẢN VÁ: CẬP NHẬT BIẾN IS_MOVING CHÍNH XÁC ĐỂ TRÌ HOÃN NGẮT TRIP
            # =====================================================================
            if speed > 0 or gear in ["2", "4", "D", "R"]:
                self._is_moving = True
                self._last_actual_move_time = current_time
                base_status = "Đang di chuyển"
            else:
                self._is_moving = False
                base_status = "Đang đỗ" if gear == "1" else "Đang dừng"

            if self._is_moving and not getattr(self, '_is_trip_active', False):
                self._trip_start_time = current_time
                self._trip_start_soc = current_soc
                self._is_trip_active = True
                self._last_data["api_trip_distance"] = 0.0
                self._last_data["api_trip_efficiency"] = 0.0
                self._trip_accumulated_distance_m = 0.0 
                self._route_coords = [] 
                self._save_state()
        except Exception: pass

        try:
            lat = safe_float(data_dict.get("00006_00001_00000", self._last_data.get("00006_00001_00000")))
            lon = safe_float(data_dict.get("00006_00001_00001", self._last_data.get("00006_00001_00001")))
            
            if lat > 0 and lon > 0:
                curr_coord = f"{lat},{lon}"
                self._last_data["api_last_lat"] = lat
                self._last_data["api_last_lon"] = lon

                if curr_coord != getattr(self, '_last_lat_lon', ""): 
                    self._last_lat_lon = curr_coord
                    threading.Thread(target=self._update_location_async, args=(lat, lon), daemon=True).start()
                    
                    if getattr(self, '_is_trip_active', False):
                        if not self._route_coords:
                            self._route_coords.append([round(lat, 6), round(lon, 6), int(speed)])
                        else:
                            last_lat = self._route_coords[-1][0]
                            last_lon = self._route_coords[-1][1]
                            
                            R = 6371000 
                            phi1 = math.radians(last_lat)
                            phi2 = math.radians(lat)
                            dphi = math.radians(lat - last_lat)
                            dlambda = math.radians(lon - last_lon)
                            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
                            distance_m = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                            
                            if 1.0 <= distance_m <= 2000:
                                self._trip_accumulated_distance_m += distance_m
                                self._eff_gps_dist = getattr(self, '_eff_gps_dist', 0.0) + distance_m
                                self._route_coords.append([round(lat, 6), round(lon, 6), int(speed)])
                                if len(self._route_coords) > 1500: self._route_coords.pop(0) 
                                self._last_data["api_trip_route"] = json.dumps(self._route_coords)
                                
            if getattr(self, '_is_trip_active', False):
                final_trip_dist = self._trip_accumulated_distance_m / 1000.0
                self._last_data["api_trip_distance"] = round(final_trip_dist, 2)

                if final_trip_dist > 0:
                    trip_hrs = (current_time - getattr(self, '_trip_start_time', current_time)) / 3600.0
                    if trip_hrs > 0:
                        self._last_data["api_trip_avg_speed"] = round(final_trip_dist / trip_hrs, 1)

                    if getattr(self, '_trip_start_soc', 0) > current_soc:
                        cap = safe_float(self._last_data.get("api_static_capacity", 0))
                        if cap > 0:
                            energy_used = ((self._trip_start_soc - current_soc) / 100.0) * cap
                            self._last_data["api_trip_energy_used"] = round(energy_used, 2)
                            self._last_data["api_trip_efficiency"] = round((energy_used / final_trip_dist) * 100, 2)

        except Exception as e: pass

        if current_soc > 0:
            if getattr(self, '_eff_soc', None) is None or current_soc > self._eff_soc:
                self._eff_soc = current_soc
                self._eff_gps_dist = 0.0
                self._eff_time = current_time 
                self._eff_speeds = []
            
            if speed > 0: 
                self._eff_speeds.append(speed)
                
            if current_soc < self._eff_soc:
                drop_amount = self._eff_soc - current_soc
                dist_km = getattr(self, '_eff_gps_dist', 0.0) / 1000.0
                
                if dist_km > 0:
                    sorted_speeds = sorted(self._eff_speeds)
                    median_speed = sorted_speeds[len(sorted_speeds) // 2] if sorted_speeds else speed
                    band_lower = int(median_speed / 10) * 10
                    band_key = f"{band_lower}-{band_lower+10}"
                    
                    if band_key not in self._eff_stats: self._eff_stats[band_key] = {"dist": 0.0, "drops": 0.0}
                    self._eff_stats[band_key]["dist"] += dist_km
                    self._eff_stats[band_key]["drops"] += drop_amount
                    
                    best_b, max_e = "Đang thu thập", 0
                    for k, v in self._eff_stats.items():
                        if v["drops"] > 0:
                            eff = v["dist"] / v["drops"]
                            if eff > max_e:
                                max_e, best_b = eff, k
                    if max_e > 0: self._last_data["api_best_efficiency_band"] = f"{best_b} km/h ({round(max_e, 2)} km/1%)"

                    # =====================================================================
                    # AI ADVISOR: CẢNH BÁO SỤT PIN BẤT THƯỜNG (Dựa trên KM / 1%)
                    # =====================================================================
                    max_range = safe_float(self._last_data.get("api_static_range", 0))
                    if max_range > 0 and drop_amount >= 1.0:
                        expected_dist_per_1 = max_range / 100.0
                        if dist_km < (expected_dist_per_1 * 0.70): # Sụt pin quá nhanh (chỉ đạt < 70% định mức)
                            now = time.time()
                            if now - getattr(self, '_last_ai_anomaly_time', 0) > 900: # Cooldown 15 phút
                                self._last_ai_anomaly_time = now
                                start_t = getattr(self, '_eff_time', None) or (now - 60)
                                time_taken_hrs = (now - start_t) / 3600.0
                                actual_spd = dist_km / time_taken_hrs if time_taken_hrs > 0 else median_speed
                                
                                anomaly_data = {"dist": dist_km, "drop": drop_amount, "expected": expected_dist_per_1, "speed": actual_spd}
                                threading.Thread(target=self._run_ai_advisor_async, args=("anomaly", anomaly_data), daemon=True).start()
                
                self._eff_soc = current_soc
                self._eff_gps_dist = 0.0
                self._eff_time = current_time
                self._eff_speeds = []

        try:
            # GHI CHÚ: Lệnh ngắt Trip đã được chuyển vào Watchdog ở _api_polling_loop 
            # để loại bỏ tình trạng ngắt nhầm khi xe mới về P vài chục giây.

            if self._model_group == "VF89":
                c_status = str(self._last_data.get("34183_00000_00001", "0"))
            else: 
                c_status = str(self._last_data.get("34193_00001_00005", "0"))

            is_charging = (c_status == "1")
            is_fully_charged = False 

            if c_status in ["0", "2", "3", "4"] or getattr(self, '_is_moving', False):
                is_charging = False
                is_fully_charged = False

            t_limit = safe_float(self._last_data.get("api_target_charge_limit", 100))
            if t_limit > 0 and current_soc >= t_limit and (is_charging or c_status in ["2", "3"]):
                is_fully_charged = True
                is_charging = False

            self._is_charging = is_charging

            if is_charging: self._last_data["api_vehicle_status"] = "Đang sạc"
            elif is_fully_charged: self._last_data["api_vehicle_status"] = "Đã sạc xong"
            else: self._last_data["api_vehicle_status"] = base_status

        except Exception as e: pass

        try:
            if self._is_charging and not getattr(self, '_last_is_charging', False):
                threading.Thread(target=self.fetch_charging_history, daemon=True).start()
                
                self._current_charge_max_power = 0.0
                self._last_data["api_last_charge_start_soc"] = current_soc
                self._charge_start_time = current_time
                self._charge_start_soc = current_soc
                self._charge_calc_soc = current_soc
                self._charge_calc_time = current_time
                self._last_data["api_live_charge_power"] = 0.0
                self._last_is_charging = True
                self._save_state() 
                
            elif not self._is_charging and getattr(self, '_last_is_charging', False):
                delta_soc = current_soc - getattr(self, '_charge_start_soc', current_soc)
                if delta_soc > 1.0: 
                    cap = safe_float(self._last_data.get("api_static_capacity", 18.64))
                    if cap == 0: cap = 18.64
                    added_kwh = (delta_soc / 100.0) * cap
                    
                    is_home_charge = True
                    try:
                        stations = json.loads(self._last_data.get("api_nearby_stations", "[]"))
                        if stations and len(stations) > 0 and float(stations[0].get("dist", 999)) < 0.5:
                            is_home_charge = False 
                    except: pass
                        
                    if is_home_charge or getattr(self, '_current_charge_max_power', 0.0) < 15.0:
                        curr_home_sessions = int(self._last_data.get("api_home_charge_sessions", 0))
                        curr_home_kwh = float(self._last_data.get("api_home_charge_kwh", 0.0))
                        self._last_data["api_home_charge_sessions"] = curr_home_sessions + 1
                        self._last_data["api_home_charge_kwh"] = round(curr_home_kwh + added_kwh, 2)
                
                threading.Thread(target=self.fetch_charging_history, daemon=True).start()
                
                self._last_data["api_last_charge_end_soc"] = current_soc
                if getattr(self, '_charge_start_time', 0) > 0:
                    duration_mins = (current_time - self._charge_start_time) / 60.0
                    self._last_data["api_last_charge_duration"] = round(duration_mins, 0)
                
                self._last_is_charging = False
                self._charge_calc_soc = 0.0
                self._charge_calc_time = current_time
                self._last_data["api_live_charge_power"] = 0.0
                self._current_charge_max_power = 0.0 
                self._save_state() 

            if self._is_charging:
                if getattr(self, '_charge_calc_soc', 0.0) == 0.0:
                    self._charge_calc_soc = current_soc
                    self._charge_calc_time = current_time
                    self._last_data["api_live_charge_power"] = 0.0
                elif current_soc > self._charge_calc_soc:
                    delta_soc = current_soc - self._charge_calc_soc
                    delta_time_hrs = (current_time - self._charge_calc_time) / 3600.0
                    cap = safe_float(self._last_data.get("api_static_capacity", 18.64))
                    if cap == 0: cap = 18.64
                    if delta_time_hrs > 0 and cap > 0:
                        power = (delta_soc / 100.0) * cap / delta_time_hrs
                        if power > 0:
                            self._last_data["api_live_charge_power"] = round(power, 1)
                            self._current_charge_max_power = max(getattr(self, '_current_charge_max_power', 0.0), power)
                            
                    self._charge_calc_soc = current_soc
                    self._charge_calc_time = current_time
                    self._save_state()
                elif current_time - getattr(self, '_charge_calc_time', current_time) > 900:
                    self._last_data["api_live_charge_power"] = 0.0
            else:
                self._last_data["api_live_charge_power"] = 0.0
        except Exception: pass

        if self.callbacks:
            for cb in self.callbacks: cb(self._last_data)
