"""Left-panel widgets: data source control and dashboard filter panel."""

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from spc_core.query import get_distinct_values, get_testnb_label_pairs
from spc_app.paths import default_output_dir

PRIMARY_SLICERS = [
    ("UnitSN", "UnitSN"),
    ("ModuleSN", "ModuleSN"),
    ("ProgramName", "ProgramName"),
    ("TestStep", "TestStep"),
    ("Channel", "Channel"),
    ("Tester", "TestStation (Tester)"),
    ("FolderBin", "Bin (PASS/FAIL folder)"),
    ("Result", "Result (row-level PASS/FAIL)"),
]

SECONDARY_SLICERS = [
    ("RunAttempt", "RunAttempt"), ("DUT_SN", "DUT_SN"), ("ProductCode", "ProductCode"),
    ("FolderRev", "FolderRev"), ("ATP", "ATP"), ("Instrument", "Instrument"),
    ("TestGrp1", "TestGrp1"), ("TestGrp2", "TestGrp2"), ("TypeofTest", "TypeofTest"),
    ("Slot", "Slot"), ("Subslot", "Subslot"), ("LpCnt", "LpCnt (loop count)"),
    ("ModulePartNum", "ModulePartNum"), ("ModuleCalState", "ModuleCalState"),
    ("IGXLVersion", "IGXLVersion"), ("SystemType", "SystemType"), ("Units", "Units"),
]


def _checked_texts(list_widget: QListWidget):
    return [list_widget.item(i).text() for i in range(list_widget.count())
            if list_widget.item(i).checkState() == Qt.Checked]


def _fill_checkable(list_widget: QListWidget, values):
    list_widget.blockSignals(True)
    list_widget.clear()
    for value in values:
        item = QListWidgetItem(str(value))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        list_widget.addItem(item)
    list_widget.blockSignals(False)


class _PickerRow(QWidget):
    def __init__(self, placeholder: str, pick_dirs: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.edit = QLineEdit(placeholder)
        self.button = QPushButton("Browse...")
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)
        self.button.clicked.connect(self._browse)
        self.pick_dirs = pick_dirs

    def _browse(self):
        if self.pick_dirs:
            chosen = QFileDialog.getExistingDirectory(self, "Select folder", self.edit.text() or "")
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "Select file", self.edit.text() or "",
                                                    "SQLite databases (*.db);;All files (*)")
        if chosen:
            self.edit.setText(chosen)

    def text(self):
        return self.edit.text().strip()


class SourcePanel(QWidget):
    consolidate_requested = Signal(str, str, str)
    db_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        mode_box = QGroupBox("1. Data source")
        mode_layout = QVBoxLayout(mode_box)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Consolidate TDF folder", "Load existing DB file"])
        self.pages = QStackedWidget()

        tdf_page = QWidget()
        tdf_layout = QVBoxLayout(tdf_page)
        tdf_layout.setContentsMargins(0, 0, 0, 0)
        self.tdf_root = _PickerRow("TDF Root Folder", pick_dirs=True)
        self.output_dir = _PickerRow("Output Storage Folder Path", pick_dirs=True)
        default_out = str(default_output_dir())
        self.output_dir.edit.setText(default_out)
        self.run_button = QPushButton("Run Log Consolidator")
        self.run_button.setDefault(False)
        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        tdf_layout.addWidget(QLabel("TDF root folder"))
        tdf_layout.addWidget(self.tdf_root)
        tdf_layout.addWidget(QLabel("Output folder"))
        tdf_layout.addWidget(self.output_dir)
        tdf_layout.addWidget(self.run_button)
        tdf_layout.addWidget(self.progress_label)
        self.pages.addWidget(tdf_page)

        db_page = QWidget()
        db_layout = QVBoxLayout(db_page)
        db_layout.setContentsMargins(0, 0, 0, 0)
        self.db_picker = _PickerRow(str(Path(default_output_dir()) / "results.db"), pick_dirs=False)
        self.load_button = QPushButton("Connect to DB")
        db_layout.addWidget(QLabel("Existing results.db path"))
        db_layout.addWidget(self.db_picker)
        db_layout.addWidget(self.load_button)
        self.pages.addWidget(db_page)

        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.pages)
        layout.addWidget(mode_box)

        self.mode_combo.currentIndexChanged.connect(self.pages.setCurrentIndex)
        self.run_button.clicked.connect(self._emit_consolidate)
        self.load_button.clicked.connect(self._emit_db_selected)

    def _emit_consolidate(self):
        root = self.tdf_root.text()
        out_dir = self.output_dir.text()
        if not root:
            self.progress_label.setText("Select a TDF root folder first.")
            return
        csv_path = str(Path(out_dir) / "results.csv")
        db_path = str(Path(out_dir) / "results.db")
        self.consolidate_requested.emit(root, csv_path, db_path)

    def _emit_db_selected(self):
        path = self.db_picker.text()
        if not path:
            return
        self.db_selected.emit(path)

    def set_running(self, running: bool):
        self.run_button.setEnabled(not running)
        self.load_button.setEnabled(not running)

    def show_progress(self, message: str):
        self.progress_label.setText(message)


class _SearchableList(QWidget):
    """Checkable list with a substring filter box for long value lists."""

    def __init__(self, on_change, max_height: int, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type to filter...")
        self.search.setClearButtonEnabled(True)
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setToolTip("Uncheck all values and clear the search box.")
        self.clear_button.clicked.connect(self._clear_requested)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.clear_button)
        self.list = QListWidget()
        self.list.setMaximumHeight(max_height)
        self.list.setAlternatingRowColors(True)
        layout.addLayout(search_row)
        layout.addWidget(self.list)
        self.search.textChanged.connect(self._apply_filter)
        self.list.itemChanged.connect(on_change)
        self._on_change = on_change

    def _clear_requested(self):
        had_selection = bool(_checked_texts(self.list))
        self.clear_selection_and_search()
        if had_selection:
            self._on_change()

    def _apply_filter(self, text):
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def set_values(self, values):
        _fill_checkable(self.list, values)

    def selected(self):
        return _checked_texts(self.list)

    def clear_selection_and_search(self):
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setCheckState(Qt.Unchecked)
            item.setHidden(False)
        self.list.blockSignals(False)


class _SlicerGroup(QGroupBox):
    def __init__(self, title: str, on_change, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.picker = _SearchableList(on_change, max_height=110)
        layout.addWidget(self.picker)

    def set_values(self, values):
        self.picker.set_values(values)

    def selected(self):
        return self.picker.selected()


class FilterPanel(QWidget):
    filtersChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.summary_label = QLabel("No dataset loaded.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        test_box = QGroupBox("2. Test selection")
        test_layout = QVBoxLayout(test_box)
        self.testnb_picker = _SearchableList(self._on_change, max_height=140)
        self.pairs_picker = _SearchableList(self._on_change, max_height=140)
        test_layout.addWidget(QLabel("Select by TestNb (includes every TestLabel)"))
        test_layout.addWidget(self.testnb_picker)
        test_layout.addWidget(QLabel("Fine control: specific TestNb - TestLabel pairs"))
        test_layout.addWidget(self.pairs_picker)
        layout.addWidget(test_box)

        self.slicer_groups = {}
        for col, label in PRIMARY_SLICERS:
            group = _SlicerGroup(label, self._on_change)
            self.slicer_groups[col] = group
            layout.addWidget(group)

        self.secondary_toggle = QToolButton()
        self.secondary_toggle.setText("More filters")
        self.secondary_toggle.setCheckable(True)
        self.secondary_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.secondary_toggle.setArrowType(Qt.RightArrow)
        self.secondary_toggle.toggled.connect(self._toggle_secondary)
        layout.addWidget(self.secondary_toggle)

        self.secondary_container = QWidget()
        sec_layout = QVBoxLayout(self.secondary_container)
        sec_layout.setContentsMargins(0, 0, 0, 0)
        for col, label in SECONDARY_SLICERS:
            group = _SlicerGroup(label, self._on_change)
            self.slicer_groups[col] = group
            sec_layout.addWidget(group)
        self.secondary_container.setVisible(False)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.secondary_container)
        scroll.setMinimumHeight(160)
        layout.addWidget(scroll)

        controls_box = QGroupBox("Dashboard controls")
        controls_layout = QHBoxLayout(controls_box)
        controls_layout.addWidget(QLabel("Max rows per chart"))
        self.row_cap = QSpinBox()
        self.row_cap.setRange(1000, 6_000_000)
        self.row_cap.setValue(800_000)
        self.row_cap.setSingleStep(1000)
        self.row_cap.valueChanged.connect(lambda _: self._on_change())
        controls_layout.addWidget(self.row_cap)
        self.reset_button = QPushButton("Reset all filters && charts")
        self.reset_button.setToolTip(
            "Uncheck every selection, clear search boxes, and clear the charts.")
        self.reset_button.clicked.connect(self.reset)
        controls_layout.addWidget(self.reset_button)
        layout.addWidget(controls_box)
        layout.addStretch(1)

    @property
    def testnb_list(self):
        return self.testnb_picker.list

    @property
    def pairs_list(self):
        return self.pairs_picker.list

    def _toggle_secondary(self, checked: bool):
        self.secondary_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.secondary_container.setVisible(checked)

    def _on_change(self, *_args):
        self.filtersChanged.emit()

    def populate(self, conn, columns):
        self.blockSignals(True)
        pairs: pd.DataFrame = get_testnb_label_pairs(conn)
        combos = (pairs["TestNb"].astype(str) + " - "
                  + pairs["TestLabel"].fillna("").astype(str))
        self._combo_map = dict(zip(combos, zip(pairs["TestNb"], pairs["TestLabel"])))
        _fill_checkable(self.testnb_list, sorted(pairs["TestNb"].astype(str).unique()))
        _fill_checkable(self.pairs_list, sorted(combos))
        for col, _label in PRIMARY_SLICERS + SECONDARY_SLICERS:
            if col in self.slicer_groups:
                values = get_distinct_values(conn, col) if col in columns else []
                self.slicer_groups[col].set_values(values)
                self.slicer_groups[col].setVisible(bool(values))
        self.blockSignals(False)
        for picker in (self.testnb_picker, self.pairs_picker):
            picker.clear_selection_and_search()

    def reset(self):
        self.blockSignals(True)
        try:
            self.testnb_picker.clear_selection_and_search()
            self.pairs_picker.clear_selection_and_search()
            for group in self.slicer_groups.values():
                group.picker.clear_selection_and_search()
        finally:
            self.blockSignals(False)
        self.filtersChanged.emit()

    @staticmethod
    def _check_item(list_widget: QListWidget, text: str):
        matches = list_widget.findItems(text, Qt.MatchExactly)
        if not matches:
            return
        list_widget.blockSignals(True)
        try:
            for item in matches:
                item.setCheckState(Qt.Checked)
        finally:
            list_widget.blockSignals(False)

    def selection_state(self) -> dict:
        """Snapshot of the current choices, suitable for JSON persistence."""
        slicers = {}
        for col, _label in PRIMARY_SLICERS + SECONDARY_SLICERS:
            group = self.slicer_groups.get(col)
            if group is not None:
                values = group.selected()
                if values:
                    slicers[col] = values
        return {
            "testnbs": _checked_texts(self.testnb_picker.list),
            "combos": _checked_texts(self.pairs_picker.list),
            "slicers": slicers,
        }

    def apply_selection(self, state: dict):
        """Restore a snapshot produced by selection_state; emits once."""
        if not isinstance(state, dict):
            return
        testnbs = [str(v) for v in state.get("testnbs") or []]
        combos = [str(v) for v in state.get("combos") or []]
        raw_slicers = state.get("slicers") or {}
        secondary_cols = {col for col, _label in SECONDARY_SLICERS}
        if any(col in raw_slicers for col in secondary_cols):
            self.secondary_toggle.setChecked(True)
        self.blockSignals(True)
        try:
            for text in testnbs:
                self._check_item(self.testnb_picker.list, text)
            for text in combos:
                self._check_item(self.pairs_picker.list, text)
            for col, values in raw_slicers.items():
                group = self.slicer_groups.get(col)
                if group is None:
                    continue
                for text in values or []:
                    self._check_item(group.picker.list, str(text))
        finally:
            self.blockSignals(False)
        if testnbs or combos or raw_slicers:
            self.filtersChanged.emit()

    def selection(self):
        filters = {}
        for col, _label in PRIMARY_SLICERS + SECONDARY_SLICERS:
            group = self.slicer_groups.get(col)
            if group is not None and group.isVisible():
                values = group.selected()
                if values:
                    filters[col] = values

        parts, params = [], []
        selected_testnbs = _checked_texts(self.testnb_picker.list)
        if selected_testnbs:
            parts.append(f'"TestNb" IN ({",".join("?" for _ in selected_testnbs)})')
            params.extend(selected_testnbs)
        selected_combos = _checked_texts(self.pairs_picker.list)
        if selected_combos:
            combo_parts = []
            for combo in selected_combos:
                nb, label = self._combo_map[combo]
                combo_parts.append('("TestNb" = ? AND "TestLabel" = ?)')
                params.extend([nb, label])
            parts.append("(" + " OR ".join(combo_parts) + ")")

        has_selection = bool(selected_testnbs or selected_combos)
        or_clauses = [("(" + " OR ".join(parts) + ")", params)] if parts else []
        return filters, or_clauses, has_selection

    def set_summary(self, summary):
        if not summary:
            self.summary_label.setText("Dataset summary unavailable.")
            return
        self.summary_label.setText(
            f"{summary['total_rows']:,} rows · {summary['n_testnb']:,} TestNb · "
            f"{summary['n_dut']:,} DUTs · {summary['n_unit']:,} Units"
        )
