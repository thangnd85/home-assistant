import logging
import json
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN, BASE_SENSORS, VF3_SENSORS

try:
    from .const import VF567_SENSORS
except ImportError:
    VF567_SENSORS = {}

try:
    from .const import VF89_SENSORS
except ImportError:
    VF89_SENSORS = {}

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    sensors = []
    
    active_dict = BASE_SENSORS.copy()
    model = getattr(api, "vehicle_model_display", "Unknown").upper()
    
    if "VF 3" in model or "VF3" in model:
        active_dict.update(VF3_SENSORS)
    elif any(m in model for m in ["VF 5", "VF 6", "VF 7", "VFE34", "VF5", "VF6", "VF7"]):
        active_dict.update(VF3_SENSORS) 
        active_dict.update(VF567_SENSORS) 
    elif any(m in model for m in ["VF 8", "VF 9", "VF8", "VF9"]):
        active_dict.update(VF89_SENSORS)
    else:
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
        
        model_slug = slugify(getattr(api, "vehicle_model_display", "VF")).replace("_", "")
        vin_slug = api.vin.lower() if api.vin else "unknown"
        
        self._attr_unique_id = f"{model_slug}_{vin_slug}_{device_key}"
        self.entity_id = f"sensor.{model_slug}_{vin_slug}_{slugify(name)}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {} # Biến lưu Attributes chủ động

        veh_name = getattr(api, 'vehicle_name', '')
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.vin)},
            name=f"{getattr(api, 'vehicle_model_display', 'VinFast')} {veh_name}".strip(),
            manufacturer="VinFast",
            model=getattr(api, "vehicle_model_display", "EV"),
        )

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        # Trả về luôn biến chứa Attributes đã được tạo ở process_new_data
        return self._attr_extra_state_attributes

    @callback
    def process_new_data(self, data):
        if self._device_key in data:
            val = data[self._device_key]
            if val is None: return

            # =======================================================
            # BƯỚC 1: XỬ LÝ VÀ "ÉP" HOME ASSISTANT HIỆN ATTRIBUTES
            # =======================================================
            if self._device_key == "api_trip_route":
                self._attr_extra_state_attributes = {"route_points": self.api._last_data.get("api_trip_route", "[]")}
                
            elif self._device_key == "api_nearby_stations":
                try: self._attr_extra_state_attributes = {"stations": json.loads(self.api._last_data.get("api_nearby_stations", "[]"))}
                except: self._attr_extra_state_attributes = {"stations": []}
                
            # ĐÂY LÀ CHỖ TẠO MẢNG CHO DEBUG RAW DATA
            elif self._device_key == "api_debug_raw":
                try:
                    log_str = self.api._last_data.get("api_debug_changelog_json", "[]")
                    raw_list = json.loads(log_str)
                    
                    # Biến mảng JSON (dict) thành mảng Chuỗi (List of Strings)
                    formatted_list = []
                    for item in raw_list:
                        time_str = item.get("time", "").split(" ")[1] if " " in item.get("time", "") else item.get("time", "")
                        code = item.get("code", "")
                        old_v = item.get("old_value", "")
                        new_v = item.get("new_value", "")
                        
                        # Format đúng như ý bạn: "Time | Code : Old -> New"
                        formatted_list.append(f"{time_str} | {code} : {old_v} ➔ {new_v}")
                        
                    self._attr_extra_state_attributes = {
                        "Lịch sử mã thay đổi": formatted_list if formatted_list else ["Đang chờ nhận tín hiệu..."]
                    }
                except Exception as e:
                    self._attr_extra_state_attributes = {"Lỗi": str(e)}

            elif self._device_key == "api_best_efficiency_band":
                attrs = {}
                stats = getattr(self.api, '_eff_stats', {})
                for k, v in stats.items():
                    if v["drops"] > 0:
                        attrs[f"Dải {k} km/h"] = f"{round(v['dist'] / v['drops'], 2)} km/1%"
                self._attr_extra_state_attributes = attrs if attrs else {"Trạng thái": "Hệ thống đang đợi % pin sụt giảm..."}
            # =======================================================

            # =======================================================
            # BƯỚC 2: XỬ LÝ TRẠNG THÁI HIỂN THỊ CHÍNH (STATE)
            # =======================================================
            if self._device_key == "api_trip_route":
                try: 
                    pts = json.loads(val)
                    self._attr_native_value = f"{len(pts)} điểm"
                except: 
                    self._attr_native_value = "Đang thu thập"
                self.async_write_ha_state()
                return
                
            if self._device_key == "api_nearby_stations":
                try: 
                    sts = json.loads(val)
                    self._attr_native_value = f"{len(sts)} trạm"
                except: 
                    self._attr_native_value = "Chưa có dữ liệu"
                self.async_write_ha_state()
                return

            if self._device_key == "api_debug_raw":
                self._attr_native_value = str(val)[:255] if val else "Đang khởi động..."
                self.async_write_ha_state()
                return

            if self._device_key in ["api_total_charge_cost", "api_total_charge_cost_est", "api_trip_charge_cost", "api_total_gas_cost", "api_trip_gas_cost"]:
                try: val = round(float(val), 0)
                except (ValueError, TypeError): val = 0
            elif self._device_key in [
                "api_static_capacity", "api_static_range", "api_battery_degradation", 
                "api_lifetime_efficiency", "api_calc_max_range", "api_calc_remain_range", 
                "api_calc_range_per_percent", "api_last_charge_energy", 
                "api_last_charge_power", "api_last_charge_efficiency",
                "api_est_range_degradation", "api_trip_avg_speed", 
                "api_trip_energy_used", "api_trip_efficiency"
            ]:
                try: val = round(float(val), 2)
                except (ValueError, TypeError): val = 0
            elif self._device_key in ["api_last_charge_duration", "api_last_charge_start_soc", "api_last_charge_end_soc"]:
                try: val = round(float(val), 0)
                except (ValueError, TypeError): val = 0
            elif self._device_key in ["10351_00001_00050", "10351_00002_00050", "10351_00003_00050", "10351_00004_00050", "10351_00005_00050", "10351_00006_00050"]:
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
            elif "Áp suất lốp" in self.name and val is not None and isinstance(val, (int, float, str)):
                try:
                    num = float(val)
                    if num > 10: val = round(num / 100, 1)
                except: pass

            self._attr_native_value = val
            self.async_write_ha_state()