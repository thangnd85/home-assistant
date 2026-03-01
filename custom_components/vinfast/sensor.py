import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, BASE_SENSORS, VF3_SENSORS, VF567_SENSORS, VF89_SENSORS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    sensors = []
    
    # 1. Luôn nạp các cảm biến dùng chung
    active_dict = BASE_SENSORS.copy()
    
    # 2. Sử dụng "vehicle_model" thu từ API để nhận diện chính xác dòng xe
    vehicle_model = getattr(api, "vehicle_model", "UNKNOWN").upper()
    vehicle_name = str(api.vehicle_name).upper()
    combined_identifier = f"{vehicle_model} {vehicle_name}"
    
    if "VF 3" in combined_identifier or "VF3" in combined_identifier:
        active_dict.update(VF3_SENSORS)
        _LOGGER.info(f"VinFast: Đã nhận diện xe VF 3 (Model: {vehicle_model}).")
        
    elif any(m in combined_identifier for m in ["VF 5", "VF5", "VF 6", "VF6", "VF 7", "VF7", "VFE34", "VF E34"]):
        active_dict.update(VF3_SENSORS)
        active_dict.update(VF567_SENSORS)
        _LOGGER.info(f"VinFast: Đã nhận diện xe VF 5/6/7 (Model: {vehicle_model}).")
        
    elif "VF 8" in combined_identifier or "VF8" in combined_identifier or "VF 9" in combined_identifier or "VF9" in combined_identifier:
        active_dict.update(VF89_SENSORS)
        _LOGGER.info(f"VinFast: Đã nhận diện xe VF 8/9 (Model: {vehicle_model}).")
        
    else:
        # Dự phòng: Tải tất cả
        active_dict.update(VF3_SENSORS)
        active_dict.update(VF567_SENSORS)
        active_dict.update(VF89_SENSORS)

    for device_key, info in active_dict.items():
        name, unit, icon, dev_class = info
        sensors.append(VinFastSensor(api, device_key, name, unit, icon, dev_class))

    async_add_entities(sensors)

    def handle_new_data(data):
        for sensor in sensors:
            hass.loop.call_soon_threadsafe(sensor.process_new_data, data)

    api.add_callback(handle_new_data)


class VinFastSensor(SensorEntity):
    def __init__(self, api, device_key, name, unit, icon, dev_class):
        self.api = api
        self._device_key = device_key
        self._attr_has_entity_name = True 
        self._attr_name = name 
        self._attr_unique_id = f"vinfast_{api.vin}_{device_key}"
        self._attr_native_unit_of_measurement = unit if unit else None
        self._attr_icon = icon
        self._attr_device_class = dev_class
        self._attr_native_value = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{api.vehicle_name} ({api.vin})",
            manufacturer="VinFast",
            model=getattr(api, "vehicle_model", api.vehicle_name),
        )

    @property
    def should_poll(self):
        return False

    @callback
    def process_new_data(self, data):
        if self._device_key in data:
            val = data[self._device_key]
            
            # --- XỬ LÝ FORMARTING HIỂN THỊ TIỀN TỆ AN TOÀN ---
            if self._device_key in ["api_total_charge_cost", "api_total_charge_cost_est", "api_trip_charge_cost", "api_total_gas_cost", "api_trip_gas_cost"]:
                try:
                    val = "{:,.0f}".format(float(val)).replace(",", ".")
                except (ValueError, TypeError):
                    pass # Bỏ qua nếu giá trị lỗi

            elif self._device_key in ["10351_00001_00050", "10351_00002_00050", "10351_00005_00050", "10351_00006_00050"]:
                val = "Mở" if str(val) == "1" else "Đóng"
                
            elif self._device_key in ["34215_00001_00002", "34215_00002_00002", "34215_00003_00002", "34215_00004_00002"]:
                val = "Đóng" if str(val) == "1" else "Mở"

            elif self._device_key == "34213_00001_00003":
                val = "Đã Khóa" if str(val) == "1" else "Mở Khóa"

            elif self._device_key in ["34193_00001_00005", "34183_00000_00001"]:
                val = "Đang Sạc" if str(val) == "1" else "Không Sạc"

            elif self._device_key in ["34183_00001_00001", "34187_00000_00000"]:
                gear_map = {"1": "P (Đỗ)", "2": "R (Lùi)", "3": "N (Mo)", "4": "D (Tiến)"}
                val = gear_map.get(str(val), val)

            elif self._device_key == "34234_00001_00003":
                val = "Đang canh gác" if str(val) == "2" else ("Mở an ninh" if str(val) == "1" else "Tắt")

            elif self._device_key == "34186_00005_00004":
                val = "Đang Nháy" if str(val) == "1" else "Tắt"

            elif self._device_key in ["34205_00001_00001", "34206_00001_00001", "34186_00000_00001", "34186_00000_00002", "34185_00000_00000", "34224_00001_00003", "34193_00001_00010"]:
                val = "Đang Bật" if str(val) == "1" else "Đã Tắt"

            elif "Áp suất lốp" in self.name and val is not None and isinstance(val, (int, float)):
                if float(val) > 10:  
                    val = round(float(val) / 100, 1)

            self._attr_native_value = val
            self.async_write_ha_state()
