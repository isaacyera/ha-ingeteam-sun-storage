"""Config flow for the Ingeteam Sun Storage integration."""

from typing import Any

from modbus_connection import ModbusError
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN
from .helpers import NotIngeteamError, async_probe, create_modbus_params

STEP_USER = probatio.Schema(
    {
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
    }
)


class IngeteamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an Ingeteam Sun Storage inverter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the inverter's address and check that it answers."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # One connection is shared per host and port, so spelling matters.
            data = {**user_input, CONF_HOST: user_input[CONF_HOST].strip().lower()}
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
                return self.async_create_entry(
                    title=f"Ingeteam {data[CONF_HOST]}", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER, user_input),
            errors=errors,
        )
