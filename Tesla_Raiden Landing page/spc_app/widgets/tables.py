"""Table widgets: virtualized DataFrame view, Cpk-by-group, raw data export."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

import pandas as pd


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df=None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        value = self._df.iat[index.row(), index.column()]
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


class DataFrameTable(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(DataFrameModel(parent=self))
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(False)

    def set_dataframe(self, df: pd.DataFrame):
        self.model().set_dataframe(df)


def _group_stats_rows(df: pd.DataFrame, group_cols):
    from spc_core.stats import compute_stats

    rows = []
    for keys, g in df.groupby(group_cols, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        g_lsl = g["LowLim_num"].dropna()
        g_usl = g["HighLim_num"].dropna()
        s = compute_stats(g["Value_num"].to_numpy(dtype=float),
                          float(g_lsl.iloc[0]) if len(g_lsl) else None,
                          float(g_usl.iloc[0]) if len(g_usl) else None)
        row = dict(zip(group_cols, keys))
        row.update({"N": s["N"], "Mean": s["Mean"], "StdDev": s["StdDev"],
                    "Cp": s["Cp"], "Cpk": s["Cpk"], "%OutOfSpec": s["PctOutOfSpec"]})
        rows.append(row)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values("Cpk", na_position="last")
    return frame


class CpkByGroupTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = DataFrameTable()
        layout.addWidget(self.table)

    def update_groups(self, df: pd.DataFrame, group_cols):
        if not group_cols:
            self.table.set_dataframe(pd.DataFrame())
            return False
        self.table.set_dataframe(_group_stats_rows(df, group_cols))
        return True


class RawDataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.info_label = QLabel("No rows loaded.")
        self.export_button = QPushButton("Download filtered data as CSV")
        self.export_button.setEnabled(False)
        bar.addWidget(self.info_label, 1)
        bar.addWidget(self.export_button)
        layout.addLayout(bar)
        self.table = DataFrameTable()
        layout.addWidget(self.table)
        self.export_button.clicked.connect(self.export_csv)

    def set_dataframe(self, df: pd.DataFrame):
        self.table.set_dataframe(df)
        self.info_label.setText(f"Raw filtered data ({len(df):,} rows)")
        self.export_button.setEnabled(len(df) > 0)

    def export_csv(self):
        df = self.table.model().dataframe()
        if df.empty:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export filtered data",
                                              "filtered_spc_data.csv",
                                              "CSV files (*.csv);;All files (*)")
        if path:
            df.to_csv(path, index=False, encoding="utf-8")
