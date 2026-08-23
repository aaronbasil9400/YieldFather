"""Process-capability statistics for the SPC dashboard.

compute_stats is moved unchanged from SPC_DASHBOARD.py. Any formula change
must follow the DATA_AND_KPIS.md workflow (definition, tests, UI label).
"""

import numpy as np


def compute_stats(values: np.ndarray, lsl, usl):
    n = len(values)
    out = {"N": n, "Mean": np.nan, "StdDev": np.nan, "Min": np.nan, "Max": np.nan,
           "Cp": np.nan, "Cpk": np.nan, "Sigma_Level": np.nan, "PctOutOfSpec": np.nan}
    if n == 0: return out
    out["Mean"], out["Min"], out["Max"] = float(np.mean(values)), float(np.min(values)), float(np.max(values))
    out["StdDev"] = float(np.std(values, ddof=1)) if n > 1 else 0.0
    std = out["StdDev"]
    if std > 0:
        cpu = (usl - out["Mean"]) / (3 * std) if usl is not None and not np.isnan(usl) else np.nan
        cpl = (out["Mean"] - lsl) / (3 * std) if lsl is not None and not np.isnan(lsl) else np.nan
        candidates = [v for v in (cpu, cpl) if not np.isnan(v)]
        if candidates: out["Cpk"] = min(candidates)
        if lsl is not None and usl is not None and not np.isnan(lsl) and not np.isnan(usl):
            out["Cp"] = (usl - lsl) / (6 * std)
        if not np.isnan(out["Cpk"]): out["Sigma_Level"] = out["Cpk"] * 3
    if lsl is not None and usl is not None and not np.isnan(lsl) and not np.isnan(usl):
        out["PctOutOfSpec"] = 100.0 * np.sum((values < lsl) | (values > usl)) / n
    return out
