import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN, CONF_EMAIL, CONF_PASSWORD,
    DEFAULT_COST_PER_KWH, DEFAULT_EV_KWH_PER_KM, 
    DEFAULT_GAS_PRICE, DEFAULT_GAS_KM_PER_LITER
)

class VinFastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional("cost_per_kwh", default=self.config_entry.options.get("cost_per_kwh", DEFAULT_COST_PER_KWH)): int,
            vol.Optional("ev_kwh_per_km", default=self.config_entry.options.get("ev_kwh_per_km", DEFAULT_EV_KWH_PER_KM)): float,
            vol.Optional("gas_price", default=self.config_entry.options.get("gas_price", DEFAULT_GAS_PRICE)): int,
            vol.Optional("gas_km_per_liter", default=self.config_entry.options.get("gas_km_per_liter", DEFAULT_GAS_KM_PER_LITER)): float,
        })
        return self.async_show_form(step_id="init", data_schema=options_schema)
