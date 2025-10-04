import json
import numpy as np
import streamlit as st
from collections import defaultdict
import re
import pandas as pd
from typing import Dict, Tuple, Optional, List

_COMMENT = re.compile(r"\{[^}]*\}")
_PARENS  = re.compile(r"\([^()]*\)")
_MOVE_NO = re.compile(r"^\d+\.{1,3}$")                 # 1. or 1... or 23...
_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}

def join_openings_to_games(df: pd.DataFrame):
    openings = _load_openings_catalog()
    
    idx, max_key_len = _build_exact_index(openings, id_col="opening_id",
                                        san_col="opening_moves_san_json", max_plies=80)

    matches = df["moves_san_json"].apply(lambda x: _match_exact_longest(x, idx, max_key_len))
    df["opening_id"], df["matched_plies"] = zip(*matches)
    df["matched_fullmove"] = (df["matched_plies"] + 1) // 2

    # optional debug: store matched sequence
    df["matched_prefix_json"] = df.apply(
        lambda r: json.dumps(_ensure_list(r["moves_san_json"])[: int(r["matched_plies"]) ])
        , axis=1
    )

    # attach opening names if needed
    df = df.merge(
        openings[["opening_id","eco","opening_fullname","opening_name","opening_variation","opening_moves_san_json"]],
        on="opening_id", how="left"
    )

    return df

def _ensure_list(x) -> List[str]:
    if isinstance(x, list): 
        return x
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return []
    return []

def _build_exact_index(openings: pd.DataFrame,
                      id_col="opening_id",
                      san_col="moves_san_json",
                      max_plies: Optional[int] = None
                     ) -> Tuple[Dict[tuple, int], int]:
    """
    Key = full opening SAN tuple; Value = opening_id.
    If duplicates exist, keep the smallest id.
    Returns (index, max_key_len).
    """
    idx: Dict[tuple, int] = {}
    max_len = 0
    for oid, san_json in openings[[id_col, san_col]].itertuples(index=False):
        sans = _ensure_list(san_json)
        if max_plies: sans = sans[:max_plies]
        key = tuple(sans)
        if not key: 
            continue
        max_len = max(max_len, len(key))
        if key not in idx or int(oid) < idx[key]:
            idx[key] = int(oid)
    return idx, max_len

def _match_exact_longest(game_san_json,
                        idx: Dict[tuple, int],
                        max_key_len: int
                       ) -> Tuple[Optional[int], int]:
    """
    Return (opening_id, matched_plies). Exact match against an opening’s full move list.
    Longest prefix wins.
    """
    sans = _ensure_list(game_san_json)
    n = min(len(sans), max_key_len)
    # search from longest to shortest
    for k in range(n, 0, -1):
        key = tuple(sans[:k])
        if key in idx:
            return idx[key], k
    return None, 0

def _san_list_from_pgn_like(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    s = _COMMENT.sub(" ", text)
    # remove nested variations greedily
    while "(" in s and ")" in s:
        s = _PARENS.sub(" ", s)
    s = re.sub(r"\s+", " ", s.strip())
    toks = []
    for t in s.split(" "):
        t = t.strip()
        if not t or _MOVE_NO.match(t) or t in _RESULTS:
            continue
        toks.append(t)
    return toks

def _load_openings_catalog(path="data/openings.parquet") -> pd.DataFrame:
    cat = pd.read_parquet(path)
    cat.columns = [c.lower() for c in cat.columns]
    def s(df,col): 
        return df[col].fillna("").astype(str) if col in df.columns else pd.Series([""]*len(df), index=df.index, dtype="string")
    cat["eco"]  = s(cat,"eco").str.upper()
    cat["name"] = s(cat,"name")
    cat["pgn"]  = s(cat,"pgn")

    # split name
    sp = cat["name"].str.split(":", n=1, expand=True)
    cat["opening_fullname"] = cat["name"]
    cat["opening_name"] = sp[0].str.strip()
    cat["opening_variation"]    = sp[1].fillna("").str.strip()

    # Moves to match later
    cat["opening_moves_san_json"] = cat["pgn"].apply(
        lambda x: json.dumps(_san_list_from_pgn_like(x))
    )

    # key + ids
    cat["opening_id"] = cat.index.astype("int32")
    return cat[["opening_id","eco","opening_fullname","opening_name","opening_variation","opening_moves_san_json"]].drop_duplicates()
