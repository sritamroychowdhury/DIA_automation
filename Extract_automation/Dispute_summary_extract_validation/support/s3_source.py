"""Finds and downloads the Dispute Summary Extract file from S3.

Defaults to the tolmar QA report extract location; override bucket/prefix
via `-D s3_bucket=<bucket>` / `-D s3_prefix=<prefix/>` for another client or
path. "Latest" means the object (whose basename contains the match pattern,
case-insensitive) with the most recent S3 LastModified timestamp - pass
`-D s3_file_name=<name>` to download a specific object instead.
"""

import os

from support.aws_session import get_session

DEFAULT_BUCKET = "icyte-sparc"
DEFAULT_PREFIX = "qa/medi/output/report_extract/tolmar/"
DEFAULT_PATTERN = "OOTB_MEDICAID_DISPUTE_SUMMARY"

# Each export drops a data file alongside a same-named .ctl control/marker
# file (written ~seconds later) - only extensions file_loader can parse are
# eligible, so "latest" can't accidentally resolve to the control file.
_DATA_EXTENSIONS = {"txt", "pdl", "csv", "parquet"}


def _list_matching_objects(bucket, prefix, pattern):
    s3 = get_session().client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    pattern_lower = pattern.lower()
    matches = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            basename = obj["Key"].rsplit("/", 1)[-1]
            ext = basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
            if basename and pattern_lower in basename.lower() and ext in _DATA_EXTENSIONS:
                matches.append(obj)
    return matches


def find_key(bucket=DEFAULT_BUCKET, prefix=DEFAULT_PREFIX, pattern=DEFAULT_PATTERN, s3_file_name=None):
    """Returns the S3 key to download: `s3_file_name` under `prefix` if
    given, otherwise the matching object with the most recent LastModified."""
    if s3_file_name:
        return f"{prefix.rstrip('/')}/{s3_file_name}"

    matches = _list_matching_objects(bucket, prefix, pattern)
    if not matches:
        raise FileNotFoundError(f'No object matching "*{pattern}*" found under s3://{bucket}/{prefix}')
    latest = max(matches, key=lambda obj: obj["LastModified"])
    return latest["Key"]


def download(local_dir, bucket=DEFAULT_BUCKET, prefix=DEFAULT_PREFIX, pattern=DEFAULT_PATTERN, s3_file_name=None):
    """Downloads the resolved key into `local_dir`, returns the local path."""
    key = find_key(bucket, prefix, pattern, s3_file_name)
    basename = key.rsplit("/", 1)[-1]
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, basename)

    get_session().client("s3").download_file(bucket, key, local_path)
    return local_path
