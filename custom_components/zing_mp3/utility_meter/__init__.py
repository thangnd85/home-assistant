"""Support for tracking consumption over given periods of time."""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (ATTR_ENTITY_ID, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from .const import (
    DOMAIN, SIGNAL_RESET_METER, METER_TYPES, METER_MODES, CONF_SOURCE_SENSOR, DEFAULT,
    CONF_METER_TYPE, CONF_METER_MODE, CONF_METER_OFFSET, CONF_METER_NET_CONSUMPTION,
    CONF_TARIFF_ENTITY, CONF_TARIFF, CONF_TARIFFS, CONF_METER, DATA_UTILITY,
    SERVICE_RESET, SERVICE_SELECT_TARIFF, SERVICE_SELECT_NEXT_TARIFF,
    ATTR_TARIFF)

_LOGGER = logging.getLogger(__name__)

TARIFF_ICON = 'mdi:clock-outline'

ATTR_TARIFFS = 'tariffs'

DEFAULT_OFFSET = timedelta(hours=0)

SERVICE_METER_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SELECT_TARIFF_SCHEMA = SERVICE_METER_SCHEMA.extend({
    vol.Required(ATTR_TARIFF): cv.string
})

METER_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_METER_TYPE): vol.In(METER_TYPES),
    vol.Optional(CONF_METER_MODE, default=DEFAULT): vol.In(METER_MODES),    
    vol.Optional(CONF_METER_OFFSET, default=DEFAULT_OFFSET):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_METER_NET_CONSUMPTION, default=False): cv.boolean,
    vol.Optional(CONF_TARIFFS, default=[]): vol.All(
        cv.ensure_list, [cv.string]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: METER_CONFIG_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up an Utility Meter."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    hass.data[DATA_UTILITY] = {}
    register_services = False

    for meter, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, meter)

        hass.data[DATA_UTILITY][meter] = conf

        if not conf[CONF_TARIFFS]:
            # only one entity is required
            hass.async_create_task(discovery.async_load_platform(
                hass, SENSOR_DOMAIN, DOMAIN,
                [{CONF_METER: meter, CONF_NAME: meter}], config))
        else:
            # create tariff selection
            await component.async_add_entities([
                TariffSelect(meter, list(conf[CONF_TARIFFS]))
            ])
            hass.data[DATA_UTILITY][meter][CONF_TARIFF_ENTITY] =\
                "{}.{}".format(DOMAIN, meter)

            # add one meter for each tariff
            tariff_confs = []
            for tariff in conf[CONF_TARIFFS]:
                tariff_confs.append({
                    CONF_METER: meter,
                    CONF_NAME: "{} {}".format(meter, tariff),
                    CONF_TARIFF: tariff,
                    })
            hass.async_create_task(discovery.async_load_platform(
                hass, SENSOR_DOMAIN, DOMAIN, tariff_confs, config))
            register_services = True

    if register_services:
        component.async_register_entity_service(
            SERVICE_RESET, SERVICE_METER_SCHEMA,
            'async_reset_meters'
        )

        component.async_register_entity_service(
            SERVICE_SELECT_TARIFF, SERVICE_SELECT_TARIFF_SCHEMA,
            'async_select_tariff'
        )

        component.async_register_entity_service(
            SERVICE_SELECT_NEXT_TARIFF, SERVICE_METER_SCHEMA,
            'async_next_tariff'
        )

    return True


class TariffSelect(RestoreEntity):
    """Representation of a Tariff selector."""

    def __init__(self, name, tariffs):
        """Initialize a tariff selector."""
        self._name = name
        self._current_tariff = None
        self._tariffs = tariffs
        self._icon = TARIFF_ICON

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self._current_tariff is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self._tariffs:
            self._current_tariff = self._tariffs[0]
        else:
            self._current_tariff = state.state

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the select input."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_tariff

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_TARIFFS: self._tariffs,
        }

    async def async_reset_meters(self):
        """Reset all sensors of this meter."""
        _LOGGER.debug("reset meter %s", self.entity_id)
        async_dispatcher_send(self.hass, SIGNAL_RESET_METER,
                              self.entity_id)

    async def async_select_tariff(self, tariff):
        """Select new option."""
        if tariff not in self._tariffs:
            _LOGGER.warning('Invalid tariff: %s (possible tariffs: %s)',
                            tariff, ', '.join(self._tariffs))
            return
        self._current_tariff = tariff
        await self.async_update_ha_state()

    async def async_next_tariff(self):
        """Offset current index."""
        current_index = self._tariffs.index(self._current_tariff)
        new_index = (current_index + 1) % len(self._tariffs)
        self._current_tariff = self._tariffs[new_index]
        await self.async_update_ha_state()
