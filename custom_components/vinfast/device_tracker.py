import logging
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker import SourceType
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    tracker = VinFastDeviceTracker(api)
    async_add_entities([tracker])

    # Đăng ký nhận dữ liệu từ MQTT
    def handle_new_data(data):
        hass.loop.call_soon_threadsafe(tracker.process_new_data, data)

    api.add_callback(handle_new_data)


class VinFastDeviceTracker(TrackerEntity):
    """Đại diện cho vị trí xe VinFast trên bản đồ Home Assistant."""
    def __init__(self, api):
        self.api = api
        self._attr_name = f"{api.vehicle_name} Location"
        self._attr_unique_id = f"vinfast_{api.vin}_tracker"
        self._attr_icon = "mdi:car"
        self._latitude = None
        self._longitude = None

    @property
    def should_poll(self):
        return False

    @property
    def source_type(self):
        return SourceType.GPS

    @property
    def latitude(self):
        return self._latitude

    @property
    def longitude(self):
        return self._longitude

    @callback
    def process_new_data(self, data):
        updated = False
        
        # Mã 00006_00001_00000: Vĩ độ (Latitude)
        if "00006_00001_00000" in data:
            self._latitude = float(data["00006_00001_00000"])
            updated = True
            
        # Mã 00006_00001_00001: Kinh độ (Longitude)
        if "00006_00001_00001" in data:
            self._longitude = float(data["00006_00001_00001"])
            updated = True

        # Chỉ vẽ lại trên bản đồ khi có đủ cả Kinh độ và Vĩ độ
        if updated and self._latitude is not None and self._longitude is not None:
            self.async_write_ha_state()