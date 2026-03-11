import logging
import json
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import (
    DOMAIN, 
    VIRTUAL_SENSORS, 
    VF3_SENSORS, 
    VF567_SENSORS, 
    VF89_SENSORS
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    sensors = []
    
    active_dict = VIRTUAL_SENSORS.copy()
    model_str = getattr(api, "vehicle_model_display", "Unknown").upper()
    
    if "VF 3" in model_str or "VF3" in model_str:
        active_dict.update(VF3_SENSORS)
    elif any(m in model_str for m in ["VF 5", "VF 6", "VF 7", "VFE34", "VF5", "VF6", "VF7"]):
        active_dict.update(VF567_SENSORS) 
    elif any(m in model_str for m in ["VF 8", "VF 9", "VF8", "VF9"]):
        active_dict.update(VF89_SENSORS)
    else:
        active_dict.update(VF3_SENSORS)

    for device_key, info in active_dict.items():
        name, unit, icon, dev_class = info
        sensors.append(VinFastSensor(api, device_key, name, unit, icon, dev_class))

    async_add_entities(sensors)

    def handle_new_data(data):
        for sensor in sensors:
            hass.loop.call_soon_threadsafe(sensor.process_new_data, data)

    api.add_callback(handle_new_data)
    handle_new_data(api._last_data)

class VinFastSensor(SensorEntity):
    def __init__(self, api, device_key, name, unit, icon, dev_class):
        self.api = api
        self._device_key = device_key
        self._attr_has_entity_name = True 
        self._attr_name = name 
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = dev_class
        
        model_str = getattr(api, "vehicle_model_display", "VF").upper()
        model_slug = slugify(model_str).replace("_", "")
        vin_slug = api.vin.lower() if api.vin else "unknown"
        
        self._attr_unique_id = f"{model_slug}_{vin_slug}_{device_key}"
        self.entity_id = f"sensor.{model_slug}_{vin_slug}_{slugify(name)}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {} 

        veh_name = getattr(api, 'vehicle_name', '')
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{getattr(api, 'vehicle_model_display', 'VinFast')} {veh_name}".strip(),
            manufacturer="VinFast",
            model=getattr(api, "vehicle_model_display", "EV"),
        )
        
        if "VF 3" in model_str or "VF3" in model_str:
            self._model_group = "VF3"
        elif any(m in model_str for m in ["VF 5", "VF 6", "VF 7", "VFE34", "VF5", "VF6", "VF7"]):
            self._model_group = "VF567"
        elif any(m in model_str for m in ["VF 8", "VF 9", "VF8", "VF9"]):
            self._model_group = "VF89"
        else:
            self._model_group = "UNKNOWN"

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes

    def _translate_value(self, val):
        if val is None: return None
        str_val = str(val)

        # KHỐI 1: CHUNG
        if self._device_key.startswith("10351_"):
            return "Mở" if str_val == "1" else "Đóng"
            
        if self._device_key == "34213_00001_00003":
            return "Đã Khóa" if str_val == "1" else "Mở Khóa"
            
        if self._device_key == "34234_00001_00003":
            return "Đang canh gác" if str_val == "2" else ("Mở an ninh" if str_val == "1" else "Tắt")

        if self._device_key == "34186_00005_00004":
            return "Đang Nháy" if str_val == "1" else "Tắt"

        if self._device_key in ["34205_00001_00001", "34206_00001_00001", "34207_00001_00001"]:
            return "Đang Bật" if str_val == "1" else "Đã Tắt"

        if "Áp suất lốp" in self.name and isinstance(val, (int, float, str)):
            try:
                num = float(val)
                if num > 10: return round(num / 100, 1)
                return round(num, 1) 
            except: pass

        if self._device_key in ["api_total_charge_cost", "api_total_charge_cost_est", "api_trip_charge_cost", "api_total_gas_cost", "api_trip_gas_cost", "api_last_charge_duration", "api_last_charge_start_soc", "api_last_charge_end_soc", "api_total_charge_sessions", "api_home_charge_sessions"]:
            try: return round(float(val), 0)
            except: return 0

        if self._device_key in ["api_static_capacity", "api_static_range", "api_battery_degradation", "api_lifetime_efficiency", "api_calc_max_range", "api_calc_remain_range", "api_calc_range_per_percent", "api_last_charge_energy", "api_last_charge_power", "api_last_charge_efficiency", "api_est_range_degradation", "api_trip_avg_speed", "api_trip_energy_used", "api_trip_efficiency", "api_home_charge_kwh", "api_soh_calculated"]:
            try: return round(float(val), 2)
            except: return 0

        # KHỐI 2: VF3
        if self._model_group == "VF3":
            if self._device_key == "34183_00001_00001":
                gear_map = {"1": "P (Đỗ)", "2": "R (Lùi)", "3": "N (Mo)", "4": "D (Tiến)"}
                return gear_map.get(str_val, val)
            if self._device_key in ["34215_00001_00002", "34215_00002_00002"]:
                return "Đóng" if str_val == "1" else "Mở"
            if self._device_key == "34193_00001_00005":
                charge_map = {"0": "Không Sạc", "1": "Đang Sạc", "2": "Không Sạc", "3": "Chờ / Lỗi", "4": "Không Sạc"}
                return charge_map.get(str_val, "Không Sạc")

        # KHỐI 3: VF5/6/7
        elif self._model_group == "VF567":
            if self._device_key in ["34215_00001_00002", "34215_00002_00002", "34215_00003_00002", "34215_00004_00002"]:
                return "Đóng" if str_val == "1" else "Mở"
            if self._device_key == "34183_00001_00001":
                gear_map = {"1": "P (Đỗ)", "2": "R (Lùi)", "3": "N (Mo)", "4": "D (Tiến)"}
                return gear_map.get(str_val, val)
            if self._device_key == "34193_00001_00005":
                charge_map = {"0": "Không Sạc", "1": "Đang Sạc", "2": "Không Sạc", "3": "Chờ / Lỗi", "4": "Không Sạc"}
                return charge_map.get(str_val, "Không Sạc")
            if self._device_key == "34183_00001_00029":
                return "Đang Kéo" if str_val == "1" else "Đã Nhả"

        # KHỐI 4: VF8/9
        elif self._model_group == "VF89":
            if self._device_key == "34187_00000_00000":
                gear_map = {"1": "P (Đỗ)", "2": "R (Lùi)", "3": "N (Mo)", "4": "D (Tiến)"}
                return gear_map.get(str_val, val)
            if self._device_key == "34183_00000_00001":
                charge_map = {"0": "Không Sạc", "1": "Đang Sạc", "2": "Không Sạc", "3": "Chờ / Lỗi", "4": "Không Sạc"}
                return charge_map.get(str_val, "Không Sạc")

        return val

    @callback
    def process_new_data(self, data):
        if self._device_key in data:
            val = data[self._device_key]
            if val is None: return

            if self._device_key == "api_trip_route":
                self._attr_extra_state_attributes = {"route_points": self.api._last_data.get("api_trip_route", "[]")}
                try: 
                    pts = json.loads(val)
                    self._attr_native_value = f"{len(pts)} điểm"
                except: 
                    self._attr_native_value = "Đang thu thập"
                self.async_write_ha_state()
                return
                
            elif self._device_key == "api_nearby_stations":
                try: 
                    sts = json.loads(self.api._last_data.get("api_nearby_stations", "[]"))
                    self._attr_extra_state_attributes = {"stations": sts}
                    self._attr_native_value = f"{len(sts)} trạm"
                except: 
                    self._attr_extra_state_attributes = {"stations": []}
                    self._attr_native_value = "Chưa có dữ liệu"
                self.async_write_ha_state()
                return

            elif self._device_key == "api_total_charge_sessions":
                try:
                    history_str = self.api._last_data.get("api_charge_history_list", "[]")
                    history_list = json.loads(history_str)
                    formatted_history = []
                    for item in history_list:
                        date = item.get("date", "")
                        address = item.get("address", "Không xác định")
                        kwh = item.get("kwh", 0)
                        dur = item.get("duration", 0)
                        formatted_history.append(f"{date} | {kwh} kWh ({dur} phút) | {address}")
                    self._attr_extra_state_attributes = {"Lịch sử sạc trạm (10 lần gần nhất)": formatted_history if formatted_history else ["Chưa có dữ liệu sạc trạm công cộng"]}
                except Exception as e:
                    self._attr_extra_state_attributes = {"Lỗi": str(e)}
                
            elif self._device_key == "api_debug_raw":
                try:
                    log_str = self.api._last_data.get("api_debug_raw_json", "{}")
                    self._attr_extra_state_attributes = {"Chi tiết": str(log_str)[:255]}
                    self._attr_native_value = str(val)[:255] if val else "Đang khởi động..."
                except Exception: pass
                self.async_write_ha_state()
                return

            elif self._device_key == "api_best_efficiency_band":
                attrs = {}
                stats = getattr(self.api, '_eff_stats', {})
                for k, v in stats.items():
                    if v["drops"] > 0:
                        attrs[f"Dải {k} km/h"] = f"{round(v['dist'] / v['drops'], 2)} km/1%"
                self._attr_extra_state_attributes = attrs if attrs else {"Trạng thái": "Hệ thống đang đợi % pin sụt giảm..."}

            self._attr_native_value = self._translate_value(val)
            self.async_write_ha_state()