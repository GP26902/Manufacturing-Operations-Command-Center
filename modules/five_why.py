"""5 Why: causal chain from a problem statement to a root-cause statement.

Pure functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
"""
from __future__ import annotations

import html
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, RED, editor, plot, report_issues, sample_data_note, table

MAX_LEVELS = 10
CHAIN_COLS = ["Cause", "Evidence", "Verified"]
CLEAN_COLS = ["Level", "Cause", "Evidence", "Verified"]
WRAP = 78
MAX_CHARS = 220

METHOD_NOTE = (
    "Each row answers 'why?' for the row above it. Row 1 is the direct cause of the problem; the last row is treated as "
    "the root cause. 'Five' is a guide: stop when the last cause is something you can act on and fixing it would prevent "
    "recurrence. Mark a row Verified only when it was checked against data, observation or records, not when it is a guess."
)


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
SAMPLE_PROBLEM = "Bored holes in housings measured oversize on one shift (simulated example)"
SAMPLE_ACTION = (
    "Add the tool-life counter reset to the changeover checklist; add a checklist review step to the "
    "equipment-upgrade change process (simulated example)."
)


def sample_chain() -> pd.DataFrame:
    rows = [
        ("Boring tool was worn past its wear limit", "Tool measured at inspection: flank wear above limit", True),
        ("Tool was not changed at the set interval", "Tool-change log shows no change for twice the interval", True),
        ("The tool-life counter was not reset at the last change", "Controller screen showed the previous count", True),
        ("Resetting the counter is not a step in the changeover checklist", "Checklist reviewed; no counter step", True),
        ("Checklist was not reviewed after the controller upgrade", "No checklist revision recorded since the upgrade", False),
    ]
    return pd.DataFrame(rows, columns=CHAIN_COLS)


# ---------------------------------------------------------------------------
# Cleaning and checks
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


def to_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "x", "✓"}
    if _is_blank(value):
        return False
    try:
        return bool(value)
    except (TypeError, ValueError):
        return False


def _empty() -> pd.DataFrame:
    return pd.DataFrame({"Level": pd.Series(dtype=int), "Cause": pd.Series(dtype=object),
                         "Evidence": pd.Series(dtype=object), "Verified": pd.Series(dtype=bool)})


def clean_chain(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate the why-chain table. Row order defines the level.

    Blank rows are dropped. A row with evidence but no cause is excluded (it would break the chain).
    Rows beyond MAX_LEVELS are ignored. Consecutive repeats are kept and reported.
    """
    issues: list[str] = []
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return _empty(), issues
    rows = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        cause, evidence = _text(rec.get("Cause")), _text(rec.get("Evidence"))
        if not cause and not evidence:
            continue
        if not cause:
            issues.append(f"Row {pos}: evidence entered without a cause. Row excluded.")
            continue
        rows.append({"Cause": cause, "Evidence": evidence, "Verified": to_bool(rec.get("Verified"))})
    if len(rows) > MAX_LEVELS:
        issues.append(f"{len(rows)} causes entered; only the first {MAX_LEVELS} are used.")
        rows = rows[:MAX_LEVELS]
    if not rows:
        return _empty(), issues
    df = pd.DataFrame(rows)
    df.insert(0, "Level", range(1, len(df) + 1))
    for i in range(1, len(df)):
        if df.loc[i, "Cause"].lower() == df.loc[i - 1, "Cause"].lower():
            issues.append(f"Why {i + 1} repeats Why {i}. Kept; check that it adds a new cause.")
    return df, issues


def chain_checks(chain: pd.DataFrame) -> list[str]:
    """Advisory messages about the chain (not errors)."""
    if chain.empty:
        return []
    msgs = []
    n = len(chain)
    if n < 3:
        msgs.append(f"Only {n} why level(s). Check that the last cause is a root cause and not a symptom.")
    unverified = chain.loc[~chain["Verified"], "Level"].tolist()
    if unverified:
        msgs.append("Not marked verified: Why " + ", ".join(str(x) for x in unverified) + ".")
    if not bool(chain["Verified"].iloc[-1]):
        msgs.append("The root-cause statement is not marked verified. Confirm it with data before assigning actions.")
    return msgs


def therefore_reading(problem: str, chain: pd.DataFrame) -> list[str]:
    """Read the chain backwards, root cause first, as 'cause -> therefore -> effect' lines (a logic check)."""
    if chain.empty:
        return []
    texts = [_text(problem) or "(problem not stated)", *chain["Cause"].tolist()]
    return [f"{texts[i].rstrip('.')}  →  therefore  →  {texts[i - 1].rstrip('.')}" for i in range(len(texts) - 1, 0, -1)]


def wrap_label(text: str, width: int = WRAP, max_chars: int = MAX_CHARS) -> str:
    text = _text(text)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return "<br>".join(html.escape(line, quote=False) for line in textwrap.wrap(text, width) or [""])


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
# Text colours are set explicitly so the diagram is readable in both light and dark Streamlit themes.
INK, MUTED, ARROW = "#1a1a1a", "#4a4a4a", "#8a8f98"
OK_TEXT, WARN_TEXT = "#1b5e20", "#b34700"
BOX_STYLE = {  # kind: (fill, border, dash)
    "problem": ("#fde0dd", RED, "solid"),
    "why": ("#e3eef9", BLUE, "solid"),
    "unverified": ("#fff3e0", ORANGE, "dash"),
    "root": ("#e2f4e2", GREEN, "solid"),
    "action": ("#f1f8f1", GREEN, "dash"),
}
BOX_X1, ACCENT_X1 = 10.0, 0.25


def _lines(text: str) -> list[str]:
    return wrap_label(text).split("<br>")


def build_chain_fig(problem: str, chain: pd.DataFrame, action: str = "") -> go.Figure:
    """Vertical chain: Problem, Why 1 ... Why n (last = root cause), then the action if one is given.

    Each box has a coloured accent bar, a title, the cause, the evidence (smaller) and a verified tag.
    Dashed orange border = not verified.
    """
    boxes = [{"kind": "problem", "title": "PROBLEM", "body": _text(problem) or "(problem not stated)", "evidence": "", "tag": ""}]
    n = len(chain)
    for _, r in chain.iterrows():
        last = int(r["Level"]) == n
        verified = bool(r["Verified"])
        kind = "root" if last else ("why" if verified else "unverified")
        boxes.append({"kind": kind, "title": f"ROOT CAUSE (Why {r['Level']})" if last else f"WHY {r['Level']}",
                      "body": r["Cause"], "evidence": r["Evidence"], "tag": "✔ verified" if verified else "? not verified",
                      "tag_color": OK_TEXT if verified else WARN_TEXT})
    if n and _text(action):
        boxes.append({"kind": "action", "title": "ACTION ON THE ROOT CAUSE", "body": _text(action), "evidence": "", "tag": ""})

    fig = go.Figure()
    y, gap = 0.0, 0.95
    prev_bottom = None
    for i, bx in enumerate(boxes):
        body, ev = _lines(bx["body"]), (_lines("Evidence: " + bx["evidence"]) if bx["evidence"] else [])
        h = 0.3 + 0.45 + len(body) * 0.42 + len(ev) * 0.36 + 0.3
        top, bottom = y, y - h
        fill, border, dash = BOX_STYLE[bx["kind"]]
        fig.add_shape(type="rect", x0=0, x1=BOX_X1, y0=bottom, y1=top, fillcolor=fill,
                      line={"color": border, "width": 2.5 if bx["kind"] == "root" else 1.5, "dash": dash})
        fig.add_shape(type="rect", x0=0, x1=ACCENT_X1, y0=bottom, y1=top, fillcolor=border, line={"width": 0})
        title_color = WARN_TEXT if border == ORANGE else border
        fig.add_annotation(x=0.5, y=top - 0.2, xanchor="left", yanchor="top", showarrow=False, align="left",
                           text=f"<b>{html.escape(bx['title'], quote=False)}</b>", font={"size": 12, "color": title_color})
        if bx["tag"]:
            fig.add_annotation(x=BOX_X1 - 0.3, y=top - 0.2, xanchor="right", yanchor="top", showarrow=False,
                               text=f"<b>{bx['tag']}</b>", font={"size": 12, "color": bx["tag_color"]})
        fig.add_annotation(x=0.5, y=top - 0.65, xanchor="left", yanchor="top", showarrow=False, align="left",
                           text="<br>".join(body), font={"size": 14, "color": INK})
        if ev:
            fig.add_annotation(x=0.5, y=top - 0.65 - len(body) * 0.42 - 0.05, xanchor="left", yanchor="top", showarrow=False,
                               align="left", text="<br>".join(ev), font={"size": 11, "color": MUTED})
        if prev_bottom is not None:
            fig.add_annotation(x=5, y=top, ax=5, ay=prev_bottom, xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                               arrowhead=2, arrowwidth=2, arrowcolor=ARROW, text="")
            label = "fix" if bx["kind"] == "action" else "why?"
            fig.add_annotation(x=5.15, y=(top + prev_bottom) / 2, text=f"<b>{label}</b>", showarrow=False, xanchor="left",
                               font={"size": 12, "color": ARROW})
        prev_bottom = bottom
        y = bottom - gap
    total = -y
    fig.update_xaxes(visible=False, range=[-0.2, 10.2])
    fig.update_yaxes(visible=False, range=[-total, 0.4])
    fig.update_layout(height=int(total * 46 + 60), margin={"l": 10, "r": 10, "t": 10, "b": 10}, showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _reset() -> None:
    st.session_state["five_why_ver"] = st.session_state.get("five_why_ver", 0) + 1
    st.session_state["five_why_problem_ver"] = st.session_state.get("five_why_problem_ver", 0) + 1


def show_results(problem: str, chain: pd.DataFrame, action: str = "") -> None:
    if chain.empty:
        st.info("Enter at least one cause to draw the chain.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Why levels", len(chain))
    c2.metric("Verified", f"{int(chain['Verified'].sum())} of {len(chain)}")
    c3.metric("Root-cause row", f"Why {int(chain['Level'].iloc[-1])}")
    for msg in chain_checks(chain):
        st.warning(msg)
    plot(build_chain_fig(problem, chain, action))
    root = chain["Cause"].iloc[-1]
    st.success(f"**Root cause:** {root}")
    with st.expander("Logic check: read the chain backwards"):
        for line in therefore_reading(problem, chain):
            st.markdown(f"- {line}")
        st.caption("Each sentence should hold on its own. If one does not, a cause is missing between those two rows.")
    st.download_button("Download chain (CSV)", chain.to_csv(index=False).encode("utf-8"),
                       file_name="five_why_chain.csv", mime="text/csv", key="five_why_dl")
    with st.expander("Chain table"):
        table(chain)


def render() -> None:
    st.header("❓ 5 Why Analysis")
    st.caption(METHOD_NOTE)
    sample_data_note("Simulated example, not from a real event. Replace the problem and the causes with your own.")
    ver = st.session_state.get("five_why_ver", 0)
    pver = st.session_state.get("five_why_problem_ver", 0)
    problem = st.text_input("Problem statement", value=SAMPLE_PROBLEM, key=f"five_why_problem_{pver}")
    raw = editor(
        sample_chain(), key=f"five_why_editor_{ver}", hide_index=True,
        column_config={
            "Cause": st.column_config.TextColumn("Cause (row 1 = Why 1)", width="large"),
            "Evidence": st.column_config.TextColumn("Evidence / how it was checked", width="large"),
            "Verified": st.column_config.CheckboxColumn("Verified", width="small"),
        },
    )
    st.button("Reset to sample data", key="five_why_reset", on_click=_reset)
    chain, issues = clean_chain(raw)
    report_issues(issues)
    action = st.text_area("Corrective / preventive action for the root cause", value=SAMPLE_ACTION, key=f"five_why_action_{pver}")
    show_results(problem, chain, action)
