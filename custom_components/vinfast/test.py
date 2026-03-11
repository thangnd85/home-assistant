import os
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HA_CONFIG_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
WWW_DIR = os.path.join(HA_CONFIG_DIR, "www")
MOCK_FILE = os.path.join(WWW_DIR, "mock_console_cmd.txt")

def main():
    print("="*60)
    print(" 📡 BẢNG ĐIỀU KHIỂN MÔ PHỎNG TƯƠNG TÁC GIAO DIỆN (UI)")
    print("="*60)
    print(" Lệnh này sẽ can thiệp trực tiếp vào Home Assistant đang chạy")
    print(" mà không cần khởi động lại mạng hay đăng nhập.")
    print("-" * 60)
    print(" ping : Gửi lệnh Wakeup lên xe thật")
    print(" cs   : Giả lập Cắm Sạc")
    print(" rs   : Giả lập Rút Sạc")
    print(" p    : Vào số P (Park)")
    print(" d    : Vào số D (Drive)")
    print(" n    : Vào số N (Neutral)")
    print(" r    : Vào số R (Reverse)")
    print(" v X  : Chạy với tốc độ X km/h (Ví dụ: v 50)")
    print(" v 0  : Dừng xe (Tốc độ = 0)")
    print(" trip : PHÁT LẠI TOÀN BỘ CHUYẾN ĐI TÂY NINH TRÊN UI")
    print(" exit : Thoát")
    print("="*60 + "\n")

    while True:
        cmd = input("Nhập lệnh > ").strip().lower()
        if cmd == "exit": break
        if cmd:
            try:
                # Đẩy lệnh vào File Bridge cho api.py bên trong HA đọc
                with open(MOCK_FILE, "w", encoding="utf-8") as f:
                    f.write(cmd)
                print(f"[+] Đã bắn lệnh '{cmd}' sang Home Assistant! Hãy xem UI thay đổi.")
            except Exception as e:
                print(f"Lỗi gửi lệnh: {e}")

if __name__ == "__main__":
    main()