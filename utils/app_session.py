from __future__ import annotations
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, ClassVar, Optional

KEY_USERNAME = "cc_username"
KEY_DF = "games_df"
# Centralized keys
class AppSession(BaseModel):
    username: Optional[str] = None
    games_df: pd.DataFrame = pd.DataFrame()

    @property
    def game_count(self) -> int:
        return 0 if self.games_df is None else int(len(self.games_df))

    @classmethod
    def from_streamlit(cls) -> "AppSession":
        return cls(
            username=st.session_state.get(KEY_USERNAME),
            games_df=st.session_state.get(KEY_DF, pd.DataFrame())
        )

    def persist(self) -> None:
        st.session_state[KEY_USERNAME] = self.username
        st.session_state[KEY_DF] = self.games_df
