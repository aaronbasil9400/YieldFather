"""Path resolution for packaged vs development runs.

Bundled resources live next to the executable (PyInstaller onedir layout);
user-writable data goes under the OS application-data directory, never beside
a protected executable (PORTABILITY_PLAN.md Phase 2 rule).
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundled_assets_dir() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "assets"
        return Path(sys.executable).resolve().parent / "_internal" / "assets"
    return PROJECT_ROOT / "assets"


def default_output_dir() -> Path:
    if is_frozen():
        base = Path(os.environ.get("APPDATA") or Path.home()) / "FactoryAnalyticsHub" / "SPC"
    else:
        base = PROJECT_ROOT / "output_data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_log_file() -> Path:
    d = default_output_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "spc_app.log"
