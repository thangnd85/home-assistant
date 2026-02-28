DOMAIN = "vinfast"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

AUTH0_DOMAIN = "vin3s.au.auth0.com"
AUTH0_CLIENT_ID = "jE5xt50qC7oIh1f32qMzA6hGznIU5mgH"
API_BASE = "https://mobile.connected-car.vinfast.vn"
AWS_REGION = "ap-southeast-1"
COGNITO_POOL_ID = "ap-southeast-1:c6537cdf-92dd-4b1f-99a8-9826f153142a"
IOT_ENDPOINT = "prod.iot.connected-car.vinfast.vn"
DEVICE_ID = "vfdashboard-community-edition"

# =========================================================
# DATA DICTIONARY - BẢN ĐỒ CẢM BIẾN (VF3 ĐÃ TEST)
# =========================================================
SENSOR_DICT = {
    # --- REST API (Lịch sử sạc) ---
    "api_total_charge_sessions": ("Tổng số lần sạc", "lần", "mdi:ev-plug-type2", None),
    "api_total_energy_charged": ("Tổng điện năng đã sạc", "kWh", "mdi:lightning-bolt", "energy"),
    "api_total_charge_cost": ("Tổng chi phí sạc", "VNĐ", "mdi:cash", "monetary"),

    # --- PIN & SẠC (MQTT) ---
    "34183_00001_00009": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34183_00001_00011": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00001_00005": ("Pin 12V (Ắc quy)", "%", "mdi:car-battery", "battery"),
    "34220_00001_00001": ("Sức khỏe pin (SOH)", "%", "mdi:heart-pulse", "battery"),
    "34220_00001_00082": ("Dung lượng thiết kế Pin", "kWh", "mdi:car-battery", "energy"),
    "34193_00001_00005": ("Trạng thái sạc", "", "mdi:ev-station", None),
    "34193_00001_00007": ("Thời gian sạc còn lại", "min", "mdi:timer-outline", "duration"),
    "34193_00001_00019": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),
    "34193_00001_00010": ("Lịch sạc thông minh", "", "mdi:calendar-clock", None),
    "34193_00001_00021": ("Giờ bắt đầu sạc", "", "mdi:clock-start", None),
    "34193_00001_00022": ("Giờ kết thúc sạc", "", "mdi:clock-end", None),
    "34193_00001_00024": ("Giờ khởi hành sạc", "", "mdi:clock-fast", None),

    # --- CHUYẾN ĐI & VỊ TRÍ ---
    "34183_00001_00001": ("Vị trí cần số", "", "mdi:car-shift-pattern", None),
    "34183_00001_00002": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34183_00001_00003": ("Tổng ODO", "km", "mdi:counter", "distance"),
    "00006_00001_00000": ("Vĩ độ (Latitude)", "°", "mdi:crosshairs-gps", None),
    "00006_00001_00001": ("Kinh độ (Longitude)", "°", "mdi:crosshairs-gps", None),
    "34181_00001_00007": ("Tên dòng xe", "", "mdi:car", None),
    "34180_00001_00010": ("Tên định danh xe", "", "mdi:account-car", None),
    "34196_00001_00004": ("Phiên bản Firmware", "", "mdi:update", None),

    # --- MÔI TRƯỜNG & ĐIỀU HÒA ---
    "34183_00001_00007": ("Nhiệt độ ngoài trời", "°C", "mdi:thermometer", "temperature"),
    "34183_00001_00015": ("Nhiệt độ trong xe", "°C", "mdi:thermometer", "temperature"),
    "34224_00001_00005": ("Nhiệt độ điều hòa cài đặt", "°C", "mdi:thermostat", "temperature"),
    "34224_00001_00003": ("Hẹn giờ điều hòa", "", "mdi:fan-clock", None),

    # --- CỬA & KHÓA ---
    "10351_00002_00050": ("Cửa tài xế", "", "mdi:car-door", None),
    "10351_00001_00050": ("Cửa phụ", "", "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", "", "mdi:car-door", None),
    "10351_00006_00050": ("Cốp sau", "", "mdi:car-door", None),
    "34215_00002_00002": ("Cửa sổ tài xế", "", "mdi:car-door", None),
    "34215_00001_00002": ("Cửa sổ phụ", "", "mdi:car-door", None),
    "34213_00001_00003": ("Khóa tổng", "", "mdi:lock", None), 

    # --- AN NINH & CẢNH BÁO ---
    "34186_00005_00004": ("Đèn nháy cảnh báo", "", "mdi:car-light-alert", None),
    "34234_00001_00003": ("Trạng thái An ninh", "", "mdi:shield-car", None),
    "34186_00007_00004": ("Còi báo động (Chống trộm)", "", "mdi:alarm-light", None),

    # --- CHẾ ĐỘ ---
    "34205_00001_00001": ("Chế độ Giao xe (Valet)", "", "mdi:account-tie-hat", None),
    "34206_00001_00001": ("Chế độ Cắm trại (Camp)", "", "mdi:tent", None),
}