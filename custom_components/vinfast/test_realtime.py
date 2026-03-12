import sys
import os
import json
import time
import logging
import threading

# --- CẤU HÌNH ĐƯỜNG DẪN ĐỂ IMPORT API.PY TRONG MÔI TRƯỜNG TEST ---
current_dir = os.path.dirname(os.path.abspath(__file__))
ha_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if ha_dir not in sys.path: 
    sys.path.append(ha_dir)

from custom_components.vinfast.api import VinFastAPI

# --- CẤU HÌNH LOGGER MÀU SẮC ĐỂ PHÂN BIỆT RÕ CÁC BƯỚC ---
class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    green = "\x1b[32;20m"
    cyan = "\x1b[36;20m"
    magenta = "\x1b[35;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: cyan + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

logger = logging.getLogger("VinFast_Realtime_Test")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# =========================================================================
# THÔNG TIN ĐĂNG NHẬP (Sửa thành thông tin thật của bạn)
# =========================================================================
EMAIL = "@gmail.com"
PASSWORD = "your_pass"

def main():
    print("="*70)
    print("🚀 VINFAST REAL-TIME NETWORK & MQTT DEBUGGER")
    print("="*70)

    api = VinFastAPI(EMAIL, PASSWORD, options={})

    # =========================================================================
    # KỸ THUẬT MONKEY PATCHING: ĐÁNH CHẶN CÁC HÀM CỦA API.PY ĐỂ LẤY LOG RAW
    # (Đảm bảo file api.py nguyên bản không bị ảnh hưởng)
    # =========================================================================

    # 1. Đánh chặn hàm nhận MQTT (Nghe ngóng T-Box)
    original_on_message = api._on_message
    def debug_on_message(client, userdata, msg):
        try:
            raw_json = json.loads(msg.payload.decode('utf-8'))
            logger.debug(f"[MQTT NHẬN] Topic: {msg.topic}")
            logger.debug(f"[MQTT RAW DATA]:\n{json.dumps(raw_json, indent=2, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"[MQTT LỖI PARSE]: {msg.payload}")
        
        # Trả lại luồng cho api.py xử lý tiếp
        original_on_message(client, userdata, msg)
    
    api._on_message = debug_on_message

    # 2. Đánh chặn hàm gửi Heartbeat (Kiểm tra xem AWS IoT có bị rớt không)
    original_send_heartbeat = api._send_heartbeat
    def debug_send_heartbeat(state="1"):
        logger.info(f"[WS PING] Gửi Heartbeat duy trì kết nối (State={state})...")
        original_send_heartbeat(state)
        
    api._send_heartbeat = debug_send_heartbeat

    # 3. Đánh chặn HTTP POST (Kiểm tra Headers và Payload gửi lên VinFast)
    original_post_api = api._post_api
    def debug_post_api(path, payload):
        logger.warning(f"[HTTP POST OUT] URL: {path}")
        logger.warning(f"[HTTP PAYLOAD]: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        res = original_post_api(path, payload)
        if res:
            logger.info(f"[HTTP RESPONSE] Code: {res.status_code}")
        return res

    api._post_api = debug_post_api

    # =========================================================================
    # BẮT ĐẦU CHẠY CÁC BƯỚC TEST THEO ĐÚNG TRÌNH TỰ
    # =========================================================================

    # BƯỚC 1: ĐĂNG NHẬP
    logger.info(">>> BƯỚC 1: ĐĂNG NHẬP TÀI KHOẢN")
    token = api.login()
    if not token:
        logger.error("❌ Đăng nhập thất bại. Dừng test.")
        return
    logger.info(f"✅ Lấy Token thành công: {token[:20]}...{token[-10:]}")

    # BƯỚC 2: LẤY THÔNG TIN XE
    logger.info(">>> BƯỚC 2: LẤY DANH SÁCH & THÔNG TIN XE")
    vehicles = api.get_vehicles()
    if not vehicles:
        logger.error("❌ Không tìm thấy xe nào.")
        return
    logger.info(f"✅ Tên xe: {api.vehicle_model_display} | VIN: {api.vin} | UID: {api.user_id}")

    # BƯỚC 3: MỞ LUỒNG LẮNG NGHE MQTT & GỬI WAKEUP
    logger.info(">>> BƯỚC 3: MỞ WS AWS IOT & GIẢ LẬP ANDROID WAKEUP")
    
    # Khởi động luồng chạy nền của MQTT
    api.start_mqtt()
    
    # Đợi 3 giây cho AWS IoT kết nối WebSocket thành công
    logger.info("Đợi 3s thiết lập Socket...")
    time.sleep(3)

    # Gửi lệnh giả lập mở App (Đánh thức T-Box)
    logger.info(">>> BƯỚC 4: GỬI LỆNH ĐÁNH THỨC T-BOX (REGISTER RESOURCES)")
    api.register_resources()

    # =========================================================================
    # BẢNG ĐIỀU KHIỂN TƯƠNG TÁC (Treo Terminal để xem Log Real-time)
    # =========================================================================
    print("\n" + "="*70)
    print(" 🎧 ĐANG LẮNG NGHE LUỒNG DỮ LIỆU TỪ XE THẬT...")
    print(" Bảng lệnh Debug:")
    print("  1. Gõ 'ping'   : Gửi lại lệnh Wakeup (Ép T-Box trả data lập tức)")
    print("  2. Gõ 'status' : In ra bảng Dictionary dữ liệu đã phân tích của api.py")
    print("  3. Gõ 'exit'   : Thoát chương trình")
    print("="*70 + "\n")

    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "exit":
                api.stop()
                break
            elif cmd == "ping":
                api.register_resources()
            elif cmd == "status":
                print("\n[BẢNG TỔNG HỢP DỮ LIỆU API.PY ĐÃ NHẬN]")
                for k, v in api._last_data.items():
                    # Lọc bớt các trường JSON dài cho dễ nhìn
                    if k not in ["api_trip_route", "api_nearby_stations", "api_charge_history_list"]:
                        print(f" - {k}: {v}")
                print("-" * 50)
        except KeyboardInterrupt:
            api.stop()
            break

if __name__ == "__main__":
    main()