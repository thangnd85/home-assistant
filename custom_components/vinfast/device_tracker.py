import logging
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    tracker = VinFastTracker(api)
    async_add_entities([tracker])

    def handle_new_data(data):
        hass.loop.call_soon_threadsafe(tracker.process_new_data, data)

    api.add_callback(handle_new_data)
    handle_new_data(api._last_data)

class VinFastTracker(TrackerEntity):
    def __init__(self, api):
        self.api = api
        self._attr_has_entity_name = True
        self._attr_name = "Vị trí GPS"
        self._attr_unique_id = f"vinfast_{api.vin}_tracker"
        self._attr_icon = "mdi:car"
        
        self._latitude = None
        self._longitude = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{getattr(api, 'vehicle_name', 'Xe VinFast')} ({getattr(api, 'vehicle_model_display', 'EV')})",
            manufacturer="VinFast",
            model=getattr(api, "vehicle_model_display", "EV"),
        )

    @property
    def should_poll(self):
        return False

    @property
    def latitude(self):
        return self._latitude

    @property
    def longitude(self):
        return self._longitude

    @property
    def source_type(self):
        return "gps"

    @callback
    def process_new_data(self, data):
        lat = data.get("00006_00001_00000")
        lon = data.get("00006_00001_00001")
        if lat and lon:
            try:
                self._latitude = float(lat)
                self._longitude = float(lon)
                self.async_write_ha_state()
            except ValueError:
                pass
