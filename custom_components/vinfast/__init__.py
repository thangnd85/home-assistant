import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .api import VinFastAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    options = entry.options

    api = VinFastAPI(email, password, options=options)
    
    try:
        await hass.async_add_executor_job(api.login)
        # BẮT BUỘC: Phải gọi lệnh này để định danh xe trước khi vẽ Sensor
        await hass.async_add_executor_job(api.get_vehicles)
    except Exception as e:
        _LOGGER.error(f"VinFast: Lỗi đăng nhập hoặc lấy thông tin xe: {e}")
        return False

    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    await hass.async_add_executor_job(api.start_mqtt)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "device_tracker"])

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "device_tracker"])
    if unload_ok:
        api = hass.data[DOMAIN][entry.entry_id]["api"]
        await hass.async_add_executor_job(api.stop)
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
