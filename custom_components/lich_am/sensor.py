"""Lich Am sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .__init__ import LichAmDataUpdateCoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="lunar_date",
        name="Ngày âm",
        icon="mdi:calendar-month",
    ),
    SensorEntityDescription(
        key="lunar_text_today",
        name="Hôm nay",
        icon="mdi:calendar-today",
    ),
    SensorEntityDescription(
        key="lunar_date_next",
        name="Âm lịch ngày mai",
        icon="mdi:calendar-arrow-right",
    ),
    SensorEntityDescription(
        key="lunar_text_next",
        name="Ngày mai",
        icon="mdi:calendar-end",
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lich Am sensors using the coordinator."""
    coordinator: LichAmDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        LichAmSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)

class LichAmSensor(CoordinatorEntity[LichAmDataUpdateCoordinator], SensorEntity):
    """Lich Am Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LichAmDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"lich_am_{description.key}"
        # Thêm thông tin thiết bị để gom nhóm trong giao diện
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "main_service")},
            "name": "Lịch Âm Việt Nam",
            "manufacturer": "Custom Component",
            "model": "Thuật toán Hồ Ngọc Đức",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None