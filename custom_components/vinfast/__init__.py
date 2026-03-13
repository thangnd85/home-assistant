import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_REGION, CONF_GEMINI_API_KEY
from .api import VinFastAPI

_LOGGER = logging.getLogger(__name__)

# Danh sách các nhóm thực thể sẽ được tạo ra (Bao gồm cả Device Tracker bạn đã cung cấp)
PLATFORMS = ["sensor", "button", "device_tracker"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Khởi tạo Integration từ ConfigEntry (Giao diện UI)."""
    hass.data.setdefault(DOMAIN, {})

    # Lấy thông tin từ cấu hình ban đầu
    email = entry.data.get(CONF_EMAIL, entry.data.get("email"))
    password = entry.data.get(CONF_PASSWORD, entry.data.get("password"))
    region = entry.data.get(CONF_REGION, "vn") # Mặc định là VN nếu bản cũ nâng cấp lên
    
    # Ưu tiên lấy Gemini API Key từ Options (nếu người dùng vừa sửa). 
    gemini_key = entry.options.get(CONF_GEMINI_API_KEY, entry.data.get(CONF_GEMINI_API_KEY, ""))

    # Khởi tạo API Lõi với tham số Region
    api = VinFastAPI(
        email=email, 
        password=password, 
        region=region, 
        gemini_api_key=gemini_key, 
        options=entry.options
    )
    
    # Đăng nhập HTTP để kiểm tra kết nối và lấy thông tin xe
    vehicles = await hass.async_add_executor_job(api.get_vehicles)
    if not vehicles:
        _LOGGER.error(f"VinFast: Không thể kết nối hoặc không tìm thấy xe nào tại Khu vực: {region.upper()}. Vui lòng kiểm tra lại tài khoản.")
        return False

    # Lưu biến API vào bộ nhớ của HA để các file sensor/button/tracker gọi đến
    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    # Báo cho HA biết và tiến hành tạo các entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Đẩy vòng lặp MQTT và Fetch Data xuống background (chạy ngầm, không làm treo HA)
    def start_mqtt_thread():
        api.start_mqtt()
        
    await hass.async_add_executor_job(start_mqtt_thread)

    # Đăng ký Listener: Khi user bấm "Lưu" ở Cấu hình Options, tự động gọi hàm update_listener
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Xử lý khi người dùng xóa hoặc vô hiệu hóa Integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data[DOMAIN].pop(entry.entry_id)
        api = domain_data.get("api")
        if api:
            # Gửi tín hiệu đóng kết nối MQTT và dọn dẹp RAM
            await hass.async_add_executor_job(api.stop)
    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Hàm chạy khi người dùng thay đổi Options. Sẽ yêu cầu HA tải lại Integration."""
    await hass.config_entries.async_reload(entry.entry_id)