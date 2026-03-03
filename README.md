🚗 VinFast Smart Integration cho Home Assistant

Tích hợp (Integration) siêu việt đưa chiếc ô tô điện VinFast của bạn vào hệ sinh thái Home Assistant. Không chỉ đơn thuần là kéo thông số, Component này được trang bị các thuật toán Khoa học Dữ liệu (Data Science) đỉnh cao để biến Home Assistant thành một "Trung tâm phân tích viễn trắc" (Telemetry Hub) mạnh mẽ, hoạt động 24/7 mà không cần mở App điện thoại.

✨ Các tính năng cốt lõi (Core Features)

🚀 Dữ liệu Thời gian thực (Real-time MQTT): Sử dụng kết nối WebSockets trực tiếp tới AWS IoT Core của VinFast với cơ chế tự động vượt rào (Bypass) để duy trì luồng dữ liệu 24/7. Tự động trả lời ping từ T-Box của xe.

🧠 Phân tích Động học Lượng tử (Smart Profiling): Thuật toán đếm tần suất mẫu tốc độ (Frequency Sampling) thông minh. Tự động loại bỏ nhiễu do dừng đèn đỏ và phân tích chính xác "Dải tốc độ tối ưu nhất" mỗi khi pin sụt 1%.

🔋 Quản lý Sạc Tức thời (Smart Charging): Bắt sự kiện Cắm/Rút súng sạc trong vài giây thông qua MQTT. Tự động tạo luồng ngầm để lấy hóa đơn sạc (Số kWh, Hiệu suất) từ máy chủ sau khi chốt phiên sạc.

⏱️ Quản lý Chuyến đi (Trip 30 Mins): Tự động nhận diện chuyến đi mới khi bánh xe lăn. Chốt sổ chuyến đi (Quãng đường, Chi phí điện/xăng quy đổi, Vận tốc trung bình) nếu xe đỗ tĩnh quá 30 phút.

🗺️ GPS Tĩnh tâm (Anti-flicker Tracking): Thuật toán làm tròn sai số vệ tinh (11 mét) để tọa độ device_tracker không bị nhảy loạn xạ khi xe đang đỗ tĩnh trong gara, giúp tiết kiệm tài nguyên cho Home Assistant.

🎮 Điều khiển Từ xa Động (Dynamic Remote): Tích hợp các nút bấm Mở khóa, Bật điều hòa, Tìm xe... Cấu trúc Entity ID được chuẩn hóa dạng [model]_[vin] giúp quản lý nhiều xe cùng lúc không bị xung đột.

📥 Hướng dẫn Cài đặt qua HACS (Khuyên dùng)

Cách dễ nhất để cài đặt và nhận các bản cập nhật tự động là sử dụng HACS (Home Assistant Community Store).

Mở Home Assistant, truy cập vào menu HACS ở cột bên trái.

Chọn mục Integrations (Tích hợp).

Bấm vào biểu tượng 3 chấm ở góc trên cùng bên phải, chọn Custom repositories (Kho lưu trữ tùy chỉnh).

Điền các thông tin sau:

Repository: [https://github.com/thangnd85/vinfast-connected-car]

Category: Chọn Integration.

Bấm Add (Thêm).

Đóng hộp thoại, lúc này bạn sẽ thấy Tích hợp "VinFast" xuất hiện trên màn hình HACS. Bấm vào nó và chọn Download (Tải về).

⚠️ Quan trọng: Khởi động lại Home Assistant của bạn.

⚙️ Cấu hình Tích hợp (Configuration)
Sau khi cài đặt và khởi động lại, bạn tiến hành đăng nhập vào xe:

Vào Cài đặt (Settings) -> Thiết bị & Dịch vụ (Devices & Services).

Bấm nút Thêm tích hợp (Add Integration) ở góc dưới bên phải.

Gõ VinFast vào ô tìm kiếm và chọn nó.

Nhập Email và Mật khẩu tài khoản App VinFast của bạn.

Home Assistant sẽ tự động quét, lấy mã VIN và sinh ra toàn bộ Cảm biến (Sensor) & Nút bấm (Button) với cấu trúc chuẩn:

sensor.[model]_[vin]_[tên_cảm_biến] (VD: sensor.vf8_abcd1234_phan_tram_pin).

🛠️ Cấu hình Tùy chọn nâng cao (Options)
Tích hợp này cho phép bạn tính toán chi phí sạc và so sánh với xe xăng theo thời gian thực.
Tại màn hình Quản lý Tích hợp VinFast, bấm vào nút Cấu hình (Configure) để thay đổi:

Giá điện: Mặc định 4000 VNĐ/kWh.

Giá xăng quy đổi: Mặc định 20.000 VNĐ/Lít.

Mức tiêu thụ Điện tham chiếu (kWh/km).

Mức tiêu thụ Xăng tham chiếu (km/Lít).

🎨 Giao diện điều khiển (Frontend / Dashboard)
Kho lưu trữ này chỉ chứa mã nguồn Backend (Core Component) sinh ra các thực thể.
Để có giao diện Digital Twin mô phỏng xe 3D và các bảng thống kê xịn xò, vui lòng truy cập và cài đặt Custom Card tại kho lưu trữ Frontend của chúng tôi:

👉 [https://github.com/thangnd85/vinfast-digital-twin-card]

🛡️ Tuyên bố Miễn trừ trách nhiệm (Disclaimer)

Dự án này được phát triển bởi cộng đồng Open Source và KHÔNG phải là sản phẩm, cũng như không được chứng nhận hay liên kết chính thức với VinFast Auto.

Mọi hành động tương tác, lấy dữ liệu và ra lệnh điều khiển từ xa (Mở khóa, Bật AC...) đều gọi qua API nội bộ của Ứng dụng di động VinFast. Người dùng hoàn toàn tự chịu trách nhiệm về mọi rủi ro (nếu có) đối với phương tiện của mình khi sử dụng tích hợp này.

Mã nguồn cam kết không lưu trữ bất kỳ thông tin cá nhân hay mật khẩu nào ngoài phạm vi của bộ nhớ Home Assistant cục bộ của bạn.


Để có giao diện đẹp, đọc thêm:

[https://github.com/thangnd85/vinfast-digital-twin-card]

<img width="1224" height="2700" alt="image" src="https://github.com/user-attachments/assets/3113b688-736e-42e8-b01a-faccaaf76885" />

<img width="598" height="808" alt="Image" src="https://github.com/user-attachments/assets/53954013-7439-473e-abe2-155474922ab6" />

<img width="545" height="937" alt="Image" src="https://github.com/user-attachments/assets/69b0f2e5-81d3-4a7e-8ef7-2f1a9b7b2688" />

<img width="572" height="997" alt="Image" src="https://github.com/user-attachments/assets/67153991-5ac8-42a9-9bdf-c2a7099051ac" />

<img width="587" height="1095" alt="Image" src="https://github.com/user-attachments/assets/2098ba0c-bc09-4508-b2ee-aeb413d5ae70" />

<img width="568" height="911" alt="Image" src="https://github.com/user-attachments/assets/e675088f-8285-4bf6-bd2f-fc9e509344f4" />

<img width="578" height="1049" alt="Image" src="https://github.com/user-attachments/assets/06e7758f-37bc-4874-8ae6-433a091be5ec" />

<img width="1002" height="1024" alt="Image" src="https://github.com/user-attachments/assets/b1dffe04-ced9-47f9-beb1-2a68c3f6f8ed" />


