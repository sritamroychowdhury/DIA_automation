"""Loads a Dispute Summary Extract file (Parquet or pipe-delimited) as an
all-string DataFrame, so that format/length checks see the raw values
rather than values already coerced/rounded by pandas dtype inference.

PDL content is shipped with a .txt extension (not .pdl), so .txt is
treated as pipe-delimited by default - see detect_format().

Real extracts have been observed using bare \\r (old Mac style) line
endings with no \\n at all, which pandas.read_csv will not split on by
default (the whole file reads as one row). Line endings are normalized to
\\n before handing the text to read_csv so \\n, \\r\\n, and \\r all work."""

import io
import os
from decimal import Decimal

import pandas as pd

SUPPORTED_FORMATS = ("parquet", "pdl")


def _parquet_cell_to_str(v):
    """str(Decimal) uses scientific notation for exact-zero/small values at
    high scale (str(Decimal("0.000000000")) == "0E-9"), which breaks the
    plain-decimal format checks - format(v, "f") forces fixed-point instead."""
    if pd.isna(v):
        return ""
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v)


def detect_format(file_path, explicit_format=None):
    if explicit_format:
        return explicit_format.lower()
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    if ext == "parquet":
        return "parquet"
    if ext in ("pdl", "txt", "csv"):
        return "pdl"
    raise ValueError(
        f'Cannot determine file format from extension ".{ext}". '
        f'Pass file_format explicitly (one of {SUPPORTED_FORMATS}).'
    )


def load_file(file_path, file_format=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    fmt = detect_format(file_path, file_format)

    if fmt == "parquet":
        df = pd.read_parquet(file_path)
        df = df.apply(lambda s: s.map(_parquet_cell_to_str))
    elif fmt == "pdl":
        with open(file_path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        df = pd.read_csv(io.StringIO(text), sep="|", dtype=str, keep_default_na=False)
    else:
        raise ValueError(f'Unsupported file format "{fmt}". Supported: {SUPPORTED_FORMATS}')

    return df
