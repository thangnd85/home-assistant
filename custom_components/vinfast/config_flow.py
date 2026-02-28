import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .api import VinFastAPI

_LOGGER = logging.getLogger(__name__)

class VinFastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Xử lý luồng cài đặt qua giao diện người dùng."""
    VERSION = 1

    def __init__(self):
        self.email = None
        self.password = None
        self.vehicles_dict = {}

    async def async_step_user(self, user_input=None):
        """Bước 1: Nhập Email và Password."""
        errors = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]

            api = VinFastAPI(self.email, self.password)
            try:
                # Thử đăng nhập
                await self.hass.async_add_executor_job(api.login)
                # Lấy danh sách xe
                vehicles = await self.hass.async_add_executor_job(api.get_vehicles)
                
                if not vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    # Tạo dictionary dạng { "VIN": "Tên xe (Biển số/VIN)" }
                    self.vehicles_dict = {
                        v["vinCode"]: f"{v.get('vehicleName', 'Xe VinFast')} ({v.get('vinCode')})"
                        for v in vehicles
                    }
                    
                    # Chuyển sang bước chọn xe
                    return await self.async_step_select_vehicle()

            except Exception as e:
                _LOGGER.error(f"Lỗi đăng nhập VinFast: {e}")
                errors["base"] = "auth_error"

        # Vẽ form đăng nhập
        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors
        )

    async def async_step_select_vehicle(self, user_input=None):
        """Bước 2: Chọn xe nếu có nhiều xe."""
        if user_input is not None:
            selected_vin = user_input["vin"]
            vehicle_name = self.vehicles_dict[selected_vin]

            # Lưu cấu hình và kết thúc
            return self.async_create_entry(
                title=vehicle_name,
                data={
                    CONF_EMAIL: self.email,
                    CONF_PASSWORD: self.password,
                    "vin": selected_vin,
                    "vehicle_name": vehicle_name
                }
            )

        # Vẽ form chọn xe (Dạng Dropdown List)
        data_schema = vol.Schema({
            vol.Required("vin"): vol.In(self.vehicles_dict)
        })

        return self.async_show_form(
            step_id="select_vehicle", 
            data_schema=data_schema
        )