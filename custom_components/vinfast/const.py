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

DEFAULT_COST_PER_KWH = 4000
DEFAULT_EV_KWH_PER_KM = 0.12
DEFAULT_GAS_PRICE = 20000
DEFAULT_GAS_KM_PER_LITER = 20

# THÔNG SỐ XE TĨNH & SO SÁNH XĂNG THEO TỪNG DÒNG XE
# Giải thích gas_km_per_liter:
# - VF3 so sánh với xe hạng A (như Kia Morning ~5.5L/100km -> ~18 km/L)
# - VF5 so sánh với xe SUV A (như Toyota Raize ~6L/100km -> ~16.5 km/L)
# - VF6 so sánh với xe SUV B (như Hyundai Creta ~6.5L/100km -> ~15.3 km/L)
# - VF7 so sánh với xe SUV C (như Mazda CX-5 ~7.5L/100km -> ~13.3 km/L)
# - VF8 so sánh với xe SUV D (như SantaFe ~9L/100km -> ~11.1 km/L)
# - VF9 so sánh với xe SUV E (như Ford Explorer ~10.5L/100km -> ~9.5 km/L)

VEHICLE_SPECS = {
    "VF 3": {"capacity": 18.64, "range": 210, "ev_kwh_per_km": 0.09, "gas_km_per_liter": 18.0},
    "VF 5": {"capacity": 37.23, "range": 326, "ev_kwh_per_km": 0.12, "gas_km_per_liter": 16.5},
    "VF 6": {"capacity": 59.6, "range": 399, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 15.3},
    "VF 7": {"capacity": 75.3, "range": 499, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 13.3},
    "VF 8": {"capacity": 87.7, "range": 471, "ev_kwh_per_km": 0.19, "gas_km_per_liter": 11.1},
    "VF 9": {"capacity": 123.0, "range": 580, "ev_kwh_per_km": 0.21, "gas_km_per_liter": 9.5},
}

# =========================================================
# 1. TỪ ĐIỂN DÙNG CHUNG (XE NÀO CŨNG CÓ)
# =========================================================
BASE_SENSORS = {
    "api_vehicle_status": ("Trạng thái hoạt động", None, "mdi:car-info", None),
    "api_current_address": ("Vị trí xe (Địa chỉ)", None, "mdi:map-marker", None),
    "api_trip_distance": ("Quãng đường chuyến đi (Trip)", "km", "mdi:map-marker-distance", "distance"),
    
    # TOÁN HỌC & THỐNG KÊ ĐỈNH CAO
    "api_static_capacity": ("Dung lượng pin thiết kế", "kWh", "mdi:car-battery", "energy"),
    "api_static_range": ("Quãng đường thiết kế (Max)", "km", "mdi:map-marker-distance", "distance"),
    "api_battery_degradation": ("Độ chai pin (Hao hụt)", "kWh", "mdi:battery-minus", "energy"),
    "api_lifetime_efficiency": ("Hiệu suất tiêu thụ (Trung bình)", "kWh/100km", "mdi:leaf", None),
    
    "api_total_charge_cost_est": ("Tổng chi phí sạc quy đổi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_trip_charge_cost": ("Chi phí sạc chuyến đi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_total_gas_cost": ("Tổng chi phí xăng tương đương", "VNĐ", "mdi:gas-station", "monetary"),
    "api_trip_gas_cost": ("Chi phí xăng chuyến đi", "VNĐ", "mdi:gas-station", "monetary"),
    
    "api_total_charge_sessions": ("Tổng số lần sạc", "lần", "mdi:ev-plug-type2", None),
    "api_total_energy_charged": ("Tổng điện năng đã sạc", "kWh", "mdi:lightning-bolt", "energy"),
    
    "api_vehicle_model": ("Tên dòng xe", None, "mdi:car", None),
    "api_vehicle_name": ("Tên định danh xe", None, "mdi:account-car", None),
    
    "34183_00001_00003": ("Tổng ODO", "km", "mdi:counter", "distance"),
    "34199_00000_00000": ("Tổng ODO (Platform Cũ)", "km", "mdi:counter", "distance"),
    "00006_00001_00000": ("Vĩ độ (Latitude)", "°", "mdi:crosshairs-gps", None),
    "00006_00001_00001": ("Kinh độ (Longitude)", "°", "mdi:crosshairs-gps", None),
    "34196_00001_00004": ("Phiên bản Firmware", None, "mdi:update", None),

    "34213_00001_00003": ("Khóa tổng", None, "mdi:lock", None),
    "34234_00001_00003": ("Trạng thái An ninh", None, "mdi:shield-car", None),
    "34186_00005_00004": ("Đèn nháy cảnh báo", None, "mdi:car-light-alert", None),
    
    # ĐÃ KHÔI PHỤC 2 CẢM BIẾN BỊ MẤT
    "34205_00001_00001": ("Chế độ Giao xe (Valet)", None, "mdi:account-tie-hat", None),
    "34206_00001_00001": ("Chế độ Cắm trại (Camp)", None, "mdi:tent", None),
}

# =========================================================
# 2. TỪ ĐIỂN DÀNH RIÊNG CHO VF 3
# =========================================================
VF3_SENSORS = {
    "10351_00002_00050": ("Cửa tài xế", None, "mdi:car-door", None),
    "10351_00001_00050": ("Cửa phụ", None, "mdi:car-door", None),
    "10351_00006_00050": ("Cốp sau", None, "mdi:car-door", None),
    "34215_00002_00002": ("Cửa sổ tài xế", None, "mdi:car-door", None),
    "34215_00001_00002": ("Cửa sổ phụ", None, "mdi:car-door", None),

    "34183_00001_00009": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34183_00001_00011": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00001_00005": ("Pin 12V (Ắc quy)", "%", "mdi:car-battery", "battery"),
    "34220_00001_00001": ("Sức khỏe pin (SOH)", "%", "mdi:heart-pulse", "battery"),
    "34220_00001_00082": ("Dung lượng thiết kế Pin", "kWh", "mdi:car-battery", "energy"),
    "34193_00001_00005": ("Trạng thái sạc", None, "mdi:ev-station", None),
    "34193_00001_00007": ("Thời gian sạc còn lại", "min", "mdi:timer-outline", "duration"),
    
    # ĐÃ KHÔI PHỤC CẢM BIẾN MỤC TIÊU SẠC
    "34193_00001_00019": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),

    "34183_00001_00001": ("Vị trí cần số", None, "mdi:car-shift-pattern", None),
    "34183_00001_00002": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34183_00001_00007": ("Nhiệt độ ngoài trời", "°C", "mdi:thermometer", "temperature"),
    "34183_00001_00015": ("Nhiệt độ trong xe", "°C", "mdi:thermometer", "temperature"),
    "34224_00001_00005": ("Nhiệt độ điều hòa cài đặt", "°C", "mdi:thermostat", "temperature"),
    "34224_00001_00007": ("Mức quạt gió", None, "mdi:fan", None),
}

# =========================================================
# 3. TỪ ĐIỂN DÀNH RIÊNG CHO VF 5, VF 6, VF 7
# =========================================================
VF567_SENSORS = {
    "10351_00004_00050": ("Cửa sau trái", None, "mdi:car-door", None),
    "10351_00003_00050": ("Cửa sau phải", None, "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", None, "mdi:car-door", None),
    "34215_00004_00002": ("Cửa sổ sau trái", None, "mdi:car-door", None),
    "34215_00003_00002": ("Cửa sổ sau phải", None, "mdi:car-door", None),

    "34183_00001_00016": ("Áp suất lốp (Trước Trái)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00017": ("Áp suất lốp (Trước Phải)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00018": ("Áp suất lốp (Sau Trái)", "bar", "mdi:tire", "pressure"),
    "34183_00001_00019": ("Áp suất lốp (Sau Phải)", "bar", "mdi:tire", "pressure"),
}

# =========================================================
# 4. TỪ ĐIỂN DÀNH RIÊNG CHO VF 8, VF 9
# =========================================================
VF89_SENSORS = {
    "10351_00002_00050": ("Cửa tài xế", None, "mdi:car-door", None),
    "10351_00001_00050": ("Cửa phụ", None, "mdi:car-door", None),
    "10351_00004_00050": ("Cửa sau trái", None, "mdi:car-door", None),
    "10351_00003_00050": ("Cửa sau phải", None, "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", None, "mdi:car-door", None),
    "10351_00006_00050": ("Cốp sau", None, "mdi:car-door", None),

    "34180_00001_00011": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34180_00001_00007": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00000_00001": ("Trạng thái sạc", None, "mdi:ev-station", None),
    "34183_00000_00004": ("Thời gian sạc còn lại", "min", "mdi:timer-outline", "duration"),
    "34183_00000_00012": ("Công suất sạc", "kW", "mdi:flash", "power"),
    "34187_00000_00000": ("Vị trí cần số", None, "mdi:car-shift-pattern", None),
    "34188_00000_00000": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34190_00000_00001": ("Áp suất lốp (Trước Trái)", "bar", "mdi:tire", "pressure"),
    "34190_00001_00001": ("Áp suất lốp (Trước Phải)", "bar", "mdi:tire", "pressure"),
    "34190_00002_00001": ("Áp suất lốp (Sau Trái)", "bar", "mdi:tire", "pressure"),
    "34190_00003_00001": ("Áp suất lốp (Sau Phải)", "bar", "mdi:tire", "pressure"),
}
