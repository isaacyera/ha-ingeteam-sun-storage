"""Constants for the Ingeteam Sun Storage integration."""

from datetime import timedelta
import logging

DOMAIN = "ingeteam_sun_storage"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID = "unit_id"
CONF_READ_METER = "read_meter"
CONF_READ_BATTERY = "read_battery"

DEFAULT_NAME = "ingeteam"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# Entity groups. The meter and the battery are optional hardware, so they are
# switched on in the options and their registers are only read when they are.
GROUP_CORE = "core"
GROUP_METER = "meter"
GROUP_BATTERY = "battery"

# Waited out after a pass finishes. Each request is held back by the one-second
# spacing Ingeteam asks for, so a pass takes about as many seconds as requests.
SCAN_INTERVAL = timedelta(seconds=5)

# Energy is not integrated across a longer silence than this.
MAX_INTEGRATION_GAP = 600
