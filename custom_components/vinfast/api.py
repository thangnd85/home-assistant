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
    AWS_REGION, COGNITO_POOL_ID, IOT_ENDPOINT, DEVICE_ID
)

_LOGGER = logging.getLogger(__name__)

class VinFastAPI:
    def __init__(self, email, password, vin=None, vehicle_name="Xe VinFast"):
        self.email = email
        self.password = password
        self.access_token = None
        self.vin = vin
        self.user_id = None
        self.vehicle_name = vehicle_name
        self.client = None
        self.callbacks = []
        self._last_data = {}  
        self._mqtt_started = False
        self._polling_thread = None

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            if self._last_data:
                cb(self._last_data)

    def login(self):
        url = f"https://{AUTH0_DOMAIN}/oauth/token"
        res = requests.post(url, json={
            "client_id": AUTH0_CLIENT_ID,
            "grant_type": "password",
            "username": self.email,
            "password": self.password,
            "scope": "openid profile email offline_access",
            "audience": API_BASE
        })
        res.raise_for_status()
        self.access_token = res.json()["access_token"]
        return self.access_token

    def get_vehicles(self):
        url = f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "x-service-name": "CAPP",
            "x-app-version": "2.17.5",
            "x-device-platform": "android"
        }
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        vehicles = res.json().get("data", [])
        if vehicles:
            self.user_id = str(vehicles[0].get("userId", ""))
            if not self.vin:
                self.vin = vehicles[0].get("vinCode")
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
            "Authorization": f"Bearer {self.access_token}",
            "x-vin-code": self.vin,
            "x-service-name": "CAPP",
            "x-app-version": "2.17.5",
            "x-device-platform": "android",
            "x-device-identifier": DEVICE_ID,
            "x-player-identifier": self.user_id,
            "Content-Type": "application/json"
        }

    def _register_device_trust(self):
        """Đăng ký thiết bị tin cậy bằng token giả để vượt lỗi 403"""
        try:
            method, api_path = "PUT", "ccarusermgnt/api/v1/device-trust/fcm-token"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({
                "X-HASH": self._generate_x_hash(method, api_path, self.vin, ts),
                "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts),
                "X-TIMESTAMP": str(ts)
            })
            payload = {"fcmToken": f"ha_bypass_token_{int(time.time())}", "devicePlatform": "android"}
            res = requests.put(f"{API_BASE}/{api_path}", headers=headers, json=payload)
            if res.status_code == 200:
                _LOGGER.info("VinFast: Đã kích hoạt cơ chế giả lập App thành công.")
        except Exception as e:
            _LOGGER.error(f"VinFast Trust Error: {e}")

    def wake_up_vehicle(self):
        """Giả lập App VinFast: Ép xe thức dậy và cập nhật TOÀN BỘ các cảm biến đang theo dõi"""
        try:
            from .const import SENSOR_DICT
            
            method, api_path = "POST", "ccaraccessmgmt/api/v1/telemetry/app/ping"
            ts = int(time.time() * 1000)
            headers = self._get_base_headers()
            headers.update({
                "X-HASH": self._generate_x_hash(method, api_path, self.vin, ts),
                "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts),
                "X-TIMESTAMP": str(ts)
            })
            
            # Tự động trích xuất toàn bộ các mã đang có trong SENSOR_DICT để ép xe cập nhật
            payload = []
            for key in SENSOR_DICT.keys():
                if "_" in key: # Chỉ lấy các mã MQTT (ví dụ: 34183_00001_00009)
                    parts = key.split("_")
                    if len(parts) == 3:
                        payload.append({
                            "objectId": str(int(parts[0])),
                            "instanceId": str(int(parts[1])),
                            "resourceId": str(int(parts[2]))
                        })
            
            # Gửi gói Ping khổng lồ (Giống hệt cách App VinFast làm)
            res = requests.post(f"{API_BASE}/{api_path}", headers=headers, json=payload)
            
            if res.status_code == 200:
                _LOGGER.info(f"VinFast: Đã bắn lệnh Wake-up yêu cầu {len(payload)} thông số. Chờ xe trả lời...")
            elif res.status_code == 401:
                self.login()
        except Exception as e:
            _LOGGER.error(f"VinFast Wake-up Error: {e}")

    def fetch_charging_history(self):
        try:
            method, api_path = "POST", "ccarcharging/api/v1/charging-sessions/search"
            all_sessions = []
            page, size, total_pages = 0, 100, 1
            
            while page < total_pages:
                ts = int(time.time() * 1000)
                headers = self._get_base_headers()
                headers.update({
                    "X-HASH": self._generate_x_hash(method, api_path, self.vin, ts),
                    "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts),
                    "X-TIMESTAMP": str(ts)
                })
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
            t_sessions = sum(1 for s in unique_sessions.values() if float(s.get("totalKWCharged", 0)) > 0)
            t_kwh = sum(float(s.get("totalKWCharged", 0)) for s in unique_sessions.values())
            t_cost = sum(float(s.get("finalAmount", 0)) for s in unique_sessions.values() if float(s.get("totalKWCharged", 0)) > 0)

            new_data = {
                "api_total_charge_sessions": t_sessions,
                "api_total_energy_charged": round(t_kwh, 2),
                "api_total_charge_cost": round(t_cost, 0)
            }
            self._last_data.update(new_data)
            if self.callbacks:
                for cb in self.callbacks: cb(new_data)
        except Exception as e: pass

    def _api_polling_loop(self):
        """Vòng lặp ngầm của Home Assistant"""
        self._register_device_trust() # Đăng ký token giả để vượt 403
        
        counter = 0
        while True:
            # 1. Ép xe cập nhật các thông số (Cửa, Pin, Tọa độ...) mỗi 5 phút
            self.wake_up_vehicle() 
            
            # 2. Quét lịch sử sạc mỗi 60 phút (Tránh gọi quá nhiều bị block)
            if counter % 12 == 0: 
                self.fetch_charging_history()
                
            counter += 1
            time.sleep(300) # Đợi 5 phút 

    def start_mqtt(self):
        if self._mqtt_started: return
        self._mqtt_started = True
        
        if not self.user_id: self.get_vehicles()
        
        self._polling_thread = threading.Thread(target=self._api_polling_loop, daemon=True)
        self._polling_thread.start()

        res_id = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}})
        creds = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": res_id.json()["IdentityId"], "Logins": {AUTH0_DOMAIN: self.access_token}}).json()["Credentials"]
        requests.post(f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": res_id.json()["IdentityId"]})

        def sign(k, m): return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()
        amz_date, date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'), datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
        cred_scope = f"{date_stamp}/{AWS_REGION}/iotdevicegateway/aws4_request"
        qs = f"X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential={urllib.parse.quote(creds['AccessKeyId'] + '/' + cred_scope, safe='')}&X-Amz-Date={amz_date}&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
        req = f"GET\n/mqtt\n{qs}\nhost:{IOT_ENDPOINT}\n\nhost\n" + hashlib.sha256("".encode('utf-8')).hexdigest()
        sts = f"AWS4-HMAC-SHA256\n{amz_date}\n{cred_scope}\n" + hashlib.sha256(req.encode('utf-8')).hexdigest()
        sig = hmac.new(sign(sign(sign(sign(('AWS4' + creds['SecretKey']).encode('utf-8'), date_stamp), AWS_REGION), 'iotdevicegateway'), 'aws4_request'), sts.encode('utf-8'), hashlib.sha256).hexdigest()
        wss_url = f"wss://{IOT_ENDPOINT}/mqtt?{qs}&X-Amz-Signature={sig}&X-Amz-Security-Token={urllib.parse.quote(creds['SessionToken'], safe='')}"

        self.client = mqtt.Client(client_id=f"HA-VFDash-{int(time.time())}", transport="websockets", protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.ws_set_options(path=wss_url.split(IOT_ENDPOINT)[1])
        self.client.tls_set()
        
        _LOGGER.info("VinFast: Bắt đầu kết nối MQTT...")
        self.client.connect(IOT_ENDPOINT, 443, 60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(f"/mobile/{self.vin}/push", qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            data_dict = {}
            for item in payload:
                obj, inst, res = str(item.get("objectId", "0")).zfill(5), str(item.get("instanceId", "0")).zfill(5), str(item.get("resourceId", "0")).zfill(5)
                key = item.get("deviceKey") if "deviceKey" in item else f"{obj}_{inst}_{res}"
                val = item.get("value")
                if key and val is not None:
                    data_dict[key] = val
            
            if data_dict:
                self._last_data.update(data_dict)
                if self.callbacks:
                    for cb in self.callbacks: cb(data_dict)
        except Exception: pass
