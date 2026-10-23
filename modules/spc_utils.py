"""Pure SPC calculations (no Streamlit) so they can be unit-tested.

Constants follow the standard SPC tables (e.g. Montgomery, Introduction to
Statistical Quality Control, Appendix VI) for subgroup sizes n = 2..10.
"""
from __future__ import annotations

import io
import re

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


# ---------------------------------------------------------------------------
# Run and trend rules (beyond Rule 1, "point outside the control limits")
# ---------------------------------------------------------------------------
DEFAULT_RUN_LENGTH = 7    # points in a row on the same side of the centerline
DEFAULT_TREND_LENGTH = 6  # points in a row steadily rising or steadily falling


def _runs_of_equal(codes: np.ndarray) -> list[tuple[int, int, int]]:
    """Maximal runs of identical non-zero codes as (start, end_inclusive, code)."""
    runs, i, n = [], 0, len(codes)
    while i < n:
        if codes[i] == 0 or np.isnan(codes[i]):
            i += 1
            continue
        j = i
        while j + 1 < n and codes[j + 1] == codes[i]:
            j += 1
        runs.append((i, j, int(codes[i])))
        i = j + 1
    return runs


def _signs(diff: np.ndarray, ref: float, values: np.ndarray) -> np.ndarray:
    """Sign of each difference, treating floating-point noise as zero.

    Without this, identical values (for example a constant column) can sit a hair
    above or below their own mean and look like a run.
    """
    finite = values[np.isfinite(values)]
    scale = max(1.0, abs(ref), float(np.max(np.abs(finite))) if finite.size else 0.0)
    out = np.sign(diff)
    out[np.abs(diff) <= 1e-9 * scale] = 0.0
    return out


def run_segments(values, center: float, length: int = DEFAULT_RUN_LENGTH) -> list[tuple[int, int]]:
    """Each run of ``length`` or more points on one side of the centerline, as (first, last) positions.

    A point exactly on the centerline ends a run. Missing values end a run.
    A run above the line followed directly by a run below it is reported as two runs.
    """
    v = np.asarray(values, dtype=float)
    return [(a, b) for a, b, _ in _runs_of_equal(_signs(v - center, center, v)) if b - a + 1 >= length]


def trend_segments(values, length: int = DEFAULT_TREND_LENGTH) -> list[tuple[int, int]]:
    """Each stretch of ``length`` or more points steadily rising or falling, as (first, last) positions.

    Equal consecutive values end a trend. Missing values end a trend.
    """
    v = np.asarray(values, dtype=float)
    if len(v) < 2:
        return []
    steps = _signs(np.diff(v), 0.0, v)  # one entry per step between neighbouring points
    return [(a, b + 1) for a, b, _ in _runs_of_equal(steps) if (b - a + 1) + 1 >= length]


def _mask(segments: list[tuple[int, int]], n: int) -> np.ndarray:
    flags = np.zeros(n, dtype=bool)
    for a, b in segments:
        flags[a : b + 1] = True
    return flags


def run_flags(values, center: float, length: int = DEFAULT_RUN_LENGTH) -> np.ndarray:
    """Mask of points that belong to a run on one side of the centerline."""
    return _mask(run_segments(values, center, length), len(np.asarray(values)))


def trend_flags(values, length: int = DEFAULT_TREND_LENGTH) -> np.ndarray:
    """Mask of points that belong to a steady rising or falling trend."""
    return _mask(trend_segments(values, length), len(np.asarray(values)))


def run_rule_violations(
    values, center: float, run_length: int = DEFAULT_RUN_LENGTH, trend_length: int = DEFAULT_TREND_LENGTH
) -> dict:
    """Flagged points and the individual runs/trends found.

    ``run`` and ``trend`` are 0-based positions of flagged points (for markers);
    ``run_segments`` and ``trend_segments`` are (first, last) positions of each run or trend.
    """
    run_seg = run_segments(values, center, run_length)
    trend_seg = trend_segments(values, trend_length)
    n = len(np.asarray(values))
    return {
        "run": np.flatnonzero(_mask(run_seg, n)).tolist(),
        "trend": np.flatnonzero(_mask(trend_seg, n)).tolist(),
        "run_segments": run_seg,
        "trend_segments": trend_seg,
    }


# ---------------------------------------------------------------------------
# Raw measurement upload: turn a CSV of raw readings into subgroup statistics
# ---------------------------------------------------------------------------
MIN_N, MAX_N = 2, 10          # subgroup sizes the constant tables cover
MAX_VALUES = 50_000           # keep the page responsive on very large files
_ID_NAME = re.compile(r"(subgroup|sample|group|batch|lot|\bid\b|\bno\b|run|time|date|index|#)", re.I)


class UploadError(ValueError):
    """A problem with the uploaded file that the user can fix (message is user-facing)."""


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame, with friendly errors."""
    if not data or not data.strip():
        raise UploadError("The file is empty.")
    try:
        df = pd.read_csv(io.BytesIO(data), encoding_errors="replace", sep=None, engine="python")
    except Exception as exc:  # malformed CSV
        raise UploadError(f"Could not read the file as CSV ({type(exc).__name__}). Check that it is a comma-separated text file.") from exc
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        raise UploadError("The file has no data rows.")
    if df.size > 2 * MAX_VALUES:
        raise UploadError(f"The file is too large for this demo (limit about {MAX_VALUES:,} measurements).")
    return df


def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    return df.apply(pd.to_numeric, errors="coerce")


def numeric_columns(df: pd.DataFrame) -> list[str]:
    """Columns that hold mostly numbers."""
    num = _numeric(df)
    return [c for c in df.columns if num[c].notna().sum() >= max(1, 0.8 * df[c].notna().sum()) and df[c].notna().any()]


def guess_id_column(df: pd.DataFrame) -> str | None:
    """First column if it looks like a subgroup label (non-numeric, or named like one)."""
    first = df.columns[0]
    if first not in numeric_columns(df) or _ID_NAME.search(str(first)):
        return first
    return None


def guess_long_columns(df: pd.DataFrame) -> tuple[str, str | None]:
    """Best guess of (group column, value column) for one-measurement-per-row files."""
    nums = numeric_columns(df)
    group = next((c for c in df.columns if _ID_NAME.search(str(c))), df.columns[0])
    value = next((c for c in reversed(nums) if c != group), None)
    return group, value


def guess_layout(df: pd.DataFrame) -> str:
    """'wide', 'long' or 'seq', judged from the file's shape."""
    id_col = guess_id_column(df)
    measures = [c for c in numeric_columns(df) if c != id_col]
    if len(measures) >= MIN_N:   # more than MAX_N columns still reads as "wide", so the user gets the size-limit message
        return "wide"
    if len(measures) == 1 and id_col is not None:
        return "long"
    return "seq"


def _check_n(n: int) -> None:
    if n < MIN_N:
        raise UploadError(f"Found subgroups of {n} measurement(s). Control-chart constants need at least {MIN_N} per subgroup; "
                          "for single readings, choose the 'single column' layout and set a subgroup size.")
    if n > MAX_N:
        raise UploadError(f"Found subgroups of {n} measurements; this tool supports subgroup sizes {MIN_N} to {MAX_N}. "
                          "Check the subgroup ID column, or choose another layout.")


def matrix_from_wide(df: pd.DataFrame, id_col: str | None) -> tuple[list, np.ndarray, list[str]]:
    """One row per subgroup, one column per measurement. Returns (labels, k x n matrix, notes)."""
    cols = [c for c in df.columns if c != id_col]
    if not cols:
        raise UploadError("No measurement columns found.")
    num = _numeric(df[cols])
    bad = [c for c in cols if num[c].notna().sum() == 0]
    if bad:
        raise UploadError(f"Column(s) {', '.join(map(str, bad))} contain no numbers. If one is a label column, pick it as the subgroup ID.")
    _check_n(len(cols))
    labels = df[id_col] if id_col is not None else pd.Series(np.arange(1, len(df) + 1), index=df.index)
    keep = num.notna().all(axis=1)
    notes = []
    if (~keep).any():
        notes.append(f"{int((~keep).sum())} row(s) with missing or non-numeric readings were skipped.")
    if keep.sum() == 0:
        raise UploadError("Every row has a missing or non-numeric reading.")
    return labels[keep].tolist(), num[keep].to_numpy(dtype=float), notes


def matrix_from_long(df: pd.DataFrame, group_col: str, value_col: str) -> tuple[list, np.ndarray, list[str]]:
    """One row per measurement with a subgroup column. Subgroups must all be the same size."""
    if group_col == value_col:
        raise UploadError("Choose different columns for the subgroup and the measurement.")
    values = pd.to_numeric(df[value_col], errors="coerce")
    d = pd.DataFrame({"g": df[group_col], "v": values})
    notes = []
    missing = int(d["v"].isna().sum())
    if missing:
        notes.append(f"{missing} missing or non-numeric reading(s) were skipped.")
    d = d.dropna(subset=["v", "g"])
    if d.empty:
        raise UploadError(f"Column '{value_col}' contains no numbers.")
    groups = {}
    for g, v in zip(d["g"], d["v"]):  # dict keeps first-appearance order
        groups.setdefault(g, []).append(v)
    sizes = {g: len(v) for g, v in groups.items()}
    common = pd.Series(list(sizes.values())).mode().iloc[0]
    odd = {g: s for g, s in sizes.items() if s != common}
    if odd:
        examples = ", ".join(f"{g} ({s})" for g, s in list(odd.items())[:4])
        raise UploadError(f"Subgroups must all be the same size (most have {common}). Different sizes: {examples}"
                          f"{' ...' if len(odd) > 4 else ''}.")
    _check_n(int(common))
    return list(groups), np.array(list(groups.values()), dtype=float), notes


def matrix_from_sequence(df: pd.DataFrame, value_col: str, n: int) -> tuple[list, np.ndarray, list[str]]:
    """A single column of readings in time order, grouped into consecutive subgroups of ``n``."""
    _check_n(int(n))
    values = pd.to_numeric(df[value_col], errors="coerce")
    notes = []
    if values.isna().any():
        notes.append(f"{int(values.isna().sum())} missing or non-numeric reading(s) were skipped.")
    v = values.dropna().to_numpy(dtype=float)
    if len(v) == 0:
        raise UploadError(f"Column '{value_col}' contains no numbers.")
    k = len(v) // n
    if k == 0:
        raise UploadError(f"Only {len(v)} readings, which is fewer than one subgroup of {n}.")
    if len(v) % n:
        notes.append(f"The last {len(v) % n} reading(s) did not fill a subgroup of {n} and were left out.")
    return list(range(1, k + 1)), v[: k * n].reshape(k, n), notes


def summarize_matrix(labels: list, matrix: np.ndarray) -> pd.DataFrame:
    """Subgroup mean, range and sample standard deviation (the table the charts use)."""
    return pd.DataFrame(
        {
            "Subgroup": labels,
            "Mean": matrix.mean(axis=1),
            "Range": matrix.max(axis=1) - matrix.min(axis=1),
            "StdDev": matrix.std(axis=1, ddof=1),
        }
    )


def overall_capability(values, usl: float, lsl: float) -> dict:
    """Pp, Ppk (and the overall mean and sigma) from all raw readings, using the overall sample std dev."""
    v = np.asarray(values, dtype=float)
    sigma = float(v.std(ddof=1)) if len(v) > 1 else 0.0
    mean = float(v.mean())
    cap = capability(usl, lsl, mean, sigma)
    return {"pp": cap["cp"], "ppk": cap["cpk"], "mean": mean, "sigma": sigma}


def example_csv(k: int = 20, n: int = 5, seed: int = 42) -> str:
    """Simulated example file (one row per subgroup) with a small upward shift from subgroup 13 on."""
    rng = np.random.default_rng(seed)
    base = rng.normal(10.0, 0.012, size=(k, n))
    base[12:] += 0.014
    out = pd.DataFrame(np.round(base, 4), columns=[f"X{i}" for i in range(1, n + 1)])
    out.insert(0, "Subgroup", np.arange(1, k + 1))
    return out.to_csv(index=False)
