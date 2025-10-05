# chesscom_downloader.py
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Optional, List

import pandas as pd
from pydantic import BaseModel, Field
import requests
from utils.models import GameModel, GameRow, MonthArchive, ProfileModel, StatsModel
from utils.openings_catalog import join_openings_to_games
import io, re, json
import pandas as pd
import chess.pgn

logger = logging.getLogger("chesscom")

# precompile once at module import
_TAGS   = re.compile(r"^\[.*?\]\s*", re.S | re.M)       # tag pair section
_COMMS  = re.compile(r"\{[^}]*\}")                      # {...}
_VARS   = re.compile(r"\([^()]*\)")                     # ( ... )
_NAGS   = re.compile(r"\$\d+")
_WS     = re.compile(r"\s+")
_MOVENO = re.compile(r"\d+\.(?:\.\.)?")                 # 12. or 12...
_RESULT = re.compile(r"(1-0|0-1|1/2-1/2|\*)")

# ---------- Cache + HTTP ----------
class IndexEntry(BaseModel):
    url: str
    etag: Optional[str] = None
    created_on: str = datetime.now().isoformat()
    updated_on: Optional[str] = None

    def is_update_needed(self) -> bool:
        return (self.updated_on is None
                or datetime.fromisoformat(self.updated_on) < datetime.now() - timedelta(hours=24))

class IndexModel(BaseModel):
    archives_list: IndexEntry
    archives: List[IndexEntry] = Field(default_factory=list)

class ChesscomDownloader:
    def __init__(
        self,
        username: str,
        timezone:str|None,
        cache_root: Path = Path(".cache/chesscom"),
        contact_email: str = "infomadevisual@gmail.com",
        timeout: float = 20.0,
        sleep_sec: float = 0.2,
        session: Optional[requests.Session] = None,
    ):
        self.cache_root = cache_root
        self.base_headers = {"User-Agent": f"chess.com Analyzer (+mailto:{contact_email})"}
        self.username = username.strip().lower()
        self.timezone = timezone
        self.timeout = timeout
        self.sleep_sec = sleep_sec
        self.sess = session or requests.Session()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    @property
    def archives_url(self) -> str:
        return f"https://api.chess.com/pub/player/{self.username}/games/archives"

    @property
    def cache_dir(self) -> Path:
         return self.cache_root / self.username

    @property
    def index_path(self) -> Path:
        return self.cache_dir / "index.json"

    @property
    def games_path(self) -> Path:
        return self.cache_dir / "games.parquet"

    # ---------- public ----------
    def load_from_cache(self) -> pd.DataFrame:
        df = self._read_parquet()
        if df is None or df.empty:
            return pd.DataFrame()

        # timezone column
        if "end_time" in df.columns:
            df["end_time_local"] = df["end_time"].dt.tz_convert(self.timezone)

        # fast PGN parse
        rows = [self._parse_pgn_min_fast(x) for x in df["pgn"].astype(str)]
        pgn_cols = pd.json_normalize(rows)
        df = pd.concat([df.drop(columns=["pgn"]), pgn_cols], axis=1)

        # openings
        df = join_openings_to_games(df)
        return df


    def download_all(self, progress_cb=None) -> pd.DataFrame:
        # Load / Create Index
        idx = IndexModel(archives_list=IndexEntry(url=self.archives_url))
        
        idx_path = self.cache_dir / "index.json"
        if idx_path.exists():
            try:
                idx = IndexModel.model_validate_json(idx_path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("index corrupt -> recreate")

        # Reload archive list if older than 24 hours
        if idx.archives_list.is_update_needed():
            headers = dict(self.base_headers)
            if idx.archives_list.etag:
                headers["If-None-Match"] = idx.archives_list.etag

            try:
                r = self.sess.get(self.archives_url, headers=headers, timeout=self.timeout)
                if r.status_code == 200:
                    urls = r.json().get("archives", [])
                    prev = {a.url: a for a in idx.archives}
                    idx.archives = []
                    for u in urls:
                        e = prev.get(u, IndexEntry(url=u))
                        idx.archives.append(e)
                    idx.archives_list.etag = r.headers.get("ETag")
                    idx.archives_list.updated_on = datetime.now().isoformat()

                if r.status_code == 304:
                    logger.info(f"304 - archives not modified for {self.username}")
                    idx.archives_list.updated_on = datetime.now().isoformat()
                if r.status_code == 404:
                    logger.warning(f"404 - user not found: {self.username}")

            except requests.RequestException as e:
                logger.exception(f"archives error: {e}")

        # Iterate over each archive and check whether it needs update (only updated every 24 hours with etag)
        rows: list[GameRow] = []
        total_archives = len(idx.archives)
        for i, archive_idx in enumerate(idx.archives, start=1):
            if not archive_idx.is_update_needed():
                logger.info(f"Skipping as no updated needed: {archive_idx.url}")
                continue

            data = self._fetch_conditional_json(archive_idx)
            if data is None:
                continue

            archive = MonthArchive.model_validate({"games": data.get("games", [])})

            logger.info(f"HTTP {len(archive.games)} games from {archive_idx.url}")

            rows.extend(GameRow.from_game(g, self.username) for g in archive.games)
            archive_idx.updated_on = datetime.now().isoformat()
            if progress_cb: progress_cb(i, total_archives)

        # Build dataframe of updated games
        new_df = pd.DataFrame([r.model_dump() for r in rows]) if rows else pd.DataFrame()
        if not new_df.empty:
            new_df["end_time"] = pd.to_datetime(new_df["end_time"], utc=True)
            for c in ["user_rating", "opponent_rating"]:
                new_df[c] = pd.to_numeric(new_df[c], errors="coerce")

        # Merge with existing parquet
        existing = self._read_parquet()

        if existing is None:
            df_final = new_df
        elif new_df.empty:
            df_final = existing
        else:
            existing["end_time"] = pd.to_datetime(existing["end_time"], utc=True, errors="coerce")

            # Month-Replacement + Prefer new rows
            upd_months = set(new_df["end_time"].dt.to_period("M"))
            keep_mask = ~existing["end_time"].dt.to_period("M").isin(upd_months)
            merged = pd.concat([existing[keep_mask], new_df], ignore_index=True, copy=False)

            # Key mit Fallback, neue Versionen gewinnen
            key = merged["game_url"].fillna(merged.get("pgn_url"))
            merged = (
                merged.assign(__key=key, __is_new=merged.index >= len(existing[keep_mask]))
                .sort_values(["__key", "__is_new", "end_time"])
                .drop_duplicates(subset="__key", keep="last")
                .drop(columns=["__key", "__is_new"])
                .sort_values("end_time")
                .reset_index(drop=True)
            )
            df_final = merged

        # Persist Parquet & Index
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if df_final is not None and not df_final.empty:
            df_final.to_parquet(self.games_path, index=False)

        self.index_path.write_text(idx.model_dump_json(indent=2), encoding="utf-8")
        return self.load_from_cache()

    # ---- internals ----
    def _fast_san_from_pgn(self, pgn_text: str) -> list[str]:
        if not pgn_text:
            return []
        s = _TAGS.sub("", pgn_text)         # drop header
        s = _COMMS.sub(" ", s)              # drop {comments}
        s = _VARS.sub(" ", s)               # drop (variations)
        s = _NAGS.sub(" ", s)               # drop $n
        s = _MOVENO.sub(" ", s)             # drop 12. or 12...
        s = _RESULT.sub(" ", s)             # drop result
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
            "moves_san_json": sans,      # keep list; JSON-encode later if needed
            "clocks_json": clocks,       # keep list
            "n_plies": len(sans),
        }

    def _read_parquet(self) -> Optional[pd.DataFrame]:
        if self.games_path.exists():
            try:
                df = pd.read_parquet(self.games_path)
                if "end_time" in df.columns:
                    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)
                return df
            except Exception as e:
                logger.warning(f"Parquet read failed {self.games_path}: {e}")
                return None
        return None

    def _fetch_conditional_json(self, idx: IndexEntry) -> Optional[dict]:
        headers = dict(self.base_headers)
        if idx.etag:
            headers["If-None-Match"] = idx.etag

        logger.info(f"GET {idx.url}")
        try:
            r = self.sess.get(idx.url, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"request error {idx.url}: {e}")
            return None

        if r.status_code == 304:
            logger.info(f"304 (Not Modified) - {idx.url}")
            return None

        if r.status_code == 200:
            logger.info(f"200 (OK) - {idx.url}")
            idx.etag = r.headers.get("ETag")
            idx.created_on = datetime.now().isoformat()
            try:
                return r.json()
            except ValueError:
                logger.error(f"json parse error {idx.url}")
                return None

        if r.status_code == 429:
            logger.warning(f"429 Too Many Requests, Retry-After={r.headers.get('Retry-After')}")
            return None

        if r.status_code == 404:
            logger.warning(f"404 {idx.url}")
            return None

        logger.warning(f"{r.status_code} {idx.url}")
        return None
