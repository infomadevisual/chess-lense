# chesscom_downloader.py
import logging
from datetime import datetime

import requests

from services.file_cache import IndexEntry, IndexModel
from utils.models import GameModel, GameRow, MonthArchive
from utils.openings_catalog import join_openings_to_games

logger = logging.getLogger("chesscom")


class ChesscomDownloader:
    def __init__(
        self,
        contact_email: str = "infomadevisual@gmail.com",
        timeout: float = 20.0,
        sleep_sec: float = 0.2,
        session: requests.Session | None = None,
    ):
        self.base_headers = {
            "User-Agent": f"chess.com Analyzer (+mailto:{contact_email})"
        }
        self.timeout = timeout
        self.sleep_sec = sleep_sec
        self.sess = session or requests.Session()

    # ---------- public ----------
    def download_index(self, username: str) -> IndexModel:
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"

        idx = IndexModel(archives_list=IndexEntry(url=archives_url))
        # Reload archive list if older than 24 hours
        headers = dict(self.base_headers)
        if idx.archives_list.etag:
            headers["If-None-Match"] = idx.archives_list.etag

        try:
            r = self.sess.get(archives_url, headers=headers, timeout=self.timeout)
            if r.status_code == 200:
                urls = r.json().get("archives", [])
                prev = {a.url: a for a in idx.archives}
                idx.archives = []
                for u in urls:
                    e = prev.get(u, IndexEntry(url=u))
                    idx.archives.append(e)
                idx.archives_list.etag = r.headers.get("ETag")
                idx.archives_list.updated_on = datetime.now().isoformat()
                logger.info(f"{username}: 200 - archives downloaded")

            if r.status_code == 304:
                logger.info(f"{username}: 304 - archives not modified")
                idx.archives_list.updated_on = datetime.now().isoformat()
            if r.status_code == 404:
                logger.warning(f"{username}: 404 - user not found")

        except requests.RequestException as e:
            logger.exception(f"{username}: archives error: {e}")
            raise e

        return idx

    def download_archive(self, idx: IndexEntry) -> list[GameModel] | None:
        data = self._fetch_conditional_json(idx)
        if data is None:
            return None

        archive = MonthArchive.model_validate({"games": data.get("games", [])})
        logger.info(f"HTTP {len(archive.games)} games from {idx.url}")
        return archive.games

    # ---- internals ----
    def _fetch_conditional_json(self, idx: IndexEntry) -> dict | None:
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
            logger.warning(
                f"429 Too Many Requests, Retry-After={r.headers.get('Retry-After')}"
            )
            return None

        if r.status_code == 404:
            logger.warning(f"404 {idx.url}")
            return None

        logger.warning(f"{r.status_code} {idx.url}")
        return None
