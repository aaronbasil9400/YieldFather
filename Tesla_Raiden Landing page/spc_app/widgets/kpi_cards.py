"""KPI card row replicating the ten Streamlit metrics."""

import numpy as np
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from spc_app.theme import LIGHT, card_qss

KPI_SPECS = [
    ("Cpk", "Cpk", "{:.4g}"),
    ("Cp", "Cp", "{:.4g}"),
    ("Sigma Level", "Sigma_Level", "{:.4g}"),
    ("Min", "Min", "{:.4g}"),
    ("Max", "Max", "{:.4g}"),
    ("Mean", "Mean", "{:.4g}"),
    ("Std Dev", "StdDev", "{:.4g}"),
    ("N (samples)", "N", "{:.0f}"),
    ("% Out of Spec", "PctOutOfSpec", "{:.2f}%"),
]


def _is_nan(v):
    return isinstance(v, float) and np.isnan(v)


class KpiCard(QFrame):
    def __init__(self, label: str, fmt: str = "{:.4g}"):
        super().__init__()
        self.setObjectName("kpiCard")
        self.fmt = fmt
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        self.title_label = QLabel(label)
        self.title_label.setObjectName("kpiLabel")
        self.value_label = QLabel("N/A")
        self.value_label.setObjectName("kpiValue")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        self.set_palette(LIGHT)

    def set_palette(self, palette: dict):
        self._palette = palette
        self.setStyleSheet(card_qss(palette))

    def set_value(self, value):
        if value is None or _is_nan(value):
            self.value_label.setText("N/A")
        elif isinstance(value, int) and not isinstance(value, bool):
            self.value_label.setText(f"{value:,}")
        else:
            try:
                self.value_label.setText(self.fmt.format(value))
            except (ValueError, TypeError):
                self.value_label.setText(str(value))


class KpiRow(QWidget):
    def __init__(self):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self._cards = []
        for col, (label, _key, fmt) in enumerate(KPI_SPECS + [("% PASS (rows)", None, "{:.2f}%")]):
            card = KpiCard(label, fmt)
            self._cards.append(card)
            grid.addWidget(card, 0, col)

    def update_stats(self, stats: dict, pass_pct):
        for card, (_, key, _fmt) in zip(self._cards, KPI_SPECS):
            card.set_value(stats.get(key) if key != "N" else stats.get("N"))
        self._cards[-1].set_value(pass_pct)

    def apply_palette(self, palette: dict):
        for card in self._cards:
            card.set_palette(palette)

    def clear(self):
        for card in self._cards:
            card.set_value(None)
