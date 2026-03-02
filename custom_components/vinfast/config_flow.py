import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, VEHICLE_SPECS

def safe_int(val, default):
    try: return int(float(val))
    except (ValueError, TypeError): return default

def safe_float(val, default):
    try: return float(val)
    except (ValueError, TypeError): return default

class VinFastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return VinFastOptionsFlowHandler(config_entry)


class VinFastOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Đọc dữ liệu xe để cung cấp Default xịn nhất cho người dùng
        domain_data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
        api = domain_data.get("api")
        
        fallback_ev = 0.15
        fallback_gas = 15.0
        
        if api and hasattr(api, "vehicle_model_display"):
            model = api.vehicle_model_display.upper()
            for k, v in VEHICLE_SPECS.items():
                if k.replace(" ", "") in model.replace(" ", ""):
                    fallback_ev = v.get("ev_kwh_per_km", 0.15)
                    fallback_gas = v.get("gas_km_per_liter", 15.0)
                    break

        opts = self._config_entry.options
        
        cost_per_kwh = safe_int(opts.get("cost_per_kwh"), 4000)
        gas_price = safe_int(opts.get("gas_price"), 20000)
        
        # Nếu chưa từng cấu hình, sẽ lấy số liệu động từ xe
        ev_kwh_per_km = safe_float(opts.get("ev_kwh_per_km"), fallback_ev)
        gas_km_per_liter = safe_float(opts.get("gas_km_per_liter"), fallback_gas)

        options_schema = vol.Schema({
            vol.Required("cost_per_kwh", default=cost_per_kwh): vol.Coerce(int),
            vol.Required("ev_kwh_per_km", default=ev_kwh_per_km): vol.Coerce(float),
            vol.Required("gas_price", default=gas_price): vol.Coerce(int),
            vol.Required("gas_km_per_liter", default=gas_km_per_liter): vol.Coerce(float),
        })
        
        return self.async_show_form(step_id="init", data_schema=options_schema)
