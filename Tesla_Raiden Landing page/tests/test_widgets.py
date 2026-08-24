"""Regression tests for the SPC desktop widgets (offscreen Qt).

Covers the search box, per-field Clear button, panel reset, selection-state
persistence roundtrip, and the per-chart reset-view controls added to
spc_app/widgets/filter_panel.py and spc_app/main.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from spc_app.main import SMOKE_TDF, MainWindow
from spc_app.widgets.filter_panel import FilterPanel
from spc_core.consolidation import run_consolidation
from spc_core.query import connect, get_columns


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def db_file(tmp_path_factory):
    root = tmp_path_factory.mktemp("spc_widget_tests")
    tree = root / "SN001_001" / "PROD_02_EVT_FT_T123_ATP-1-2" / "20240102_030405"
    tree.mkdir(parents=True)
    (tree / "TestData.tdf").write_text(SMOKE_TDF, encoding="utf-8")
    out = root / "out"
    run_consolidation(str(root / "SN001_001"), str(out / "results.csv"),
                      str(out / "results.db"))
    return out / "results.db"


@pytest.fixture()
def filter_panel(qapp, db_file):
    panel = FilterPanel()
    conn = connect(db_file)
    panel.populate(conn, get_columns(conn))
    yield panel
    conn.close()


def _check_first(panel):
    panel.testnb_list.item(0).setCheckState(Qt.Checked)


class TestSearchBox:
    def test_substring_match_is_case_insensitive(self, filter_panel):
        picker = filter_panel.slicer_groups["Channel"].picker
        picker.search.setText("ch3")
        visible = [i for i in range(picker.list.count())
                   if not picker.list.item(i).isHidden()]
        assert [picker.list.item(i).text() for i in visible] == ["CH3"]

    def test_no_match_hides_all(self, filter_panel):
        picker = filter_panel.testnb_picker
        picker.search.setText("__no_such_value__")
        assert all(picker.list.item(i).isHidden()
                   for i in range(picker.list.count()))

    def test_clearing_search_restores_items(self, filter_panel):
        picker = filter_panel.testnb_picker
        picker.search.setText("zzz")
        picker.search.clear()
        assert not any(picker.list.item(i).isHidden()
                       for i in range(picker.list.count()))


class TestPerFieldClearButton:
    def test_unchecks_field_and_emits_once(self, filter_panel):
        _check_first(filter_panel)
        emissions = []
        filter_panel.filtersChanged.connect(lambda: emissions.append(1))
        filter_panel.testnb_picker.clear_button.click()
        assert not filter_panel.selection()[2], "selection not cleared"
        assert emissions == [1]

    def test_no_signal_when_already_empty(self, filter_panel):
        emissions = []
        filter_panel.filtersChanged.connect(lambda: emissions.append(1))
        filter_panel.slicer_groups["Channel"].picker.clear_button.click()
        assert emissions == []

    def test_only_target_field_is_cleared(self, filter_panel):
        _check_first(filter_panel)
        channel_group = filter_panel.slicer_groups["Channel"]
        channel_group.picker.list.item(0).setCheckState(Qt.Checked)
        filter_panel.testnb_picker.clear_button.click()
        assert channel_group.selected() == ["CH0"]


class TestResetAndPersistenceRoundtrip:
    def test_reset_clears_everything_and_emits_once(self, filter_panel):
        _check_first(filter_panel)
        filter_panel.slicer_groups["Channel"].picker.list.item(0).setCheckState(Qt.Checked)
        filter_panel.pairs_picker.list.item(0).setCheckState(Qt.Checked)
        emissions = []
        filter_panel.filtersChanged.connect(lambda: emissions.append(1))
        filter_panel.reset()
        assert filter_panel.selection_state() == {"testnbs": [], "combos": [],
                                                  "slicers": {}}
        assert emissions == [1]

    def test_selection_state_apply_roundtrip(self, filter_panel):
        _check_first(filter_panel)
        state = filter_panel.selection_state()
        assert state["testnbs"] == ["12"]
        filter_panel.reset()
        emissions = []
        filter_panel.filtersChanged.connect(lambda: emissions.append(1))
        filter_panel.apply_selection(state)
        assert filter_panel.selection_state()["testnbs"] == ["12"]
        assert emissions == [1]

    def test_apply_secondary_selection_expands_more_filters(self, filter_panel):
        instrument_values = filter_panel.slicer_groups["Instrument"].selected()
        assert instrument_values == []
        filter_panel.apply_selection({"slicers": {"Instrument": ["PS1600"]}})
        assert filter_panel.secondary_toggle.isChecked()
        assert filter_panel.slicer_groups["Instrument"].selected() == ["PS1600"]

    def test_apply_rejects_non_dict(self, filter_panel):
        filter_panel.apply_selection(None)  # must not raise


class TestChartResetControls:
    def test_reset_view_buttons_exist_and_are_clickable(self, qapp, db_file,
                                                        monkeypatch):
        monkeypatch.setattr("spc_app.settings.save_settings", lambda cfg: True)
        window = MainWindow()
        window.load_db_file(str(db_file))
        _check_first(window.filter_panel)
        window.refresh_results()

        window.control_reset_button.click()
        window.hist_reset_button.click()

        vr = window.control_chart.getPlotItem().getViewBox().viewRange()
        assert vr[0][0] <= 1.0, "control chart not zoomed out to all samples"
        window.close()
