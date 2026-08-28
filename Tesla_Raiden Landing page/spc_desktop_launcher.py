"""PyInstaller entry point for the FLEX Dragon SPC desktop app."""

import os
import sys

from spc_app import main as app_main

if __name__ == "__main__":
    if os.environ.get("SPC_APP_SMOKE") == "1":
        sys.exit(app_main.run_packaged_selftest())
    app_main.main()
