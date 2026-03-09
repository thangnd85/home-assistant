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
import paho.mqtt.client as mqtt

from .const import (
    AUTH0_DOMAIN, AUTH0_CLIENT_ID, API_BASE, 
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID, 
    BASE_SENSORS, VF3_SENSORS
)

try:
    from .const import VF567_SENSORS
except ImportError:
    VF567_SENSORS = {}

try:
    from .const import VF89_SENSORS
except ImportError:
    VF89_SENSORS = {}

try:
    from .const import VEHICLE_SPECS
except ImportError:
    VEHICLE_SPECS = {
        "VF3": {"capacity": 18.64, "range": 210, "ev_kwh_per_km": 0.09, "gas_km_per_liter": 20.0},
        "VF5": {"capacity": 37.23, "range": 326, "ev_kwh_per_km": 0.115, "gas_km_per_liter": 18.0},
        "VF6": {"capacity": 59.6, "range": 399, "ev_kwh_per_km": 0.149, "gas_km_per_liter": 15.0},
        "VF7": {"capacity": 75.3, "range": 431, "ev_kwh_per_km": 0.174, "gas_km_per_liter": 14.0},
        "VF8": {"capacity": 87.7, "range": 471, "ev_kwh_per_km": 0.186, "gas_km_per_liter": 12.0},
        "VF9": {"capacity": 123.0, "range": 594, "ev_kwh_per_km": 0.207, "gas_km_per_liter": 10.0}
    }

_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HA_CONFIG_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
WWW_DIR = os.path.join(HA_CONFIG_DIR, "www")

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
            "api_current_address": "Đang tải dữ liệu...",
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
            "api_vehicle_name": "Xe VinFast"
        }  
        
        self.cost_per_kwh = safe_float(self.options.get("cost_per_kwh", 4000), 4000)
        self.gas_price = safe_float(self.options.get("gas_price", 20000), 20000)
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", 0.15), 0.15)
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", 15.0), 15.0)

        self._is_moving = False
        self._is_charging = False
        self._last_is_charging = False 
        self._last_gear = "1"
        self._last_lat_lon = None
        
        self._last_activity_time = time.time()
        self._force_full_scan = False
        
        self._is_trip_active = False
        self._last_move_time = time.time()
        self._trip_start_odo = None
        self._trip_start_time = None
        self._trip_start_soc = None
        self._trip_start_address = "Không xác định"
        self._route_coords = []
        self._last_gps_time = None 
        self._trip_accumulated_distance_m = 0.0
        
        self._eff_soc = None
        self._eff_odo = None
        self._eff_speeds = []
        self._eff_stats = {}
        
        self._charge_start_time = None
        self._charge_start_soc = None
        self._charge_calc_soc = None
        self._charge_calc_time = None

        self._last_geocoded_grid = None
        self._geocode_lock = threading.Lock()
        self._last_geocode_time = 0
        
        self._raw_changelog_data = [] 
        self._log_lock = threading.Lock()

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
                if method.upper() == "POST":
                    return requests.post(url, **kwargs)
                elif method.upper() == "PUT":
                    return requests.put(url, **kwargs)
                else:
                    return requests.get(url, **kwargs)
            except requests.exceptions.RequestException as e:
                _LOGGER.warning(f"VinFast Network: Đợi mạng khả dụng (Thử lại {attempt+1}/{max_retries} sau {delay}s): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
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
        self.ev_kwh_per_km = safe_float(self.options.get("ev_kwh_per_km", target_spec.get("ev_kwh_per_km", 0.15)), target_spec.get("ev_kwh_per_km", 0.15))
        self.gas_km_per_liter = safe_float(self.options.get("gas_km_per_liter", target_spec.get("gas_km_per_liter", 15.0)), target_spec.get("gas_km_per_liter", 15.0))

    def _load_state(self):
        if not self.vin: return
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        changelog_file = os.path.join(WWW_DIR, f"vinfast_changelog_{self.vin.lower()}.json")
        
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    if "last_data" in saved_data:
                        self._last_data.update(saved_data["last_data"])
                    if "internal_memory" in saved_data:
                        mem = saved_data["internal_memory"]
                        self._is_trip_active = mem.get("is_trip_active", False)
                        self._trip_start_odo = mem.get("trip_start_odo", None)
                        self._trip_start_time = mem.get("trip_start_time", None)
                        self._trip_start_soc = mem.get("trip_start_soc", None)
                        self._trip_start_address = mem.get("trip_start_address", "Không xác định")
                        self._route_coords = mem.get("route_coords", [])
                        self._last_gps_time = mem.get("last_gps_time", None)
                        self._trip_accumulated_distance_m = mem.get("trip_accumulated_distance_m", 0.0)
                        self._is_charging = mem.get("is_charging", False)
                        self._last_is_charging = mem.get("last_is_charging", False)
                        self._is_moving = mem.get("is_moving", False)
                        self._last_move_time = mem.get("last_move_time", time.time())
                        self._last_activity_time = mem.get("last_activity_time", time.time())
                        self._last_geocoded_grid = mem.get("last_geocoded_grid", None)
            except Exception as e: 
                _LOGGER.error(f"VinFast: Lỗi đọc JSON State: {e}")
            
        if os.path.exists(changelog_file):
            try:
                with open(changelog_file, 'r', encoding='utf-8') as f:
                    self._raw_changelog_data = json.load(f)
            except: pass

    def _save_state(self):
        if not self.vin: return
        if not os.path.exists(WWW_DIR):
            os.makedirs(WWW_DIR, exist_ok=True)
        state_file = os.path.join(WWW_DIR, f"vinfast_state_{self.vin.lower()}.json")
        try:
            data_to_save = {
                "last_data": self._last_data.copy(),
                "internal_memory": {
                    "is_trip_active": getattr(self, '_is_trip_active', False),
                    "trip_start_odo": getattr(self, '_trip_start_odo', None),
                    "trip_start_time": getattr(self, '_trip_start_time', None),
                    "trip_start_soc": getattr(self, '_trip_start_soc', None),
                    "trip_start_address": getattr(self, '_trip_start_address', "Không xác định"),
                    "route_coords": getattr(self, '_route_coords', []),
                    "last_gps_time": getattr(self, '_last_gps_time', None), 
                    "trip_accumulated_distance_m": getattr(self, '_trip_accumulated_distance_m', 0.0), 
                    "is_charging": getattr(self, '_is_charging', False),
                    "last_is_charging": getattr(self, '_last_is_charging', False),
                    "is_moving": getattr(self, '_is_moving', False),
                    "last_move_time": getattr(self, '_last_move_time', time.time()),
                    "last_activity_time": getattr(self, '_last_activity_time', time.time()),
                    "last_geocoded_grid": getattr(self, '_last_geocoded_grid', None)
                },
                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False)
        except Exception: pass

    def _save_changelog_to_json(self):
        if not self.vin: return
        if not os.path.exists(WWW_DIR):
            os.makedirs(WWW_DIR, exist_ok=True)
        changelog_file = os.path.join(WWW_DIR, f"vinfast_changelog_{self.vin.lower()}.json")
        try:
            with self._log_lock:
                data_to_write = list(self._raw_changelog_data)
            with open(changelog_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_write, f, ensure_ascii=False, indent=2)
        except Exception as e: 
            _LOGGER.error(f"VinFast: Lỗi ghi file Changelog JSON: {e}")

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        headers = {"Authorization": f"Bearer {self.access_token}", "x-service-name": "CAPP", "x-app-version": "2.17.5", "x-device-platform": "android"}
        
        res = self._safe_request("GET", url, headers=headers, timeout=15, max_retries=5, delay=5)
        if not res or res.status_code == 401: 
            return []
            
        try:
            vehicles = res.json().get("data", [])
            if vehicles:
                v = vehicles[0]
                self.user_id = str(v.get("userId", ""))
                if not self.vin: self.vin = v.get("vinCode", "")
                
                self._load_state()

                # Tạm thời khôi phục tên cũ để chờ MQTT ghi đè vào
                api_custom_name = v.get("customizedVehicleName")
                if api_custom_name and str(api_custom_name).lower() not in ["none", "", "null"]:
                    if not self._last_data.get("api_vehicle_name") or self._last_data.get("api_vehicle_name") == "Xe VinFast":
                        self._last_data["api_vehicle_name"] = str(api_custom_name)
                else:
                    if not self._last_data.get("api_vehicle_name") or self._last_data.get("api_vehicle_name") == "Xe VinFast":
                        self._last_data["api_vehicle_name"] = self.vehicle_name

                self.vehicle_model_display = v.get("marketingName") or v.get("dmsVehicleModel") or "VF"
                self._last_data["api_vehicle_image"] = v.get("vehicleImage") or v.get("avatarUrl") or ""
                self._last_data["api_vehicle_model"] = self.vehicle_model_display
                
                self._update_dynamic_costs() 
                self._calculate_advanced_stats()

                lat_start = self._last_data.get("api_last_lat")
                lon_start = self._last_data.get("api_last_lon")
                addr_start = self._last_data.get("api_current_address", "")
                if lat_start and lon_start and ("Tọa độ" in addr_start or "Đang" in addr_start):
                    threading.Thread(target=self._update_location_async, args=(lat_start, lon_start), daemon=True).start()

                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
            return vehicles
        except Exception as e:
            _LOGGER.error(f"VinFast: Lỗi phân tích thông tin xe: {e}")
            return []

    def send_remote_command(self, command_type, params=None):
        payload = {"commandType": command_type, "vinCode": self.vin, "params": params or {}}
        res = self._post_api("ccaraccessmgmt/api/v2/remote/app/command", payload)
        if res and res.status_code == 200: return True
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
            raw_range = safe_float(self._last_data.get("34183_00001_00004", 0))

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

                calc_range = 0
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
            self._safe_request("PUT", f"{API_BASE}/{api_path}", headers=headers, json={"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"}, timeout=10, max_retries=2, delay=2)
        except Exception: pass

    # =====================================================================
    # ÉP BUỘC XE TRẢ VỀ TÊN ĐỊNH DANH (34180_00001_00010) MỖI KHI PING
    # =====================================================================
    def _send_app_ping_only(self):
        try:
            active_dict = BASE_SENSORS.copy()
            request_objects = [{"objectId": str(int(k.split("_")[0])), "instanceId": str(int(k.split("_")[1])), "resourceId": str(int(k.split("_")[2]))} for k in active_dict.keys() if "_" in k and not k.startswith("api_")]
            
            # GÀI LỆNH LẤY TÊN XE VÀO GÓI TIN ĐÁNH THỨC
            name_req = {"objectId": "34180", "instanceId": "00001", "resourceId": "00010"}
            if name_req not in request_objects:
                request_objects.append(name_req)

            self._post_api("ccaraccessmgmt/api/v1/telemetry/app/ping", request_objects)
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
            request_objects = [{"objectId": str(int(k.split("_")[0])), "instanceId": str(int(k.split("_")[1])), "resourceId": str(int(k.split("_")[2]))} for k in active_dict.keys() if "_" in k and not k.startswith("api_")]
            
            # GÀI LỆNH LẤY TÊN XE VÀO DANH SÁCH ĐĂNG KÝ
            name_req = {"objectId": "34180", "instanceId": "00001", "resourceId": "00010"}
            if name_req not in request_objects:
                request_objects.append(name_req)

            self._post_api("ccaraccessmgmt/api/v1/telemetry/app/ping", request_objects)
            res = self._post_api(f"ccaraccessmgmt/api/v1/telemetry/{self.vin}/list_resource", request_objects)
            if res and res.status_code == 404:
                self._post_api("ccaraccessmgmt/api/v1/telemetry/list_resource", request_objects)
        except Exception as e:
            _LOGGER.error(f"VinFast: Lỗi register_resources: {e}")

    def get_address_from_osm(self, lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            headers = {"User-Agent": f"HA-VinFast-Connect-{uuid.uuid4().hex[:6]}"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200: 
                data = res.json()
                display_name = data.get("display_name", "")
                if display_name:
                    parts = [p.strip() for p in display_name.split(',')]
                    filtered_parts = [p for p in parts if p.lower() not in ['việt nam', 'vietnam'] and not (p.isdigit() and len(p) >= 5)]
                    return ", ".join(filtered_parts)
        except Exception: pass

        try:
            url2 = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=vi"
            res2 = requests.get(url2, timeout=10)
            if res2.status_code == 200:
                data2 = res2.json()
                locality = data2.get("locality", "")
                city = data2.get("principalSubdivision", data2.get("city", ""))
                if locality and city: return f"{locality}, {city}"
                elif city: return city
                elif locality: return locality
        except Exception: pass
        return None 

    def _update_location_async(self, lat, lon):
        try:
            grid_coord = f"{round(float(lat), 3)},{round(float(lon), 3)}"
            now = time.time()
            curr_addr = self._last_data.get("api_current_address", "")
            
            needs_update = False
            if getattr(self, '_last_geocoded_grid', None) != grid_coord:
                needs_update = True
            elif "Tọa độ" in curr_addr or "Đang" in curr_addr:
                if now - getattr(self, '_last_geocode_time', 0) > 30:
                    needs_update = True

            if needs_update:
                with getattr(self, '_geocode_lock', threading.Lock()):
                    if getattr(self, '_last_geocoded_grid', None) == grid_coord and "Tọa độ" not in curr_addr and "Đang" not in curr_addr:
                        return
                    now_lock = time.time()
                    if (now_lock - getattr(self, '_last_geocode_time', 0)) < 3.0: 
                        return 
                    
                    addr = self.get_address_from_osm(lat, lon)
                    self._last_geocode_time = time.time()

                    if addr:
                        self._last_data["api_current_address"] = addr
                        self._last_geocoded_grid = grid_coord
                        self._save_state()
                    else:
                        self._last_geocoded_grid = grid_coord
                        if not curr_addr or "Đang tải" in curr_addr or "Đang kết nối" in curr_addr:
                            self._last_data["api_current_address"] = f"Tọa độ: {round(float(lat), 5)}, {round(float(lon), 5)}"
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
                        if meta_records is not None:
                            total_records_from_api = int(meta_records)
                            
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
                        
                except Exception: 
                    consecutive_errors += 1
                
                if consecutive_errors >= 5:
                    is_success = False
                    break
                    
                if consecutive_errors > 0:
                    time.sleep(5) 
            
            if is_success:
                unique_sessions = {s.get("id") or f"noid_{s.get('pluggedTime')}": s for s in all_sessions}
                
                if total_records_from_api > 0:
                    new_t_sessions = total_records_from_api
                else:
                    new_t_sessions = sum(1 for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0)
                
                new_t_kwh = sum(safe_float(s.get("totalKWCharged", 0)) for s in unique_sessions.values())
                
                current_t_sessions = safe_float(self._last_data.get("api_total_charge_sessions", 0))
                current_t_energy = safe_float(self._last_data.get("api_total_energy_charged", 0))

                if new_t_sessions > 0 and new_t_sessions >= current_t_sessions:
                    self._last_data["api_total_charge_sessions"] = new_t_sessions
                elif current_t_sessions == 0 and new_t_sessions == 0:
                     self._last_data["api_total_charge_sessions"] = 0

                odo = safe_float(self._last_data.get("34183_00001_00003", self._last_data.get("34199_00000_00000", 0)))
                
                est_kwh = 0
                if new_t_kwh == 0 and odo > 0:
                    est_kwh = odo * self.ev_kwh_per_km
                
                final_kwh = max(new_t_kwh, est_kwh)

                if final_kwh > 0 and final_kwh >= current_t_energy:
                    self._last_data["api_total_energy_charged"] = round(final_kwh, 2)
                    self._last_data["api_total_charge_cost_est"] = round(final_kwh * self.cost_per_kwh, 0)
                elif current_t_energy == 0 and final_kwh == 0:
                     self._last_data["api_total_energy_charged"] = 0
                     self._last_data["api_total_charge_cost_est"] = 0

                valid_sessions = [s for s in unique_sessions.values() if safe_float(s.get("totalKWCharged", 0)) > 0]
                if valid_sessions:
                    sorted_sessions = sorted(valid_sessions, key=lambda x: safe_float(x.get("pluggedTime", 0)), reverse=True)
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
                
                if new_t_sessions == 0 and current_t_sessions > 0:
                    threading.Thread(target=self._retry_fetch_charging_history, daemon=True).start()
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
            current_lat = self._last_data.get("api_last_lat")
            current_lon = self._last_data.get("api_last_lon")
            if not current_lat or not current_lon: return
                
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
                    stations.append({
                        "id": st.get("locationId", ""), 
                        "name": st.get("stationName", "Trạm sạc VinFast").strip(), 
                        "lat": st_lat, "lng": st_lng, 
                        "power": max_power, 
                        "avail": avail, 
                        "total": total, 
                        "dist": dist
                    })
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
        except Exception:
            return None

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
                self.register_resources()
        except Exception: pass

    def _save_trip_to_history(self):
        try:
            if not os.path.exists(WWW_DIR):
                os.makedirs(WWW_DIR, exist_ok=True)
            history_file = os.path.join(WWW_DIR, f"vinfast_trips_{self.vin.lower()}.json")
            trips = []
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    try: trips = json.load(f)
                    except: pass
            
            start_dt = datetime.datetime.fromtimestamp(self._trip_start_time) if self._trip_start_time else datetime.datetime.now()
            duration_mins = int((time.time() - self._trip_start_time) / 60) if self._trip_start_time else 0
            
            end_address = self._last_data.get("api_current_address", "Không xác định")
            if "Đang" in end_address or "Tọa độ" in end_address: end_address = "Điểm dừng"
            start_addr = getattr(self, '_trip_start_address', "Không xác định")
            if "Đang" in start_addr or "Tọa độ" in start_addr: start_addr = "Điểm xuất phát"

            new_trip = {
                "id": int(time.time()),
                "date": start_dt.strftime('%d/%m/%Y'),
                "start_time": start_dt.strftime('%H:%M'),
                "end_time": datetime.datetime.now().strftime('%H:%M'),
                "duration": duration_mins,
                "distance": self._last_data.get("api_trip_distance", 0),
                "start_address": start_addr,
                "end_address": end_address,
                "route": getattr(self, '_route_coords', [])
            }
            trips.insert(0, new_trip) 
            if len(trips) > 30: trips = trips[:30]
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(trips, f, ensure_ascii=False)
        except Exception: pass

    def _api_polling_loop(self):
        time.sleep(5) 
        
        if not self.user_id: 
            self.get_vehicles()
            
        self._renew_aws_connection()
        
        start_time = time.time()
        last_heartbeat = start_time
        last_state_save = start_time
        last_app_ping = start_time
        last_full_wakeup = start_time
        
        while self._running:
            try:
                time.sleep(1)
                now = time.time()
                if now - last_state_save >= 60:
                    last_state_save = now
                    self._save_state()

                if getattr(self, '_is_trip_active', False):
                    if not getattr(self, '_is_moving', False):
                        if now - getattr(self, '_last_move_time', now) > 300:
                            self._is_trip_active = False
                            self._save_trip_to_history()
                            self._trip_start_odo = None
                            self._trip_start_time = None
                            self._route_coords = []
                            self._last_gps_time = None 
                            self._trip_accumulated_distance_m = 0.0 
                            self._save_state() 
                
                if now - last_heartbeat >= 60:
                    last_heartbeat = now
                    state = "2" if (getattr(self, '_is_moving', False) or getattr(self, '_is_charging', False)) else "1"
                    self._send_heartbeat(state)

                charge_ping_interval = 60 if getattr(self, '_is_charging', False) else 180
                if now - last_app_ping >= charge_ping_interval:
                    last_app_ping = now
                    if getattr(self, '_is_charging', False): self.register_resources()
                    else: self._send_app_ping_only()

                if now - last_full_wakeup >= 900 or getattr(self, '_force_full_scan', False):
                    self._force_full_scan = False
                    last_full_wakeup = now
                    self.register_resources()

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

    def _on_disconnect(self, client, userdata, rc):
        pass

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            data_dict = {}
            for item in payload:
                obj, inst, res = str(item.get("objectId", "0")).zfill(5), str(item.get("instanceId", "0")).zfill(5), str(item.get("resourceId", "0")).zfill(5)
                key = item.get("deviceKey") if "deviceKey" in item else f"{obj}_{inst}_{res}"
                val = item.get("value")
                if key == "34180_00001_00011" and isinstance(val, str) and "profile_email" in val: continue 
                if key and val is not None:
                    str_val = str(val)
                    if key in ["10351_00001_00050", "10351_00002_00050", "10351_00003_00050", "10351_00004_00050", "10351_00006_00050", "34213_00002_00003"]:
                        data_dict[key] = "Mở" if str_val == "1" else "Đóng"
                    elif key == "34183_00001_00029": data_dict[key] = "Kéo" if str_val == "1" else "Nhả"
                    elif key == "34184_00001_00004": data_dict[key] = "Bật" if str_val == "1" else "Tắt"
                    elif key == "34184_00001_00025": data_dict[key] = "Tắt" if str_val == "0" else f"Mức {str_val}"
                    elif key == "34184_00001_00041": data_dict[key] = "Lạnh nhất (1)" if str_val == "1" else f"Mức {str_val}"
                    elif key == "34183_00001_00010":
                        if str_val == "1": data_dict[key] = "ACC (Nghe nhạc)"
                        elif str_val == "2": data_dict[key] = "Cắm trại (Camp Mode)"
                        elif str_val == "3": data_dict[key] = "Sẵn sàng (Ready to Drive)"
                        else: data_dict[key] = "Tắt máy (Off)"
                    else: data_dict[key] = val
            
            if data_dict:
                current_time = time.time()
                
                try:
                    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    time_only = now_str.split(' ')[1]
                    old_debug_str = self._last_data.get("api_debug_raw_json", "{}")
                    old_debug = json.loads(old_debug_str)
                    has_changes = False
                    latest_change_msg = self._last_data.get("api_debug_raw", "Đang theo dõi sự thay đổi...")
                    new_logs_to_add = []
                    for k, v in data_dict.items():
                        if k in old_debug:
                            old_v = old_debug[k]
                            if str(old_v) != str(v):
                                new_logs_to_add.append({ "time": now_str, "code": k, "old_value": str(old_v), "new_value": str(v) })
                                has_changes = True
                                latest_change_msg = f"{time_only} : {k} : {old_v} ➔ {v}"
                        else:
                            if old_debug: 
                                new_logs_to_add.append({ "time": now_str, "code": k, "old_value": "NEW", "new_value": str(v) })
                                has_changes = True
                                latest_change_msg = f"{time_only} : {k} : Mới ➔ {v}"
                    old_debug.update(data_dict)
                    self._last_data["api_debug_raw_json"] = json.dumps(old_debug)
                    self._last_data["api_debug_raw"] = latest_change_msg
                    if has_changes:
                        with self._log_lock:
                            for log_item in new_logs_to_add: self._raw_changelog_data.insert(0, log_item)
                            if len(self._raw_changelog_data) > 1000: self._raw_changelog_data = self._raw_changelog_data[:1000]
                        threading.Thread(target=self._save_changelog_to_json, daemon=True).start()
                except Exception: pass

                target_limit = data_dict.get("34193_00001_00012", data_dict.get("34193_00001_00014", None))
                if target_limit is not None:
                    self._last_data["api_target_charge_limit"] = target_limit
                    self._last_data["34193_00001_00014"] = target_limit
                
                self._last_data.update(data_dict)

                # =====================================================================
                # CHỘP LẤY TÊN ĐỊNH DANH (TG FAMILY) KHI XE GỬI VỀ QUA MQTT
                # =====================================================================
                if "34180_00001_00010" in data_dict and data_dict["34180_00001_00010"]:
                    new_name = str(data_dict["34180_00001_00010"])
                    if self._last_data.get("api_vehicle_name") != new_name:
                        _LOGGER.warning(f"VinFast MQTT: Đã bắt được tên xe từ phần cứng -> Cập nhật thành: {new_name}")
                        self._last_data["api_vehicle_name"] = new_name

                current_soc = safe_float(data_dict.get("34183_00001_00009", data_dict.get("34180_00001_00011", self._last_data.get("34183_00001_00009", 0))))
                
                c_status_1 = str(data_dict.get("34193_00001_00005", self._last_data.get("34193_00001_00005", "0")))
                c_status_2 = str(data_dict.get("34183_00000_00001", self._last_data.get("34183_00000_00001", "0")))
                self._is_charging = (c_status_1 == "1") or (c_status_2 == "1")

                if self._is_charging and not getattr(self, '_last_is_charging', False):
                    self._last_data["api_last_charge_start_soc"] = current_soc
                    self._charge_start_time = current_time
                    self._charge_start_soc = current_soc
                    self._charge_calc_soc = current_soc
                    self._charge_calc_time = current_time
                    self._last_data["api_live_charge_power"] = 0.0
                    self._last_is_charging = True
                    self._save_state() 
                    
                elif not self._is_charging and getattr(self, '_last_is_charging', False):
                    self._last_data["api_last_charge_end_soc"] = current_soc
                    if hasattr(self, '_charge_start_time') and self._charge_start_time:
                        duration_mins = (current_time - self._charge_start_time) / 60.0
                        self._last_data["api_last_charge_duration"] = round(duration_mins, 0)
                    self._last_is_charging = False
                    self._charge_calc_soc = None
                    self._charge_calc_time = None
                    self._last_data["api_live_charge_power"] = 0.0
                    self._save_state() 

                if self._is_charging:
                    if getattr(self, '_charge_calc_soc', None) is None:
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
                            self._last_data["api_live_charge_power"] = round(power, 1)
                        self._charge_calc_soc = current_soc
                        self._charge_calc_time = current_time
                        self._save_state() 

                self._calculate_advanced_stats()
                
                speed = safe_float(data_dict.get("34183_00001_00002", self._last_data.get("34183_00001_00002", 0)))
                gear = str(data_dict.get("34183_00001_00001", self._last_data.get("34183_00001_00001", "1"))) 
                odo = safe_float(data_dict.get("34183_00001_00003", self._last_data.get("34183_00001_00003", 0))) 
                
                self._is_moving = (speed > 0) or (gear not in ["1", "0", "P"])
                if self._is_moving: self._last_data["api_vehicle_status"] = "Đang di chuyển"
                elif self._is_charging: self._last_data["api_vehicle_status"] = "Đang sạc"
                else: self._last_data["api_vehicle_status"] = "Đang đỗ"

                if self._is_moving:
                    self._last_move_time = current_time

                if self._is_moving and not getattr(self, '_is_trip_active', False) and odo > 0:
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
                    if getattr(self, '_trip_start_soc', None) is not None and self._trip_start_soc >= current_soc and trip_dist > 0:
                        cap = safe_float(self._last_data.get("api_static_capacity", 0))
                        if cap > 0:
                            energy_used = ((self._trip_start_soc - current_soc) / 100.0) * cap
                            self._last_data["api_trip_energy_used"] = round(energy_used, 2)
                            self._last_data["api_trip_efficiency"] = round((energy_used / trip_dist) * 100, 2)

                lat = data_dict.get("00006_00001_00000", self._last_data.get("00006_00001_00000"))
                lon = data_dict.get("00006_00001_00001", self._last_data.get("00006_00001_00001"))
                
                if lat and lon:
                    lat_f, lon_f = float(lat), float(lon)
                    curr_coord = f"{lat},{lon}"
                    
                    self._last_data["api_last_lat"] = lat_f
                    self._last_data["api_last_lon"] = lon_f

                    if curr_coord != getattr(self, '_last_lat_lon', None): 
                        self._last_lat_lon = curr_coord
                        threading.Thread(target=self._update_location_async, args=(lat, lon), daemon=True).start()
                        
                        # THUẬT TOÁN DEAD-RECKONING VÀ LỌC NHIỄU GPS HOÀN HẢO (BẢN GỐC)
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
                                is_valid_point = True

                                if actual_speed_kmh == 0 and distance_m > 5:
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
                                        lat2 = math.asin(math.sin(lat1) * math.cos(expected_distance_m / R) + math.cos(lat1) * math.sin(expected_distance_m / R) * math.cos(brng))
                                        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(expected_distance_m / R) * math.cos(lat1), math.cos(expected_distance_m / R) - math.sin(lat1) * math.sin(lat2))
                                        final_lat, final_lon = math.degrees(lat2), math.degrees(lon2)

                                if is_valid_point and (distance_m > 2 or final_lat != lat_f):
                                    self._route_coords.append([round(final_lat, 6), round(final_lon, 6), int(actual_speed_kmh)])
                                    if len(self._route_coords) > 600: self._route_coords.pop(0) 
                                    self._last_data["api_trip_route"] = json.dumps(self._route_coords)
                                    self._last_gps_time = current_time 
                                    
                if self.callbacks:
                    for cb in self.callbacks: cb(self._last_data)
        except Exception as e: 
            _LOGGER.error(f"VinFast: Lỗi xử lý MQTT ngầm: {e}")