"""Constants for the Ingeteam Sun Storage integration."""

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

# Seconds from the start of one refresh to the start of the next. A refresh
# cannot take less than about a second per request, because every request waits
# the one-second spacing Ingeteam asks for, so a shorter interval is simply
# followed as closely as the requests allow (see registers.minimum_period).
# The default keeps the 10 second cadence of the earlier integration.
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300

# Shown where the exact floor is not known yet (first setup). A test checks it
# against the smallest and largest request counts.
TYPICAL_REFRESH = "6 to 9"

# Energy is not integrated across a longer silence than this.
MAX_INTEGRATION_GAP = 600
