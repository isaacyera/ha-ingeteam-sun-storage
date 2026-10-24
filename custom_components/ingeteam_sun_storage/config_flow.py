"""Config flow for the Ingeteam Sun Storage integration."""

from typing import Any

from modbus_connection import ModbusError
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_READ_BATTERY,
    CONF_READ_METER,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .helpers import NotIngeteamError, async_probe, create_modbus_params, flag

OPTIONS = {
    probatio.Required(CONF_READ_METER, default=False): BooleanSelector(),
    probatio.Required(CONF_READ_BATTERY, default=False): BooleanSelector(),
}

STEP_USER = probatio.Schema(
    {
        probatio.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
            ),
            probatio.Coerce(int),
        ),
        **OPTIONS,
    }
)

STEP_OPTIONS = probatio.Schema(OPTIONS)


class IngeteamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an Ingeteam Sun Storage inverter."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "IngeteamOptionsFlow":
        """Return the options flow."""
        return IngeteamOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the inverter's address and check that it answers."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                **user_input,
                CONF_NAME: user_input[CONF_NAME].strip() or DEFAULT_NAME,
                # One connection is shared per host and port, so spelling matters.
                CONF_HOST: user_input[CONF_HOST].strip().lower(),
            }
            await self.async_set_unique_id(
                f"{data[CONF_HOST]}:{data[CONF_PORT]}:{data[CONF_UNIT_ID]}"
            )
            self._abort_if_unique_id_configured()

            try:
                async with async_get_temporary_unit(
                    self.hass, create_modbus_params(data), data[CONF_UNIT_ID]
                ) as unit:
                    await async_probe(unit)
            except HomeAssistantError:
                errors["base"] = "link_settings_in_use"
            except ModbusError:
                errors["base"] = "cannot_connect"
            except NotIngeteamError:
                errors["base"] = "unknown_device"
            else:
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER, user_input),
            errors=errors,
        )


class IngeteamOptionsFlow(OptionsFlowWithReload):
    """Switch the optional meter and battery on or off."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {
            key: flag(self.config_entry, key)
            for key in (CONF_READ_METER, CONF_READ_BATTERY)
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(STEP_OPTIONS, current),
        )
