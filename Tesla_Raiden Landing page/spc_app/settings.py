"""Persisted user session settings for the SPC desktop app.

Stores a small JSON document under the writable application-data directory
(paths.default_output_dir) so the app can restore the last DB connection,
source paths, and filter choices across launches. Kept free of Qt imports
so the logic stays unit-testable.
"""

import json
import logging
from pathlib import Path

from spc_app.paths import default_output_dir

log = logging.getLogger("spc_app.settings")

SETTINGS_FILENAME = "settings.json"


def settings_file() -> Path:
    return default_output_dir() / SETTINGS_FILENAME


def load_settings() -> dict:
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.warning("Could not read settings file", exc_info=True)
        return {}


def save_settings(settings: dict) -> bool:
    try:
        settings_file().write_text(
            json.dumps(settings, indent=2, default=str), encoding="utf-8")
        return True
    except OSError:
        log.warning("Could not write settings file", exc_info=True)
        return False
