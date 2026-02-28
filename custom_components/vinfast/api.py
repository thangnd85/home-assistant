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
        self.callbacks = []  # Danh sách các hàm chờ nhận dữ liệu
        self._mqtt_started = False
        self._polling_thread = None

    def add_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)

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

    def fetch_charging_history(self):
        try:
            if not self.user_id: self.get_vehicles()
            method, api_path = "POST", "ccarcharging/api/v1/charging-sessions/search"
            url = f"{API_BASE}/{api_path}?page=0&size=1000"
            ts = int(time.time() * 1000)
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "x-vin-code": self.vin,
                "x-service-name": "CAPP",
                "x-app-version": "2.17.5",
                "x-device-platform": "android",
                "x-device-identifier": DEVICE_ID,
                "Content-Type": "application/json",
                "x-player-identifier": self.user_id,
                "X-HASH": self._generate_x_hash(method, api_path, self.vin, ts),
                "X-HASH-2": self._generate_x_hash_2("android", self.vin, DEVICE_ID, api_path, method, ts),
                "X-TIMESTAMP": str(ts)
            }
            res = requests.post(url, headers=headers, json={"orderStatus": [3, 5, 7]})
            
            if res.status_code == 401:
                self.login()
                headers["Authorization"] = f"Bearer {self.access_token}"
                res = requests.post(url, headers=headers, json={"orderStatus": [3, 5, 7]})
            
            if res.status_code != 200: return
                
            data = res.json()
            raw_data = data.get("data")
            sessions = raw_data if isinstance(raw_data, list) else (raw_data.get("content", []) if isinstance(raw_data, dict) else [])
            
            t_sessions = sum(1 for s in sessions if float(s.get("totalKWCharged", 0)) > 0)
            t_kwh = sum(float(s.get("totalKWCharged", 0)) for s in sessions)
            t_cost = sum(float(s.get("finalAmount", 0)) for s in sessions if float(s.get("totalKWCharged", 0)) > 0)

            # Phân phát cho tất cả các nền tảng đang lắng nghe
            if self.callbacks:
                for cb in self.callbacks:
                    cb({
                        "api_total_charge_sessions": t_sessions,
                        "api_total_energy_charged": round(t_kwh, 2),
                        "api_total_charge_cost": round(t_cost, 0)
                    })
        except Exception as e: _LOGGER.error(f"Lỗi lấy lịch sử sạc: {e}")

    def _api_polling_loop(self):
        while True:
            self.fetch_charging_history()
            time.sleep(3600)

    def start_mqtt(self):
        if self._mqtt_started:
            return
        self._mqtt_started = True
        
        self._polling_thread = threading.Thread(target=self._api_polling_loop, daemon=True)
        self._polling_thread.start()

        res_id = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}, json={"IdentityPoolId": COGNITO_POOL_ID, "Logins": {AUTH0_DOMAIN: self.access_token}})
        creds = requests.post(f"https://cognito-identity.{AWS_REGION}.amazonaws.com/", headers={"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity"}, json={"IdentityId": res_id.json()["IdentityId"], "Logins": {AUTH0_DOMAIN: self.access_token}}).json()["Credentials"]
        requests.post(f"{API_BASE}/ccarusermgnt/api/v1/user-vehicle/attach-policy", headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "x-service-name": "CAPP"}, json={"target": res_id.json()["IdentityId"]})

        def sign(k, m): return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()
        amz_date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
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
            
            # Đẩy dữ liệu cho Map và Sensor
            if data_dict and self.callbacks:
                for cb in self.callbacks:
                    cb(data_dict)
        except Exception:
            pass