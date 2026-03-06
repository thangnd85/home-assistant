import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    
    buttons = [
        VinFastButton(api, "34213_00001_00001", "Khóa cửa", "mdi:lock"),
        VinFastButton(api, "34213_00001_00002", "Mở khóa cửa", "mdi:lock-open"),
        VinFastButton(api, "34224_00001_00001", "Bật điều hòa", "mdi:air-conditioner"),
        VinFastButton(api, "34224_00001_00002", "Tắt điều hòa", "mdi:air-conditioner-off"),
        VinFastButton(api, "34186_00005_00001", "Nháy đèn", "mdi:car-light-high"),
        VinFastButton(api, "34186_00005_00002", "Bấm còi", "mdi:bugle"),
        VinFastButton(api, "34215_00005_00001", "Mở cốp", "mdi:car-back"),
        # NÚT MỚI
        VinFastButton(api, "find_stations", "Tìm trạm sạc", "mdi:ev-station"),
    ]
    async_add_entities(buttons)

class VinFastButton(ButtonEntity):
    def __init__(self, api, command_key, name, icon):
        self.api = api
        self._command_key = command_key
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_icon = icon
        
        model_slug = slugify(getattr(api, "vehicle_model_display", "VF")).replace("_", "")
        vin_slug = api.vin.lower() if api.vin else "unknown"
        
        self._attr_unique_id = f"{model_slug}_{vin_slug}_btn_{command_key}"
        self.entity_id = f"button.{model_slug}_{vin_slug}_{slugify(name)}"

        veh_name = getattr(api, 'vehicle_name', '')
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{getattr(api, 'vehicle_model_display', 'VinFast')} {veh_name}".strip(),
            manufacturer="VinFast",
            model=getattr(api, "vehicle_model_display", "EV"),
        )

    async def async_press(self) -> None:
        if self._command_key == "find_stations":
            await self.hass.async_add_executor_job(self.api.fetch_nearby_stations)
            return

        cmd_map = {
            "34213_00001_00001": ("Remote-Lock", {"34213_00001_00001": "1"}),
            "34213_00001_00002": ("Remote-UnLock", {"34213_00001_00002": "1"}),
            "34224_00001_00001": ("Remote-ClimateOn", {"34224_00001_00001": "1"}),
            "34224_00001_00002": ("Remote-ClimateOff", {"34224_00001_00002": "1"}),
            "34186_00005_00001": ("Remote-Flash-Light", {"34186_00005_00001": "1"}),
            "34186_00005_00002": ("Remote-Honk-Horn", {"34186_00005_00002": "1"}),
            "34215_00005_00001": ("Remote-Trunk-Open", {"34215_00005_00001": "1"}),
        }
        
        if self._command_key in cmd_map:
            cmd_type, params = cmd_map[self._command_key]
            await self.hass.async_add_executor_job(self.api.send_remote_command, cmd_type, params)