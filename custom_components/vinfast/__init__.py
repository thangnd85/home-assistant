import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_GEMINI_API_KEY
from .api import VinFastAPI

_LOGGER = logging.getLogger(__name__)

# Các thư mục (platform) thiết bị sẽ được HA load lên
PLATFORMS = ["sensor", "button"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Khởi tạo Integration từ ConfigEntry (UI)."""
    hass.data.setdefault(DOMAIN, {})

    email = entry.data.get(CONF_EMAIL, entry.data.get("email"))
    password = entry.data.get(CONF_PASSWORD, entry.data.get("password"))
    
    # Ưu tiên lấy Gemini API Key từ Options (nếu người dùng vừa sửa). 
    # Nếu trong Options rỗng thì mới lấy từ cấu hình lúc đầu (Data).
    gemini_key = entry.options.get(CONF_GEMINI_API_KEY, entry.data.get(CONF_GEMINI_API_KEY, ""))

    api = VinFastAPI(email, password, gemini_api_key=gemini_key, options=entry.options)
    
    # BẮT BUỘC: Đăng nhập HTTP để lấy Access Token trước
    logged_in = await hass.async_add_executor_job(api.login)
    if not logged_in:
        _LOGGER.error("VinFast: Đăng nhập thất bại. Vui lòng kiểm tra kết nối mạng hoặc thông tin Email/Mật khẩu.")
        return False
    
    # Sau khi có token mới được phép gọi API lấy danh sách xe
    vehicles = await hass.async_add_executor_job(api.get_vehicles)
    if not vehicles:
        _LOGGER.error("VinFast: Tài khoản đã đăng nhập nhưng không tìm thấy xe VinFast nào được liên kết.")
        return False

    # Lưu lại instance của API vào bộ nhớ của HA để các file sensor/button gọi đến
    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    # Báo cho HA biết và tiến hành tạo các entities (Cảm biến, Nút bấm)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Đẩy vòng lặp MQTT lắng nghe real-time xuống background (chạy ngầm)
    def start_mqtt_thread():
        api.start_mqtt()
        
    await hass.async_add_executor_job(start_mqtt_thread)

    # Đăng ký Listener: Bất cứ khi nào user bấm "Lưu" ở mục Cấu hình Options, hệ thống sẽ tự động gọi hàm update_listener bên dưới
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Xử lý khi người dùng xóa hoặc vô hiệu hóa (disable) Integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data[DOMAIN].pop(entry.entry_id)
        api = domain_data.get("api")
        if api:
            # Gửi tín hiệu đóng kết nối MQTT và dọn dẹp RAM
            await hass.async_add_executor_job(api.stop)
    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Hàm này sẽ tự động khởi động lại Integration ngầm khi người dùng bấm Lưu ở UI Options."""
    _LOGGER.info("VinFast: Phát hiện thay đổi cấu hình Options, đang tự động nạp lại...")
    await hass.config_entries.async_reload(entry.entry_id)