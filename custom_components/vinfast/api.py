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
import traceback
import paho.mqtt.client as mqtt

from .const import (
    AUTH0_DOMAIN, AUTH0_CLIENT_ID, API_BASE, 
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID, 
    VIRTUAL_SENSORS, VF3_SENSORS, VF567_SENSORS, VF89_SENSORS, VEHICLE_SPECS
)

_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HA_CONFIG_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
WWW_DIR = os.path.join(HA_CONFIG_DIR, "www")

# DỮ LIỆU TRIP TÂY NINH (DÙNG ĐỂ MÔ PHỎNG UI BẢN ĐỒ)
TRIP_DATA = [
    [11.5553, 106.172331, 1], [11.5553, 106.172318, 2], [11.555303, 106.172308, 3], [11.555306, 106.172288, 4], 
    [11.55531, 106.172264, 2], [11.555312, 106.172251, 2], [11.555312, 106.172221, 9], [11.555265, 106.172221, 9], 
    [11.555265, 106.172188, 17], [11.55513, 106.17217, 25], [11.55495, 106.172148, 27], [11.55475, 106.17212, 29], 
    [11.554536, 106.172094, 31], [11.554315, 106.172071, 32], [11.554089, 106.172038, 33], [11.553853, 106.172005, 28], 
    [11.553644, 106.17198, 19], [11.5535, 106.171968, 24], [11.553333, 106.171951, 29], [11.553128, 106.171929, 29], 
    [11.552919, 106.171908, 29], [11.552713, 106.171889, 29], [11.552507, 106.171868, 27], [11.552346, 106.17185, 5], 
    [11.552279, 106.171844, 5], [11.552251, 106.171844, 0], [11.552235, 106.171845, 4], [11.552214, 106.171847, 1], 
    [11.552167, 106.171853, 10], [11.552108, 106.171885, 22], [11.552065, 106.17202, 22], [11.55203, 106.17226, 35], 
    [11.551987, 106.17256, 46], [11.551937, 106.172893, 48], [11.551885, 106.173241, 48], [11.551815, 106.173712, 47], 
    [11.551764, 106.174056, 46], [11.55171, 106.174397, 46], [11.551654, 106.174735, 47], [11.551601, 106.175078, 47], 
    [11.551549, 106.175424, 46], [11.551497, 106.175762, 44], [11.551443, 106.176076, 37], [11.551389, 106.176342, 31], 
    [11.551352, 106.176556, 19], [11.551332, 106.176683, 11], [11.551318, 106.176756, 5], [11.551308, 106.176786, 3], 
    [11.551295, 106.176807, 6], [11.551246, 106.176829, 17], [11.551114, 106.17682, 24], [11.550937, 106.1768, 21], 
    [11.550779, 106.176786, 13], [11.550667, 106.176778, 15]
]

class FakeMQTTMsg:
    def __init__(self, payload_str):
        self.payload = payload_str.encode('utf-8')

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except: return default

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
        
        CHARS = "0123456789qwertyuiopasdfghjklzxcvbnm"
        self._mqtt_client_id_rand = "".join(random.choice(CHARS) for _ in range(20))
        
        self._last_data = {
            "api_vehicle_status": "Đang kết nối...",
            "api_current_address": "Đang kết nối...",
            "api_trip_route": "[]",
            "api_nearby_stations": "[]",
            "api_debug_raw": "Đang kết nối...", 
            "api_debug_raw_json": "{}", 
            "api_trip_distance": 0.0,
            "api_trip_avg_speed": 0.0,
            "api_trip_energy_used": 0.0,
            "api_trip_efficiency": 0.0,
            "api_trip_gas_cost": 0,
            "api_trip_charge_cost": 0,
            "api_live_charge_power": 0.0,
            "api_last_lat": None, 
            "api_last_lon": None,
            "api_total_charge_sessions": 0,
            "api_total_energy_charged": 0.0,
            "api_vehicle_name": self.vehicle_name,
            "api_charge_history_list": "[]", 
            "api_home_charge_kwh": 0.0,
            "api_home_charge_sessions": 0,
            "api_outside_temp": "--",
            "api_weather_condition": "Đang tải...",
            "api_hvac_load_estimate": "Bình thường",
            "api_ai_advisor": "Hệ thống AI đang chờ phân tích...",
            "api_target_charge_limit": None
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
        
        self._is_trip_active = False
        self._trip_start_odo = 0.0
        self._trip_start_time = time.time()
        self._trip_start_soc = 100.0
        self._trip_start_address = "Không xác định"
        self._route_coords = []
        self._last_gps_time = time.time()
        self._trip_accumulated_distance_m = 0.0
        
        self._eff_soc = 100.0
        self._eff_odo = 0.0
        self._eff_speeds = []
        self._eff_stats = {}
        
        self._charge_start_time = time.time()
        self._charge_start_soc = 0.0
        self._charge_calc_soc = 0.0
        self._charge_calc_time = time.time()
        self._current_charge_max_power = 0.0 

        self._last_geocoded_grid = None
        self._last_weather_fetch_time = 0 
        self._last_mqtt_msg_time = time.time() 
        self._geocode_lock = threading.Lock()
        self._raw_changelog_data = [] 
        self._log_lock = threading.Lock()

    # =========================================================================
    # BỘ CÔNG CỤ NHẬN LỆNH TỪ CONSOLE ĐỂ GIẢ LẬP TRÊN GIAO DIỆN (UI)
    # =========================================================================
    def inject_mock_data(self, data_dict):
        payload_list = []
        for k, v in data_dict.items():
            payload_list.append({"deviceKey": k, "value": str(v)})
        fake_msg = FakeMQTTMsg(json.dumps(payload_list))
        self._on_message(None, None, fake_msg)

    def test_mock_play_trip(self):
        if getattr(self, '_is_playing_mock_trip', False): return
        
        def run_trip():
            self._is_playing_mock_trip = True
            _LOGGER.warning("VINFAST TEST: ĐANG PHÁT LẠI TRIP TÂY NINH TRÊN UI...")
            self.inject_mock_data({"34183_00001_00001": "4", "34187_00000_00000": "4"})
            time.sleep(1)

            current_odo = safe_float(self._last_data.get("34183_00001_00003", 20000.0))
            current_soc = safe_float(self._last_data.get("34183_00001_00009", 80.0))
            
            for point in TRIP_DATA:
                if not getattr(self, '_is_playing_mock_trip', False): break
                lat, lon, speed = point
                current_odo += (speed / 3600.0) 
                if speed > 20: current_soc -= 0.05
                
                self.inject_mock_data({
                    "34183_00001_00002": str(speed), "34188_00000_00000": str(speed),
                    "00006_00001_00000": str(lat), "00006_00001_00001": str(lon),
                    "34183_00001_00003": str(current_odo), "34183_00001_00009": str(current_soc)
                })
                time.sleep(1.5) # Giả lập cập nhật bản đồ Frontend mỗi 1.5s
            
            self.inject_mock_data({
                "34183_00001_00002": "0", "34188_00000_00000": "0",
                "34183_00001_00001": "1", "34187_00000_00000": "1"
            })
            self._is_playing_mock_trip = False

        threading.Thread(target=run_trip, daemon=True).start()

    def _process_console_command(self, cmd):
        _LOGGER.warning(f"VINFAST TEST: Đã nhận lệnh [{cmd}] từ Console, đang đưa lên Giao diện...")
        parts = cmd.lower().split()
        if not parts: return
        action = parts[0]
        
        if action == "cs":
            self.inject_mock_data({"34193_00001_00005": "1", "34183_00000_00001": "1"})
        elif action == "rs":
            self.inject_mock_data({"34193_00001_00005": "2", "34183_00000_00001": "2"})
        elif action == "p":
            self.inject_mock_data({"34183_00001_00001": "1", "34187_00000_00000": "1", "34183_00001_00002": "0"})
        elif action == "n":
            self.inject_mock_data({"34183_00001_00001": "3", "34187_00000_00000": "3", "34183_00001_00002": "0"})
        elif action == "r":
            self.inject_mock_data({"34183_00001_00001": "2", "34187_00000_00000": "2"})
        elif action == "d":
            self.inject_mock_data({"34183_00001_00001": "4", "34187_00000_00000": "4"})
        elif action == "v":
            speed = 40
            if len(parts) > 1:
                try: speed = int(parts[1])
                except: pass
            current_lat = safe_float(self._last_data.get("00006_00001_00000", 11.555))
            current_lon = safe_float(self._last_data.get("00006_00001_00001", 106.172))
            current_odo = safe_float(self._last_data.get("34183_00001_00003", 20000.0))
            if speed > 0:
                self.inject_mock_data({
                    "34183_00001_00002": str(speed), "34188_00000_00000": str(speed),
                    "00006_00001_00000": str(current_lat + 0.001), "00006_00001_00001": str(current_lon + 0.001),
                    "34183_00001_00003": str(current_odo + 0.2)
                })
            else:
                self.inject_mock_data({"34183_00001_00002": "0", "34188_00000_00000": "0"})
        elif action == "trip" or action == "play":
            self.test_mock_play_trip()
    # =========================================================================

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            if self._last_data: cb(self._last_data)

    def stop(self):
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _safe_request(self, method, url, max_retries=6, delay=10, **kwargs):
        for attempt in range(max_retries):
            try:
                if method.upper() == "POST": return requests.post(url, **kwargs)
                elif method.upper() == "PUT": return requests.put(url, **kwargs)
                else: return requests.get(url, **kwargs)
            except requests.exceptions.RequestException:
                if attempt < max_retries - 1: time.sleep(delay)
        return None

    def login(self):
        url = f"https://{AUTH0_DOMAIN}/oauth/token"
        res = self._safe_request("POST", url, json={
            "client_id": AUTH0_CLIENT_ID, "grant_type": "password",
            "username": self.email, "password": self.password,
            "scope": "openid profile email offline_access", "audience": API_BASE
        }, timeout=15, max_retries=6, delay=10) 
        if res and res.status_code == 200:
            self.access_token = res.json()["access_token"]
            return self.access_token
        return None

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

    def _load_state(self):
        if not self.vin: return
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        changelog_file = os.path.join(WWW_DIR, f"vinfast_changelog_{self.vin.lower()}.json")
        charge_history_file = os.path.join(WWW_DIR, f"vinfast_charge_history_{self.vin.lower()}.json")
        
        if os.path.exists(charge_history_file):
            try:
                with open(charge_history_file, 'r', encoding='utf-8') as f:
                    c_data = json.load(f)
                    self._last_data["api_charge_history_list"] = json.dumps(c_data)
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
                        self._trip_start_address = mem.get("trip_start_address", "Không xác định")
                        self._route_coords = mem.get("route_coords", [])
                        self._last_gps_time = mem.get("last_gps_time", time.time())
                        self._trip_accumulated_distance_m = mem.get("trip_accumulated_distance_m", 0.0)
                        self._eff_soc = mem.get("eff_soc", 100.0)
                        self._eff_odo = mem.get("eff_odo", 0.0)
                        self._eff_speeds = mem.get("eff_speeds", [])
                        self._eff_stats = mem.get("eff_stats", {})
                        self._is_charging = mem.get("is_charging", False)
                        self._last_is_charging = mem.get("last_is_charging", False)
                        self._last_actual_move_time = mem.get("last_actual_move_time", time.time())
                        self._current_charge_max_power = mem.get("current_charge_max_power", 0.0)
            except Exception: pass
            
        if os.path.exists(changelog_file):
            try:
                with open(changelog_file, 'r', encoding='utf-8') as f:
                    self._raw_changelog_data = json.load(f)
            except: pass

    def _save_state(self):
        if not self.vin: return
        if not os.path.exists(WWW_DIR): os.makedirs(WWW_DIR, exist_ok=True)
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        try:
            data_to_save = {
                "last_data": self._last_data.copy(),
                "internal_memory": {
                    "is_trip_active": getattr(self, '_is_trip_active', False),
                    "trip_start_odo": getattr(self, '_trip_start_odo', 0.0),
                    "trip_start_time": getattr(self, '_trip_start_time', time.time()),
                    "trip_start_soc": getattr(self, '_trip_start_soc', 100.0),
                    "trip_start_address": getattr(self, '_trip_start_address', "Không xác định"),
                    "route_coords": getattr(self, '_route_coords', []),
                    "last_gps_time": getattr(self, '_last_gps_time', time.time()), 
                    "trip_accumulated_distance_m": getattr(self, '_trip_accumulated_distance_m', 0.0), 
                    "eff_soc": getattr(self, '_eff_soc', 100.0),
                    "eff_odo": getattr(self, '_eff_odo', 0.0),
                    "eff_speeds": getattr(self, '_eff_speeds', []),
                    "eff_stats": getattr(self, '_eff_stats', {}),
                    "is_charging": getattr(self, '_is_charging', False),
                    "last_is_charging": getattr(self, '_last_is_charging', False),
                    "last_actual_move_time": getattr(self, '_last_actual_move_time', time.time()),
                    "current_charge_max_power": getattr(self, '_current_charge_max_power', 0.0)
                },
                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "unix_time": time.time()
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False)
        except Exception: pass

    def _save_changelog_to_json(self):
        if not self.vin: return
        if not os.path.exists(WWW_DIR): os.makedirs(WWW_DIR, exist_ok=True)
        changelog_file = os.path.join(WWW_DIR, f"vinfast_changelog_{self.vin.lower()}.json")
        try:
            with self._log_lock:
                data_to_write = list(self._raw_changelog_data)
            with open(changelog_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_write, f, ensure_ascii=False, indent=2)
        except Exception: pass
        
    def _save_charge_history_file(self, detailed_history):
        if not self.vin: return
        if not os.path.exists(WWW_DIR): os.makedirs(WWW_DIR, exist_ok=True)
        charge_file = os.path.join(WWW_DIR, f"vinfast_charge_history_{self.vin.lower()}.json")
        try:
            with open(charge_file, 'w', encoding='utf-8') as f:
                json.dump(detailed_history, f, ensure_ascii=False, indent=2)
        except Exception: pass

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        headers = {"Authorization": f"Bearer {self.access_token}", "x-service-name": "CAPP", "x-app-version": "2.17.5", "x-device-platform": "android"}
        res = self._safe_request("GET", url, headers=headers, timeout=15, max_retries=5, delay=5)
        if not res or res.status_code == 401: return []
            
        try:
            vehicles = res.json().get("data", [])
            if vehicles:
                v = vehicles[0]
                self.user_id = str(v.get("userId", ""))
                if not self.vin: self.vin = v.get("vinCode", "")
                
                self._load_state()

                api_custom_name = v.get("customizedVehicleName")
                if api_custom_name and str(api_custom_name).lower() not in ["none", "", "null"]:
                    self._last_data["api_vehicle_name"] = str(api_custom_name)
                else:
                    self._last_data["api_vehicle_name"] = self.vehicle_name

                self.vehicle_model_display = v.get("marketingName") or v.get("dmsVehicleModel") or "VF"
                self._last_data["api_vehicle_image"] = v.get("vehicleImage") or v.get("avatarUrl") or ""
                self._last_data["api_vehicle_model"] = self.vehicle_model_display
                
                model_str = self.vehicle_model_display.upper()
                if "VF 3" in model_str or "VF3" in model_str: self._model_group = "VF3"
                elif any(m in model_str for m in ["VF 5", "VF 6", "VF 7", "VFE34", "VF5", "VF6", "VF7"]): self._model_group = "VF567"
                elif any(m in model_str for m in ["VF 8", "VF 9", "VF8", "VF9"]): self._model_group = "VF89"
                else: self._model_group = "UNKNOWN"
                
                self._update_dynamic_costs() 
                self._calculate_advanced_stats()

                lat_start = self._last_data.get("api_last_lat")
                lon_start = self._last_data.get("api_last_lon")
                if lat_start and lon_start:
                    threading.Thread(target=self._update_location_async, args=(lat_start, lon_start), daemon=True).start()

                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
            return vehicles
        except Exception: return []

    def send_remote_command(self, command_type, params=None):
        payload = {"commandType": command_type, "vinCode": self.vin, "params": params or {}}
        res = self._post_api("ccaraccessmgmt/api/v2/remote/app/command", payload)
        if res and res.status_code == 200:
            threading.Thread(target=self.register_resources, daemon=True).start()
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
            
            soc = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 0)))
            current_range = safe_float(self._last_data.get("34183_00001_00011", self._last_data.get("34180_00001_00007", 0)))
            
            if cap > 0:
                self._last_data["api_static_capacity"] = cap
                self._last_data["api_static_range"] = ran
                
                if ran > 0 and soc > 0 and current_range > 0:
                    theoretical_range_at_current_soc = (ran / 100.0) * soc
                    soh_calc = (current_range / theoretical_range_at_current_soc) * 100.0
                    soh_calc = min(soh_calc, 100.0) 
                    self._last_data["api_soh_calculated"] = round(soh_calc, 1)
                    self._last_data["api_est_range_degradation"] = max(round(100.0 - soh_calc, 2), 0.0)
                else:
                    soh_raw = safe_float(self._last_data.get("34220_00001_00001", 100))
                    self._last_data["api_soh_calculated"] = round(soh_raw, 1)
                    self._last_data["api_est_range_degradation"] = max(round(100.0 - soh_raw, 2), 0.0)
                
                total_kwh = safe_float(self._last_data.get("api_total_energy_charged", 0))
                self._last_data["api_total_charge_cost_est"] = round(total_kwh * self.cost_per_kwh, 0)
                
                odo = safe_float(self._last_data.get("34183_00001_00003", 0))
                if odo == 0: odo = safe_float(self._last_data.get("34199_00000_00000", 0))
                eff = 0
                if total_kwh > 0 and odo > 0:
                    eff = (total_kwh / odo) * 100
                    self._last_data["api_lifetime_efficiency"] = round(eff, 2)

                if eff > 0:
                    calc_max_range = cap / (eff / 100)
                    self._last_data["api_calc_max_range"] = round(calc_max_range, 1)
                    self._last_data["api_calc_range_per_percent"] = round(calc_max_range / 100, 2)
                    if soc > 0:
                        self._last_data["api_calc_remain_range"] = round(calc_max_range * (soc / 100), 1)
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
            except Exception: return None
        return None

    def _register_device_trust(self):
        try:
            method, api_path = "PUT", "ccarusermgnt/api/v1/device-trust/fcm-token"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), "X-TIMESTAMP": str(ts)})
            self._safe_request("PUT", f"{API_BASE}/{api_path}", headers=headers, json={"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"}, timeout=10, max_retries=2, delay=2)
        except Exception: pass

    def _get_active_sensors_list(self):
        active_dict = {}
        if self._model_group == "VF3": active_dict = VF3_SENSORS.copy()
        elif self._model_group == "VF567": active_dict = VF567_SENSORS.copy()
        elif self._model_group == "VF89": active_dict = VF89_SENSORS.copy()
        else: active_dict = VF3_SENSORS.copy()
        
        request_objects = [{"objectId": str(int(k.split("_")[0])), "instanceId": str(int(k.split("_")[1])), "resourceId": str(int(k.split("_")[2]))} for k in active_dict.keys() if "_" in k and not k.startswith("api_")]
        name_req = {"objectId": "34180", "instanceId": "00001", "resourceId": "00010"}
        if name_req not in request_objects: request_objects.append(name_req)
        return request_objects

    def register_resources(self):
        try:
            self._post_api("ccarusermgnt/api/v1/user-vehicle/set-primary-vehicle", {"vinCode": self.vin})
            self._post_api("ccaraccessmgmt/api/v1/remote/app/wakeup", {})
            reqs = self._get_active_sensors_list()
            self._post_api("ccaraccessmgmt/api/v1/telemetry/app/ping", reqs)
            res = self._post_api(f"ccaraccessmgmt/api/v1/telemetry/{self.vin}/list_resource", reqs)
            if res and res.status_code == 404:
                self._post_api("ccaraccessmgmt/api/v1/telemetry/list_resource", reqs)
        except Exception: pass

    def get_address_from_osm(self, lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            headers = {"User-Agent": f"HA-VinFast-Connect-{uuid.uuid4().hex[:6]}"}
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200: return res.json().get("display_name", f"{lat}, {lon}")
        except Exception: pass
        return f"{lat}, {lon}"

    def _fetch_weather_and_hvac(self, lat, lon):
        try:
            now = time.time()
            if now - self._last_weather_fetch_time < 900: return
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            res = requests.get(url, timeout=10)
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
                        self._save_state()
                        if self.callbacks:
                            for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _run_ai_advisor_async(self):
        try:
            if not getattr(self, 'gemini_api_key', None) or self.gemini_api_key.strip() == "":
                self._last_data["api_ai_advisor"] = "Vui lòng nhập Google Gemini API Key trong phần Cấu hình Integration (Config Flow) để AI có thể đánh giá."
                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
                return
            dist = self._last_data.get("api_trip_distance", 0)
            if dist < 1.0: return 
            eff = self._last_data.get("api_trip_efficiency", 0)
            spd = self._last_data.get("api_trip_avg_speed", 0)
            temp = self._last_data.get("api_outside_temp", "Không rõ")
            cond = self._last_data.get("api_weather_condition", "Không rõ")
            soc_end = safe_float(self._last_data.get("34183_00001_00009", 50))
            
            prompt = (
                f"Đóng vai một kỹ sư phân tích xe điện chuyên nghiệp. Xe vừa hoàn thành chuyến đi {dist}km. "
                f"Tốc độ trung bình {spd}km/h. Hiệu suất tiêu thụ: {eff} kWh/100km. "
                f"Thời tiết hiện tại: {temp} độ C, {cond}. Pin còn lại: {soc_end}%. "
                "Hãy viết 1 đoạn văn tiếng Việt ngắn gọn (dưới 100 từ), đánh giá xem hiệu suất này là tốt hay kém do nguyên nhân nào (nhấn mạnh ảnh hưởng của tốc độ và thời tiết), "
                "và đưa ra 1 lời khuyên ngắn để sạc pin hoặc lái xe tốt hơn ở chuyến sau. Trả lời trực tiếp."
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
            if res.status_code == 200:
                ai_text = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if ai_text:
                    self._last_data["api_ai_advisor"] = ai_text.replace("*", "").strip()
                    self._save_state()
                    if self.callbacks:
                        for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def fetch_charging_history(self):
        try:
            if not self.vin or not self.access_token: return
            api_path = "ccarcharging/api/v1/charging-sessions/search"
            all_sessions = []
            page, size = 0, 50 
            is_success = False 
            consecutive_errors = 0 
            total_records_from_api = 0 
            while self._running:
                ts = int(time.time() * 1000)
                headers = self._get_base_headers()
                headers.update({"X-HASH": self._generate_x_hash("POST", api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, "POST", ts), "X-TIMESTAMP": str(ts)})
                payload = {"orderStatus": [3, 5, 7], "startTime": 1609459200000, "endTime": int(time.time() * 1000)}
                try: 
                    res = requests.post(f"{API_BASE}/{api_path}?page={page}&size={size}", headers=headers, json=payload, timeout=15)
                    if res.status_code == 401:
                        self.login()
                        consecutive_errors += 1
                    elif res.status_code != 200:
                        consecutive_errors += 1
                    else:
                        data = res.json()
                        meta_records = data.get("metadata", {}).get("totalRecords")
                        if meta_records is not None: total_records_from_api = int(meta_records)
                        sessions = []
                        if isinstance(data.get("data"), list): sessions = data["data"]
                        elif isinstance(data.get("data"), dict) and "content" in data["data"]: sessions = data["data"]["content"]
                        if not sessions: 
                            is_success = True
                            break
                        all_sessions.extend(sessions)
                        consecutive_errors = 0 
                        if len(sessions) < size: 
                            is_success = True
                            break
                        page += 1
                        time.sleep(0.5) 
                except Exception: consecutive_errors += 1
                if consecutive_errors >= 5:
                    break
                if consecutive_errors > 0: time.sleep(5) 
            
            if is_success:
                unique_sessions = {s.get("id") or f"noid_{s.get('pluggedTime')}": s for s in all_sessions}
                valid_sessions = [s for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0]
                sorted_sessions = sorted(valid_sessions, key=lambda x: safe_float(x.get("pluggedTime", 0)), reverse=True)
                
                detailed_history = []
                for s in sorted_sessions[:10]:
                    addr = s.get("chargingStationAddress", "Trạm sạc VinFast")
                    kwh = safe_float(s.get("totalKWCharged", 0))
                    p_time = safe_float(s.get("pluggedTime", 0))
                    u_time = safe_float(s.get("unpluggedTime", 0))
                    dur = round((u_time - p_time) / 60000) if u_time > p_time else 0
                    date_str = datetime.datetime.fromtimestamp(p_time/1000).strftime('%d/%m/%Y %H:%M') if p_time > 0 else ""
                    detailed_history.append({"date": date_str, "address": addr, "kwh": kwh, "duration": dur})
                self._last_data["api_charge_history_list"] = json.dumps(detailed_history)
                self._save_charge_history_file(detailed_history)

                if total_records_from_api > 0: api_public_sessions = total_records_from_api
                else: api_public_sessions = len(valid_sessions)
                
                public_energy = sum(safe_float(s.get("totalKWCharged", 0)) for s in valid_sessions)
                home_kwh = safe_float(self._last_data.get("api_home_charge_kwh", 0.0))
                home_sessions = int(self._last_data.get("api_home_charge_sessions", 0))
                
                self._last_data["api_total_charge_sessions"] = api_public_sessions + home_sessions
                self._last_data["api_total_energy_charged"] = round(public_energy + home_kwh, 2)
                
                if sorted_sessions:
                    last_session = sorted_sessions[0]
                    if safe_float(last_session.get("startBatteryLevel", 0)) > 0: self._last_data["api_last_charge_start_soc"] = safe_float(last_session.get("startBatteryLevel", 0))
                    if safe_float(last_session.get("endBatteryLevel", 0)) > 0: self._last_data["api_last_charge_end_soc"] = safe_float(last_session.get("endBatteryLevel", 0))
                    energy_grid = safe_float(last_session.get("totalKWCharged", 0))
                    self._last_data["api_last_charge_energy"] = round(energy_grid, 2)
                    p_time = safe_float(last_session.get("pluggedTime", 0))
                    u_time = safe_float(last_session.get("unpluggedTime", 0))
                    duration_min = (u_time - p_time) / 60000 if u_time > p_time else 0
                    if duration_min > 0:
                        self._last_data["api_last_charge_duration"] = round(duration_min, 0)
                        self._last_data["api_last_charge_power"] = round((energy_grid / (duration_min / 60)), 1)
                
                if api_public_sessions == 0: threading.Thread(target=self._retry_fetch_charging_history, daemon=True).start()
                else:
                    self._calculate_advanced_stats()
                    self._save_state()
                    if self.callbacks:
                        for cb in self.callbacks: cb(self._last_data)
        except Exception: pass

    def _retry_fetch_charging_history(self):
        time.sleep(300) 
        self.fetch_charging_history()

    def _delayed_fetch_charging_history(self):
        time.sleep(120) 
        self.fetch_charging_history()

    def fetch_nearby_stations(self):
        try:
            if not self._last_lat_lon: return
            lat_str, lon_str = self._last_lat_lon.split(',')
            current_lat, current_lon = float(lat_str), float(lon_str)
            method, api_path = "POST", "ccarcharging/api/v1/stations/search"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({"X-HASH": self._generate_x_hash(method, api_path, self.vin, ts), "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts), "X-TIMESTAMP": str(ts)})
            payload = {"latitude": current_lat, "longitude": current_lon, "radius": 50000, "excludeFavorite": False, "stationType": [], "status": [], "brandIds": []}
            try: res = requests.post(f"{API_BASE}/{api_path}?page=0&size=50", headers=headers, json=payload, timeout=15)
            except Exception: return
            if res and res.status_code == 200:
                data = res.json().get("data", [])
                if isinstance(data, dict) and "content" in data: data = data.get("content", [])
                stations = []
                for st in data:
                    st_lat = safe_float(st.get("latitude"))
                    st_lng = safe_float(st.get("longitude"))
                    if not st_lat or not st_lng: continue
                    if st_lat > 80.0 and st_lng < 30.0: st_lat, st_lng = st_lng, st_lat
                    if not (8.0 <= st_lat <= 23.5 and 102.0 <= st_lng <= 109.5): continue 
                    dist = 0.0
                    R = 6371.0 
                    dlat = math.radians(st_lat - current_lat)
                    dlon = math.radians(st_lng - current_lon)
                    a = math.sin(dlat/2)**2 + math.cos(math.radians(current_lat)) * math.cos(math.radians(st_lat)) * math.sin(dlon/2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    dist = round(R * c, 1)
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

    def _get_aws_mqtt_url(self):
        try:
            url_id = f"https://cognito-identity.{AWS_REGION}.amazonaws.com/"
            res_id = self._safe_request("POST", url_id, headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15, max_retries=3, delay=5)
            if not res_id or res_id.status_code != 200: return None
            identity_id = res_id.json()["IdentityId"]
            res_cred = self._safe_request("POST", url_id, headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": identity_id, "Logins": {AUTH0_DOMAIN: self.access_token}}, timeout=15, max_retries=3, delay=5)
            if not res_cred or res_cred.status_code != 200: return None
            creds = res_cred.json()["Credentials"]
            self._safe_request("POST", f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": identity_id}, timeout=15, max_retries=2, delay=2)
            def sign(k, m): return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()
            amz_date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
            cred_scope = f"{date_stamp}/{AWS_REGION}/iotdevicegateway/aws4_request"
            qs = f"X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={urllib.parse.quote(creds['AccessKeyId'] + '/' + cred_scope, safe='')}&X-Amz-Date={amz_date}&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
            req = f"GET\n/mqtt\n{qs}\nhost:{IOT_ENDPOINT}\n\nhost\n" + hashlib.sha256("".encode('utf-8')).hexdigest()
            sts = f"AWS4-HMAC-SHA256\n{amz_date}\n{cred_scope}\n" + hashlib.sha256(req.encode('utf-8')).hexdigest()
            sig = hmac.new(sign(sign(sign(sign(('AWS4' + creds['SecretKey']).encode('utf-8'), date_stamp), AWS_REGION), 'iotdevicegateway'), 'aws4_request'), sts.encode('utf-8'), hashlib.sha256).hexdigest()
            return f"wss://{IOT_ENDPOINT}/mqtt?{qs}&X-Amz-Signature={sig}&X-Amz-Security-Token={urllib.parse.quote(creds['SessionToken'], safe='')}"
        except Exception: return None

    def _renew_aws_connection(self):
        try:
            if not self.client:
                client_id = f"Android_{self.vin}_{self._mqtt_client_id_rand}"
                self.client = mqtt.Client(client_id=client_id, transport="websockets", protocol=mqtt.MQTTv311)
                self.client.username_pw_set("?SDK=Android&Version=2.81.0")
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.on_message = self._on_message
                self.client.tls_set()
            self.login()
            self._register_device_trust()
            new_url = self._get_aws_mqtt_url()
            if new_url:
                self.client.loop_stop()
                self.client.disconnect()
                self.client.ws_set_options(path=new_url.split(IOT_ENDPOINT)[1])
                self.client.connect(IOT_ENDPOINT, 443, 60)
                self.client.loop_start()
        except Exception: pass

    # =========================================================================
    # VÒNG LẶP POLLING ĐỌC FILE BRIDGE TỪ TỪ CONSOLE
    # =========================================================================
    def _api_polling_loop(self):
        time.sleep(5) 
        if not self.user_id: self.get_vehicles()
        self._renew_aws_connection()
        
        start_time = time.time()
        last_heartbeat = start_time
        last_state_save = start_time
        last_aws_renew = start_time
        last_app_open_sim = start_time
        
        while self._running:
            try:
                time.sleep(1)
                now = time.time()
                
                # --- ĐỌC CẦU NỐI (FILE BRIDGE) TỪ TERMINAL CHUYỂN VÀO UI ---
                try:
                    mock_file = os.path.join(WWW_DIR, "mock_console_cmd.txt")
                    if os.path.exists(mock_file):
                        with open(mock_file, "r", encoding="utf-8") as f:
                            cmd = f.read().strip()
                        os.remove(mock_file)
                        if cmd: self._process_console_command(cmd)
                except Exception: pass
                # ------------------------------------------------------------

                if now - last_heartbeat >= 60:
                    last_heartbeat = now
                    state = "2" if getattr(self, '_is_moving', False) else "1"
                    self._send_heartbeat(state)

                if now - last_aws_renew >= 3000:
                    last_aws_renew = now
                    self._renew_aws_connection()

                if now - last_app_open_sim >= 300:
                    last_app_open_sim = now
                    if not getattr(self, '_is_moving', False):
                        self.register_resources()
                    else:
                        if now - getattr(self, '_last_mqtt_msg_time', now) > 300:
                            self.register_resources()

                time_since_move = now - getattr(self, '_last_actual_move_time', now)
                current_status = self._last_data.get("api_vehicle_status", "")
                
                if current_status == "Đang dừng" and time_since_move >= 300:
                    self._last_data["api_vehicle_status"] = "Đang đỗ"
                    if self.callbacks:
                        for cb in self.callbacks: cb(self._last_data)

                if getattr(self, '_is_trip_active', False) and time_since_move >= 300:
                    self._is_moving = False 
                    trip_dist = float(self._last_data.get("api_trip_distance", 0))
                    
                    if trip_dist >= 0.05: 
                        self._is_trip_active = False
                        self._save_trip_to_history()
                        threading.Thread(target=self._run_ai_advisor_async, daemon=True).start()
                    else:
                        self._is_trip_active = False 
                        
                    self._trip_start_odo = 0.0
                    self._trip_start_time = time.time()
                    self._route_coords = []
                    self._last_gps_time = time.time()
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

    def _send_heartbeat(self, state="1"):
        if not self.client or not self.client.is_connected() or not self.vin: return
        topic = f"/vehicles/{self.vin}/push/connected/heartbeat"
        payload = {"version": "1.2", "timestamp": int(time.time() * 1000), "trans_id": str(uuid.uuid4()), "content": {"34183": { "1": { "54": str(state) } }}}
        try: self.client.publish(topic, json.dumps(payload), qos=1)
        except Exception: pass

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0: 
            client.subscribe(f"/mobile/{self.vin}/push", qos=1)
            client.subscribe(f"monitoring/server/{self.vin}/push", qos=1)
            client.subscribe(f"/server/{self.vin}/remctrl", qos=1)
            self._last_mqtt_msg_time = time.time()

    def _on_disconnect(self, client, userdata, rc): pass

    def _filter_critical_data(self, key, current_val, fallback_val):
        if current_val is None: return fallback_val
        if key in ["34183_00001_00009", "34180_00001_00011", "34183_00001_00003", "34199_00000_00000", "34183_00001_00004", "34180_00001_00007", "34193_00001_00012", "34193_00001_00014", "34193_00001_00019"]:
            try:
                num_val = float(current_val)
                if num_val <= 0.0 and fallback_val is not None and float(fallback_val) > 0:
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
                    if v_num > 0:
                        self._last_data["api_target_charge_limit"] = v_num
                        self._last_data["34193_00001_00014"] = v_num
                except: pass

            self._last_data.update(data_dict)
            if "34180_00001_00010" in data_dict and data_dict["34180_00001_00010"]:
                self._last_data["api_vehicle_name"] = str(data_dict["34180_00001_00010"])
                
        except Exception as e: return

        current_soc = safe_float(self._last_data.get("34183_00001_00009", self._last_data.get("34180_00001_00011", 0)))
        odo = safe_float(self._last_data.get("34183_00001_00003", self._last_data.get("34199_00000_00000", 0)))
        
        try:
            if self._model_group == "VF89":
                gear = str(self._last_data.get("34187_00000_00000", "1"))
                speed = safe_float(self._last_data.get("34188_00000_00000", 0))
            else: 
                gear = str(self._last_data.get("34183_00001_00001", "1"))
                speed = safe_float(self._last_data.get("34183_00001_00002", 0))

            is_mechanically_moving = (speed > 0) or (gear in ["2", "4", "D", "R"])
            is_gps_moving = False

            if is_mechanically_moving and not getattr(self, '_is_trip_active', False) and odo > 0:
                self._trip_start_odo = odo
                self._trip_start_time = current_time
                self._trip_start_soc = current_soc
                self._trip_start_address = self._last_data.get("api_current_address", "Không xác định")
                self._is_trip_active = True
                self._last_data["api_trip_distance"] = 0.0
                self._last_data["api_trip_gas_cost"] = 0
                self._last_data["api_trip_charge_cost"] = 0
                self._last_data["api_trip_avg_speed"] = 0.0
                self._last_data["api_trip_energy_used"] = 0.0
                self._last_data["api_trip_efficiency"] = 0.0
                self._trip_accumulated_distance_m = 0.0 
                self._route_coords = [] 
                self._save_state()
        except Exception: pass

        try:
            lat = data_dict.get("00006_00001_00000", self._last_data.get("00006_00001_00000"))
            lon = data_dict.get("00006_00001_00001", self._last_data.get("00006_00001_00001"))
            
            if lat and lon and str(lat).upper() != "NONE" and str(lon).upper() != "NONE":
                lat_f, lon_f = float(lat), float(lon)
                curr_coord = f"{lat_f},{lon_f}"
                
                self._last_data["api_last_lat"] = lat_f
                self._last_data["api_last_lon"] = lon_f

                if curr_coord != getattr(self, '_last_lat_lon', ""): 
                    self._last_lat_lon = curr_coord
                    threading.Thread(target=self._update_location_async, args=(lat_f, lon_f), daemon=True).start()
                    
                    if getattr(self, '_is_trip_active', False):
                        actual_speed_kmh = float(speed)
                        if not self._route_coords:
                            self._route_coords.append([lat_f, lon_f, int(actual_speed_kmh)])
                            self._last_gps_time = current_time
                        else:
                            last_lat = self._route_coords[-1][0]
                            last_lon = self._route_coords[-1][1]
                            last_time = getattr(self, '_last_gps_time', current_time - 1)
                            dt = current_time - last_time
                            if dt <= 0: dt = 1 
                            
                            R = 6371000 
                            phi1, phi2 = math.radians(last_lat), math.radians(lat_f)
                            dphi = math.radians(lat_f - last_lat)
                            dlambda = math.radians(lon_f - last_lon)
                            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
                            distance_m = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                            calc_speed_kmh = (distance_m / dt) * 3.6 
                            
                            final_lat, final_lon = lat_f, lon_f
                            valid_distance = distance_m
                            is_valid_point = True

                            if actual_speed_kmh == 0 and distance_m > 10:
                                final_lat, final_lon = last_lat, last_lon
                                is_valid_point = False 
                            elif actual_speed_kmh > 0:
                                if calc_speed_kmh > (actual_speed_kmh + 40):
                                    y = math.sin(math.radians(lon_f - last_lon)) * math.cos(math.radians(lat_f))
                                    x = math.cos(math.radians(last_lat)) * math.sin(math.radians(lat_f)) - math.sin(math.radians(last_lat)) * math.cos(math.radians(lat_f)) * math.cos(math.radians(lon_f - last_lon))
                                    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
                                    expected_distance_m = (actual_speed_kmh / 3.6) * dt
                                    brng = math.radians(bearing)
                                    lat1 = math.radians(last_lat)
                                    lon1 = math.radians(last_lon)
                                    asin_arg = math.sin(lat1) * math.cos(expected_distance_m / R) + math.cos(lat1) * math.sin(expected_distance_m / R) * math.cos(brng)
                                    asin_arg = max(min(asin_arg, 1.0), -1.0)
                                    lat2 = math.asin(asin_arg)
                                    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(expected_distance_m / R) * math.cos(lat1), math.cos(expected_distance_m / R) - math.sin(lat1) * math.sin(lat2))
                                    final_lat, final_lon = math.degrees(lat2), math.degrees(lon2)
                                    valid_distance = expected_distance_m

                            if is_valid_point and (distance_m >= 1.0 or final_lat != lat_f):
                                if distance_m > 15.0: is_gps_moving = True
                                self._trip_accumulated_distance_m += valid_distance
                                self._route_coords.append([round(final_lat, 6), round(final_lon, 6), int(actual_speed_kmh)])
                                if len(self._route_coords) > 800: self._route_coords.pop(0) 
                                self._last_data["api_trip_route"] = json.dumps(self._route_coords)
                                self._last_gps_time = current_time 
                                
            if getattr(self, '_is_trip_active', False):
                gps_dist_km = self._trip_accumulated_distance_m / 1000.0
                odo_dist_km = 0.0
                if self._trip_start_odo > 0 and odo >= self._trip_start_odo:
                    odo_dist_km = odo - self._trip_start_odo

                final_trip_dist = gps_dist_km if gps_dist_km >= odo_dist_km else odo_dist_km
                self._last_data["api_trip_distance"] = round(final_trip_dist, 2)

                if final_trip_dist > 0:
                    if self.gas_km_per_liter > 0:
                        self._last_data["api_trip_gas_cost"] = round((final_trip_dist / self.gas_km_per_liter) * self.gas_price, 0)
                    self._last_data["api_trip_charge_cost"] = round(final_trip_dist * self.ev_kwh_per_km * self.cost_per_kwh, 0)

                    if getattr(self, '_trip_start_time', 0) > 0:
                        trip_hrs = (current_time - self._trip_start_time) / 3600.0
                        if trip_hrs > 0:
                            self._last_data["api_trip_avg_speed"] = round(final_trip_dist / trip_hrs, 1)

                    if getattr(self, '_trip_start_soc', 0) > 0 and self._trip_start_soc >= current_soc:
                        cap = safe_float(self._last_data.get("api_static_capacity", 0))
                        if cap > 0:
                            energy_used = ((self._trip_start_soc - current_soc) / 100.0) * cap
                            self._last_data["api_trip_energy_used"] = round(energy_used, 2)
                            self._last_data["api_trip_efficiency"] = round((energy_used / final_trip_dist) * 100, 2)

        except Exception as e: pass

        try:
            if self._model_group == "VF89":
                c_status = str(self._last_data.get("34183_00000_00001", "0"))
            else: 
                c_status = str(self._last_data.get("34193_00001_00005", "0"))

            is_moving_now = is_mechanically_moving or is_gps_moving
            if is_moving_now:
                self._last_actual_move_time = current_time
                self._is_moving = True
            else:
                self._is_moving = False

            is_charging = (c_status == "1")
            is_fully_charged = False 

            if c_status in ["0", "2", "3", "4"] or self._is_moving:
                is_charging = False
                is_fully_charged = False

            if is_charging and getattr(self, '_last_is_charging', False):
                time_charging = current_time - getattr(self, '_charge_start_time', current_time)
                if time_charging > 180 and getattr(self, '_current_charge_max_power', 0.0) == 0.0:
                    is_charging = False
                    is_fully_charged = False

            t_limit = safe_float(self._last_data.get("api_target_charge_limit", 100))
            if t_limit > 0 and current_soc >= t_limit and (is_charging or c_status in ["2", "3"]):
                is_fully_charged = True
                is_charging = False

            self._is_charging = is_charging
            time_since_move = current_time - self._last_actual_move_time

            if is_charging: final_status = "Đang sạc"
            elif is_fully_charged: final_status = "Đã sạc xong"
            elif self._is_moving: final_status = "Đang di chuyển"
            elif time_since_move < 300: final_status = "Đang dừng"
            else: final_status = "Đang đỗ"

            self._last_data["api_vehicle_status"] = final_status

        except Exception as e: pass

        try:
            if self._is_charging and not getattr(self, '_last_is_charging', False):
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
                    try:
                        stations = json.loads(self._last_data.get("api_nearby_stations", "[]"))
                        is_home_charge = True
                        if stations and len(stations) > 0:
                            if float(stations[0].get("dist", 999)) < 0.5:
                                is_home_charge = False 
                    except:
                        is_home_charge = True
                    if is_home_charge or getattr(self, '_current_charge_max_power', 0.0) < 15.0:
                        curr_home_sessions = int(self._last_data.get("api_home_charge_sessions", 0))
                        curr_home_kwh = float(self._last_data.get("api_home_charge_kwh", 0.0))
                        self._last_data["api_home_charge_sessions"] = curr_home_sessions + 1
                        self._last_data["api_home_charge_kwh"] = round(curr_home_kwh + added_kwh, 2)
                
                threading.Thread(target=self.fetch_charging_history, daemon=True).start()
                threading.Thread(target=self._delayed_fetch_charging_history, daemon=True).start()
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