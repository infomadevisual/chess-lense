# models.py
from __future__ import annotations
from typing import Optional, List, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict

# ---------- Cache + HTTP ----------
class CacheNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    path: Optional[str] = None

class ArchiveEntry(BaseModel):
    url: str
    node: CacheNode = Field(default_factory=CacheNode)

class IndexModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    profile: CacheNode = Field(default_factory=CacheNode)
    stats: CacheNode = Field(default_factory=CacheNode)
    archives: List[ArchiveEntry] = Field(default_factory=list)

    def get_or_create_archive(self, url: str) -> ArchiveEntry:
        for a in self.archives:
            if a.url == url:
                return a
        a = ArchiveEntry(url=url)
        self.archives.append(a)
        return a

# ---------- API payloads ----------
class PlayerRef(BaseModel):
    username: Optional[str] = None
    rating: Optional[int] = None
    result: Optional[str] = None

class GameModel(BaseModel):
    url: Optional[str] = None
    pgn: Optional[str] = None
    time_control: Optional[str] = None
    time_class: Optional[str] = None
    rules: Optional[str] = None
    rated: bool = False
    end_time: Optional[int] = None  # epoch seconds
    initial_setup: Optional[str] = None
    eco: Optional[str] = None
    opening: Optional[str] = None
    termination: Optional[str] = None
    white: PlayerRef = Field(default_factory=PlayerRef)
    black: PlayerRef = Field(default_factory=PlayerRef)

class MonthArchive(BaseModel):
    games: List[GameModel] = Field(default_factory=list)

class ProfileModel(BaseModel):
    # chess.com profile has many fields; capture the common ones safely
    username: Optional[str] = None
    player_id: Optional[int] = None
    status: Optional[str] = None
    joined: Optional[int] = None  # epoch
    url: Optional[str] = None
    name: Optional[str] = None

class StatsModel(BaseModel):
    # keep raw to avoid breaking on schema drift
    raw: Any = None

# ---------- Normalized row for DataFrame ----------
class GameRow(BaseModel):
    game_url: Optional[str] = None
    # Direct link to the game page on chess.com

    pgn_url: Optional[str] = None
    # Link to the PGN file of the game

    time_control: Optional[str] = None
    # Time control format (e.g. "600+0" = 10 minutes, no increment)

    time_class: Optional[str] = None
    # Game category: "bullet", "blitz", "rapid", "daily"

    rules: Optional[str] = None
    # Ruleset, usually "chess", sometimes variants like "chess960"

    rated: bool = False
    # True if the game was rated and affected Elo ratings

    end_time: Optional[datetime] = None
    # UTC datetime when the game ended

    initial_setup_fen: Optional[str] = None
    # Starting position in FEN notation (non-standard in Chess960, etc.)

    white_username: Optional[str] = None
    # Username of the white player

    white_rating: Optional[int] = None
    # Elo rating of the white player at the time of the game

    white_result: Optional[str] = None
    # Result from white's perspective ("win", "checkmated", "timeout", "resigned",
    # "stalemate", "agreed", "repetition", "abandoned", etc.)

    black_username: Optional[str] = None
    # Username of the black player

    black_rating: Optional[int] = None
    # Elo rating of the black player at the time of the game

    black_result: Optional[str] = None
    # Result from black's perspective (same codes as white_result)

    eco: Optional[str] = None
    # ECO (Encyclopaedia of Chess Openings) code, e.g. "C65"

    opening: Optional[str] = None
    # Opening name, e.g. "Ruy Lopez, Berlin Defense"

    termination: Optional[str] = None
    # Termination type reported by the server ("normal", "time vs. insufficient material",
    # "abandoned", etc.)

    @staticmethod
    def from_game(g: GameModel) -> "GameRow":
        ts = datetime.fromtimestamp(g.end_time, tz=timezone.utc) if g.end_time else None
        return GameRow(
            game_url=g.url,
            pgn_url=g.pgn,
            time_control=g.time_control,
            time_class=g.time_class,
            rules=g.rules,
            rated=g.rated,
            end_time=ts,
            initial_setup_fen=g.initial_setup,
            white_username=g.white.username,
            white_rating=g.white.rating,
            white_result=g.white.result,
            black_username=g.black.username,
            black_rating=g.black.rating,
            black_result=g.black.result,
            eco=g.eco,
            opening=g.opening,
            termination=g.termination,
        )

# ---------- Meta for UI ----------
class MetaModel(BaseModel):
    username: str
    archives_count: int = 0
    games_count: int = 0
    profile_cached: bool = False
    stats_cached: bool = False
    parquet_path: Optional[str] = None
    csv_path: Optional[str] = None
