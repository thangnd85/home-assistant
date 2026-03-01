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

# --- CẤU HÌNH ĐỘNG MẶC ĐỊNH ---
DEFAULT_COST_PER_KWH = 4000
DEFAULT_EV_KWH_PER_KM = 0.12
DEFAULT_GAS_PRICE = 20000
DEFAULT_GAS_KM_PER_LITER = 25

# =========================================================
# 1. TỪ ĐIỂN DÙNG CHUNG (XE NÀO CŨNG CÓ)
# =========================================================
BASE_SENSORS = {
    # --- ẢO: Trạng thái & Vị trí ---
    "api_vehicle_status": ("Trạng thái hoạt động", "", "mdi:car-info", None),
    "api_current_address": ("Vị trí xe (Địa chỉ)", "", "mdi:map-marker", None),
    "api_trip_distance": ("Quãng đường chuyến đi (Trip)", "km", "mdi:map-marker-distance", "distance"),
    
    # --- ẢO: Tính toán Chi phí ---
    "api_total_charge_cost_est": ("Tổng chi phí sạc quy đổi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_trip_charge_cost": ("Chi phí sạc chuyến đi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_total_gas_cost": ("Tổng chi phí xăng tương đương", "VNĐ", "mdi:gas-station", "monetary"),
    "api_trip_gas_cost": ("Chi phí xăng chuyến đi", "VNĐ", "mdi:gas-station", "monetary"),
    
    # --- REST API: Lịch sử sạc ---
    "api_total_charge_sessions": ("Tổng số lần sạc", "lần", "mdi:ev-plug-type2", None),
    "api_total_energy_charged": ("Tổng điện năng đã sạc", "kWh", "mdi:lightning-bolt", "energy"),
    
    # --- MQTT: GPS & Thông tin chung ---
    "00006_00001_00000": ("Vĩ độ (Latitude)", "°", "mdi:crosshairs-gps", None),
    "00006_00001_00001": ("Kinh độ (Longitude)", "°", "mdi:crosshairs-gps", None),
    "34181_00001_00007": ("Tên dòng xe", "", "mdi:car", None),
    "34180_00001_00010": ("Tên định danh xe", "", "mdi:account-car", None),
    "34196_00001_00004": ("Phiên bản Firmware", "", "mdi:update", None),

    # --- MQTT: Cửa, Khóa, An Ninh ---
    "10351_00002_00050": ("Cửa tài xế", "", "mdi:car-door", None),
    "10351_00001_00050": ("Cửa phụ", "", "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", "", "mdi:car-door", None),
    "10351_00006_00050": ("Cốp sau", "", "mdi:car-door", None),
    "34213_00001_00003": ("Khóa tổng", "", "mdi:lock", None),
    "34234_00001_00003": ("Trạng thái An ninh", "", "mdi:shield-car", None),
    
    # --- MQTT: Cảnh báo & Chế độ ---
    "34205_00001_00001": ("Chế độ Giao xe (Valet)", "", "mdi:account-tie-hat", None),
    "34206_00001_00001": ("Chế độ Cắm trại (Camp)", "", "mdi:tent", None),
    "34186_00005_00004": ("Đèn nháy cảnh báo", "", "mdi:car-light-alert", None),
    "34186_00007_00004": ("Còi báo động", "", "mdi:alarm-light", None),
}

# =========================================================
# 2. TỪ ĐIỂN DÀNH RIÊNG CHO VF 3
# =========================================================
VF3_SENSORS = {
    # --- PIN & SẠC ---
    "34183_00001_00009": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34183_00001_00011": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00001_00005": ("Pin 12V (Ắc quy)", "%", "mdi:car-battery", "battery"),
    "34220_00001_00001": ("Sức khỏe pin (SOH)", "%", "mdi:heart-pulse", "battery"),
    "34220_00001_00082": ("Dung lượng thiết kế Pin", "kWh", "mdi:car-battery", "energy"),
    "34193_00001_00005": ("Trạng thái sạc", "", "mdi:ev-station", None),
    "34193_00001_00007": ("Thời gian sạc còn lại", "phút", "mdi:timer-outline", "duration"),
    "34193_00001_00019": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),
    "34193_00001_00010": ("Lịch sạc thông minh", "", "mdi:calendar-clock", None),
    "34193_00001_00021": ("Giờ bắt đầu sạc", "", "mdi:clock-start", None),
    "34193_00001_00022": ("Giờ kết thúc sạc", "", "mdi:clock-end", None),
    "34193_00001_00024": ("Giờ khởi hành sạc", "", "mdi:clock-fast", None),

    # --- LÁI XE & ĐIỀU HÒA ---
    "34183_00001_00001": ("Vị trí cần số", "", "mdi:car-shift-pattern", None),
    "34183_00001_00002": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34183_00001_00003": ("Tổng ODO", "km", "mdi:counter", "distance"),
    "34183_00001_00007": ("Nhiệt độ ngoài trời", "°C", "mdi:thermometer", "temperature"),
    "34183_00001_00015": ("Nhiệt độ trong xe", "°C", "mdi:thermometer", "temperature"),
    "34224_00001_00005": ("Nhiệt độ điều hòa cài đặt", "°C", "mdi:thermostat", "temperature"),
    "34224_00001_00007": ("Mức quạt gió", "", "mdi:fan", None),
    "34224_00001_00003": ("Hẹn giờ điều hòa", "", "mdi:fan-clock", None),

    # --- KÍNH (2 Cửa) ---
    "34215_00002_00002": ("Cửa sổ tài xế", "", "mdi:car-door", None),
    "34215_00001_00002": ("Cửa sổ phụ", "", "mdi:car-door", None),
}

# =========================================================
# 3. TỪ ĐIỂN DÀNH RIÊNG CHO VF 5, VF 6, VF 7
# =========================================================
VF567_SENSORS = {
    # Áp suất lốp (TPMS)
    "34183_00001_00016": ("Áp suất lốp (Trước Trái)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00017": ("Áp suất lốp (Trước Phải)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00018": ("Áp suất lốp (Sau Trái)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00019": ("Áp suất lốp (Sau Phải)", "bar", "mdi:tire", "pressure"),
    
    # Kính sau (4 Cửa)
    "34215_00004_00002": ("Cửa sổ sau trái", "", "mdi:car-door", None),
    "34215_00003_00002": ("Cửa sổ sau phải", "", "mdi:car-door", None),
}

# =========================================================
# 4. TỪ ĐIỂN DÀNH RIÊNG CHO VF 8, VF 9 (Platform cũ)
# =========================================================
VF89_SENSORS = {
    "34180_00001_00011": ("Phần trăm Pin (VF8/9)", "%", "mdi:battery", "battery"), # Khác mã VF3
    "34180_00001_00007": ("Quãng đường dự kiến (VF8/9)", "km", "mdi:map-marker-distance", "distance"),
    "34183_00000_00001": ("Trạng thái sạc (VF8/9)", "", "mdi:ev-station", None),
    "34183_00000_00004": ("Thời gian sạc còn lại (VF8/9)", "phút", "mdi:timer-outline", "duration"),
    "34183_00000_00012": ("Công suất sạc", "kW", "mdi:flash", "power"),
    
    "34187_00000_00000": ("Vị trí cần số", "", "mdi:car-shift-pattern", None),
    "34188_00000_00000": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34199_00000_00000": ("Tổng ODO", "km", "mdi:counter", "distance"),
    
    "34190_00000_00001": ("Áp suất lốp (Trước Trái)", "bar", "mdi:tire", "pressure"),
    "34190_00001_00001": ("Áp suất lốp (Trước Phải)", "bar", "mdi:tire", "pressure"),
    "34190_00002_00001": ("Áp suất lốp (Sau Trái)", "bar", "mdi:tire", "pressure"),
    "34190_00003_00001": ("Áp suất lốp (Sau Phải)", "bar", "mdi:tire", "pressure"),
    
    "34185_00000_00000": ("Trạng thái Điều hòa", "", "mdi:air-conditioner", None),
    "34186_00000_00001": ("Đèn pha (Headlight)", "", "mdi:car-light-high", None),
    "34186_00000_00002": ("Gạt mưa (Wipers)", "", "mdi:wiper", None),
}
