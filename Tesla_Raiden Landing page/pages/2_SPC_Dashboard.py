import runpy
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent

runpy.run_path(
    str(base_dir / "SPC_DASHBOARD.py"),
    run_name="__main__"
)