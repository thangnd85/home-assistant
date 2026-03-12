import sys
import os
import json
import time
import logging
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
ha_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if ha_dir not in sys.path: sys.path.append(ha_dir)

from custom_components.vinfast.api import VinFastAPI
from custom_components.vinfast.sensor import VinFastSensor
from custom_components.vinfast.const import (
    COMMON_SENSORS, VF3_SENSORS, VF5_SENSORS, VFE34_SENSORS, VF67_SENSORS, VF89_SENSORS, VIRTUAL_SENSORS
)

# =========================================================================
# THÔNG TIN ĐĂNG NHẬP
# =========================================================================
EMAIL = "@gmail.com"
PASSWORD = "your_pass"

# =========================================================================
# MOCK MÔI TRƯỜNG HOME ASSISTANT
# =========================================================================
class MockLoop:
    def call_soon_threadsafe(self, func, *args):
        func(*args)

class MockHass:
    def __init__(self):
        self.loop = MockLoop()
        self.data = {}

def main():
    print("="*90)
    print(" 📡 TRẠM KIỂM THỬ SENSOR THỜI GIAN THỰC (REAL-TIME TRANSLATOR)")
    print("="*90)

    api = VinFastAPI(EMAIL, PASSWORD, options={})
    hass_mock = MockHass()

    # 1. Đăng nhập và lấy thông tin xe
    print("⏳ Đang đăng nhập và cấu hình xe...")
    api.login()
    vehicles = api.get_vehicles()
    if not vehicles:
        print("❌ Không tìm thấy xe!")
        return

    model_str = api.vehicle_model_display.upper()
    print(f"✅ Đã kết nối xe: {model_str} | VIN: {api.vin}")

    # 2. Xây dựng từ điển Sensor theo đúng dòng xe
    active_dict = VIRTUAL_SENSORS.copy()
    active_dict.update(COMMON_SENSORS)
    if "VF 3" in model_str or "VF3" in model_str: active_dict.update(VF3_SENSORS)
    elif "VF 5" in model_str or "VF5" in model_str: active_dict.update(VF5_SENSORS)
    elif any(m in model_str for m in ["VFE34", "VF E34", "VFE 34"]): active_dict.update(VFE34_SENSORS)
    elif any(m in model_str for m in ["VF 6", "VF 7", "VF6", "VF7"]): active_dict.update(VF67_SENSORS)
    elif any(m in model_str for m in ["VF 8", "VF 9", "VF8", "VF9"]): active_dict.update(VF89_SENSORS)
    else: active_dict.update(VF3_SENSORS)

    # 3. Khởi tạo toàn bộ Object Sensor vào bộ nhớ tạm
    sensor_registry = {}
    for key, (name, unit, icon, dev_class) in active_dict.items():
        sensor = VinFastSensor(api, key, name, unit, icon, dev_class)
        sensor.hass = hass_mock
        sensor.async_write_ha_state = lambda: None # Vô hiệu hóa ghi đè UI thật
        sensor_registry[key] = sensor

    # 4. Kỹ thuật Monkey Patch: Đánh chặn MQTT để Test Real-time
    original_on_message = api._on_message
    
    def live_test_on_message(client, userdata, msg):
        # Chạy logic gốc của api.py để cập nhật _last_data
        original_on_message(client, userdata, msg)
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            items = payload if isinstance(payload, list) else payload.get("data", payload.get("content", []))
            
            for item in items:
                if not isinstance(item, dict): continue
                obj, inst, res = str(item.get("objectId", "0")).zfill(5), str(item.get("instanceId", "0")).zfill(5), str(item.get("resourceId", "0")).zfill(5)
                key = item.get("deviceKey") if "deviceKey" in item else f"{obj}_{inst}_{res}"
                val = item.get("value")
                
                if key and val is not None and key in sensor_registry:
                    # Cho sensor tiến hành dịch thuật
                    sensor = sensor_registry[key]
                    sensor._process_update(api._last_data)
                    
                    translated_val = sensor._attr_native_value
                    unit = sensor._attr_native_unit_of_measurement or ""
                    
                    # Định dạng màu sắc để dễ nhìn
                    time_str = datetime.now().strftime("%H:%M:%S")
                    status = "✅ DỊCH OK" if str(val) != str(translated_val) or type(val) is float else "⚠️ GIỮ NGUYÊN"
                    
                    print(f"[{time_str}] \033[96m{sensor._attr_name:<22}\033[0m | RAW: \033[93m{str(val):<10}\033[0m ➔ GIAO DIỆN: \033[92m{str(translated_val)} {unit}\033[0m ({status})")
                    
        except Exception as e:
            pass

    # Áp dụng hàm đánh chặn
    api._on_message = live_test_on_message

    # 5. Mở luồng MQTT
    print("🚀 Bắt đầu mở luồng MQTT lắng nghe sự kiện...\n")
    api.start_mqtt()
    time.sleep(2)
    api.register_resources() # Gửi lệnh Wakeup

    print("="*90)
    print(" 🎧 HỆ THỐNG ĐANG LẮNG NGHE. HÃY THỬ ĐÓNG/MỞ CỬA, KHÓA XE HOẶC CẮM SẠC...")
    print(" (Gõ 'ping' để ép xe gửi lại toàn bộ dữ liệu. Gõ 'exit' để thoát)")
    print("="*90)

    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "exit":
                api.stop()
                break
            elif cmd == "ping":
                print("🔄 Đang gửi yêu cầu ép xe nhả dữ liệu (Wakeup)...")
                api.register_resources()
        except KeyboardInterrupt:
            api.stop()
            break

if __name__ == "__main__":
    main()