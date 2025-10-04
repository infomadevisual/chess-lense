# utils/openings_catalog.py

import io, re, pandas as pd, streamlit as st
from urllib.parse import urlparse, unquote
import chess.pgn
import pandas as pd
from utils.openings_catalog import (
    load_openings_catalog, _slug_from_eco_url, _san_prefix_from_pgn
)

_rm_nums = re.compile(r"\d+\.(\.\.)?")
_rm_syms = re.compile(r"[+#?!x]")

def _moves_key(s: str, max_ply: int = 12) -> str:
    if not isinstance(s, str):
        return ""
    s = _rm_nums.sub("", s)
    toks = [_rm_syms.sub("", t).strip().lower()
            for t in s.split() if t and t not in {"1-0","0-1","1/2-1/2","*"}]
    return " ".join(toks[:max_ply])

def _slug_from_eco_url(eco_url) -> str:
    if eco_url is None or pd.isna(eco_url):
        return ""
    s = str(eco_url).strip()
    if not s:
        return ""
    last = unquote(urlparse(s).path).strip("/").split("/")[-1]
    return re.split(r"-\d+\.", last, maxsplit=1)[0].lower()

def _san_prefix_from_pgn(pgn_text, max_ply: int = 12) -> str:
    if pgn_text is None or pd.isna(pgn_text):
        return ""
    g = chess.pgn.read_game(io.StringIO(str(pgn_text)))
    if g is None:
        return ""
    toks, node = [], g
    while node.variations and len(toks) < max_ply:
        node = node.variations[0]
        toks.append(_rm_syms.sub("", node.san()).lower())
    return " ".join(toks)

def load_openings_catalog(path: str = "data/openings.parquet") -> pd.DataFrame:
    cat = pd.read_parquet(path)

    # normalize
    cat["eco"] = cat["eco"].astype(str).str.upper()
    cat["name"] = cat["name"].astype(str)
    cat["variation"] = (cat["variation"].fillna("").astype(str)
                        if "variation" in cat.columns
                        else pd.Series([""] * len(cat), index=cat.index, dtype="string"))
    cat["moves"] = (cat["moves"].fillna("").astype(str)
                    if "moves" in cat.columns
                    else pd.Series([""] * len(cat), index=cat.index, dtype="string"))

    cat["moves_key12"] = cat["moves"].map(lambda s: _moves_key(s, 12))
    cat["slug"] = (cat["name"] + " " + cat["variation"].where(cat["variation"] != "", ""))
    cat["slug"] = (cat["slug"].str.strip().str.lower()
                   .str.replace(r"[^a-z0-9]+", "-", regex=True).str.strip("-"))

    # keep clean names (no prefixes)
    return cat[["eco", "name", "variation", "moves", "moves_key12", "slug"]].drop_duplicates()


def attach_openings(games: pd.DataFrame, catalog: pd.DataFrame | None = None) -> pd.DataFrame:
    if games is None or games.empty: return games
    cat = catalog if catalog is not None else load_openings_catalog()
    out = games.copy()

    def _series(df: pd.DataFrame, col: str) -> pd.Series:
        return df[col] if col in df.columns else pd.Series([""] * len(df), index=df.index, dtype="string")

    eco_url_s = _series(out, "eco_url").astype("object").fillna("")
    pgn_s     = _series(out, "pgn").astype("object").fillna("")

    out["eco_slug"]    = eco_url_s.map(_slug_from_eco_url)
    out["moves_key12"] = pgn_s.map(lambda s: _san_prefix_from_pgn(s, 12))

    # Build lookups
    cat_lu = cat.rename(columns={
        "eco":"cat_eco","name":"cat_name","moves":"cat_moves",
        "moves_key12":"cat_moves_key12","slug":"cat_slug"
    })
    by_moves = (cat_lu.dropna(subset=["cat_moves_key12"])
                      .drop_duplicates("cat_moves_key12")
                      .set_index("cat_moves_key12"))
    by_slug  = (cat_lu.dropna(subset=["cat_slug"])
                      .drop_duplicates("cat_slug")
                      .set_index("cat_slug"))

    # 1) primary: moves
    out["cat_eco"]   = out["moves_key12"].map(by_moves["cat_eco"])
    out["cat_name"]  = out["moves_key12"].map(by_moves["cat_name"])
    out["cat_moves"] = out["moves_key12"].map(by_moves["cat_moves"])

    # 2) fallback: slug from chess.com URL
    miss = out["cat_name"].isna()
    if miss.any():
        out.loc[miss, "cat_eco"]   = out.loc[miss, "eco_slug"].map(by_slug["cat_eco"])
        out.loc[miss, "cat_name"]  = out.loc[miss, "eco_slug"].map(by_slug["cat_name"])
        out.loc[miss, "cat_moves"] = out.loc[miss, "eco_slug"].map(by_slug["cat_moves"])

    # Final columns
    out["opening_eco"]   = out["cat_eco"]
    out["opening_name"]  = out["cat_name"]
    out["opening_moves"] = out["cat_moves"]

    return out.drop(columns=["cat_eco","cat_name","cat_moves","eco_slug","moves_key12"])

