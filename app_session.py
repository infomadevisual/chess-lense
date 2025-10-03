from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict
from typing import Any, Optional

# Centralized keys
class AppSession(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)  # allow pandas objects

    username: Optional[str] = None
    games_df: Optional[pd.DataFrame] = None

    key_username = "cc_username"
    key_df = "games_df"

    @property
    def has_data(self) -> bool:
        return self.games_df is not None and not self.games_df.empty

    @property
    def game_count(self) -> int:
        return 0 if self.games_df is None else int(len(self.games_df))

    @classmethod
    def from_streamlit(cls) -> "AppSession":
        return cls(
            username=st.session_state.get(AppSession.key_username),
            games_df=st.session_state.get(AppSession.key_df)
        )

    def persist(self) -> None:
        st.session_state[AppSession.key_username] = self.username
        st.session_state[AppSession.key_df] = self.games_df
        