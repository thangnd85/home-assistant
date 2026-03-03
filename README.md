🚗 VinFast Smart Integration for Home Assistant
Tích hợp siêu việt đưa chiếc ô tô điện VinFast của bạn vào Home Assistant. Không chỉ đơn thuần là hiển thị thông số, Component này được trang bị các thuật toán Khoa học Dữ liệu (Data Science) đỉnh cao để biến Home Assistant thành một "Trung tâm phân tích viễn trắc" (Telemetry Hub) mang phong cách của Tesla hay Rivian.

✨ Tính năng Nổi bật (Core Features)
🚀 Dữ liệu Thời gian thực (Real-time MQTT): Sử dụng kết nối WebSockets trực tiếp tới AWS IoT Core của VinFast với cơ chế tự động vượt rào (Bypass) để duy trì luồng dữ liệu 24/7 mà không cần mở App trên điện thoại.

🧠 Phân tích Động học Lượng tử (Smart Profiling): Thuật toán đếm tần suất mẫu tốc độ (Frequency Sampling) siêu việt. Tự động loại bỏ nhiễu do dừng đèn đỏ và phân tích chính xác "Dải tốc độ nào đang đem lại hiệu suất tốt nhất cho xe" mỗi khi pin sụt 1%.

🔋 Quản lý Pin & Sạc Thông minh: Tự động bắt sự kiện Cắm/Rút súng sạc trong tích tắc. Tự động tạo luồng chạy ngầm để lấy hóa đơn sạc (Số kWh, Hiệu suất) sau 60 giây kể từ khi rút súng.

⏱️ Quản lý Chuyến đi (Trip 30 Mins): Thông minh nhận diện chuyến đi mới. Tự động chốt sổ chuyến đi (Quãng đường, Chi phí, Vận tốc trung bình) nếu xe đỗ quá 30 phút.

🗺️ GPS Tĩnh tâm (Anti-flicker Map): Định vị xe với OpenStreetMap. Tự động làm tròn sai số vệ tinh (11 mét) để bản đồ không bao giờ bị nhấp nháy khi xe đang đỗ.

🎮 Điều khiển Từ xa Động (Dynamic Remote): Mở khóa, Bật điều hòa, Tìm xe... Cơ chế thông minh tự động ẩn các nút điều khiển nếu phát hiện xe của bạn là dòng VF 3 (không hỗ trợ phần cứng).

🎨 Giao diện Digital Twin: Giao diện thẻ Card cực kỳ sang trọng, responsive (1 cột trên Mobile, 3 cột trên Desktop).

⚙️ Yêu cầu Hệ thống (Prerequisites)
Để giao diện hoạt động đẹp nhất, bạn cần cài đặt các thành phần sau từ HACS (Home Assistant Community Store) -> tab Frontend:

Mushroom Cards (Hỗ trợ UI bo góc đẹp mắt).

Layout-Card (Hỗ trợ chia cột Responsive).

📥 Hướng dẫn Cài đặt (Installation)
Bước 1: Cài đặt Backend (Code Python)
Copy toàn bộ thư mục vinfast vào trong thư mục custom_components của Home Assistant.

Khởi động lại Home Assistant.

Vào Cài đặt (Settings) -> Thiết bị & Dịch vụ (Devices & Services) -> Bấm Thêm tích hợp (Add Integration).

Tìm kiếm VinFast và đăng nhập bằng Tài khoản & Mật khẩu App VinFast của bạn.

Ngay sau khi đăng nhập, các thực thể (Entity) sẽ được tạo ra tự động theo chuẩn nhận diện: sensor.[model]_[vin]_[tên_cảm_biến] (Ví dụ: sensor.vf8_jhp1234..._phan_tram_pin).

Bước 2: Cài đặt Giao diện Frontend (Custom Card)
Copy file vinfast-digital-twin.js vào thư mục www/ trong Home Assistant (nếu không có thì tự tạo thư mục www).

Vào Cài đặt -> Dashboards -> Bấm nút ba chấm góc trên bên phải -> Chọn Tài nguyên (Resources).

Bấm Thêm tài nguyên (Add Resource).

Nhập URL: /local/vinfast-digital-twin.js?v=1

Chọn loại Resource là: JavaScript Module và Lưu lại.

💻 Cấu hình Dashboard (Lovelace UI)
Mở màn hình Dashboard của bạn, chọn Chỉnh sửa giao diện (Edit Dashboard).

Thêm một Thẻ mới (Add Card), kéo xuống dưới cùng chọn Thủ công (Manual).

Copy và dán đoạn mã YAML dưới đây vào:

YAML
type: custom:vinfast-digital-twin
entity_prefix: vf8_jhp123456789  # THAY BẰNG PREFIX CỦA BẠN
(Mẹo: Bạn có thể vào phần Thực thể của HA, tìm một cảm biến của xe, lấy ID của nó bỏ đi phần sensor. và bỏ phần chức năng ở cuối, phần còn lại chính là entity_prefix của bạn).

🛠️ Cấu hình Tùy chọn nâng cao (Options)
Bạn có thể thay đổi các thông số chi phí ngay trong UI Tích hợp:

Giá điện: Mặc định 4000 VNĐ/kWh.

Giá xăng quy đổi: Mặc định 20.000 VNĐ/Lít.

Tiêu thụ Điện / Xăng tham chiếu: Để hệ thống tính toán quy đổi ra số tiền bạn đã tiết kiệm được khi đi xe điện so với xe xăng!

🛡️ Tuyên bố Miễn trừ trách nhiệm (Disclaimer)
Dự án này được phát triển bởi cộng đồng, KHÔNG phải là sản phẩm chính thức của VinFast.

Mọi hành động điều khiển xe (Mở khóa, bật điều hòa...) thông qua API đều do người dùng tự chịu trách nhiệm.

Vui lòng bảo mật tài khoản và mật khẩu của bạn.

🌟 Nếu bạn thấy dự án này tuyệt vời, đừng quên chia sẻ với cộng đồng những người đam mê xe điện! 🌟
VI
Phần này đã quá cũ. Đợt này em chỉ làm cái component vinfast thôi 
<img width="598" height="808" alt="Image" src="https://github.com/user-attachments/assets/53954013-7439-473e-abe2-155474922ab6" />

<img width="545" height="937" alt="Image" src="https://github.com/user-attachments/assets/69b0f2e5-81d3-4a7e-8ef7-2f1a9b7b2688" />

<img width="572" height="997" alt="Image" src="https://github.com/user-attachments/assets/67153991-5ac8-42a9-9bdf-c2a7099051ac" />

<img width="587" height="1095" alt="Image" src="https://github.com/user-attachments/assets/2098ba0c-bc09-4508-b2ee-aeb413d5ae70" />

<img width="568" height="911" alt="Image" src="https://github.com/user-attachments/assets/e675088f-8285-4bf6-bd2f-fc9e509344f4" />

<img width="578" height="1049" alt="Image" src="https://github.com/user-attachments/assets/06e7758f-37bc-4874-8ae6-433a091be5ec" />

<img width="1002" height="1024" alt="Image" src="https://github.com/user-attachments/assets/b1dffe04-ced9-47f9-beb1-2a68c3f6f8ed" />


