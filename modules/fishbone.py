"""Fishbone (Ishikawa) diagram built from an editable cause table, using the 6M categories.

Pure functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
"""
from __future__ import annotations

import html
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, PURPLE, RED, editor, plot, report_issues, sample_data_note, table

TOP = ["Man (People)", "Method", "Machine"]
BOTTOM = ["Material", "Measurement", "Environment"]
CATEGORIES = TOP + BOTTOM
CATEGORY_COLORS = {"Man (People)": BLUE, "Method": ORANGE, "Machine": GREEN, "Material": PURPLE,
                   "Measurement": "#8c564b", "Environment": "#17becf"}
CAUSE_COLS = ["Category", "Cause", "Sub-cause", "Suspected"]
CLEAN_COLS = ["Category", "Cause", "Sub-cause", "Suspected"]
LABEL_CHARS = 34
SUB_CHARS = 30

_ALIASES = {
    "man": "Man (People)", "people": "Man (People)", "manpower": "Man (People)", "personnel": "Man (People)",
    "operator": "Man (People)", "man (people)": "Man (People)",
    "method": "Method", "methods": "Method", "process": "Method", "procedure": "Method",
    "machine": "Machine", "machines": "Machine", "equipment": "Machine", "machinery": "Machine",
    "material": "Material", "materials": "Material",
    "measurement": "Measurement", "measurements": "Measurement", "inspection": "Measurement", "gauge": "Measurement",
    "mother nature": "Environment", "environment": "Environment", "mother nature (environment)": "Environment",
}

METHOD_NOTE = (
    "A fishbone (Ishikawa) diagram groups possible causes of one problem under six categories: Man (People), Method, "
    "Machine, Material, Measurement and Mother Nature (Environment). It lists possible causes; it does not show which "
    "one is true. Tick 'Suspected' for the causes the team wants to verify, then test them (for example with a 5 Why)."
)


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
SAMPLE_EFFECT = "Intermittent leak at seal joint (simulated example)"


def sample_causes() -> pd.DataFrame:
    rows = [
        ("Machine", "Press force drifts during the shift", "Hydraulic pressure not checked after startup", False),
        ("Machine", "Clamp pads on the fixture are worn", "", False),
        ("Method", "Seal fitted without lubricant", "", True),
        ("Method", "Torque sequence not defined", "One work instruction covers both joint sizes", False),
        ("Material", "Seal hardness varies between lots", "", True),
        ("Material", "Flange surface finish rough", "", False),
        ("Man (People)", "New operators trained by shadowing only", "", False),
        ("Man (People)", "Step skipped when the line is rushed", "", False),
        ("Measurement", "Leak tester calibrated once a year", "", False),
        ("Measurement", "Pass limit set wider than the requirement", "", False),
        ("Environment", "Seal storage temperature varies by season", "", False),
        ("Environment", "Dust at the assembly bench", "", False),
    ]
    return pd.DataFrame(rows, columns=CAUSE_COLS)


# ---------------------------------------------------------------------------
# Cleaning and structure
# ---------------------------------------------------------------------------
def _is_blank(value) -> bool:
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(value, str) and not value.strip()


def _text(value) -> str:
    return "" if _is_blank(value) else " ".join(str(value).split())


def _to_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "x", "✓"}
    if _is_blank(value):
        return False
    try:
        return bool(value)
    except (TypeError, ValueError):
        return False


def normalise_category(name) -> str | None:
    key = " ".join(_text(name).lower().replace("_", " ").split())
    return _ALIASES.get(key)


def _empty() -> pd.DataFrame:
    return pd.DataFrame({"Category": pd.Series(dtype=object), "Cause": pd.Series(dtype=object),
                         "Sub-cause": pd.Series(dtype=object), "Suspected": pd.Series(dtype=bool)})


def clean_causes(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate the cause table. Never raises on bad cell values.

    Excluded and reported: unknown or missing category (when the row has text), sub-cause without a cause.
    Rows with only a category are dropped silently. Repeated (category, cause, sub-cause) rows keep the first.
    """
    issues: list[str] = []
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return _empty(), issues
    rows, seen = [], set()
    dups = 0
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        cat_raw, cause, sub = rec.get("Category"), _text(rec.get("Cause")), _text(rec.get("Sub-cause"))
        if _is_blank(cat_raw) and not cause and not sub:
            continue
        cat = normalise_category(cat_raw)
        label = cause or sub or "no description"
        if cat is None:
            if not cause and not sub:
                issues.append(f"Row {pos}: category '{_text(cat_raw)}' is not one of the six categories. Row excluded.")
            else:
                issues.append(f"Row {pos} ({label}): category missing or not one of {', '.join(CATEGORIES)}. Row excluded.")
            continue
        if not cause and not sub:
            continue  # category only
        if not cause:
            issues.append(f"Row {pos} ({sub}): a sub-cause needs a cause. Row excluded.")
            continue
        key = (cat, cause.lower(), sub.lower())
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        rows.append({"Category": cat, "Cause": cause, "Sub-cause": sub, "Suspected": _to_bool(rec.get("Suspected"))})
    if dups:
        issues.append(f"{dups} repeated row(s) ignored (same category, cause and sub-cause).")
    return (pd.DataFrame(rows)[CLEAN_COLS] if rows else _empty()), issues


def build_structure(clean: pd.DataFrame) -> dict[str, list[dict]]:
    """{category: [{'cause', 'subs', 'suspected'}]} for all six categories, in first-appearance order.

    Rows with the same category and cause are merged; the cause is suspected if any of its rows is ticked.
    """
    struct: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for _, r in clean.iterrows():
        entries = struct[r["Category"]]
        match = next((e for e in entries if e["cause"].lower() == r["Cause"].lower()), None)
        if match is None:
            match = {"cause": r["Cause"], "subs": [], "suspected": False}
            entries.append(match)
        if r["Sub-cause"]:
            match["subs"].append(r["Sub-cause"])
        match["suspected"] = match["suspected"] or bool(r["Suspected"])
    return struct


def category_summary(struct: dict[str, list[dict]]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Category": c, "Causes": len(struct[c]), "Sub-causes": sum(len(e["subs"]) for e in struct[c]),
         "Suspected": sum(e["suspected"] for e in struct[c])}
        for c in CATEGORIES
    ])


def suspected_causes(struct: dict[str, list[dict]]) -> list[tuple[str, str]]:
    return [(c, e["cause"]) for c in CATEGORIES for e in struct[c] if e["suspected"]]


# ---------------------------------------------------------------------------
# Geometry and figure
# ---------------------------------------------------------------------------
def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def layout_fishbone(struct: dict[str, list[dict]]) -> dict:
    """Coordinates for the diagram. x spans about 0 to 100; y is in row units (spine at 0, top bones positive).

    Returns {'H', 'lines', 'texts'}: lines are ((x0, y0), (x1, y1), category, kind), texts are dicts.
    """
    rows_per = {c: sum(1 + len(e["subs"]) for e in struct[c]) for c in CATEGORIES}
    max_rows = max(max(rows_per.values()), 3)
    H = max_rows + 1.5
    attach = [30.0, 54.0, 78.0]
    lines = [((2.0, 0.0), (82.0, 0.0), "", "spine")]
    texts = []
    for side, cats in ((1, TOP), (-1, BOTTOM)):
        for xa, cat in zip(attach, cats):
            x_out = xa - 10.0
            lines.append(((x_out, side * H), (xa, 0.0), cat, "bone"))
            texts.append({"x": x_out, "y": side * (H + 0.8), "text": cat, "full": cat, "category": cat, "kind": "category",
                          "suspected": False})
            row = 0
            for e in struct[cat]:
                items = [(e["cause"], "cause", LABEL_CHARS, e["suspected"])] + [(s, "sub", SUB_CHARS, False) for s in e["subs"]]
                for text, kind, limit, susp in items:
                    y = side * (H - 1.2 - row)
                    xb = xa - 10.0 * (abs(y) / H)
                    length = 3.0 if kind == "cause" else 2.0
                    lines.append(((xb - length, y), (xb, y), cat, "rib" if kind == "cause" else "subrib"))
                    texts.append({"x": xb - length - 0.3, "y": y, "text": ("– " if kind == "sub" else "") + shorten(text, limit),
                                  "full": text, "category": cat, "kind": kind, "suspected": susp})
                    row += 1
    return {"H": H, "lines": lines, "texts": texts}


def build_fishbone_fig(effect: str, struct: dict[str, list[dict]]) -> go.Figure:
    geo = layout_fishbone(struct)
    H = geo["H"]
    fig = go.Figure()
    for color_key in ["spine", *CATEGORIES]:
        xs, ys = [], []
        for (p0, p1, cat, kind) in geo["lines"]:
            if (kind == "spine" and color_key == "spine") or (cat == color_key and kind != "spine"):
                xs += [p0[0], p1[0], None]
                ys += [p0[1], p1[1], None]
        if xs:
            color = "#333333" if color_key == "spine" else CATEGORY_COLORS[color_key]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line={"color": color, "width": 4 if color_key == "spine" else 2},
                                     hoverinfo="skip", showlegend=False))
    t = geo["texts"]
    esc = [html.escape(i["text"], quote=False) for i in t]
    labels = [f"<b>{s}</b>" if i["kind"] == "category" or i["suspected"] else s for s, i in zip(esc, t)]
    fig.add_trace(go.Scatter(
        x=[i["x"] for i in t], y=[i["y"] for i in t], mode="text", text=labels,
        textposition=["middle center" if i["kind"] == "category" else "middle left" for i in t],
        textfont={"size": [15 if i["kind"] == "category" else 11 if i["kind"] == "sub" else 12 for i in t],
                  "color": [RED if i["suspected"] else CATEGORY_COLORS[i["category"]] if i["kind"] == "category" else "#222222"
                            for i in t]},
        hovertext=[html.escape(i["full"], quote=False) + (" (suspected)" if i["suspected"] else "") for i in t],
        hoverinfo="text", showlegend=False))
    effect_text = "<br>".join(html.escape(line, quote=False) for line in _wrap(effect or "(problem not stated)", 16, 90))
    fig.add_annotation(x=92, y=0, text=f"<b>{effect_text}</b>", showarrow=False, align="center", bordercolor="#333333",
                       borderwidth=2, borderpad=8, bgcolor="#fde0dd", font={"size": 13, "color": "#1a1a1a"})
    fig.update_xaxes(visible=False, range=[-6, 103])
    fig.update_yaxes(visible=False, range=[-(H + 1.8), H + 1.8])
    fig.update_layout(height=int(2 * (H + 1.8) * 30 + 40), margin={"l": 5, "r": 5, "t": 10, "b": 10},
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


def _wrap(text: str, width: int, max_chars: int) -> list[str]:
    text = _text(text)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return textwrap.wrap(text, width) or [""]


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _reset() -> None:
    for k in ("fishbone_ver", "fishbone_effect_ver"):
        st.session_state[k] = st.session_state.get(k, 0) + 1


def show_results(effect: str, clean: pd.DataFrame) -> None:
    struct = build_structure(clean)
    summary = category_summary(struct)
    c1, c2, c3 = st.columns(3)
    c1.metric("Causes", int(summary["Causes"].sum()))
    c2.metric("Categories with causes", int((summary["Causes"] > 0).sum()))
    c3.metric("Suspected", int(summary["Suspected"].sum()))
    if clean.empty:
        st.info("Add causes to the table to fill the diagram. The six category bones are shown empty until then.")
    plot(build_fishbone_fig(effect, struct))
    sus = suspected_causes(struct)
    if sus:
        st.info("**Suspected causes to verify:** " + "; ".join(f"{cause} ({cat})" for cat, cause in sus) + ".")
    else:
        st.caption("No cause is ticked as suspected.")
    with st.expander("Causes per category"):
        table(summary)
    st.download_button("Download causes (CSV)", clean.to_csv(index=False).encode("utf-8"),
                       file_name="fishbone_causes.csv", mime="text/csv", key="fishbone_dl")


def render() -> None:
    st.header("🐟 Fishbone (Ishikawa) Diagram")
    st.caption(METHOD_NOTE)
    sample_data_note("Simulated example, not from a real event. Replace the problem and the causes with your own.")
    ver = st.session_state.get("fishbone_ver", 0)
    ever = st.session_state.get("fishbone_effect_ver", 0)
    effect = st.text_input("Problem (effect)", value=SAMPLE_EFFECT, key=f"fishbone_effect_{ever}")
    raw = editor(
        sample_causes(), key=f"fishbone_editor_{ver}", hide_index=True,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, width="small"),
            "Cause": st.column_config.TextColumn("Cause", width="large"),
            "Sub-cause": st.column_config.TextColumn("Sub-cause (optional)", width="large"),
            "Suspected": st.column_config.CheckboxColumn("Suspected", width="small"),
        },
    )
    st.button("Reset to sample data", key="fishbone_reset", on_click=_reset)
    clean, issues = clean_causes(raw)
    report_issues(issues)
    show_results(effect, clean)
