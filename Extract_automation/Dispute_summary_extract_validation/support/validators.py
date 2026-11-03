"""Validation primitives used by the BDD step definitions.

Every function returns a list of DataFrame row indices that violate the
check (empty list == passes). Steps turn that into an assert with a
human-readable message.
"""

import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from support import data_dictionary as dd

_QUARTER_RE = re.compile(r"^\d{4}q[1-4]$")
_NDC11_RE = re.compile(r"^\d{11}$")


def missing_columns(df):
    expected = dd.all_columns()
    return [c for c in expected if c not in df.columns]


def extra_columns(df):
    expected = set(dd.all_columns())
    return [c for c in df.columns if c not in expected]


def find_nulls(df, technical_name):
    if technical_name not in df.columns:
        return list(df.index)
    series = df[technical_name].astype(str).str.strip()
    mask = series.eq("") | series.str.lower().isin(["none", "nan", "null"])
    return df.index[mask].tolist()


def _numeric_regex(precision, scale):
    """Snowflake NUMBER(precision, scale): a bare integer with no decimal
    point at all is valid (e.g. "10"), and so is a value with MORE than
    `scale` decimal digits as long as everything past the `scale`th digit is
    a trailing zero (e.g. scale=2 permits "10.0000" but not "10.0001") -
    exports don't necessarily trim insignificant trailing zeros."""
    integer_digits = max(precision - scale, 1)
    return re.compile(rf"^-?\d{{1,{integer_digits}}}(\.\d{{1,{scale}}}0*)?$")


def find_format_violations(df, technical_name):
    col = dd.by_technical_name(technical_name)
    fmt = col.get("format_type")
    if fmt is None:
        return []  # format unspecified in the data dictionary - nothing to assert

    if technical_name not in df.columns:
        return list(df.index)

    series = df[technical_name].astype(str)
    non_blank_mask = series.str.strip().ne("")

    if fmt == "varchar":
        max_length = col.get("max_length")
        if not max_length:
            return []
        mask = non_blank_mask & (series.str.len() > max_length)
        return df.index[mask].tolist()

    if fmt == "quarter":
        mask = non_blank_mask & ~series.str.match(_QUARTER_RE)
        return df.index[mask].tolist()

    if fmt == "numeric":
        pattern = _numeric_regex(col["precision"], col["scale"])
        mask = non_blank_mask & ~series.str.match(pattern)
        return df.index[mask].tolist()

    if fmt == "timestamp":
        import pandas as pd

        def _invalid(v):
            try:
                pd.to_datetime(v)
                return False
            except (ValueError, TypeError):
                return True

        mask = non_blank_mask & series.apply(_invalid)
        return df.index[mask].tolist()

    raise ValueError(f'Unknown format_type "{fmt}" for column "{technical_name}"')


def find_disallowed_values(df, technical_name, allowed_values):
    if technical_name not in df.columns:
        return list(df.index)
    series = df[technical_name].astype(str).str.strip().str.upper()
    allowed = {v.upper() for v in allowed_values}
    mask = series.ne("") & ~series.isin(allowed)
    return df.index[mask].tolist()


def find_future_dates(df, technical_name):
    """EXPORT_DATE is TIMESTAMP_LTZ, so this compares full timestamps against
    now, not just calendar dates."""
    if technical_name not in df.columns:
        return list(df.index)

    import pandas as pd

    now = pd.Timestamp.now(tz="UTC")

    def _is_future(v):
        v = str(v).strip()
        if not v:
            return False
        try:
            parsed = pd.to_datetime(v, utc=True)
        except (ValueError, TypeError):
            return False  # malformed values are caught by the format-validation scenario
        return parsed > now

    mask = df[technical_name].apply(_is_future)
    return df.index[mask].tolist()


def find_ndc11_violations(df, technical_name="ndc11"):
    if technical_name not in df.columns:
        return list(df.index)
    series = df[technical_name].astype(str).str.strip()
    mask = series.ne("") & ~series.str.match(_NDC11_RE)
    return df.index[mask].tolist()


# ---------------------------------------------------------------------------
# File vs. Snowflake source view reconciliation
# ---------------------------------------------------------------------------

# UPDATE_TIME / EXPORT_DATE are CURRENT_TIMESTAMP() in the view, so they can
# never match a previously generated file.
SOURCE_COMPARE_EXCLUDED = {"UPDATE_TIME", "EXPORT_DATE"}


def _canonical(value):
    """Numbers compare by value (18.00 == 18.000), everything else as
    trimmed, case-folded text (true == TRUE)."""
    v = str(value).strip()
    if v == "" or v.lower() in ("none", "nan", "null"):
        return ""
    try:
        d = Decimal(v)
        if d.is_finite():
            return format(d.normalize(), "f") if d != 0 else "0"
    except InvalidOperation:
        pass
    return v.casefold()


def compare_with_source(file_df, source_df, excluded=SOURCE_COMPARE_EXCLUDED):
    """Multiset comparison of rows on the columns both sides share (there is
    no guaranteed unique key in the extract). Returns (only_in_file,
    only_in_source, compared_columns), each side a Counter of row tuples."""
    columns = [c for c in file_df.columns if c in source_df.columns and c not in excluded]

    def _rows(df):
        return Counter(tuple(_canonical(v) for v in row) for row in df[columns].itertuples(index=False))

    file_rows, source_rows = _rows(file_df), _rows(source_df)
    return file_rows - source_rows, source_rows - file_rows, columns


def format_row_diff(diff, columns, limit=5):
    lines = []
    for row, count in list(diff.items())[:limit]:
        pairs = ", ".join(f"{c}={v!r}" for c, v in zip(columns, row))
        lines.append(f"  x{count}: {pairs}")
    return "\n".join(lines)


