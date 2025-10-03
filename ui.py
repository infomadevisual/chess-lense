import pandas as pd
import streamlit as st


def inject_page_styles():
    st.markdown(
        """
        <style>
            .block-container {
                padding: 2rem !important;
            }
            .stApp {
                padding: 0 !important;
                margin: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def time_filter_controls(df_scope: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    # counts sorted desc by default
    s = df_scope["time_label"].astype("string")
    counts = s.value_counts()
    labels: list[str] = [str(x) for x in counts.index.tolist()]
    counts_map: dict[str, int] = {str(k): int(v) for k, v in counts.items()}

    options = [f"{lbl} ({counts_map[lbl]})" for lbl in labels]
    default = options  # select all

    if hasattr(st, "pills"):
        selected_opts = st.pills(
            label="Time controls",
            options=options,
            selection_mode="multi",
            default=default,
            key=f"{key_prefix}_pills",
        )
    else:
        selected_opts = st.multiselect(
            label="Time controls",
            options=options,
            default=default,
            label_visibility="collapsed",
            key=f"{key_prefix}_ms",
        )

    selected_labels = [s.split(" (", 1)[0] for s in selected_opts]

    if not selected_labels:
        return df_scope.iloc[0:0]

    mask = df_scope["time_label"].astype(str).isin(selected_labels)
    return df_scope[mask]