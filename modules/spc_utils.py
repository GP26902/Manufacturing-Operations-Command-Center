"""Pure SPC calculations (no Streamlit) so they can be unit-tested.

Constants follow the standard SPC tables (e.g. Montgomery, Introduction to
Statistical Quality Control, Appendix VI) for subgroup sizes n = 2..10.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# n:   A2      D3     D4      B3     B4      d2
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}
B3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.030, 7: 0.118, 8: 0.185, 9: 0.239, 10: 0.284}
B4 = {2: 3.267, 3: 2.568, 4: 2.266, 5: 2.089, 6: 1.970, 7: 1.882, 8: 1.815, 9: 1.761, 10: 1.716}
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}


def variable_limits(df: pd.DataFrame, n: int) -> dict:
    """Control limits for X-bar, R and S charts from subgroup summary stats.

    ``df`` needs columns Mean, Range, StdDev (one row per subgroup).
    """
    xbarbar = df["Mean"].mean()
    rbar = df["Range"].mean()
    sbar = df["StdDev"].mean()
    return {
        "xbarbar": xbarbar,
        "rbar": rbar,
        "sbar": sbar,
        "x_ucl": xbarbar + A2[n] * rbar,
        "x_lcl": xbarbar - A2[n] * rbar,
        "r_ucl": D4[n] * rbar,
        "r_lcl": D3[n] * rbar,
        "s_ucl": B4[n] * sbar,
        "s_lcl": B3[n] * sbar,
    }


def sigma_within(rbar: float, n: int) -> float:
    """Short-term (within-subgroup) sigma estimate: R-bar / d2."""
    return rbar / D2[n]


def capability(usl: float, lsl: float, mean: float, sigma: float) -> dict:
    """Cp, Cpk, Cpm for a given process mean and sigma."""
    if sigma <= 0 or usl <= lsl:
        return {"cp": float("nan"), "cpk": float("nan"), "cpm": float("nan")}
    target = (usl + lsl) / 2
    cp = (usl - lsl) / (6 * sigma)
    cpk = min((usl - mean) / (3 * sigma), (mean - lsl) / (3 * sigma))
    cpm = (usl - lsl) / (6 * np.sqrt(sigma**2 + (mean - target) ** 2))
    return {"cp": cp, "cpk": cpk, "cpm": cpm}


def out_of_control(values: pd.Series, ucl: float, lcl: float) -> pd.Series:
    """Boolean mask of points beyond the control limits (Rule 1)."""
    return (values > ucl) | (values < lcl)


def attribute_limits(kind: str, counts: np.ndarray, n: float | np.ndarray = 1.0) -> dict:
    """Centerline and 3-sigma limits for c, u, p and np charts.

    ``counts`` are defects (c, u) or defectives (p, np). ``n`` is the sample
    size per lot (or area of opportunity for u). Returns plotted series too.
    """
    counts = np.asarray(counts, dtype=float)
    n_arr = np.broadcast_to(np.asarray(n, dtype=float), counts.shape)
    if kind == "c":
        cbar = counts.mean()
        sd = np.sqrt(cbar)
        return {"series": counts, "cl": cbar, "ucl": cbar + 3 * sd, "lcl": max(0.0, cbar - 3 * sd)}
    if kind == "u":
        series = counts / n_arr
        ubar = counts.sum() / n_arr.sum()
        sd = np.sqrt(ubar / n_arr)
        return {"series": series, "cl": ubar, "ucl": ubar + 3 * sd, "lcl": np.maximum(0.0, ubar - 3 * sd)}
    if kind == "p":
        series = counts / n_arr
        pbar = counts.sum() / n_arr.sum()
        sd = np.sqrt(pbar * (1 - pbar) / n_arr)
        return {"series": series, "cl": pbar, "ucl": pbar + 3 * sd, "lcl": np.maximum(0.0, pbar - 3 * sd)}
    if kind == "np":
        nbar = float(n_arr.mean())
        pbar = counts.sum() / n_arr.sum()
        sd = np.sqrt(nbar * pbar * (1 - pbar))
        cl = nbar * pbar
        return {"series": counts, "cl": cl, "ucl": cl + 3 * sd, "lcl": max(0.0, cl - 3 * sd)}
    raise ValueError(f"Unknown attribute chart type: {kind}")
