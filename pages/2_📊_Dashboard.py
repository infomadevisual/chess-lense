import streamlit as st
import pandas as pd
from typing import List

from lib.app_session import AppSession
from ui import inject_page_styles

# ---------- Helpers ----------
_ORDER = ["bullet", "blitz", "rapid", "daily", "classical"]

def _normalize_time_label(tc: str) -> str:
    """Return human label from chess.com time_control like '300+0' -> '5+0 min'."""
    if not tc or not isinstance(tc, str):
        return "unknown"
    try:
        if "+" in tc:
            base, inc = tc.split("+", 1)
            base_s = int(base)
            inc_s = int(inc)
            mins = int(round(base_s / 60))
            return f"{mins}+{inc_s} min" if inc_s else f"{mins} min"
        if "/" in tc:
            # daily format like '1/86400' (X moves per Y seconds). Label as 'Daily'.
            return "daily (correspondence)"
        return tc
    except Exception:
        return tc

def _order_classes(classes: List[str]) -> List[str]:
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in _ORDER if c in lower and not seen.add(c)]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)

def _render_viz(df: pd.DataFrame) -> None:
    st.caption(f"{len(df)} games")
    if df.empty:
        st.info("No games for this selection.")
        return

    # Example 1: games per month
    if "end_time" in df.columns and pd.api.types.is_datetime64_any_dtype(df["end_time"]):
        monthly = df.resample("ME", on="end_time").size().rename("games")
        st.line_chart(monthly)

    # Example 2: top openings
    if "opening" in df.columns:
        top_open = df["opening"].fillna("unknown").value_counts().head(10)
        st.bar_chart(top_open)

    # Example 3: quick table preview
    show_cols = [c for c in ["game_url","time_class","time_control","opening","eco","rated","end_time"] if c in df.columns]
    st.dataframe(df[show_cols].head(50), width="stretch")

# ---------- Page ----------
def run():
    inject_page_styles()
    session = AppSession.from_streamlit()

    st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")
    st.header(f"Dashboard of {session.username}")

    if not session.has_data:
        st.warning("Load games first.")
        return

    df = session.games_df.copy() # type: ignore

    # Ensure needed columns exist
    for c in ["time_class", "time_control"]:
        if c not in df.columns:
            df[c] = None

    # Build labels for second-level
    # if "time_label" not in df.columns:
    #     df["time_label"] = df["time_control"].astype(str).map(_normalize_time_label)

    # Top-level: time_class tabs (with All)
    total_n = len(df)
    class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
    classes = _order_classes(class_counts.index.tolist())

    top_labels = [f"All ({total_n})"] + [f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes]
    top_tabs = st.tabs(top_labels)

    # Tab 0: All classes
    with top_tabs[0]:
        _render_viz(df)

    # Each class-specific tab
    for i, cls in enumerate(classes, start=1):
        with top_tabs[i]:
            df_cls = df[df["time_class"].str.lower().fillna("unknown") == cls]
            _render_second_level(df_cls)

def _render_second_level(df_scope: pd.DataFrame) -> None:
    # Second-level tabs: time controls within scope (with All)
    n_scope = len(df_scope)
    ctrl_counts = df_scope["time_label"].value_counts()
    controls = ctrl_counts.index.tolist()

    # Keep a stable numeric sort by base minutes if possible
    def _sort_key(lbl: str):
        # try to parse "X+Y min" or "X min"
        try:
            tok = lbl.split(" ")[0]  # "X+Y" or "X"
            base = tok.split("+")[0]
            return int(base)
        except Exception:
            return 10**9
    controls_sorted = sorted(controls, key=_sort_key)

    sec_labels = [f"All ({n_scope})"] + [f"{c} ({int(ctrl_counts[c])})" for c in controls_sorted]
    sec_tabs = st.tabs(sec_labels)

    # All controls
    with sec_tabs[0]:
        _render_viz(df_scope)

    # Each specific control
    for j, ctrl in enumerate(controls_sorted, start=1):
        with sec_tabs[j]:
            df_ctrl = df_scope[df_scope["time_label"] == ctrl]
            _render_viz(df_ctrl)
            
if __name__ == "__main__":
    run()