# chesscom_downloader.py
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Optional, List

import pandas as pd
import requests
from models import CacheNode, GameModel, GameRow, IndexModel, MonthArchive, ProfileModel, StatsModel

logger = logging.getLogger("chesscom")

class ChesscomDownloader:
    def __init__(
        self,
        cache_root: Path = Path(".cache/chesscom"),
        contact_email: str = "infomadevisual@gmail.com",
        timeout: float = 20.0,
        sleep_sec: float = 0.2,
        session: Optional[requests.Session] = None,
    ):
        self.cache_root = cache_root
        self.base_headers = {"User-Agent": f"chess.com Analyzer (+mailto:{contact_email})"}
        self.timeout = timeout
        self.sleep_sec = sleep_sec
        self.sess = session or requests.Session()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    # ---------- public ----------
    def load_from_cache(self, username: str, timezone:str|None, progress_cb=None) -> pd.DataFrame:
        u = username.strip().lower()
        cdir = self._ensure_user_dir(u)
        df_existing = self._read_parquet(cdir)  # -> DataFrame oder None

        if df_existing is None:
            return pd.DataFrame()

        # Convert to TZ
        df_existing["end_time_local"] = df_existing["end_time"].dt.tz_convert(timezone)

        # --- derive extra columns ---
        df_existing["year"] = df_existing["end_time_local"].dt.year
        df_existing["month"] = df_existing["end_time_local"].dt.month          # 1–12
        df_existing["month_name"] = df_existing["end_time_local"].dt.strftime("%B")
        df_existing["weekday"] = df_existing["end_time_local"].dt.dayofweek    # 0=Mon .. 6=Sun
        df_existing["weekday_name"] = df_existing["end_time_local"].dt.strftime("%A")

        return df_existing

    def download_all(self, username: str, timezone:str|None, progress_cb=None) -> pd.DataFrame:
        cdir = self._ensure_user_dir(username)
        idx = self._load_index(cdir)

        # Profile/Stats
        self.fetch_profile(username, cdir, idx)
        self.fetch_stats(username, cdir, idx)

        archives = self.list_archives(username)

        # 1) Load parquet
        df_existing = self._read_parquet(cdir)  # -> DataFrame oder None
        months_in_parquet = self._months_in_df(df_existing) if df_existing is not None else set()

        # 2) Get new data (only of current month if cached already)
        rows: list[GameRow] = []
        total = len(archives)
        for i, month_url in enumerate(archives, start=1):
            y, m = self._parse_ym_from_url(month_url)
            month_key = f"{y}-{m:02d}"
            is_current = self._is_current_month(y, m)
            already_ingested = month_key in months_in_parquet

            if not is_current and already_ingested:
                # Historischer Monat bereits im Parquet -> skip
                logger.info(f"SKIP {month_key} (already in parquet)")
                if progress_cb: progress_cb(i, total)
                continue

            games = self._fetch_month_games_http(month_url, idx)
            rows.extend(GameRow.from_game(g, username) for g in games)
            if progress_cb: progress_cb(i, total)

        # 3) build dataframe
        if rows:
            new_df = pd.DataFrame([r.model_dump() for r in rows])
            if not new_df.empty:
                new_df["end_time"] = pd.to_datetime(new_df["end_time"], utc=True)
                for c in ["user_rating", "opponent_rating"]:
                    new_df[c] = pd.to_numeric(new_df[c], errors="coerce")
        else:
            new_df = pd.DataFrame()

        # 4) Merge with existing parquet
        if df_existing is None:
            df_final = new_df
        else:
            if new_df.empty:
                df_final = df_existing
            else:
                # Ersetze alle Monate, die in new_df vorkommen
                upd_months = set(new_df["end_time"].dt.strftime("%Y-%m").unique())
                mask_keep = ~df_existing["end_time"].dt.strftime("%Y-%m").isin(upd_months)
                df_final = pd.concat([df_existing[mask_keep], new_df], ignore_index=True)
                # Optional: Dedupe via game_url
                if "game_url" in df_final.columns:
                    df_final = df_final.sort_values("end_time").drop_duplicates("game_url", keep="last")

        # Convert to TZ
        df_final["end_time_local"] = df_final["end_time"].dt.tz_convert(timezone)

        # --- derive extra columns ---
        df_final["year"] = df_final["end_time_local"].dt.year
        df_final["month"] = df_final["end_time_local"].dt.month          # 1–12
        df_final["weekday"] = df_final["end_time_local"].dt.dayofweek    # 0=Mon .. 6=Sun
        df_final["weekday_name"] = df_final["end_time_local"].dt.strftime("%A")

        # 5) Persist Parquet
        dfp = cdir / "games.parquet"
        if df_final is not None and not df_final.empty:
            df_final.to_parquet(dfp, index=False)

        self._save_index(cdir, idx)
        return df_final if df_final is not None else pd.DataFrame()

    def fetch_profile(self, username: str, cache_dir: Path, idx: IndexModel) -> Optional[ProfileModel]:
        url = f"https://api.chess.com/pub/player/{username}"
        data = self._fetch_conditional_json(url, idx.profile)
        if not data:
            return None
        prof = ProfileModel.model_validate(data)
        p = cache_dir / "profile.json"
        p.write_text(ProfileModel.model_dump_json(prof, indent=2), encoding="utf-8")
        idx.profile.path = str(p)
        self._save_index(cache_dir, idx)
        return prof

    def fetch_stats(self, username: str, cache_dir: Path, idx: IndexModel) -> Optional[StatsModel]:
        url = f"https://api.chess.com/pub/player/{username}/stats"
        data = self._fetch_conditional_json(url, idx.stats)
        if not data:
            return None
        stats = StatsModel(raw=data)
        p = cache_dir / "stats.json"
        p.write_text(stats.model_dump_json(indent=2), encoding="utf-8")
        idx.stats.path = str(p)
        self._save_index(cache_dir, idx)
        return stats

    def list_archives(self, username: str) -> List[str]:
        url = f"https://api.chess.com/pub/player/{username}/games/archives"
        try:
            r = self.sess.get(url, headers=self.base_headers, timeout=self.timeout)
            if r.status_code == 200:
                arcs = r.json().get("archives", [])
                logger.info(f"{len(arcs)} archives for {username}")
                return arcs
            if r.status_code == 404:
                logger.warning(f"user not found: {username}")
                return []
            logger.warning(f"archives non-200: {r.status_code}")
        except requests.RequestException as e:
            logger.error(f"archives error: {e}")
        return []

    # ---- internals ----
    def _read_parquet(self, cache_dir: Path) -> Optional[pd.DataFrame]:
        p = cache_dir / "games.parquet"
        if p.exists():
            try:
                df = pd.read_parquet(p)
                if "end_time" in df.columns:
                    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)
                return df
            except Exception as e:
                logger.warning(f"Parquet read failed {p}: {e}")
        return None

    def _months_in_df(self, df: pd.DataFrame) -> set[str]:
        if df is None or df.empty or "end_time" not in df.columns:
            return set()
        return set(df["end_time"].dt.strftime("%Y-%m").unique())

    def _parse_ym_from_url(self, url: str) -> tuple[int, int]:
        parts = url.rstrip("/").split("/")
        return int(parts[-2]), int(parts[-1])

    def _is_current_month(self, y: int, m: int) -> bool:
        now = datetime.now(timezone.utc)
        return (y == now.year) and (m == now.month)

    def _fetch_month_games_http(self, url: str, idx: IndexModel) -> list[GameModel]:
        # Optional: Conditional GET nur für aktuellen Monat sinnvoll
        # Hier weiter ETag/Last-Modified auf entry.node pflegen, aber ohne path
        entry = idx.get_or_create_archive(url)
        data = self._fetch_conditional_json(url, entry.node)
        if not data:
            return []
        archive = MonthArchive.model_validate(data)
        logger.info(f"HTTP {len(archive.games)} games from {url}")
        return archive.games

    def fetch_month_games(self, url: str, cache_dir: Path, idx: IndexModel) -> List[GameModel]:
        y, m = self._parse_ym_from_url(url)
        month_key = f"{y}-{m:02d}"
        p = cache_dir / "archives" / f"{month_key}.json"

        entry = idx.get_or_create_archive(url)

        # 1) Historische Monate: direkt aus Datei, kein HTTP
        if not self._is_current_month(y, m) and p.exists():
            logger.info(f"LOAD-CACHE {month_key} (historical)")
            entry.node.path = str(p)
            try:
                return MonthArchive.model_validate_json(p.read_text(encoding="utf-8")).games
            except Exception as e:
                logger.warning(f"Cache read failed {p}: {e} -> fallback to HTTP")

        # 2) Aktueller Monat ODER Cache fehlt: Conditional GET
        data = self._fetch_conditional_json(url, entry.node)
        if not data:
            # 304 oder Fehler -> falls Datei existiert, daraus laden
            if p.exists():
                try:
                    return MonthArchive.model_validate_json(p.read_text(encoding="utf-8")).games
                except Exception as e:
                    logger.error(f"Fallback cache read failed {p}: {e}")
            return []

        archive = MonthArchive.model_validate(data)
        p.write_text(archive.model_dump_json(indent=2), encoding="utf-8")
        entry.node.path = str(p)
        self._save_index(cache_dir, idx)
        logger.info(f"{len(archive.games)} games in {month_key}")
        return archive.games
    
    def _ensure_user_dir(self, username: str) -> Path:
        p = self.cache_root / username
        p.mkdir(parents=True, exist_ok=True)
        (p / "archives").mkdir(exist_ok=True)
        return p

    def _load_index(self, cache_dir: Path) -> IndexModel:
        ip = cache_dir / "index.json"
        if ip.exists():
            try:
                return IndexModel.model_validate_json(ip.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("index corrupt -> recreate")
        return IndexModel()

    def _save_index(self, cache_dir: Path, idx: IndexModel) -> None:
        (cache_dir / "index.json").write_text(idx.model_dump_json(indent=2), encoding="utf-8")

    def _fetch_conditional_json(self, url: str, node: CacheNode) -> Optional[dict]:
        headers = dict(self.base_headers)
        if node.etag:
            headers["If-None-Match"] = node.etag
        if node.last_modified:
            headers["If-Modified-Since"] = node.last_modified

        logger.info(f"GET {url}")
        try:
            r = self.sess.get(url, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"request error {url}: {e}")
            return None

        if r.status_code == 304:
            logger.info(f"304 (Not Modified) - {url}")
            if node.path and Path(node.path).exists():
                try:
                    return json.loads(Path(node.path).read_text(encoding="utf-8"))
                except Exception as e:
                    logger.error(f"cache read error {node.path}: {e}")
            return None

        if r.status_code == 200:
            logger.info(f"200 (OK) - {url}")
            node.etag = r.headers.get("ETag")
            node.last_modified = r.headers.get("Last-Modified")
            try:
                return r.json()
            except ValueError:
                logger.error(f"json parse error {url}")
                return None

        if r.status_code == 429:
            logger.warning(f"429 Too Many Requests, Retry-After={r.headers.get('Retry-After')}")
            return None

        if r.status_code == 404:
            logger.warning(f"404 {url}")
            return None

        logger.warning(f"{r.status_code} {url}")
        return None
