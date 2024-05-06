"""
Configuration handling of the integration driver.

:copyright: (c) by Ian Campbell.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from dataclasses import dataclass
from typing import Optional

_LOG = logging.getLogger(__name__)

_CFG_FILENAME = "config.json"


@dataclass
class MythTVDevice:
    """MythTV device configuration."""

    id: str
    """Unique identifier of the device."""
    name: str
    """Friendly name of the device."""
    address: str
    """Hostname or IP address of device."""
    port: Optional[int] = None
    """Optional port number for Frontend service API"""
