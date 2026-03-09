import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from requests.exceptions import RequestException

from .const import DOMAIN
from .api import VinFastAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "device_tracker", "button"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Thiết lập VinFast Integration từ Config Entry."""
    hass.data.setdefault(DOMAIN, {})

    email = entry.data.get("email")
    password = entry.data.get("password")

    api = VinFastAPI(email, password)

    try:
        # Bọc luồng mạng để tự động đợi nếu lúc Raspberry Pi vừa bật chưa có mạng
        login_success = await hass.async_add_executor_job(api.login)
        if not login_success:
            _LOGGER.error("VinFast: Sai tài khoản hoặc mật khẩu đăng nhập!")
            return False

        vehicle_success = await hass.async_add_executor_job(api.get_vehicles)
        if not vehicle_success:
            _LOGGER.error("VinFast: Không tìm thấy xe nào trong tài khoản!")
            return False

    except RequestException as e:
        _LOGGER.error(f"VinFast: Mất mạng lúc khởi động. Tự động chờ... Lỗi: {e}")
        raise ConfigEntryNotReady(f"Đang chờ kết nối mạng: {e}")
    except Exception as e:
        raise ConfigEntryNotReady(f"Lỗi khởi động: {e}")

    # CHỐNG LỖI SUBSCRIPTABLE: Bọc api vào dictionary để sensor.py đọc được
    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    await hass.async_add_executor_job(api.start_mqtt)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Hủy các nền tảng khi người dùng xóa/tải lại Integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api_data = hass.data[DOMAIN].pop(entry.entry_id)
        if "api" in api_data:
            await hass.async_add_executor_job(api_data["api"].stop)
    return unload_ok