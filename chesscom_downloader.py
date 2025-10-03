# chesscom_downloader.py
import json
import logging
from pathlib import Path
from typing import Callable, Optional, Tuple, List

import pandas as pd
import requests
from models import CacheNode, GameModel, GameRow, IndexModel, MetaModel, MonthArchive, ProfileModel, StatsModel
from pydantic import TypeAdapter

logger = logging.getLogger("chesscom")

class ChesscomDownloader:
    def __init__(
        self,
        cache_root: Path = Path(".cache/chesscom"),
        contact_email: str = "you@example.com",
        timeout: float = 20.0,
        sleep_sec: float = 0.2,
        session: Optional[requests.Session] = None,
    ):
        self.cache_root = cache_root
        self.base_headers = {"User-Agent": f"ChessCom Analyzer (+mailto:{contact_email})"}
        self.timeout = timeout
        self.sleep_sec = sleep_sec
        self.sess = session or requests.Session()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    # ---------- public ----------
    def download_all(self, username: str, progress_cb: Optional[Callable[[int, int], None]] = None) -> Tuple[pd.DataFrame, MetaModel]:
        u = username.strip().lower()
        cdir = self._ensure_user_dir(u)
        idx = self._load_index(cdir)

        profile = self.fetch_profile(u, cdir, idx)
        stats = self.fetch_stats(u, cdir, idx)

        archives = self.list_archives(u)
        meta = MetaModel(
            username=u,
            archives_count=len(archives),
            profile_cached=profile is not None,
            stats_cached=stats is not None,
        )
        if not archives:
            return pd.DataFrame(), meta

        rows: List[GameRow] = []
        total = len(archives)
        for i, month_url in enumerate(archives, start=1):
            games = self.fetch_month_games(month_url, cdir, idx)
            rows.extend(GameRow.from_game(g) for g in games)
            if progress_cb:
                progress_cb(i, total)

        # To DataFrame
        ta = TypeAdapter(List[GameRow])
        rows_dicts = [ta.validate_python([r])[0].model_dump() for r in rows]  # fully validated dicts
        df = pd.DataFrame(rows_dicts)

        if not df.empty:
            # Normalize types for pandas
            df["end_time_iso"] = pd.to_datetime(df["end_time_iso"], utc=True)
            for c in ["white_rating", "black_rating"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            # Persist
            dfp = cdir / "games.parquet"
            dfc = cdir / "games.csv"
            df.to_parquet(dfp, index=False)
            df.to_csv(dfc, index=False, encoding="utf-8")
            meta.parquet_path = str(dfp)
            meta.csv_path = str(dfc)
            logger.info(f"Saved {dfp} and {dfc}")

        meta.games_count = int(len(df))
        self._save_index(cdir, idx)
        return df, meta

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

    def fetch_month_games(self, url: str, cache_dir: Path, idx: IndexModel) -> List[GameModel]:
        entry = idx.get_or_create_archive(url)
        data = self._fetch_conditional_json(url, entry.node)
        if not data:
            return []
        archive = MonthArchive.model_validate(data)
        month = url.rsplit("/", 2)[-1].replace("/", "-")
        p = cache_dir / "archives" / f"{month}.json"
        p.write_text(archive.model_dump_json(indent=2), encoding="utf-8")
        entry.node.path = str(p)
        self._save_index(cache_dir, idx)
        logger.info(f"{len(archive.games)} games in {month}")
        return archive.games

    # ---------- internals ----------
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
