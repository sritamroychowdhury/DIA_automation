import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from support import data_dictionary as dd
from support.file_loader import load_file
from support.snowflake_source import client_from_filename

DEFAULT_FILE_PATH = os.path.join(_PROJECT_ROOT, "data", "dispute_summary_extract.parquet")


def before_all(context):
    context.dictionary = dd.DISPUTE_SUMMARY_EXTRACT_COLUMNS

    # An explicit -D file_path pins a specific local file and skips the S3
    # auto-download Background step entirely; the default path is not
    # "explicit" (nothing exists there until a file is placed or downloaded).
    context.explicit_file_path = "file_path" in context.config.userdata

    file_path = context.config.userdata.get("file_path", DEFAULT_FILE_PATH)
    file_format = context.config.userdata.get("file_format")

    context.file_available = os.path.exists(file_path)
    context.df = None
    context.file_load_error = None
    # Mutable holders: attributes assigned inside a scenario are discarded by
    # behave when it ends, so steps that should only act once per run (the
    # @source Snowflake query, the S3 download) cache their result here.
    context.source_cache = {}
    context.s3_download_cache = {}

    try:
        context.client = client_from_filename(file_path)
        context.client_error = None
    except ValueError as exc:
        context.client = None
        context.client_error = str(exc)

    if context.file_available:
        try:
            context.df = load_file(file_path, file_format)
        except Exception as exc:  # noqa: BLE001 - surfaced via scenario skip/failure
            context.file_available = False
            context.file_load_error = f'Failed to load "{file_path}": {exc}'
    else:
        context.file_load_error = (
            f'No Dispute Summary Extract file found at "{file_path}". '
            f'Run behave with -D file_path=<path> [-D file_format=parquet|pdl], '
            f'or let the Background step download the latest one from S3.'
        )
