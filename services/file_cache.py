# chesscom_downloader.py
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel, Field

from utils.models import GameRow
from utils.openings_catalog import join_openings_to_games

logger = logging.getLogger("FileCache")


class IndexEntry(BaseModel):
    url: str
    etag: Optional[str] = None
    created_on: str = datetime.now().isoformat()
    updated_on: Optional[str] = None

    def is_update_needed(self) -> bool:
        return self.updated_on is None or datetime.fromisoformat(
            self.updated_on
        ) < datetime.now() - timedelta(hours=24)


class IndexModel(BaseModel):
    archives_list: IndexEntry
    archives: list[IndexEntry] = Field(default_factory=list)


class FileCache:
    def __init__(self, username: str, base_dir: Path):
        self.cache_root = base_dir
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.normalized_username = username.strip().lower()

    @property
    def user_folder(self) -> Path:
        return self.cache_root / self.normalized_username

    @property
    def index_path(self) -> Path:
        return self.user_folder / "index.json"

    @property
    def raw_path(self) -> Path:
        return self.user_folder / "raw.parquet"

    @property
    def games_path(self) -> Path:
        return self.user_folder / "games.parquet"

    def load_index(self) -> IndexModel | None:
        if not self.index_path.exists():
            return None
        try:
            return IndexModel.model_validate_json(
                self.index_path.read_text(encoding="utf-8")
            )
        except Exception:
            logger.exception("index corrupt -> recreate")
            return None

    def save_index(self, idx: IndexModel) -> None:
        self.user_folder.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(idx.model_dump_json(indent=2), encoding="utf-8")

    def update_games(self, games_rows: list[GameRow]) -> pd.DataFrame:
        # Build dataframe of updated games
        new_df = (
            pd.DataFrame([r.model_dump() for r in games_rows])
            if games_rows
            else pd.DataFrame()
        )
        if not new_df.empty:
            new_df["end_time"] = pd.to_datetime(new_df["end_time"], utc=True)
            for c in ["user_rating", "opponent_rating"]:
                new_df[c] = pd.to_numeric(new_df[c], errors="coerce")

        # Merge with existing parquet
        existing = self._read_parquet(self.raw_path)

        if existing is None:
            df_final = new_df
        elif new_df.empty:
            df_final = existing  # TODO: refactor to avoid this branch
        else:
            existing["end_time"] = pd.to_datetime(
                existing["end_time"], utc=True, errors="coerce"
            )

            # Month-Replacement + Prefer new rows
            upd_months = set(new_df["end_time"].dt.to_period("M"))
            keep_mask = ~existing["end_time"].dt.to_period("M").isin(upd_months)
            merged = pd.concat(
                [existing[keep_mask], new_df], ignore_index=True, copy=False
            )

            # If game_url and/or pgn_url exist use as key, else fallback to composite key
            if "game_url" in merged or "pgn_url" in merged:
                key = merged["game_url"].combine_first(
                    merged.get("pgn_url", pd.Series(index=merged.index, dtype=object))
                )
            else:
                key = (
                    merged["end_time"].astype(str)
                    + "_"
                    + merged["white_username"].fillna("")
                    + "_"
                    + merged["black_username"].fillna("")
                )

            # Key with fallback, new versions win
            merged = (
                merged.assign(
                    __key=key, __is_new=merged.index >= len(existing[keep_mask])
                )
                .sort_values(["__key", "__is_new", "end_time"])
                .drop_duplicates(subset="__key", keep="last")
                .drop(columns=["__key", "__is_new"])
                .sort_values("end_time")
                .reset_index(drop=True)
            )
            df_final = merged

        # Persist Parquet & Index
        self.user_folder.mkdir(parents=True, exist_ok=True)
        if df_final is not None and not df_final.empty:
            df_final.to_parquet(self.raw_path, index=False)

        return df_final

    def load_games(self) -> pd.DataFrame:
        df = self._read_parquet(self.games_path)
        if df is None or df.empty:
            return pd.DataFrame()

        return df

    def save_games(self, df: pd.DataFrame):
        self.user_folder.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.games_path, index=False)

    def _read_parquet(self, p: Path) -> Optional[pd.DataFrame]:
        if p.exists():
            try:
                df = pd.read_parquet(p)
                if "end_time" in df.columns:
                    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)
                return df
            except Exception as e:
                logger.warning(f"Parquet read failed {p}: {e}")
                return None
        return None
