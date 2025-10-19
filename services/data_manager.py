import logging
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa

from data.openings_preprocessor import OPENINGS_PATH_PREPROCESSED
from services.chesscom_downloader import ChesscomDownloader
from services.file_cache import FileCache
from utils.config import Config
from utils.models import GameRow

# precompile once at module import
_TAGS = re.compile(r"^\[.*?\]\s*", re.S | re.M)  # tag pair section
_COMMS = re.compile(r"\{[^}]*\}")  # {...}
_VARS = re.compile(r"\([^()]*\)")  # ( ... )
_NAGS = re.compile(r"\$\d+")
_WS = re.compile(r"\s+")
_MOVENO = re.compile(r"\d+\.(?:\.\.)?")  # 12. or 12...
_RESULT = re.compile(r"(1-0|0-1|1/2-1/2|\*)")

logger = logging.getLogger("DataManager")


class DataManager:
    def __init__(self, base_dir: Path = Config.cache_root):
        self.base_dir = base_dir

    def get_games_path(self, username: str) -> Path:
        return FileCache(username=username, base_dir=self.base_dir).games_path

    def check_for_updates_and_init(self, username: str, progress_cb=None) -> None:
        downloader = ChesscomDownloader()

        # (Re-)Load index
        cache = FileCache(username=username, base_dir=self.base_dir)
        idx = cache.load_index()
        if idx is None or idx.archives_list.is_update_needed():
            logger.info(f"{username}: Loading Index...")
            idx = downloader.download_index(username)
            cache.save_index(idx)
        else:
            logger.info(f"{username}: Index is younger than 24 hours. No Update.")

        # Iterate over each archive and check whether it needs update (only updated every 24 hours with etag)
        rows: list[GameRow] = []
        progress_bar_len = len(idx.archives) + 2
        for i, archive_idx in enumerate(idx.archives, start=1):
            if not archive_idx.is_update_needed():
                logger.info(
                    f"{username}: Skipping as no updated needed: {archive_idx.url}"
                )
                continue

            games_rows = downloader.download_archive(archive_idx)
            if games_rows is None:
                logger.warning(f"{username}: GameRows None for: {archive_idx.url}")
                continue

            rows.extend(GameRow.from_game(g, username) for g in games_rows)

            archive_idx.updated_on = datetime.now().isoformat()
            if progress_cb:
                progress_cb(i, progress_bar_len)

        if len(rows) > 0:
            if progress_cb:
                progress_cb(progress_bar_len - 1, progress_bar_len)
            cache.update_games_raw(rows)
            cache.save_index(idx)

        # Preprocess and save final games with openings etc.
        if len(rows) > 0 or not cache.games_path.exists():
            if progress_cb:
                progress_cb(progress_bar_len, progress_bar_len)
            self._preprocess_and_save(cache)

    # --- helpers ---
    def to_py_list(self, v) -> list[str]:
        # fast paths
        if isinstance(v, list):
            return v
        if isinstance(v, tuple):
            return list(v)
        if isinstance(v, np.ndarray):
            return v.tolist()

        # Arrow variants
        if pa is not None:
            if isinstance(v, pa.Scalar):
                x = v.as_py()
                return x if isinstance(x, list) else []
            if isinstance(v, pa.Array):
                return v.to_pylist()
            if isinstance(v, pa.ChunkedArray):
                return pa.concat_arrays(v.chunks).to_pylist()

        # null-ish
        if v is None or v is pd.NA:
            return []
        if isinstance(v, float) and math.isnan(v):
            return []

        return []  # fallback

    def _build_exact_index(
        self,
        openings: pd.DataFrame,
        id_col: str = "opening_id",
        san_col: str = "opening_moves_san",
        max_plies: int = 80,
    ) -> tuple[dict[tuple, int], int]:
        idx: dict[tuple, int] = {}
        max_len = 0
        for oid, san in openings[[id_col, san_col]].itertuples(index=False):
            sans = self.to_py_list(san)
            sans = sans[:max_plies]
            key = tuple(sans)
            max_len = max(max_len, len(key))
            if key not in idx or int(oid) < idx[key]:
                idx[key] = int(oid)
        return idx, max_len

    def _match_exact_longest(
        self, game_san, idx: dict[tuple, int], max_key_len: int
    ) -> tuple[int | None, int]:
        sans = self.to_py_list(game_san)
        n = min(len(sans), max_key_len)
        for k in range(n, 0, -1):
            key = tuple(sans[:k])
            if key in idx:
                return idx[key], k
        return None, 0

    def _attach_opening_ids(self, games: pd.DataFrame) -> pd.DataFrame:
        openings = pd.read_parquet(OPENINGS_PATH_PREPROCESSED)
        idx, max_key_len = self._build_exact_index(
            openings, id_col="opening_id", san_col="opening_moves_san", max_plies=80
        )
        matches = games["moves_san"].map(
            lambda x: self._match_exact_longest(x, idx, max_key_len)
        )
        opening_id, matched_plies = zip(*matches)

        out = games.copy()
        # nullable ints so missing stays NA in Parquet
        out["opening_id"] = pd.Series(opening_id, dtype="Int32")
        out["matched_plies"] = pd.Series(matched_plies, dtype="Int16")
        return out

    def _preprocess_and_save(self, cache: FileCache):
        df = cache.load_games_raw()

        # PGN fast summary
        p = pd.json_normalize(
            [self._parse_pgn_min_fast(x) for x in df["pgn"].astype(str)]
        )
        df = pd.concat([df.drop(columns=["pgn"]), p], axis=1)

        # drop unused
        drop_cols = [
            "eco_url",
            "game_url",
            "tournament_url",
            "username",
            "initial_setup_fen",
            "moves_normalized",
        ]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        df = self._attach_opening_ids(df)
        cache.save_games(df)

    def _fast_san_from_pgn(self, pgn_text: str) -> list[str]:
        if not pgn_text:
            return []
        s = _TAGS.sub("", pgn_text)  # drop header
        s = _COMMS.sub(" ", s)  # drop {comments}
        s = _VARS.sub(" ", s)  # drop (variations)
        s = _NAGS.sub(" ", s)  # drop $n
        s = _MOVENO.sub(" ", s)  # drop 12. or 12...
        s = _RESULT.sub(" ", s)  # drop result
        s = _WS.sub(" ", s).strip()
        # tokens now are SAN or clocks, etc.; filter out clocks if present
        toks = [t for t in s.split(" ") if not t.startswith("%clk")]
        # also drop bare '+' or '#' artifacts if present
        return [t for t in toks if t and t not in ["+", "#"]]

    def _parse_pgn_min_fast(self, pgn_text: str) -> dict:
        sans = self._fast_san_from_pgn(pgn_text)
        # clocks straight from text; no parsing tree needed
        clocks = re.findall(r"%clk\s+([0-9:.\-]+)", pgn_text)
        # ECO header without full parse
        eco = None
        m = re.search(r'^\[ECO\s+"([^"]+)"\]', pgn_text, re.M)
        if m:
            eco = m.group(1)
        moves_normalized = " ".join(
            (f"{(i//2)+1}. {m}" if i % 2 == 0 else m) for i, m in enumerate(sans)
        )
        return {
            "eco": eco,
            "moves_normalized": moves_normalized,
            "moves_san": sans,  # keep list; JSON-encode later if needed
            "clocks": clocks,  # keep list
            "n_plies": len(sans),
        }
