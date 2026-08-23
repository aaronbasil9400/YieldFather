"""KPI card row replicating the ten Streamlit metrics."""

import numpy as np
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

CARD_QSS = """
QFrame#kpiCard {
    background: rgba(128, 128, 128, 0.08);
    border: 1px solid rgba(128, 128, 128, 0.3);
    border-radius: 10px;
}
QFrame#kpiCard QLabel { background: transparent; border: none; }
QLabel#kpiLabel {
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
    color: #64748B;
}
QLabel#kpiValue { font-size: 19px; font-weight: 800; color: #31333F; }
"""

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
        self.setStyleSheet(CARD_QSS)

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

    def clear(self):
        for card in self._cards:
            card.set_value(None)
