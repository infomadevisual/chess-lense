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
    rated: Optional[bool] = False
    end_time: Optional[int] = None
    initial_setup: Optional[str] = None
    eco: Optional[str] = None
    tournament: Optional[str] = None
    white: PlayerRef
    black: PlayerRef

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
    end_time: Optional[datetime] = None
    username: Optional[str] = None
    opponent_username: Optional[str] = None
    user_played_as: Optional[str] = None
    user_result: Optional[str] = None
    user_result_simple: Optional[str] = None
    opponent_result:Optional[str] = None
    user_rating: Optional[int] = None
    opponent_rating: Optional[int] = None
    rated: Optional[bool] = None
    rules: Optional[str] = None
    time_class: Optional[str] = None
    time_control: Optional[str] = None
    initial_setup_fen: Optional[str] = None
    game_url: Optional[str] = None
    pgn_url: Optional[str] = None
    eco_url: Optional[str] = None
    tournament_url: Optional[str] = None

    @staticmethod
    def from_game(g: GameModel, username: str) -> "GameRow":
        if g.black.username != None and g.black.username.strip().lower() == username:
            user_played_as = "black"
            user_name = g.black.username
            opponent_username = g.white.username
            user_rating = g.black.rating
            opponent_rating = g.white.rating
            user_result = g.black.result
            opponent_result = g.white.result
        elif g.white.username != None and g.white.username.strip().lower() == username:
            user_played_as = "white"
            user_name = g.white.username
            opponent_username = g.black.username
            user_rating = g.white.rating
            opponent_rating = g.black.rating
            user_result = g.white.result
            opponent_result = g.black.result
        else:
            print("Something went wrong, skipping game.")

        return GameRow(
            end_time=datetime.fromtimestamp(g.end_time, tz=timezone.utc) if g.end_time else None,
            username=user_name,
            opponent_username=opponent_username,
            user_played_as=user_played_as,
            user_result=user_result,
            user_result_simple=GameRow.simplify_result(user_result),
            opponent_result=opponent_result,
            user_rating=user_rating,
            rated=g.rated,
            opponent_rating=opponent_rating,
            rules=g.rules,
            time_class=g.time_class,
            time_control=g.time_control,
            initial_setup_fen=g.initial_setup,
            game_url=g.url,
            eco_url=g.eco,
            tournament_url=g.tournament,
            pgn_url=g.pgn,
        )
    
    @staticmethod
    def simplify_result(result: Optional[str]) -> Optional[str]:
        if result is None:
            return None
        result = result.lower()
        if result in ["win"]:
            return "win"
        if result in ["agreed", "stalemate", "repetition", "insufficient", "50move", "timevsinsufficient"]:
            return "draw"
        if result in ["checkmated", "resigned", "timeout", "abandoned", "lose"]:
            return "loss"
        return None  # fallback if chess.com adds new codes