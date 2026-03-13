DOMAIN = "vinfast"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_GEMINI_API_KEY = "gemini_api_key"

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

VEHICLE_SPECS = {
    "VF 3": {"capacity": 18.64, "range": 210, "ev_kwh_per_km": 0.09, "gas_km_per_liter": 18.0},
    "VF E34": {"capacity": 42.0, "range": 285, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 14.0},
    "VFE34": {"capacity": 42.0, "range": 285, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 14.0},
    "VF 5": {"capacity": 37.23, "range": 326, "ev_kwh_per_km": 0.12, "gas_km_per_liter": 16.5},
    "VF 6": {"capacity": 59.6, "range": 399, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 15.3},
    "VF 7": {"capacity": 75.3, "range": 499, "ev_kwh_per_km": 0.15, "gas_km_per_liter": 13.3},
    "VF 8": {"capacity": 87.7, "range": 471, "ev_kwh_per_km": 0.19, "gas_km_per_liter": 11.1},
    "VF 9": {"capacity": 123.0, "range": 580, "ev_kwh_per_km": 0.21, "gas_km_per_liter": 9.5},
}

# =========================================================================
# LỚP 1: VIRTUAL SENSORS (CẢM BIẾN TÍNH TOÁN DO MÃ TỰ TẠO)
# =========================================================================
VIRTUAL_SENSORS = {
    "api_vehicle_status": ("Trạng thái hoạt động", None, "mdi:car-info", None),
    "api_current_address": ("Vị trí xe (Địa chỉ)", None, "mdi:map-marker", None),
    "api_trip_distance": ("Quãng đường chuyến đi (Trip)", "km", "mdi:map-marker-distance", "distance"),
    "api_trip_avg_speed": ("Tốc độ TB chuyến đi", "km/h", "mdi:speedometer-medium", "speed"),
    "api_trip_energy_used": ("Điện năng tiêu thụ Trip", "kWh", "mdi:lightning-bolt", "energy"),
    "api_trip_efficiency": ("Hiệu suất tiêu thụ Trip", "kWh/100km", "mdi:leaf-circle", None),
    "api_static_capacity": ("Dung lượng pin thiết kế", "kWh", "mdi:car-battery", "energy"),
    "api_static_range": ("Quãng đường công bố (Max)", "km", "mdi:map-marker-distance", "distance"),
    "api_soh_calculated": ("Sức khỏe pin (SOH Tính toán)", "%", "mdi:heart-pulse", "battery"),
    "api_battery_degradation": ("Độ chai pin (Theo SOH)", "kWh", "mdi:battery-minus", "energy"),
    "api_est_range_degradation": ("Khả năng chai pin (Tham khảo)", "%", "mdi:battery-alert", None),
    "api_lifetime_efficiency": ("Hiệu suất tiêu thụ (Trung bình xe)", "kWh/100km", "mdi:leaf", None),
    "api_calc_max_range": ("Quãng đường thực tế (Đầy 100% pin)", "km", "mdi:map-marker-path", "distance"),
    "api_calc_remain_range": ("Quãng đường còn lại (Theo hiệu suất)", "km", "mdi:map-marker-distance", "distance"),
    "api_calc_range_per_percent": ("Quãng đường đi được mỗi 1% pin", "km", "mdi:ruler", "distance"),
    "api_best_efficiency_band": ("Dải tốc độ tối ưu nhất", None, "mdi:chart-bell-curve", None),
    "api_last_charge_start_soc": ("% Pin lúc cắm sạc (Lần cuối)", "%", "mdi:battery-arrow-down", "battery"),
    "api_last_charge_end_soc": ("% Pin lúc rút sạc (Lần cuối)", "%", "mdi:battery-arrow-up", "battery"),
    "api_last_charge_duration": ("Thời gian cắm sạc (Lần cuối)", "min", "mdi:timer-sand", "duration"),
    "api_last_charge_energy": ("Điện năng lấy từ lưới (Lần cuối)", "kWh", "mdi:flash", "energy"),
    "api_last_charge_power": ("Công suất sạc trung bình (Lần cuối)", "kW", "mdi:ev-plug-type2", "power"),
    "api_last_charge_efficiency": ("Hiệu suất sạc thực tế (Lần cuối)", "%", "mdi:battery-charging-high", None),
    "api_total_charge_cost_est": ("Tổng chi phí sạc quy đổi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_trip_charge_cost": ("Chi phí sạc chuyến đi", "VNĐ", "mdi:cash-fast", "monetary"),
    "api_total_gas_cost": ("Tổng chi phí xăng tương đương", "VNĐ", "mdi:gas-station", "monetary"),
    "api_trip_gas_cost": ("Chi phí xăng chuyến đi", "VNĐ", "mdi:gas-station", "monetary"),
    
    # 3 Sensor phân mảnh lịch sử sạc cực chuẩn
    "api_total_charge_sessions": ("Tổng số lần sạc", "lần", "mdi:battery-charging-100", None),
    "api_public_charge_sessions": ("Số lần sạc tại trạm", "lần", "mdi:ev-station", None),
    "api_home_charge_sessions": ("Số lần sạc tại nhà", "lần", "mdi:home-lightning-bolt-outline", None),
    
    "api_home_charge_kwh": ("Điện năng sạc tại nhà", "kWh", "mdi:home-battery", "energy"),
    "api_total_energy_charged": ("Tổng điện năng đã sạc", "kWh", "mdi:lightning-bolt", "energy"),
    "api_vehicle_model": ("Tên dòng xe", None, "mdi:car", None),
    "api_vehicle_name": ("Tên định danh xe", None, "mdi:account-car", None),
    "api_outside_temp": ("Nhiệt độ ngoài trời (GPS)", "°C", "mdi:thermometer", "temperature"),
    "api_weather_condition": ("Thời tiết hiện tại", None, "mdi:weather-partly-cloudy", None),
    "api_hvac_load_estimate": ("Ước tính tải Điều hòa", None, "mdi:air-conditioner", None),
    "api_ai_advisor": ("Cố vấn Xe điện AI", None, "mdi:robot-outline", None),
    "api_vehicle_image": ("Hình ảnh xe URL", None, "mdi:image", None),
    "api_trip_route": ("Lộ trình GPS", None, "mdi:map-marker-path", None),
    "api_nearby_stations": ("Trạm sạc lân cận", None, "mdi:ev-station", None),
    "api_debug_raw": ("System Debug Raw", None, "mdi:bug", None)
}

# =========================================================================
# LỚP 2: COMMON SENSORS (CẢM BIẾN MÃ GIỐNG HỆT NHAU TRÊN MỌI XE)
# =========================================================================
COMMON_SENSORS = {
    "34213_00001_00003": ("Khóa tổng", None, "mdi:lock", None),
    "34234_00001_00003": ("Trạng thái An ninh", None, "mdi:shield-car", None),
    "34186_00005_00004": ("Đèn nháy cảnh báo", None, "mdi:car-light-alert", None),
    "34205_00001_00001": ("Chế độ Giao xe (Valet)", None, "mdi:account-tie-hat", None),
    "34206_00001_00001": ("Chế độ Cắm trại (Camp)", None, "mdi:tent", None),
    "34207_00001_00001": ("Chế độ Thú cưng (Pet)", None, "mdi:paw", None),
    "00006_00001_00000": ("Vĩ độ (Latitude)", "°", "mdi:crosshairs-gps", None),
    "00006_00001_00001": ("Kinh độ (Longitude)", "°", "mdi:crosshairs-gps", None),
    "00006_00001_00002": ("Độ cao (Altitude)", "m", "mdi:elevation-rise", None),
    "00005_00001_00030": ("Phiên bản Phần mềm (FRP)", None, "mdi:update", None),
    "34196_00001_00004": ("Phiên bản T-Box", None, "mdi:cellphone-link", None),
    "34181_00001_00007": ("Biển số / Tên xe phụ", None, "mdi:card-text-outline", None),
    
    # --- CỬA VẬT LÝ ---
    "10351_00002_00050": ("Cửa tài xế", None, "mdi:car-door", None),
    "10351_00001_00050": ("Cửa phụ", None, "mdi:car-door", None),
    "10351_00006_00050": ("Cốp sau", None, "mdi:car-door", None),

    # ==========================================================
    # BẢN VÁ: THÊM HỆ THỐNG KÍNH, ĐÈN VÀ ĐIỀU HÒA TỪ LOG VF5
    # ==========================================================
    "34215_00001_00002": ("Kính phụ", None, "mdi:window-open", None),
    "34215_00002_00002": ("Kính tài xế", None, "mdi:window-open", None),
    "34215_00003_00002": ("Kính sau phụ", None, "mdi:window-open", None),
    "34215_00004_00002": ("Kính sau tài xế", None, "mdi:window-open", None),
    
    "34213_00004_00003": ("Trạng thái nháy đèn pha", None, "mdi:car-light-high", None),
    
    "34184_00001_00004": ("Trạng thái điều hòa", None, "mdi:air-conditioner", None),
    "34184_00001_00011": ("Chế độ lấy gió", None, "mdi:car-windshield-outline", None),
    "34184_00001_00012": ("Hướng gió điều hòa", None, "mdi:fan", None),
    "34184_00001_00009": ("Sấy kính lái", None, "mdi:car-defrost-front", None),
    "34184_00001_00025": ("Tốc độ quạt gió", "Mức", "mdi:fan-speed-1", None),
    "34184_00001_00041": ("Mức độ làm lạnh", "Mức", "mdi:snowflake", None),
}

# =========================================================================
# LỚP 3A: NỀN TẢNG A (VF3, VF5, e34, VF6, VF7)
# =========================================================================
PLATFORM_A_BASE = COMMON_SENSORS.copy()
PLATFORM_A_BASE.update({
    "34183_00001_00010": ("Trạng thái Lái (Ready/MQTT)", None, "mdi:car-key", None), 
    "34183_00001_00009": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34183_00001_00011": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00001_00005": ("Pin 12V (Ắc quy)", "%", "mdi:car-battery", "battery"),
    "34220_00001_00001": ("Sức khỏe pin (SOH)", "%", "mdi:heart-pulse", "battery"),
    "34193_00001_00005": ("Trạng thái sạc", None, "mdi:ev-station", None),
    "34193_00001_00007": ("Thời gian sạc còn lại", "min", "mdi:timer-outline", "duration"),
    "34183_00001_00001": ("Vị trí cần số", None, "mdi:car-shift-pattern", None),
    "34183_00001_00002": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34183_00001_00003": ("Tổng ODO (MQTT)", "km", "mdi:counter", "distance"),
    "34183_00001_00004": ("Điện áp / Tiêu thụ (00004)", None, "mdi:flash", None), 
    "34183_00001_00007": ("Nhiệt độ ngoài trời", "°C", "mdi:thermometer", "temperature"),
    "34183_00001_00015": ("Nhiệt độ trong xe", "°C", "mdi:thermometer", "temperature"),
    "34224_00001_00005": ("Nhiệt độ điều hòa cài đặt", "°C", "mdi:thermostat", "temperature"),
    "34224_00001_00007": ("Mức quạt gió", None, "mdi:fan", None),
    
    # BẢN VÁ: THÊM PHANH TAY ĐIỆN TỬ
    "34183_00001_00029": ("Phanh tay điện tử", None, "mdi:car-brake-parking", None),
})

# --- DÒNG VF 3 ---
VF3_SENSORS = PLATFORM_A_BASE.copy()
VF3_SENSORS.update({
    "34193_00001_00019": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),
})

# --- DÒNG VF 5 ---
VF5_SENSORS = PLATFORM_A_BASE.copy()
VF5_SENSORS.update({
    "10351_00004_00050": ("Cửa sau trái", None, "mdi:car-door", None),
    "10351_00003_00050": ("Cửa sau phải", None, "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", None, "mdi:car-door", None),
    "34193_00001_00014": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),
})

# --- DÒNG VFe34, VF 6, VF 7 ---
VF67_SENSORS = VF5_SENSORS.copy()
VF67_SENSORS.update({
    "34183_00001_00016": ("Áp suất lốp Trước Trái", "bar", "mdi:tire", "pressure"),
    "34183_00001_00017": ("Áp suất lốp Trước Phải", "bar", "mdi:tire", "pressure"),
    "34183_00001_00018": ("Áp suất lốp Sau Trái", "bar", "mdi:tire", "pressure"),
    "34183_00001_00019": ("Áp suất lốp Sau Phải", "bar", "mdi:tire", "pressure"),
})
VFE34_SENSORS = VF67_SENSORS.copy()

# =========================================================================
# LỚP 3B: NỀN TẢNG B (VF8, VF9)
# =========================================================================
VF89_SENSORS = COMMON_SENSORS.copy()
VF89_SENSORS.update({
    "10351_00004_00050": ("Cửa sau trái", None, "mdi:car-door", None),
    "10351_00003_00050": ("Cửa sau phải", None, "mdi:car-door", None),
    "10351_00005_00050": ("Nắp Capo", None, "mdi:car-door", None),
    
    "34183_00001_00005": ("Pin 12V (Ắc quy)", "%", "mdi:car-battery", "battery"),
    "34220_00001_00001": ("Sức khỏe pin (SOH)", "%", "mdi:heart-pulse", "battery"),
    "34183_00001_00007": ("Nhiệt độ ngoài trời", "°C", "mdi:thermometer", "temperature"),
    "34183_00001_00015": ("Nhiệt độ trong xe", "°C", "mdi:thermometer", "temperature"),
    "34224_00001_00005": ("Nhiệt độ điều hòa cài đặt", "°C", "mdi:thermostat", "temperature"),
    "34224_00001_00007": ("Mức quạt gió", None, "mdi:fan", None),
    
    "34180_00001_00010": ("Tên định danh xe (MQTT)", None, "mdi:badge-account", None),
    "34180_00001_00011": ("Phần trăm Pin", "%", "mdi:battery", "battery"),
    "34180_00001_00007": ("Quãng đường dự kiến", "km", "mdi:map-marker-distance", "distance"),
    "34183_00000_00001": ("Trạng thái sạc", None, "mdi:ev-station", None),
    "34183_00000_00004": ("Thời gian sạc còn lại", "min", "mdi:timer-outline", "duration"),
    "34183_00000_00012": ("Công suất sạc", "kW", "mdi:flash", "power"),
    "34183_00000_00015": ("Điện áp sạc", "V", "mdi:flash-outline", "voltage"),
    "34183_00000_00016": ("Dòng điện sạc", "A", "mdi:current-ac", "current"),
    "34193_00001_00012": ("Mục tiêu sạc (Target)", "%", "mdi:battery-charging-100", "battery"),
    "34187_00000_00000": ("Vị trí cần số", None, "mdi:car-shift-pattern", None),
    "34188_00000_00000": ("Tốc độ hiện tại", "km/h", "mdi:speedometer", "speed"),
    "34199_00000_00000": ("Tổng ODO (MQTT)", "km", "mdi:counter", "distance"),
    
    # BẢN VÁ: THÊM PHANH TAY
    "34183_00001_00029": ("Phanh tay điện tử", None, "mdi:car-brake-parking", None),
    
    "34190_00000_00001": ("Áp suất lốp Trước Trái", "bar", "mdi:tire", "pressure"),
    "34190_00001_00001": ("Áp suất lốp Trước Phải", "bar", "mdi:tire", "pressure"),
    "34190_00002_00001": ("Áp suất lốp Sau Trái", "bar", "mdi:tire", "pressure"),
    "34190_00003_00001": ("Áp suất lốp Sau Phải", "bar", "mdi:tire", "pressure"),
})

KNOWN_COMMANDS = {
    1: ("Khóa cửa", "mdi:lock", "khoa_cua"),
    2: ("Mở cửa", "mdi:lock-open", "mo_cua"),
    3: ("Bấm còi", "mdi:bullhorn", "bam_coi"),
    4: ("Nháy đèn", "mdi:car-light-high", "nhay_den"),
    5: ("Bật điều hòa", "mdi:fan", "bat_dieu_hoa"),
    6: ("Tắt điều hòa", "mdi:fan-off", "tat_dieu_hoa"),
    7: ("Mở cốp", "mdi:car-back", "mo_cop"),
}