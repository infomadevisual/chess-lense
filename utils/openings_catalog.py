import numpy as np
import re, pandas as pd, streamlit as st
from collections import defaultdict

OPENING_KEY_PLY = 32
_rm_tags  = re.compile(r"^\[.*?\]\s*", re.MULTILINE)        # PGN headers
_rm_notes = re.compile(r"\{[^}]*\}|\([^)]*\)")              # comments/vars
_rm_nums  = re.compile(r"\b\d+\.(\.\.)?\b")                 # move numbers
_rm_nags  = re.compile(r"\$\d+")                            # NAGs like $4
_rm_syms  = re.compile(r"[+#?!]")                           # keep 'x' captures

def _norm_castling(tok: str) -> str:
    t = tok.replace("0-0-0", "O-O-O").replace("0-0", "O-O") # unify zeros to O
    return t

def san_key(text: str, n: int = OPENING_KEY_PLY) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    s = _rm_tags.sub(" ", text)
    s = _rm_notes.sub(" ", s)
    s = _rm_nags.sub(" ", s)
    s = _rm_nums.sub(" ", s)
    toks = s.split()
    out = []
    for t in toks:
        if t in {"1-0","0-1","1/2-1/2","*"}: 
            continue
        t = _norm_castling(t)
        t = _rm_syms.sub("", t).strip().lower()
        if t:
            out.append(t)
        if len(out) >= n:
            break
    return " ".join(out)

@st.cache_data(show_spinner=False)
def load_openings_catalog(path="data/openings.parquet") -> pd.DataFrame:
    cat = pd.read_parquet(path)
    cat.columns = [c.lower() for c in cat.columns]
    def s(df,col): 
        return df[col].fillna("").astype(str) if col in df.columns else pd.Series([""]*len(df), index=df.index, dtype="string")
    cat["eco"]  = s(cat,"eco").str.upper()
    cat["name"] = s(cat,"name")
    cat["pgn"]  = s(cat,"pgn")
    # split name
    sp = cat["name"].str.split(":", n=1, expand=True)
    cat["opening_name"] = sp[0].str.strip()
    cat["variation"]    = sp[1].fillna("").str.strip()
    # key + ids
    cat["open_key"] = cat["pgn"].map(lambda x: san_key(x, OPENING_KEY_PLY))
    keys = cat[["open_key"]].drop_duplicates().reset_index(drop=True)
    keys["opening_id"] = keys.index.astype("int32")
    cat = cat.merge(keys, on="open_key", how="left")
    return cat[["opening_id","open_key","eco","opening_name","variation","pgn","eco-volume"]].drop_duplicates()

def ensure_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col] if col in df.columns else pd.Series([""]*len(df), index=df.index, dtype="string")

def build_prefix_map(
    cat: pd.DataFrame,
    key_col: str = "open_key",
    id_col: str = "opening_id"
) -> dict[str, int]:
    keys = cat[key_col].astype(str).to_numpy()
    ids  = cat[id_col].astype(int).to_numpy()

    scores = defaultdict(lambda: defaultdict(float))
    for k, oid in zip(keys, ids):
        toks = k.split()
        upto = min(len(toks), OPENING_KEY_PLY)
        for i in range(1, upto + 1):
            pref = " ".join(toks[:i])
            scores[pref][oid] += 1.0

    return {p: max(d.items(), key=lambda kv: kv[1])[0] for p, d in scores.items()}

def resolve_opening_id(open_key: str, prefix_to_id: dict[str,int]) -> int | None:
    if not isinstance(open_key, str) or not open_key:
        return None
    toks = open_key.split()
    for i in range(len(toks), 0, -1):              # longest → shortest
        oid = prefix_to_id.get(" ".join(toks[:i]))
        if oid is not None:
            return oid
    return None