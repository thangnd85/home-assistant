🚘 Tài liệu Lập trình Component: VinFast EV Custom Integration
VinFast EV Custom Integration là bộ lõi giao tiếp (Backend) viết bằng Python, giúp Home Assistant kết nối trực tiếp với máy chủ đám mây AWS IoT của VinFast.
Khác với các tích hợp lấy dữ liệu định kỳ (Polling API) chậm chạp, hệ thống này sử dụng MQTT qua WebSockets để nhận luồng dữ liệu thời gian thực (Real-time) và sở hữu cơ chế Phục hồi Trạng thái (State Persistence) độc quyền giúp vượt qua giới hạn "Ngủ đông" của T-Box trên xe.

Tài liệu này cung cấp kiến trúc và hướng dẫn từng bước để các nhà phát triển tự do thêm tính năng, giải mã cảm biến mới, hoặc can thiệp sâu vào luồng dữ liệu.

📂 1. Cấu trúc thư mục lõi
api.py: "Trái tim" của hệ thống. Quản lý xác thực Auth0, ký chứng chỉ AWS, duy trì kết nối MQTT, tính toán luồng Trip, và quản lý file JSON lưu trữ.

const.py: "Từ điển dịch thuật". Chứa danh sách các API Base và toàn bộ từ điển ánh xạ các mã nguyên thủy (Raw OMA-LWM2M Code) sang Cảm biến Home Assistant.

sensor.py: Chịu trách nhiệm tạo các Entity Sensor lên giao diện. Quản lý việc dịch các giá trị thô (như 1/0) thành ngôn ngữ con người (như Mở/Đóng), đồng thời xử lý các giới hạn về độ dài ký tự của Home Assistant.

button.py / device_tracker.py: Xử lý các lệnh điều khiển từ xa (Bấm còi, Mở khóa) và vẽ GPS.

🧠 2. Nguyên lý Hoạt động (Core Concepts)
A. Chuẩn OMA-LWM2M
VinFast sử dụng chuẩn IoT OMA-LWM2M. Dữ liệu xe ném về qua MQTT có dạng chuỗi JSON chứa các object:
{"objectId": "34183", "instanceId": "1", "resourceId": "9", "value": "85"}
Trong code, chúng ta nối chúng lại thành định dạng chuỗi: 34183_00001_00009 (Đây chính là mã gốc đại diện cho % Pin).

B. Trục dữ liệu trung tâm (self._last_data)
Mọi dữ liệu bắt được từ MQTT sẽ được đẩy vào một Dictionary khổng lồ tên là self._last_data nằm trong class VinFastAPI (file api.py). Mọi Sensor đều "hút" dữ liệu từ Dictionary này để hiển thị.

🛠 3. Hướng dẫn Phát triển (How-To Guides)
Bài 1: Cách thêm một Cảm biến (Sensor) mới bắt được
Giả sử bạn dùng công cụ Sniffer và tìm ra mã 34210_00001_00002 là cảm biến "Độ sáng màn hình" (thang đo 0-100%). Để đưa nó lên HA, bạn làm đúng 2 bước:

Bước 1: Khai báo vào const.py
Tìm đến từ điển của dòng xe tương ứng (VD: VF3_SENSORS hoặc BASE_SENSORS) và thêm 1 dòng:

Python
    # Cấu trúc: "Mã_gốc": ("Tên hiển thị", "Đơn vị", "Icon mdi", "Device Class")
    "34210_00001_00002": ("Độ sáng màn hình", "%", "mdi:brightness-6", None),
Bước 2: (Tùy chọn) Dịch trạng thái trong sensor.py
Nếu mã trả về là con số nhưng bạn muốn hiện chữ, mở sensor.py, tìm hàm process_new_data và chèn logic elif:

Python
            # Ví dụ biến giá trị 0/1 thành Tối/Sáng
            elif self._device_key == "34210_00001_00002":
                val = "Sáng tối đa" if str(val) == "100" else f"{val}%"
Bài 2: Cách qua mặt giới hạn 255 ký tự của Home Assistant
Home Assistant sẽ báo "Không rõ" (Unknown) / Lỗi State nếu giá trị của một cảm biến dài quá 255 ký tự (Ví dụ: Chuỗi JSON lưu tọa độ GPS).
Cách giải quyết: Giấu dữ liệu khổng lồ đó vào thuộc tính (Attributes).
Mở sensor.py, tìm hàm extra_state_attributes:

Python
    @property
    def extra_state_attributes(self):
        if self._device_key == "ten_bien_data_khong_lo_cua_ban":
            return {"data_an": json.loads(self.api._last_data.get("ten_bien_data_khong_lo_cua_ban", "{}"))}
        return None
Sau đó, ở hàm process_new_data, ép State chính hiển thị một chuỗi ngắn (VD: "Đã tải xong").

Bài 3: Cách thêm logic chạy ngầm (Background Task)
Nếu bạn muốn tính toán các số liệu như "Độ chai pin", "Dự đoán bảo dưỡng", "Theo dõi nhiệt độ"... bạn cần viết logic trong api.py.
Có 2 điểm can thiệp chính:

Tính toán tức thời khi có dữ liệu tới: Chèn code vào hàm _on_message().

Tính toán đếm lùi thời gian (như Trip) dù xe đã ngủ đông: Chèn code vào vòng lặp vô tận while self._running: trong hàm _api_polling_loop().

💾 4. Cơ chế State Persistence (Cold Boot Recovery)
Để chống lại việc HA bị mất điện/Restart trong lúc xe đang đỗ và ngủ đông (không phát MQTT), hệ thống có cơ chế tự động sao lưu cấu hình vào file /config/www/vinfast_state_xxx.json mỗi 60 giây.

Nếu bạn tạo thêm biến Logic nội bộ mới (VD: self._thoi_gian_bat_dieu_hoa):
Bạn PHẢI đăng ký biến đó vào 2 hàm lưu trữ ở file api.py để nó không bị "quên" khi HA Restart:

Hàm _save_state(self):
Bổ sung vào dict internal_memory:
"thoi_gian_bat_dieu_hoa": getattr(self, '_thoi_gian_bat_dieu_hoa', None),

Hàm _load_state(self):
Bổ sung để khôi phục:
self._thoi_gian_bat_dieu_hoa = mem.get("thoi_gian_bat_dieu_hoa", None)

🔍 5. Hỗ trợ Dịch ngược (Reverse Engineering Tips)
Đối với các anh em vọc vạch muốn bắt mã OMA-LWM2M:

Không cần chạy tool rời. Component này đã tích hợp sẵn một cảm biến tên là sensor.[ten_xe]_debug_raw_data.

Toàn bộ hàng trăm mã thô xe đẩy về đều được nén thành chuỗi JSON và nhét vào Attributes của cảm biến này.

Chỉ cần vào công cụ Nhà phát triển (Developer Tools) của Home Assistant, tìm cảm biến Debug này, anh em sẽ thấy toàn bộ thông số thực tế của xe đang chạy theo Real-time để tự đối chiếu!

Hãy đóng góp (Contributing)
Nếu bạn phân tích thành công một mã mới (VD: Cảnh báo áp suất lốp thấp, Trạng thái sưởi ghế...), hãy tạo Pull Request hoặc chia sẻ từ điển const.py mới của bạn cho cộng đồng nhé! 🚀
