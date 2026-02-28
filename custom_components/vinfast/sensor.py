import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SENSOR_DICT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    sensors = []
    
    for device_key, info in SENSOR_DICT.items():
        name, unit, icon, dev_class = info
        sensors.append(VinFastSensor(api, device_key, name, unit, icon, dev_class))

    async_add_entities(sensors)

    def handle_new_data(data):
        for sensor in sensors:
            hass.loop.call_soon_threadsafe(sensor.process_new_data, data)

    # Đăng ký nhận dữ liệu từ MQTT
    api.add_callback(handle_new_data)


class VinFastSensor(SensorEntity):
    def __init__(self, api, device_key, name, unit, icon, dev_class):
        self.api = api
        self._device_key = device_key
        
        # 1. Khai báo đây là tên độc lập của thực thể (Không nối thêm tên xe)
        self._attr_has_entity_name = True 
        self._attr_name = name 
        
        self._attr_unique_id = f"vinfast_{api.vin}_{device_key}"
        self._attr_native_unit_of_measurement = unit if unit else None
        self._attr_icon = icon
        self._attr_device_class = dev_class
        self._attr_native_value = None

        # 2. Nhóm toàn bộ cảm biến vào chung 1 Thiết bị (Device) trong HA
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{api.vehicle_name} ({api.vin})",
            manufacturer="VinFast",
            model=api.vehicle_name,
        )

    @property
    def should_poll(self):
        return False

    @callback
    def process_new_data(self, data):
        if self._device_key in data:
            val = data[self._device_key]
            
            if self._device_key == "api_total_charge_cost":
                val = "{:,.0f}".format(float(val)).replace(",", ".")

            elif self._device_key in ["10351_00001_00050", "10351_00002_00050", "10351_00005_00050", "10351_00006_00050"]:
                val = "Mở" if str(val) == "1" else "Đóng"
                
            elif self._device_key in ["34215_00001_00002", "34215_00002_00002"]:
                val = "Đóng" if str(val) == "1" else "Mở"

            elif self._device_key == "34213_00001_00003":
                val = "Đã Khóa" if str(val) == "1" else "Mở Khóa"

            elif self._device_key == "34193_00001_00005":
                val = "Đang Sạc" if str(val) == "1" else "Không Sạc"

            elif self._device_key == "34183_00001_00001":
                gear_map = {"1": "P (Đỗ)", "2": "R (Lùi)", "3": "N (Mo)", "4": "D (Tiến)"}
                val = gear_map.get(str(val), val)

            elif self._device_key == "34234_00001_00003":
                val = "Đang canh gác" if str(val) == "2" else ("Mở an ninh" if str(val) == "1" else "Tắt")

            elif self._device_key == "34186_00007_00004":
                val = "🚨 CÓ ĐỘT NHẬP!" if str(val) == "1" else "Bình thường"

            elif self._device_key == "34186_00005_00004":
                val = "Đang Nháy" if str(val) == "1" else "Tắt"

            elif self._device_key in ["34205_00001_00001", "34206_00001_00001", "34193_00001_00010"]:
                val = "Đang Bật" if str(val) == "1" else "Đã Tắt"

            self._attr_native_value = val
            self.async_write_ha_state()