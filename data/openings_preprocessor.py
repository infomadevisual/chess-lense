import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

_COMMENT = re.compile(r"\{[^}]*\}")
_PARENS = re.compile(r"\([^()]*\)")
_MOVE_NO = re.compile(r"^\d+\.{1,3}$")
_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}

OPENINGS_PATH_RAW = Path("data/openings.parquet")
OPENINGS_PATH_PREPROCESSED = Path("data/openings_preprocessed.parquet")

logger = logging.getLogger("openings_preprocessor")


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


def preprocess_openings() -> None:
    if OPENINGS_PATH_PREPROCESSED.exists():
        logger.info(
            f"Preprocessed openings already exist at {OPENINGS_PATH_PREPROCESSED}, skipping."
        )
        return

    cat = pd.read_parquet(OPENINGS_PATH_RAW)
    cat.columns = [c.lower() for c in cat.columns]

    def s(df, col):
        return (
            (df[col].fillna("").astype("string"))
            if col in df.columns
            else pd.Series([""] * len(df), index=df.index, dtype="string")
        )

    cat["eco"] = s(cat, "eco").str.upper()
    cat["name"] = s(cat, "name")
    cat["pgn"] = s(cat, "pgn")

    sp = cat["name"].str.split(":", n=1, expand=True)
    cat["opening_fullname"] = cat["name"]
    cat["opening_name"] = sp[0].str.strip()
    cat["opening_variation"] = sp[1].fillna("").str.strip()

    # canonical SAN list + a short prefix for fast joins
    san_lists = cat["pgn"].apply(lambda x: _san_list_from_pgn_like(x))
    cat["opening_moves_san"] = san_lists
    cat["san_prefix_8"] = san_lists.apply(lambda L: L[:8])

    cat["opening_id"] = cat.index.astype("int32")

    out_cols = [
        "opening_id",
        "eco",
        "opening_name",
        "opening_variation",
        "opening_fullname",
    ]
    cat = cat[out_cols].drop_duplicates()

    dtypes = {
        "opening_id": np.int32,
        "eco": "string",
        "opening_name": "string",
        "opening_variation": "string",
        "opening_fullname": "string",
        "opening_moves_san": "string",
        "san_prefix_8": "string",
    }

    for c, dtype in dtypes.items():
        cat[c] = cat[c].astype(dtype, copy=False)

    OPENINGS_PATH_PREPROCESSED.parent.mkdir(parents=True, exist_ok=True)
    cat.to_parquet(
        OPENINGS_PATH_PREPROCESSED, engine="pyarrow", compression="zstd", index=False
    )
