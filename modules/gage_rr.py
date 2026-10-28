"""Gage R&R (crossed, ANOVA method): how much of the variation in readings comes from the measuring process.

Pure functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
The ANOVA method needs no lookup table of constants. The F-distribution p-value is computed here
(regularized incomplete beta function) so the app needs no extra dependency; the tests compare it with scipy.
"""
from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, PURPLE, RED, editor, plot, report_issues, sample_data_note, table, white_card

INK = "#1a1a1a"
DATA_COLS = ["Part", "Operator", "Measurement"]
OPERATOR_COLORS = [BLUE, ORANGE, GREEN, RED, PURPLE, "#8c564b", "#17becf", "#7f7f7f", "#bcbd22", "#e377c2"]
STUDY_VAR_MULTIPLIER = 6.0  # spread = 6 standard deviations
ACCEPT_PCT, UNACCEPT_PCT, MIN_NDC = 10.0, 30.0, 5
DEFAULT_ALPHA = 0.25  # interaction term is dropped from the model when its p-value exceeds this

METHOD_NOTE = (
    "Gage R&R (repeatability and reproducibility) estimates how much of the variation in measurements comes from the "
    "measuring process rather than from real differences between parts. Several operators measure the same parts "
    "several times; an ANOVA splits the variation into part-to-part, repeatability (same operator, same part) and "
    "reproducibility (operator differences). This page uses the crossed design with the ANOVA method and needs a balanced "
    "study: every operator measures every part the same number of times."
)

GUIDE_NOTE = (
    f"Common guideline (AIAG MSA manual): total Gage R&R below {ACCEPT_PCT:.0f}% of total variation is acceptable, "
    f"{ACCEPT_PCT:.0f}% to {UNACCEPT_PCT:.0f}% may be acceptable depending on the application and cost, and above "
    f"{UNACCEPT_PCT:.0f}% is not acceptable; at least {MIN_NDC} distinct categories are expected. These limits are a "
    "guideline; your customer or organization may set different ones."
)


# ---------------------------------------------------------------------------
# F distribution (no scipy needed)
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float, max_iter: int = 500, eps: float = 3e-16) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc_reg(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def f_sf(f: float, d1: float, d2: float) -> float:
    """P(F > f) for an F distribution with (d1, d2) degrees of freedom. NaN in, NaN out; infinity gives 0."""
    if f is None or d1 <= 0 or d2 <= 0 or (isinstance(f, float) and math.isnan(f)):
        return math.nan
    if f <= 0:
        return 1.0
    if math.isinf(f):
        return 0.0
    return betainc_reg(d2 / (d2 + d1 * f), d2 / 2.0, d1 / 2.0)


# ---------------------------------------------------------------------------
# Data: simulation, sample, cleaning
# ---------------------------------------------------------------------------
SAMPLE_PARAMS = {"parts": 10, "operators": 3, "reps": 3, "sigma_part": 0.020, "sigma_repeat": 0.003,
                 "sigma_oper": 0.0025, "sigma_inter": 0.0015, "mean": 25.0, "seed": 42}
SAMPLE_TOLERANCE = 0.12


def operator_names(n: int) -> list[str]:
    return [chr(ord("A") + i) if i < 26 else f"Op{i + 1}" for i in range(n)]


def simulate(parts: int, operators: int, reps: int, sigma_part: float, sigma_repeat: float, sigma_oper: float,
             sigma_inter: float, mean: float = 25.0, seed: int = 42, decimals: int = 3) -> pd.DataFrame:
    """Simulated crossed study in long format (Part, Operator, Measurement). Same seed gives the same data."""
    rng = np.random.RandomState(int(seed))
    part_eff = rng.normal(0.0, max(sigma_part, 0.0), parts)
    oper_eff = rng.normal(0.0, max(sigma_oper, 0.0), operators)
    inter_eff = rng.normal(0.0, max(sigma_inter, 0.0), (parts, operators))
    rows = []
    for i in range(parts):
        for j, op in enumerate(operator_names(operators)):
            for _ in range(reps):
                y = mean + part_eff[i] + oper_eff[j] + inter_eff[i, j] + rng.normal(0.0, max(sigma_repeat, 0.0))
                rows.append((str(i + 1), op, round(float(y), decimals)))
    return pd.DataFrame(rows, columns=DATA_COLS)


def sample_data() -> pd.DataFrame:
    return simulate(**SAMPLE_PARAMS)


def _label(value) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def _to_number(value) -> float:
    try:
        x = float(value.strip().replace(",", "")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return math.nan
    return x if math.isfinite(x) else math.nan


def clean_measurements(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate long-format data. Rows with a missing part or operator label, or a measurement that is not a finite
    number, are excluded and reported. Never raises on bad cell values."""
    issues: list[str] = []
    empty = pd.DataFrame({"Part": pd.Series(dtype=object), "Operator": pd.Series(dtype=object),
                          "Measurement": pd.Series(dtype=float)})
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty, issues
    rows = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        part, oper, meas_raw = _label(rec.get("Part")), _label(rec.get("Operator")), rec.get("Measurement")
        meas_blank = _label(meas_raw) == ""
        if not part and not oper and meas_blank:
            continue
        if not part or not oper:
            issues.append(f"Row {pos}: part or operator missing. Row excluded.")
            continue
        meas = _to_number(meas_raw)
        if math.isnan(meas):
            issues.append(f"Row {pos} (part {part}, operator {oper}): measurement missing or not a number. Row excluded.")
            continue
        rows.append({"Part": part, "Operator": oper, "Measurement": meas})
    return (pd.DataFrame(rows) if rows else empty), issues


def parse_upload(content: bytes) -> tuple[pd.DataFrame | None, str]:
    """Read an uploaded CSV with columns Part, Operator, Measurement (case-insensitive). Returns (frame, message)."""
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:  # noqa: BLE001 - any parse failure becomes a message
        return None, "The file could not be read as CSV."
    lookup = {str(c).strip().lower(): c for c in df.columns}
    missing = [c for c in DATA_COLS if c.lower() not in lookup]
    if missing:
        return None, f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(DATA_COLS)}."
    out = df[[lookup[c.lower()] for c in DATA_COLS]].copy()
    out.columns = DATA_COLS
    return out, ""


def ordered(values) -> list[str]:
    """Labels in natural order: numeric if every label is a number, otherwise first-appearance order."""
    uniq = list(dict.fromkeys(values))
    try:
        return sorted(uniq, key=float)
    except (TypeError, ValueError):
        return uniq


def check_design(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """The crossed ANOVA needs at least 2 parts, 2 operators and the same number (>= 2) of readings in every cell."""
    if df.empty:
        return False, ["No valid measurements."]
    parts, opers = ordered(df["Part"]), ordered(df["Operator"])
    problems = []
    if len(parts) < 2:
        problems.append("At least 2 parts are needed.")
    if len(opers) < 2:
        problems.append("At least 2 operators are needed.")
    counts = df.groupby(["Part", "Operator"]).size()
    full = pd.MultiIndex.from_product([parts, opers], names=["Part", "Operator"])
    counts = counts.reindex(full, fill_value=0)
    if len(parts) >= 2 and len(opers) >= 2:
        r = int(counts.max())
        if r < 2:
            problems.append("Each operator needs at least 2 readings per part (repeatability cannot be estimated otherwise).")
        bad = counts[counts != counts.max()]
        if len(bad):
            shown = ", ".join(f"part {p}/operator {o}: {n}" for (p, o), n in list(bad.items())[:6])
            more = f" (and {len(bad) - 6} more)" if len(bad) > 6 else ""
            problems.append(f"The study is not balanced; every part and operator needs {r} readings. Cells with a different "
                            f"count: {shown}{more}.")
    return not problems, problems


# ---------------------------------------------------------------------------
# ANOVA Gage R&R
# ---------------------------------------------------------------------------
def anova_table(df: pd.DataFrame) -> dict:
    """Two-way crossed ANOVA with replication (balanced). Returns sums of squares, df, mean squares and design size."""
    parts, opers = ordered(df["Part"]), ordered(df["Operator"])
    p, o = len(parts), len(opers)
    r = int(df.groupby(["Part", "Operator"]).size().iloc[0])
    cell = df.groupby(["Part", "Operator"])["Measurement"].mean().unstack().reindex(index=parts, columns=opers)
    grand = float(df["Measurement"].mean())
    part_m, oper_m = cell.mean(axis=1), cell.mean(axis=0)
    ss_part = o * r * float(((part_m - grand) ** 2).sum())
    ss_oper = p * r * float(((oper_m - grand) ** 2).sum())
    resid = cell.sub(part_m, axis=0).sub(oper_m, axis=1) + grand
    ss_inter = r * float((resid**2).to_numpy().sum())
    cell_mean = df.groupby(["Part", "Operator"])["Measurement"].transform("mean")
    ss_eq = float(((df["Measurement"] - cell_mean) ** 2).sum())
    dfs = {"part": p - 1, "oper": o - 1, "inter": (p - 1) * (o - 1), "eq": p * o * (r - 1)}
    ss = {"part": ss_part, "oper": ss_oper, "inter": ss_inter, "eq": ss_eq}
    ms = {k: ss[k] / dfs[k] for k in ss}
    return {"p": p, "o": o, "r": r, "grand": grand, "ss": ss, "df": dfs, "ms": ms, "cell": cell}


def _ratio(num: float, den: float) -> float:
    if den > 0:
        return num / den
    return math.inf if num > 0 else math.nan


def analyze(df: pd.DataFrame, alpha: float = DEFAULT_ALPHA, tolerance: float | None = None) -> dict:
    """Full Gage R&R result. The caller must check ``check_design`` first."""
    a = anova_table(df)
    p, o, r, ms, ss, dfs = a["p"], a["o"], a["r"], a["ms"], a["ss"], a["df"]
    f_inter = _ratio(ms["inter"], ms["eq"])
    p_inter = f_sf(f_inter, dfs["inter"], dfs["eq"])
    if math.isnan(p_inter):
        p_inter = 1.0  # no variation at all to test; treat the interaction as absent
    keep_inter = p_inter <= alpha
    notes = []
    if keep_inter:
        denom, ddf = ms["inter"], dfs["inter"]
        var_inter = max(0.0, (ms["inter"] - ms["eq"]) / r)
        var_repeat = ms["eq"]
        f_oper, f_part = _ratio(ms["oper"], ms["inter"]), _ratio(ms["part"], ms["inter"])
        p_oper, p_part = f_sf(f_oper, dfs["oper"], ddf), f_sf(f_part, dfs["part"], ddf)
        raw_oper, raw_part = (ms["oper"] - ms["inter"]) / (p * r), (ms["part"] - ms["inter"]) / (o * r)
    else:
        pooled_df = dfs["inter"] + dfs["eq"]
        pooled = (ss["inter"] + ss["eq"]) / pooled_df
        denom, ddf = pooled, pooled_df
        var_inter, var_repeat = 0.0, pooled
        f_oper, f_part = _ratio(ms["oper"], pooled), _ratio(ms["part"], pooled)
        p_oper, p_part = f_sf(f_oper, dfs["oper"], ddf), f_sf(f_part, dfs["part"], ddf)
        raw_oper, raw_part = (ms["oper"] - pooled) / (p * r), (ms["part"] - pooled) / (o * r)
        notes.append(f"Operator-by-part interaction was not significant (p = {p_inter:.3f} > {alpha:g}), so it was removed "
                     "from the model and pooled with repeatability.")
    var_oper, var_part = max(0.0, raw_oper), max(0.0, raw_part)
    clipped = [n for n, v in (("operator", raw_oper), ("part-to-part", raw_part)) if v < 0]
    if clipped:
        notes.append("Negative variance estimate set to 0 for: " + ", ".join(clipped) + ".")
    var_repro = var_oper + var_inter
    var_grr = var_repeat + var_repro
    var_total = var_grr + var_part

    def comp(name: str, v: float) -> dict:
        sd = math.sqrt(v)
        row = {"Source": name, "Variance": v, "Std dev": sd, "Study var (6 sd)": STUDY_VAR_MULTIPLIER * sd}
        row["% Contribution"] = 100.0 * v / var_total if var_total > 0 else math.nan
        row["% Study var"] = 100.0 * sd / math.sqrt(var_total) if var_total > 0 else math.nan
        row["% Tolerance"] = 100.0 * STUDY_VAR_MULTIPLIER * sd / tolerance if tolerance and tolerance > 0 else math.nan
        return row

    rows = [comp("Total Gage R&R", var_grr), comp("Repeatability", var_repeat), comp("Reproducibility", var_repro)]
    rows.append(comp("Operator", var_oper))
    if keep_inter:
        rows.append(comp("Operator x Part", var_inter))
    rows += [comp("Part-to-Part", var_part), comp("Total variation", var_total)]
    components = pd.DataFrame(rows)

    sd_grr, sd_part = math.sqrt(var_grr), math.sqrt(var_part)
    if var_total <= 0:
        ndc = math.nan
    elif sd_grr == 0:
        ndc = math.inf
    else:
        ndc = float(math.floor(1.41 * sd_part / sd_grr))
    table_rows = [
        {"Source": "Part", "DF": dfs["part"], "SS": ss["part"], "MS": ms["part"], "F": f_part, "P": p_part},
        {"Source": "Operator", "DF": dfs["oper"], "SS": ss["oper"], "MS": ms["oper"], "F": f_oper, "P": p_oper},
    ]
    if keep_inter:
        table_rows.append({"Source": "Operator x Part", "DF": dfs["inter"], "SS": ss["inter"], "MS": ms["inter"],
                           "F": f_inter, "P": p_inter})
        table_rows.append({"Source": "Repeatability", "DF": dfs["eq"], "SS": ss["eq"], "MS": ms["eq"], "F": math.nan,
                           "P": math.nan})
    else:
        table_rows.append({"Source": "Repeatability (pooled with interaction)", "DF": ddf, "SS": ss["inter"] + ss["eq"],
                           "MS": denom, "F": math.nan, "P": math.nan})
    total_ss = sum(ss.values())
    table_rows.append({"Source": "Total", "DF": p * o * r - 1, "SS": total_ss, "MS": math.nan, "F": math.nan, "P": math.nan})
    return {
        "design": {"parts": p, "operators": o, "reps": r, "readings": p * o * r},
        "anova": pd.DataFrame(table_rows), "components": components, "keep_interaction": keep_inter,
        "p_interaction": p_inter, "alpha": alpha, "ndc": ndc, "var": {"grr": var_grr, "repeat": var_repeat, "repro": var_repro,
                                                                       "oper": var_oper, "inter": var_inter, "part": var_part,
                                                                       "total": var_total},
        "tolerance": tolerance if tolerance and tolerance > 0 else None, "notes": notes, "grand_mean": a["grand"],
    }


def verdict(pct_study_var: float, ndc: float) -> tuple[str, str]:
    """Classify with the common guideline limits. Returns (level, text); level is one of
    'acceptable', 'marginal', 'unacceptable', 'undetermined'."""
    if pct_study_var is None or math.isnan(pct_study_var):
        return "undetermined", "Total variation is zero (all readings are identical), so percentages cannot be calculated."
    if pct_study_var < ACCEPT_PCT:
        level, text = "acceptable", f"Total Gage R&R is {pct_study_var:.1f}% of total variation (below {ACCEPT_PCT:.0f}%)."
    elif pct_study_var <= UNACCEPT_PCT:
        level, text = "marginal", (f"Total Gage R&R is {pct_study_var:.1f}% of total variation "
                                   f"({ACCEPT_PCT:.0f}% to {UNACCEPT_PCT:.0f}%).")
    else:
        level, text = "unacceptable", f"Total Gage R&R is {pct_study_var:.1f}% of total variation (above {UNACCEPT_PCT:.0f}%)."
    if not math.isnan(ndc) and ndc < MIN_NDC:
        text += f" The gauge distinguishes {ndc:.0f} distinct categories (fewer than {MIN_NDC})."
    return level, text


def dominant_source(result: dict) -> str:
    """Plain statement of which part of the gauge variation is larger, with a generic hint."""
    v = result["var"]
    if v["grr"] <= 0:
        return "No measurement variation was detected."
    share_rep = 100.0 * v["repeat"] / v["grr"]
    if v["repeat"] >= v["repro"]:
        return (f"Repeatability is the larger source ({share_rep:.0f}% of gauge variance). The same operator gets different "
                "readings on the same part: look at the gauge, fixture, resolution and measurement method.")
    return (f"Reproducibility is the larger source ({100 - share_rep:.0f}% of gauge variance). Operators differ from each other: "
            "look at training, the written method and how the part is held or located.")


def cell_means(df: pd.DataFrame) -> pd.DataFrame:
    parts, opers = ordered(df["Part"]), ordered(df["Operator"])
    return df.groupby(["Part", "Operator"])["Measurement"].mean().unstack().reindex(index=parts, columns=opers)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _op_color(opers: list[str], op: str) -> str:
    return OPERATOR_COLORS[opers.index(op) % len(OPERATOR_COLORS)]


def build_components_fig(result: dict) -> go.Figure:
    comp = result["components"].set_index("Source")
    names = ["Total Gage R&R", "Repeatability", "Reproducibility", "Part-to-Part"]
    fig = go.Figure()
    series = [("% Contribution", "#7f7f7f"), ("% Study var", BLUE)]
    if result["tolerance"]:
        series.append(("% Tolerance", ORANGE))
    for col, color in series:
        vals = [float(comp.loc[n, col]) for n in names]
        fig.add_trace(go.Bar(x=names, y=vals, name=col, marker_color=color, text=[f"{v:.1f}%" for v in vals],
                             textposition="outside", textfont={"color": INK}, cliponaxis=False))
    for y, label in ((ACCEPT_PCT, f"{ACCEPT_PCT:.0f}%"), (UNACCEPT_PCT, f"{UNACCEPT_PCT:.0f}%")):
        fig.add_hline(y=y, line_dash="dot", line_color="#8a8f98", annotation_text=label, annotation_position="top left",
                      annotation_font_color="#4a4a4a")
    top = max([float(comp.loc[n, c]) for n in names for c, _ in series if not math.isnan(float(comp.loc[n, c]))] + [UNACCEPT_PCT])
    fig.update_layout(barmode="group", height=420, yaxis={"title": "Percent", "range": [0, min(top * 1.2, 130)]},
                      legend={"orientation": "h", "y": -0.2}, margin={"l": 60, "r": 20, "t": 20, "b": 60})
    return white_card(fig)


def build_by_part_fig(df: pd.DataFrame, units: str = "") -> go.Figure:
    parts, opers = ordered(df["Part"]), ordered(df["Operator"])
    fig = go.Figure()
    n_op = len(opers)
    for k, op in enumerate(opers):
        sub = df[df["Operator"] == op]
        off = (k - (n_op - 1) / 2) * min(0.6 / max(n_op, 1), 0.2)
        fig.add_trace(go.Scatter(x=[parts.index(p) + off for p in sub["Part"]], y=list(sub["Measurement"]), mode="markers",
                                 name=f"Operator {op}", marker={"size": 8, "color": _op_color(opers, op), "opacity": 0.85},
                                 hovertext=[f"Part {p}, operator {op}: {m:g}" for p, m in zip(sub["Part"], sub["Measurement"])],
                                 hoverinfo="text"))
    means = df.groupby("Part")["Measurement"].mean().reindex(parts)
    fig.add_trace(go.Scatter(x=list(range(len(parts))), y=list(means), mode="markers", name="Part mean",
                             marker={"symbol": "line-ew", "size": 28, "color": "#222222", "line": {"width": 3, "color": "#222222"}},
                             hovertext=[f"Part {p} mean: {m:.4g}" for p, m in zip(parts, means)], hoverinfo="text"))
    fig.update_xaxes(tickvals=list(range(len(parts))), ticktext=parts, title="Part", range=[-0.6, len(parts) - 0.4])
    fig.update_yaxes(title=f"Measurement{f' ({units})' if units else ''}")
    fig.update_layout(height=420, legend={"orientation": "h", "y": -0.25}, margin={"l": 70, "r": 20, "t": 20, "b": 60})
    return white_card(fig)


def build_by_operator_fig(df: pd.DataFrame, units: str = "") -> go.Figure:
    opers = ordered(df["Operator"])
    fig = go.Figure()
    for op in opers:
        sub = df[df["Operator"] == op]
        color = _op_color(opers, op)
        fig.add_trace(go.Box(y=list(sub["Measurement"]), name=f"Operator {op}", boxpoints="all", jitter=0.5, pointpos=0,
                             boxmean=True, marker={"color": color, "size": 5}, line={"color": color},
                             fillcolor="rgba(0,0,0,0)"))
    fig.update_yaxes(title=f"Measurement{f' ({units})' if units else ''}")
    fig.update_layout(height=420, showlegend=False, margin={"l": 70, "r": 20, "t": 20, "b": 40})
    return white_card(fig)


def build_interaction_fig(df: pd.DataFrame, units: str = "") -> go.Figure:
    cm = cell_means(df)
    opers = list(cm.columns)
    fig = go.Figure()
    for op in opers:
        fig.add_trace(go.Scatter(x=list(cm.index), y=list(cm[op]), mode="lines+markers", name=f"Operator {op}",
                                 line={"color": _op_color(opers, op), "width": 2}, marker={"size": 7}))
    fig.update_xaxes(title="Part", type="category", categoryorder="array", categoryarray=list(cm.index))
    fig.update_yaxes(title=f"Mean measurement{f' ({units})' if units else ''}")
    fig.update_layout(height=420, legend={"orientation": "h", "y": -0.25}, margin={"l": 70, "r": 20, "t": 20, "b": 60})
    return white_card(fig)


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _fmt_pct(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1f}%"


def show_results(df: pd.DataFrame, tolerance: float | None, alpha: float, units: str = "") -> None:
    ok, problems = check_design(df)
    if not ok:
        for msg in problems:
            st.warning(msg)
        return
    res = analyze(df, alpha, tolerance)
    comp = res["components"].set_index("Source")
    pct_sv = float(comp.loc["Total Gage R&R", "% Study var"])
    level, text = verdict(pct_sv, res["ndc"])
    banner = {"acceptable": st.success, "marginal": st.warning, "unacceptable": st.error, "undetermined": st.info}[level]
    banner(f"**{level.capitalize()}.** {text}")
    d = res["design"]
    st.caption(f"{d['parts']} parts x {d['operators']} operators x {d['reps']} readings = {d['readings']} measurements.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("% Study variation (Gage R&R)", _fmt_pct(pct_sv))
    c2.metric("% Contribution (Gage R&R)", _fmt_pct(float(comp.loc["Total Gage R&R", "% Contribution"])))
    ndc = res["ndc"]
    c3.metric("Distinct categories", "n/a" if math.isnan(ndc) else ("no gauge variation" if math.isinf(ndc) else f"{ndc:.0f}"))
    c4.metric("% Tolerance (Gage R&R)", _fmt_pct(float(comp.loc["Total Gage R&R", "% Tolerance"])) if res["tolerance"] else "set tolerance")
    st.markdown("**What this means:** " + dominant_source(res))
    for n in res["notes"]:
        st.caption("ℹ️ " + n)
    tabs = st.tabs(["Variation components", "By part", "By operator", "Interaction", "ANOVA table"])
    with tabs[0]:
        plot(build_components_fig(res))
        st.caption("% Contribution uses variances (the parts add to 100%). % Study var uses standard deviations, so the "
                   "parts do not add to 100%. % Tolerance compares 6 standard deviations with the tolerance width.")
    with tabs[1]:
        plot(build_by_part_fig(df, units))
        st.caption("Vertical spread of dots for one part and one colour = repeatability. Colours sitting at different heights "
                   "on the same part = operator differences. Black bar = part mean.")
    with tabs[2]:
        plot(build_by_operator_fig(df, units))
        st.caption("Boxes at different heights suggest operator bias; wider boxes suggest more noise. Dashed line = mean.")
    with tabs[3]:
        plot(build_interaction_fig(df, units))
        st.caption("Roughly parallel lines mean operators differ by about the same amount on every part. Lines that cross or "
                   "fan out mean the operator effect depends on the part (interaction).")
    with tabs[4]:
        show = res["anova"].copy()
        table(show.round({"SS": 6, "MS": 6, "F": 3, "P": 4}))
        comp_show = res["components"].copy()
        table(comp_show.round({"Variance": 8, "Std dev": 6, "Study var (6 sd)": 5, "% Contribution": 2, "% Study var": 2,
                               "% Tolerance": 2}))
        st.download_button("Download components (CSV)", res["components"].to_csv(index=False).encode("utf-8"),
                           file_name="gage_rr_components.csv", mime="text/csv", key="grr_dl")


def _reset() -> None:
    st.session_state["grr_ver"] = st.session_state.get("grr_ver", 0) + 1


def render() -> None:
    st.header("📏 Gage R&R (measurement system analysis)")
    st.caption(METHOD_NOTE)
    with st.expander("How to read this page"):
        st.markdown(
            "- **Repeatability:** the same operator measures the same part again and gets a slightly different number "
            "(gauge noise, fixture, resolution).\n"
            "- **Reproducibility:** different operators get different averages on the same parts (technique, training, "
            "how the part is held).\n"
            "- **Part-to-part:** real differences between the parts. This is the variation you want the gauge to see.\n"
            "- **% Study variation:** gauge standard deviation divided by total standard deviation.\n"
            "- **Distinct categories:** roughly how many groups of parts the gauge can tell apart.\n"
            "- **% Tolerance:** gauge spread (6 standard deviations) divided by the tolerance width USL - LSL.")
        st.caption(GUIDE_NOTE)
    sample_data_note("Simulated measurements of a generic bore diameter. No real gauge, part or operator is represented.")

    mode = st.radio("Data source", ["Simulate a gauge", "Edit or upload data"], horizontal=True, key="grr_mode")
    ver = st.session_state.get("grr_ver", 0)
    issues: list[str] = []
    if mode == "Simulate a gauge":
        st.markdown("Change the sources of variation and watch the result move. Standard deviations are in the units below.")
        a1, a2, a3, a4 = st.columns(4)
        parts = a1.number_input("Parts", min_value=3, max_value=30, value=int(min(SAMPLE_PARAMS["parts"], 30)), step=1, key="grr_parts")
        opers = a2.number_input("Operators", min_value=2, max_value=10, value=int(min(SAMPLE_PARAMS["operators"], 10)), step=1,
                                key="grr_opers")
        reps = a3.number_input("Readings per part", min_value=2, max_value=6, value=int(min(SAMPLE_PARAMS["reps"], 6)), step=1,
                               key="grr_reps")
        seed = a4.number_input("Random seed", min_value=0, max_value=9999, value=int(min(SAMPLE_PARAMS["seed"], 9999)), step=1,
                               key="grr_seed")
        b1, b2, b3, b4 = st.columns(4)
        s_part = b1.number_input("Part-to-part sd", min_value=0.0, max_value=1.0, value=SAMPLE_PARAMS["sigma_part"], step=0.002,
                                 format="%.4f", key="grr_sp")
        s_rep = b2.number_input("Repeatability sd", min_value=0.0, max_value=1.0, value=SAMPLE_PARAMS["sigma_repeat"], step=0.0005,
                                format="%.4f", key="grr_sr")
        s_op = b3.number_input("Operator sd", min_value=0.0, max_value=1.0, value=SAMPLE_PARAMS["sigma_oper"], step=0.0005,
                               format="%.4f", key="grr_so")
        s_int = b4.number_input("Operator x part sd", min_value=0.0, max_value=1.0, value=SAMPLE_PARAMS["sigma_inter"], step=0.0005,
                                format="%.4f", key="grr_si")
        data = simulate(int(parts), int(opers), int(reps), s_part, s_rep, s_op, s_int, SAMPLE_PARAMS["mean"], int(seed))
        st.caption("Things to try: double the repeatability sd and watch % study variation and distinct categories; set operator "
                   "sd to 0 and check that reproducibility shrinks; add an operator x part sd and look at the Interaction tab.")
    else:
        up = st.file_uploader("Upload a CSV (columns Part, Operator, Measurement)", type=["csv"], key=f"grr_up_{ver}")
        raw = None
        if up is not None:
            raw, msg = parse_upload(up.getvalue())
            if raw is None:
                st.error(msg)
        if raw is None:
            raw = editor(sample_data(), key=f"grr_editor_{ver}", hide_index=True,
                         column_config={"Measurement": st.column_config.NumberColumn("Measurement", format="%.4f")})
            st.button("Reset to sample data", key="grr_reset", on_click=_reset)
        data, issues = clean_measurements(raw)
        report_issues(issues)

    s1, s2, s3 = st.columns(3)
    units = s1.text_input("Units", value="mm", key="grr_units")
    tol = s2.number_input(f"Tolerance width, USL - LSL ({units})", min_value=0.0, max_value=1000.0,
                          value=float(min(SAMPLE_TOLERANCE, 1000.0)), step=0.01, format="%.4f", key="grr_tol",
                          help="Set to 0 to skip the % Tolerance figure.")
    alpha = s3.number_input("Alpha to remove interaction", min_value=0.01, max_value=0.5, value=float(min(DEFAULT_ALPHA, 0.5)),
                            step=0.01, key="grr_alpha",
                            help="If the operator x part interaction has a p-value above this, it is removed from the model.")
    show_results(data, tol if tol > 0 else None, float(alpha), units.strip())
