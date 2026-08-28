"""Background consolidation worker so the UI never blocks on large parses."""

import logging

from PySide6.QtCore import QThread, Signal

from spc_core.consolidation import run_consolidation

log = logging.getLogger("spc_app.consolidator")


class ConsolidationWorker(QThread):
    progress = Signal(str)
    succeeded = Signal(int, int)
    failed = Signal(str)

    def __init__(self, root: str, csv_path: str, db_path: str, parent=None):
        super().__init__(parent)
        self._root, self._csv_path, self._db_path = root, csv_path, db_path

    def run(self):
        self.progress.emit(f"Scanning {self._root} for *Data*.tdf files...")
        state = {"last": 0}

        def report(done, total, filename):
            step = max(1, total // 25)
            if done == total or done - state["last"] >= step or state["last"] == 0:
                state["last"] = done
                self.progress.emit(f"Parsing {filename} ({done}/{total})...")

        try:
            files, rows = run_consolidation(self._root, self._csv_path, self._db_path,
                                            progress_cb=report)
        except Exception as ex:
            log.exception("Consolidation failed")
            self.failed.emit(str(ex))
            return
        self.progress.emit(f"Parsed {rows:,} rows across {files} TDF file(s).")
        self.succeeded.emit(files, rows)
