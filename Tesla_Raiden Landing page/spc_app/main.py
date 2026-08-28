"""FLEX - Teradyne UltraFlexPlus Dragon SPC Dashboard, desktop edition.

PySide6 front end over the shared spc_core package. Replicates the Streamlit
dashboard: source control with background consolidation, TestNb/TestLabel
selection plus slicers, KPI cards, control chart, histogram, Cpk-by-group
table, and raw filtered data with CSV export.
"""

import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import spc_app.reporting as reporting
from spc_core.consolidation import TABLE
from spc_core.query import (
    build_where_clause,
    connect,
    get_columns,
    get_dataset_summary,
    query_filtered,
)
from spc_core.stats import compute_stats
from spc_app import paths
from spc_app import settings
from spc_app import theme
from spc_app.charts import build_control_chart, build_histogram, clear_chart, configure_plot
from spc_app.workers import ConsolidationWorker
from spc_app.widgets import CpkByGroupTab, FilterPanel, KpiRow, RawDataTab, SourcePanel

WINDOW_TITLE = "FLEX - Teradyne UltraFlexPlus Dragon SPC Dashboard"

log = logging.getLogger("spc_app")


def _make_banner() -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background: rgba(245, 158, 11, 0.15);"
        " border: 1px solid rgba(245, 158, 11, 0.5); border-radius: 8px; }"
        "QLabel { color: #7C4A03; font-weight: 600; border: none; }"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 6, 12, 6)
    label = QLabel()
    label.setWordWrap(True)
    layout.addWidget(label)
    frame.hide()
    return frame, label


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        icon_path = paths.bundled_assets_dir() / "logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.conn = None
        self.columns = []
        self.worker = None
        self._last_db_path = ""
        self._last_eval = None

        self.source_panel = SourcePanel()
        self.filter_panel = FilterPanel()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.source_panel)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: rgba(128,128,128,0.3);")
        left_layout.addWidget(separator)
        left_layout.addWidget(self.filter_panel)
        left_layout.addStretch(1)
        left_scroll.setWidget(left_container)

        self.kpi_row = KpiRow()
        self.control_chart = pg.PlotWidget()
        configure_plot(self.control_chart)
        self.histogram_chart = pg.PlotWidget()
        configure_plot(self.histogram_chart)
        self._palette = theme.LIGHT

        def _reset_view(plot_widget):
            vb = plot_widget.getPlotItem().getViewBox()
            vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
            vb.autoRange()

        self.cpk_tab = CpkByGroupTab()
        self.raw_tab = RawDataTab()

        control_header = QWidget()
        control_header_layout = QHBoxLayout(control_header)
        control_header_layout.setContentsMargins(0, 0, 0, 0)
        section_title = QLabel("SPC Control Chart")
        self.control_title = section_title
        self.control_reset_button = QPushButton("Reset view")
        self.control_reset_button.setToolTip("Zoom the control chart back out to all data.")
        self.control_reset_button.clicked.connect(lambda: _reset_view(self.control_chart))
        control_header_layout.addWidget(section_title)
        control_header_layout.addStretch(1)
        control_header_layout.addWidget(self.control_reset_button)

        hist_container = QWidget()
        hist_layout = QVBoxLayout(hist_container)
        hist_layout.setContentsMargins(0, 0, 0, 0)
        hist_header_layout = QHBoxLayout()
        hist_title = QLabel("Distribution / Histogram")
        self.hist_title = hist_title
        self.hist_reset_button = QPushButton("Reset view")
        self.hist_reset_button.setToolTip("Zoom the histogram back out to all data.")
        self.hist_reset_button.clicked.connect(lambda: _reset_view(self.histogram_chart))
        hist_header_layout.addWidget(hist_title)
        hist_header_layout.addStretch(1)
        hist_header_layout.addWidget(self.hist_reset_button)
        hist_layout.addLayout(hist_header_layout)
        hist_layout.addWidget(self.histogram_chart, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(hist_container, "Distribution / Histogram")
        self.tabs.addTab(self.cpk_tab, "Cpk by group")
        self.tabs.addTab(self.raw_tab, "Raw filtered data")

        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(control_header)
        chart_layout.addWidget(self.control_chart, 1)

        results_split = QSplitter(Qt.Vertical)
        results_split.addWidget(chart_container)
        results_split.addWidget(self.tabs)
        results_split.setSizes([420, 320])

        self.warning_banner, self.warning_label = _make_banner()

        kpi_title = QLabel("Key Statistics")
        self.kpi_title = kpi_title

        self.results_widget = QWidget()
        results_layout = QVBoxLayout(self.results_widget)
        results_layout.setContentsMargins(12, 8, 12, 8)
        results_layout.addWidget(kpi_title)
        results_layout.addWidget(self.kpi_row)
        results_layout.addWidget(self.warning_banner)
        results_layout.addWidget(results_split, 1)

        self.info_page = QLabel(
            "Enter paths and run the Log Consolidator, or connect to an existing "
            "results.db to begin.\n\nThen select a TestNb (broad) or a TestNb/TestLabel "
            "pair (fine control) to populate the evaluation engine matrix.")
        self.info_page.setAlignment(Qt.AlignCenter)
        self.info_page.setWordWrap(True)
        self.info_page.setStyleSheet("color: #64748B; font-size: 14px;")

        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.info_page)
        self.right_stack.addWidget(self.results_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_scroll)
        splitter.addWidget(self.right_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 1000])
        self.setCentralWidget(splitter)

        status = self.statusBar()
        self.status_provenance = QLabel("")
        self.status_summary = QLabel("")
        status.addPermanentWidget(self.status_provenance)
        status.addPermanentWidget(self.status_summary)

        self.source_panel.consolidate_requested.connect(self.start_consolidation)
        self.source_panel.db_selected.connect(self.load_db_file)
        self.filter_panel.filtersChanged.connect(self.refresh_results)

        export_bar = QToolBar("Export")
        export_bar.setMovable(False)
        export_bar.addAction("Control chart (PNG)",
                             lambda: self._export_chart_png(self.control_chart,
                                                            "control_chart.png"))
        export_bar.addAction("Histogram (PNG)",
                             lambda: self._export_chart_png(self.histogram_chart,
                                                            "histogram.png"))
        export_bar.addAction("Full report",
                             lambda: self._export_full_report())
        export_bar.addSeparator()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(theme.THEME_MODES))
        self.theme_combo.setToolTip(
            "App appearance. 'System' follows the Windows personalization setting.")
        self.theme_combo.currentTextChanged.connect(lambda _mode: self._apply_theme())
        export_bar.addWidget(QLabel("Theme:"))
        export_bar.addWidget(self.theme_combo)
        self.addToolBar(export_bar)

        self._set_controls_enabled(False)
        self.resize(1400, 900)
        self._restore_session()

    def _set_controls_enabled(self, enabled: bool):
        self.filter_panel.setEnabled(enabled)

    def start_consolidation(self, root: str, csv_path: str, db_path: str):
        if not Path(root).exists():
            QMessageBox.critical(self, "Consolidator",
                                 f"Specified TDF Root folder path does not exist!\n{root}")
            return
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        self.source_panel.set_running(True)
        self.source_panel.show_progress(f"Scanning {root} for *Data*.tdf files...")
        self.worker = ConsolidationWorker(root, csv_path, db_path)
        self.worker.progress.connect(self.source_panel.show_progress)
        self.worker.succeeded.connect(lambda files, rows: self.on_consolidated(db_path))
        self.worker.failed.connect(self.on_consolidation_failed)
        self.worker.finished.connect(self._worker_cleanup)
        self.worker.start()

    def _worker_cleanup(self):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def on_consolidated(self, db_path: str):
        self.source_panel.set_running(False)
        self.source_panel.show_progress("Consolidation complete.")
        try:
            self.load_db_file(db_path)
        except Exception as ex:
            log.exception("Loading consolidated DB failed")
            QMessageBox.critical(self, "Load DB", f"Could not load {db_path}:\n{ex}")

    def on_consolidation_failed(self, message: str):
        self.source_panel.set_running(False)
        self.source_panel.show_progress("Consolidation failed.")
        QMessageBox.critical(self, "Consolidator", f"Execution terminated:\n{message}")

    def load_db_file(self, db_path: str):
        db_file = Path(db_path).expanduser().resolve()
        if not db_file.exists():
            QMessageBox.critical(self, "Load DB", f"DB file not found:\n{db_file}")
            return
        conn = connect(db_file)
        columns = get_columns(conn)
        if not columns:
            conn.close()
            QMessageBox.critical(
                self, "Load DB",
                f"No '{TABLE}' table found — is this a valid consolidated results DB?")
            return
        if self.conn is not None:
            self.conn.close()
        self.conn = conn
        self.columns = columns
        summary = get_dataset_summary(conn)
        self.filter_panel.populate(conn, columns)
        self.filter_panel.set_summary(summary)
        suffix = f" · {summary['total_rows']:,} rows" if summary else ""
        self.status_summary.setText(f"Connected: {db_file.name}{suffix}")
        self._show_provenance(conn)
        self._set_controls_enabled(True)
        self.right_stack.setCurrentWidget(self.results_widget)
        self.refresh_results()

    def _show_provenance(self, conn):
        try:
            row = conn.execute(
                "SELECT created_utc, source_root, parser_version FROM consolidation_meta "
                "ORDER BY rowid DESC LIMIT 1").fetchone()
        except sqlite3.Error:
            row = None
        if row:
            self.status_provenance.setText(
                f"parser v{row[2]} · built {row[0]} · source {Path(row[1]).name}")
        else:
            self.status_provenance.setText("")

    def refresh_results(self):
        if self.conn is None:
            return
        filters, or_clauses, has_selection = self.filter_panel.selection()
        if not has_selection:
            self._clear_results()
            self._set_warning(None)
            self.right_stack.setCurrentWidget(self.results_widget)
            self.statusBar().showMessage("Select a TestNb (broad) or a TestNb/TestLabel pair "
                                         "(fine control) within the sidebar to populate the "
                                         "evaluation engine matrix.")
            return

        where_sql, params = build_where_clause(filters, or_clauses)
        df = query_filtered(self.conn, where_sql, params, int(self.filter_panel.row_cap.value()))
        df = df.dropna(subset=["Value_num"])
        if df.empty:
            self._clear_results()
            self._set_warning("No rows match the current filter selection.")
            return

        group_cols = [c for c in ["TestNb", "Channel"] if df[c].nunique() > 1]
        if group_cols:
            joined = ", ".join(group_cols)
            self._set_warning("Warning: Selected filters cross-reference multiple distinct "
                              f"values across {joined} variations.")
        else:
            self._set_warning(None)

        lsl_series = df["LowLim_num"].dropna()
        usl_series = df["HighLim_num"].dropna()
        lsl = float(lsl_series.iloc[0]) if len(lsl_series) else None
        usl = float(usl_series.iloc[0]) if len(usl_series) else None
        stats = compute_stats(df["Value_num"].to_numpy(dtype=float), lsl, usl)
        pass_pct = (100.0 * (df["Result"].str.upper() == "PASS").mean()
                    if "Result" in df else float("nan"))

        title = (f"{df['TestStep'].iloc[0]} | TestNb {df['TestNb'].iloc[0]} | "
                 f"{df['TestLabel'].iloc[0]}")
        self._last_eval = {"stats": stats, "pass_pct": pass_pct, "title": title,
                           "lsl": lsl, "usl": usl}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.kpi_row.update_stats(stats, pass_pct)
            build_control_chart(self.control_chart, df, stats, lsl, usl, title,
                                hover_callback=self._show_hover,
                                title_color=self._palette["plot_fg"])
            build_histogram(self.histogram_chart, df["Value_num"].to_numpy(dtype=float),
                            lsl, usl, stats["Mean"],
                            title_color=self._palette["plot_fg"])
            self.cpk_tab.update_groups(df, group_cols)
            self.raw_tab.set_dataframe(df)
        finally:
            QApplication.restoreOverrideCursor()

    def _clear_results(self):
        self._last_eval = None
        self.kpi_row.clear()
        clear_chart(self.control_chart)
        clear_chart(self.histogram_chart)
        self.cpk_tab.table.model().set_dataframe(pd.DataFrame())
        self.raw_tab.set_dataframe(pd.DataFrame())

    def _set_warning(self, text):
        if text is None:
            self.warning_banner.hide()
        else:
            self.warning_label.setText(text)
            self.warning_banner.show()

    def _show_hover(self, text):
        self.statusBar().showMessage(text.replace("\n", " | "), 4000)

    def _apply_theme(self):
        mode = self.theme_combo.currentText()
        self._palette = theme.resolve_palette(mode)
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setPalette(theme.build_app_palette(self._palette))
        self.kpi_row.apply_palette(self._palette)
        self.warning_banner.setStyleSheet(theme.banner_qss(self._palette))
        p = self._palette
        for title in (self.control_title, self.hist_title, self.kpi_title):
            title.setStyleSheet(f"font-weight: 700; color: {p['text']};")
        self.info_page.setStyleSheet(f"color: {p['muted']}; font-size: 14px;")
        configure_plot(self.control_chart, p["plot_bg"], p["plot_fg"], p["plot_axis"])
        configure_plot(self.histogram_chart, p["plot_bg"], p["plot_fg"],
                       p["plot_axis"])
        self.refresh_results()

    def closeEvent(self, event):
        self._save_session()
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        super().closeEvent(event)

    def _save_session(self):
        try:
            settings.save_settings({
                "mode_index": self.source_panel.mode_combo.currentIndex(),
                "tdf_root": self.source_panel.tdf_root.text(),
                "output_dir": self.source_panel.output_dir.text(),
                "last_db": self._last_db_path,
                "row_cap": self.filter_panel.row_cap.value(),
                "theme_mode": self.theme_combo.currentText(),
                "selection": self.filter_panel.selection_state(),
            })
        except Exception:
            log.exception("Saving session settings failed")

    def _restore_session(self):
        cfg = settings.load_settings()
        if not isinstance(cfg, dict) or not cfg:
            self._apply_theme()
            return
        theme_mode = cfg.get("theme_mode")
        if theme_mode in theme.THEME_MODES:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(theme_mode)
            self.theme_combo.blockSignals(False)
        self._apply_theme()
        mode_index = cfg.get("mode_index")
        if mode_index in (0, 1):
            self.source_panel.mode_combo.setCurrentIndex(int(mode_index))
        for key, picker in (("tdf_root", self.source_panel.tdf_root),
                            ("output_dir", self.source_panel.output_dir)):
            value = cfg.get(key)
            if value:
                picker.edit.setText(str(value))
        row_cap = cfg.get("row_cap")
        if row_cap:
            self.filter_panel.row_cap.setValue(int(row_cap))
        db_path = cfg.get("last_db")
        if not db_path or not Path(db_path).exists():
            return
        try:
            self.load_db_file(db_path)
            selection = cfg.get("selection")
            if selection:
                self.filter_panel.apply_selection(selection)
        except Exception:
            log.exception("Auto-reconnect to last DB failed")

    def _export_chart_png(self, plot_widget, suggested_name: str):
        path, _ = QFileDialog.getSaveFileName(self, "Export chart as PNG",
                                              suggested_name,
                                              "PNG images (*.png);;All files (*)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = plot_widget.grab().save(path, "PNG")
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            self.statusBar().showMessage(f"Chart exported: {path}", 5000)
        else:
            QMessageBox.critical(self, "Export chart",
                                 f"Could not write PNG file:\n{path}")

    def _export_full_report(self):
        df = self.raw_tab.table.model().dataframe()
        if df is None or df.empty or not self._last_eval:
            QMessageBox.information(
                self, "Export report",
                "No evaluation results to export.\n"
                "Select a TestNb or TestNb/TestLabel pair first.")
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Select report output folder")
        if not out_dir:
            return
        evaluation = self._last_eval
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            control_png = Path(out_dir) / "control_chart.png"
            hist_png = Path(out_dir) / "histogram.png"
            ok_control = self.control_chart.grab().save(str(control_png), "PNG")
            ok_hist = self.histogram_chart.grab().save(str(hist_png), "PNG")
            cpk_df = self.cpk_tab.table.model().dataframe()
            written = reporting.write_report(
                Path(out_dir), df, evaluation["stats"], evaluation["pass_pct"],
                evaluation["title"], lsl=evaluation["lsl"], usl=evaluation["usl"],
                cpk_df=cpk_df)
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            log.exception("Report export failed")
            QMessageBox.critical(self, "Export report",
                                 f"Report export failed:\n{ex}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        files = ([control_png] if ok_control else []) + \
                ([hist_png] if ok_hist else []) + written
        QMessageBox.information(
            self, "Export report",
            "Report files written:\n" + "\n".join(str(p) for p in files))


SMOKE_TDF = (
    "TDF Version: 8.00.00\n"
    "Tester: UFP-SMOKE\n"
    "IG-XL VERSION: 7.2.1\n"
    "IG-XL BUILD: 20230301\n"
    "CURRENT TIME: 03/14/2024 10:11:12\n"
    "SYSTEM TYPE: UltraFlexPlus\n"
    "PROGRAM NAME: SMOKE_FT\n"
    "SYSTEM SERIAL NUMBER: SN123\n"
    "FileNumber: 1\n"
    "Board Configuration:\n"
    "0.0\tOPTA\tMODSN1\t2024-01-01\t638-249-30\tCAL_OK\n"
    "P/F\tSlot\tSubslot\n"
    + "".join(
        f"P|0|0|PS1600|GP2|GP1|FUNC|12|CH{i}|CONT|1.0|0.0|{0.5 + i * 0.01:.3f}|2.0|V|0|1|SmokeLabel|\n"
        for i in range(5)
    )
)


def _smoke_report(out_path, message: str):
    if out_path:
        Path(out_path).write_text(message, encoding="utf-8")


def run_packaged_selftest() -> int:
    """Env-gated end-to-end check used to validate frozen bundles (Step 4).

    Activated by SPC_APP_SMOKE=1; writes 'SMOKE OK' or a traceback to the
    file named by SPC_SMOKE_OUT and exits non-zero on failure.
    """
    import traceback

    from PySide6.QtCore import Qt

    from spc_core.consolidation import run_consolidation

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    out_path = os.environ.get("SPC_SMOKE_OUT")
    try:
        tmp = Path(tempfile.mkdtemp(prefix="spc_bundle_smoke_"))
        tree = tmp / "SN001_001" / "PROD_02_EVT_FT_T123_ATP-1-2" / "20240102_030405"
        tree.mkdir(parents=True)
        (tree / "TestData.tdf").write_text(SMOKE_TDF, encoding="utf-8")

        files, rows = run_consolidation(str(tmp / "SN001_001"),
                                        str(tmp / "results.csv"), str(tmp / "results.db"))
        assert rows == 5, f"consolidated {rows} rows, expected 5"

        app = QApplication.instance() or QApplication(sys.argv)
        window = MainWindow()
        window.load_db_file(str(tmp / "results.db"))
        assert window.filter_panel.isEnabled(), "filters not enabled after load"

        unit_rows = window.conn.execute(
            "SELECT DISTINCT UnitSN, RunAttempt FROM test_results").fetchall()
        assert unit_rows == [("SN001", "001")], f"UnitSN fallback broken: {unit_rows}"

        nb_list = window.filter_panel.testnb_list
        assert nb_list.count() == 1, f"expected 1 TestNb, got {nb_list.count()}"
        nb_list.item(0).setCheckState(Qt.Checked)
        window.refresh_results()

        model = window.raw_tab.table.model()
        assert model.rowCount() == 5, f"raw table rows={model.rowCount()}, expected 5"
        n_card = window.kpi_row._cards[7].value_label.text()
        assert n_card == "5", f"N KPI card={n_card!r}, expected '5'"

        exported = tmp / "export.csv"
        model.dataframe().to_csv(exported, index=False, encoding="utf-8")
        assert exported.exists() and exported.stat().st_size > 0, "CSV export failed"

        window.close()
        if window.conn is not None:
            window.conn.close()
        _smoke_report(out_path, "SMOKE OK")
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
        _smoke_report(out_path, "SMOKE FAILED\n" + error)
        return 1


def main():
    logging.basicConfig(filename=str(paths.default_log_file()),
                        level=logging.WARNING, format="%(levelname)s: %(message)s")
    pg.setConfigOptions(antialias=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(WINDOW_TITLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if os.environ.get("SPC_APP_SMOKE") == "1":
        sys.exit(run_packaged_selftest())
    main()
