# utils/openings_catalog.py
import io, re
from urllib.parse import urlparse, unquote
import chess.pgn
import re, pandas as pd, streamlit as st
import pandas as pd

_rm_nums = re.compile(r"\d+\.(\.\.)?")
_rm_syms = re.compile(r"[+#?!x]")

def attach_openings(games: pd.DataFrame, catalog: pd.DataFrame | None = None) -> pd.DataFrame:
    if games is None or games.empty: return games
    cat = catalog if catalog is not None else load_openings_catalog()
    out = games.copy()

    def _series(df: pd.DataFrame, col: str) -> pd.Series:
        return df[col] if col in df.columns else pd.Series([""] * len(df), index=df.index, dtype="string")

    eco_url_s = _series(out, "eco_url")
    pgn_s     = _series(out, "pgn")
    out["eco_slug"]    = eco_url_s.astype("string").map(_slug_from_eco_url)
    out["moves_key12"] = pgn_s.astype("string").map(lambda s: _san_prefix_from_pgn(str(s), 12))

    # 1) match by eco_slug
    m1 = out.merge(cat.add_prefix("o_"), left_on="eco_slug", right_on="o_o_slug", how="left")

    # 2) fill misses by moves_key12
    miss = m1["o_name"].isna()
    if miss.any():
        m2 = out.loc[miss, ["moves_key12"]].merge(
            cat.add_prefix("o_"),
            left_on="moves_key12", right_on="o_o_moves_key12", how="left"
        )
        for col in ["o_eco","o_name","o_variation","o_moves"]:
            m1.loc[miss, col] = m2[col].values

    # final columns
    m1["opening_eco"] = m1["o_eco"]
    m1["opening_name"] = m1.apply(
        lambda r: r["o_name"] if not isinstance(r.get("o_variation"), str) or r["o_variation"]=="" 
        else f'{r["o_name"]}, {r["o_variation"]}', axis=1)
    m1["opening_moves"] = m1["o_moves"]

    return m1.drop(columns=[c for c in m1.columns if c.startswith("o_")])

def _moves_key(s: str, max_ply: int = 12) -> str:
    if not isinstance(s, str): return ""
    s = _rm_nums.sub("", s)          # drop "1." or "1..."
    toks = [ _rm_syms.sub("", t).strip().lower()
             for t in s.split() if t and t not in {"1-0","0-1","1/2-1/2","*"} ]
    return " ".join(toks[:max_ply])

@st.cache_data(show_spinner=False)
def load_openings_catalog(path: str = "data/openings.parquet") -> pd.DataFrame:
    cat = pd.read_parquet(path)
    # expected columns: eco, name, variation, moves (SAN string)
    cat["eco"] = cat["eco"].astype(str).str.upper()
    cat["name"] = cat["name"].astype(str)
    cat["variation"] = (
        cat["variation"].fillna("").astype(str)
        if "variation" in cat.columns
        else pd.Series([""] * len(cat), index=cat.index, dtype="string")
    )
    cat["moves"] = (
        cat["moves"].fillna("").astype(str)
        if "moves" in cat.columns
        else pd.Series([""] * len(cat), index=cat.index, dtype="string")
    )
    cat["o_moves_key12"] = cat["moves"].map(lambda s: _moves_key(s, 12))
    # derive a slug for chess.com URLs if repo doesn't provide one
    cat["o_slug"] = (cat["name"] + " " + cat["variation"].where(cat["variation"]!="","")).str.strip().str.lower().str.replace(r"[^a-z0-9]+","-",regex=True).str.strip("-")
    return cat[["eco","name","variation","moves","o_moves_key12","o_slug"]].drop_duplicates()


def _slug_from_eco_url(eco_url) -> str:
    if eco_url is None or pd.isna(eco_url):
        return ""
    s = str(eco_url).strip()
    if not s:
        return ""
    last = unquote(urlparse(s).path).strip("/").split("/")[-1]
    return re.split(r"-\d+\.", last, maxsplit=1)[0].lower()

def _san_prefix_from_pgn(pgn_text: str, max_ply: int = 12) -> str:
    if pgn_text is None or pd.isna(pgn_text):
        return ""
    g = chess.pgn.read_game(io.StringIO(pgn_text))
    if g is None: return ""
    toks = []
    node = g
    while node.variations and len(toks) < max_ply:
        node = node.variations[0]
        san = node.san()
        san = _rm_syms.sub("", san).lower()
        toks.append(san)
    return " ".join(toks)

