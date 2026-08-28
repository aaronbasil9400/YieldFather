"""pyqtgraph builders for the SPC control chart and value histogram.

Presentation-only helpers mirroring the Plotly charts in SPC_DASHBOARD.py:
mean/UCL/LCL/USL/LSL reference lines and red/amber/green point coloring.
"""

import numpy as np
import pandas as pd
import pyqtgraph as pg

COLOR_LINE = "#64748B"
COLOR_MEAN = "#3B82F6"
COLOR_LIMIT = "#EF4444"
COLOR_CTRL = "#F59E0B"
COLOR_OK = "#10B981"
COLOR_HIST = "#0284C7"


def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.4g}"


def _hline(plot, y, color, style, text, position=0.9):
    line = pg.InfiniteLine(
        pos=float(y), angle=0,
        pen=pg.mkPen(color, width=1.6, style=style),
        label=text,
        labelOpts={"position": position, "color": pg.mkColor(color)},
    )
    plot.addItem(line)
    return line


def _vline(plot, x, color, style):
    plot.addItem(pg.InfiniteLine(pos=float(x), angle=90,
                                 pen=pg.mkPen(color, width=1.6, style=style)))


def configure_plot(plot_widget: pg.PlotWidget, bg: str = "w",
                   fg: str = "#31333F", axis_color: str = "#94A3B8"):
    plot_widget.setBackground(bg)
    pi = plot_widget.getPlotItem()
    pi.showGrid(x=True, y=True, alpha=0.15)
    for axis_name in ("bottom", "left"):
        axis = pi.getAxis(axis_name)
        axis.setPen(pg.mkPen(axis_color, width=1))
        axis.setTextPen(pg.mkColor(fg))


def clear_chart(plot_widget: pg.PlotWidget, title=""):
    plot_widget.clear()
    plot_widget.setTitle(title)


def build_control_chart(plot_widget: pg.PlotWidget, df: pd.DataFrame, stats: dict,
                        lsl, usl, title: str, hover_callback=None,
                        title_color: str = "#31333F"):
    """Populate *plot_widget* with the measured-value control chart."""
    plot_widget.clear()
    plot_widget.setTitle(title, color=title_color, size="11pt")
    values = df["Value_num"].to_numpy(dtype=float)
    n = len(values)
    if n == 0:
        return

    x = np.arange(1, n + 1)
    mean, std = stats.get("Mean", np.nan), stats.get("StdDev", np.nan)
    ucl = mean + 3 * std if not (np.isnan(mean) or np.isnan(std)) else None
    lcl = mean - 3 * std if not (np.isnan(mean) or np.isnan(std)) else None

    def out_of_spec(v):
        return ((lsl is not None and not np.isnan(lsl) and v < lsl)
                or (usl is not None and not np.isnan(usl) and v > usl))

    def beyond_ctrl(v):
        return ((ucl is not None and v > ucl) or (lcl is not None and v < lcl))

    colors = [COLOR_LIMIT if out_of_spec(v) else COLOR_CTRL if beyond_ctrl(v) else COLOR_OK
              for v in values]

    hover = [
        f"UnitSN: {u}<br>DUT_SN: {d}<br>Channel: {c}<br>Result: {r}<br>Time: {t}"
        for u, d, c, r, t in zip(df["UnitSN"], df["DUT_SN"], df["Channel"],
                                 df["Result"], df["RunTimestampFolder"])
    ]

    plot_widget.plot(x, values, pen=pg.mkPen(COLOR_LINE, width=1))
    spots = [{"pos": (float(xi), float(yi)), "brush": pg.mkBrush(colors[i]),
              "pen": pg.mkPen(None), "data": hover[i]}
             for i, (xi, yi) in enumerate(zip(x, values))]
    scatter = pg.ScatterPlotItem(size=8)
    scatter.addPoints(spots)

    def on_hover(_item, points):
        if points and hover_callback:
            hover_callback(points[-1].data().replace("<br>", "\n"))

    scatter.sigHovered.connect(on_hover)
    plot_widget.addItem(scatter)

    if not np.isnan(mean):
        _hline(plot_widget, mean, COLOR_MEAN, pg.QtCore.Qt.SolidLine, f"Mean={_fmt(mean)}")
    if ucl is not None:
        _hline(plot_widget, ucl, COLOR_CTRL, pg.QtCore.Qt.DashLine, f"UCL={_fmt(ucl)}")
    if lcl is not None:
        _hline(plot_widget, lcl, COLOR_CTRL, pg.QtCore.Qt.DashLine, f"LCL={_fmt(lcl)}",
               position=0.08)
    if usl is not None and not np.isnan(usl):
        _hline(plot_widget, usl, COLOR_LIMIT, pg.QtCore.Qt.DotLine, f"USL={_fmt(usl)}",
               position=0.97)
    if lsl is not None and not np.isnan(lsl):
        _hline(plot_widget, lsl, COLOR_LIMIT, pg.QtCore.Qt.DotLine, f"LSL={_fmt(lsl)}",
               position=0.03)

    plot_widget.setLabel("bottom", "Sample #")
    plot_widget.setLabel("left", "Measured Value")


def build_histogram(plot_widget: pg.PlotWidget, values: np.ndarray, lsl, usl, mean,
                    title_color: str = "#31333F"):
    """Populate *plot_widget* with the distribution of measured values."""
    plot_widget.clear()
    plot_widget.setTitle("Distribution", color=title_color, size="11pt")
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return

    counts, bins = np.histogram(values, bins=min(30, max(5, len(values) // 10 or 5)))
    plot_widget.addItem(pg.BarGraphItem(x0=bins[:-1], x1=bins[1:], height=counts,
                                        brush=pg.mkBrush(COLOR_HIST),
                                        pen=pg.mkPen(None)))

    if lsl is not None and not np.isnan(lsl):
        _vline(plot_widget, lsl, COLOR_LIMIT, pg.QtCore.Qt.DotLine)
    if usl is not None and not np.isnan(usl):
        _vline(plot_widget, usl, COLOR_LIMIT, pg.QtCore.Qt.DotLine)
    if mean is not None and not np.isnan(mean):
        _vline(plot_widget, mean, COLOR_MEAN, pg.QtCore.Qt.SolidLine)

    plot_widget.setLabel("bottom", "Measured Value")
    plot_widget.setLabel("left", "Count")
