"""
Facility configuration modules for lab report parsing.
Each module defines regex patterns and extraction logic for a specific medical facility.
"""

from .base_config import FacilityConfig
from .rcb_config import RCBConfig
from .kpa_config import KPAConfig
from .mhb_config import MHBConfig

# Registry of all facility configs
FACILITY_CONFIGS = [
    RCBConfig(),
    KPAConfig(),
    MHBConfig(),
]

def get_config_for_filename(filename: str) -> FacilityConfig | None:
    """Return the appropriate facility config based on filename patterns."""
    for config in FACILITY_CONFIGS:
        if config.matches_filename(filename):
            return config
    return None

__all__ = [
    'FacilityConfig',
    'RCBConfig',
    'KPAConfig',
    'MHBConfig',
    'FACILITY_CONFIGS',
    'get_config_for_filename',
]
