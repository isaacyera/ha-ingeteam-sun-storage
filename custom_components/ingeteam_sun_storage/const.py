"""Constants for the Ingeteam Sun Storage integration."""

from datetime import timedelta
import logging

DOMAIN = "ingeteam_sun_storage"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID = "unit_id"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# Waited out after a pass finishes. A pass is nine requests, each held back by
# the one-second spacing Ingeteam asks for, so values refresh about every 15 s.
SCAN_INTERVAL = timedelta(seconds=5)
