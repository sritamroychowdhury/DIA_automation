import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from behave import given, then

from support import s3_source, snowflake_source, validators
from support.file_loader import load_file


@given('the latest Dispute Summary Extract file is downloaded from S3')
def step_impl(context):
    if context.explicit_file_path:
        return  # -D file_path pinned a specific local file - skip S3 entirely

    bucket = context.config.userdata.get("s3_bucket", s3_source.DEFAULT_BUCKET)
    prefix = context.config.userdata.get("s3_prefix", s3_source.DEFAULT_PREFIX)

    if "result" not in context.s3_download_cache:
        pattern = context.config.userdata.get("s3_pattern", s3_source.DEFAULT_PATTERN)
        s3_file_name = context.config.userdata.get("s3_file_name")

        try:
            local_path = s3_source.download(
                os.path.join(_PROJECT_ROOT, "data"), bucket=bucket, prefix=prefix, pattern=pattern, s3_file_name=s3_file_name
            )
            df = load_file(local_path)
            try:
                client = snowflake_source.client_from_filename(local_path)
                client_error = None
            except ValueError as exc:
                client = None
                client_error = str(exc)
            result = dict(file_available=True, df=df, file_load_error=None, client=client, client_error=client_error)
        except Exception as exc:  # noqa: BLE001 - surfaced via scenario skip/failure
            result = dict(
                file_available=False,
                df=None,
                file_load_error=f'Failed to download/load extract from s3://{bucket}/{prefix}: {exc}',
                client=None,
                client_error=None,
            )
        context.s3_download_cache["result"] = result

    # behave scopes attribute writes to the current scenario - re-apply the
    # cached result on every scenario, not just the one that did the actual
    # download, or later scenarios see before_all's stale defaults instead.
    for key, value in context.s3_download_cache["result"].items():
        setattr(context, key, value)


@given('a Dispute Summary Extract file is available for validation')
def step_impl(context):
    if not context.file_available:
        context.scenario.skip(context.file_load_error)
        return


@then('the file contains all columns defined in the data dictionary')
def step_impl(context):
    missing = validators.missing_columns(context.df)
    assert not missing, f"Missing expected columns: {missing}"


@then('the file does not contain any undefined extra columns')
def step_impl(context):
    extra = validators.extra_columns(context.df)
    assert not extra, f"Unexpected extra columns found in file: {extra}"


@then('the column "{technical_name}" exists in the file')
def step_impl(context, technical_name):
    assert technical_name in context.df.columns, f'Column "{technical_name}" was not found in the file'


@then('the column "{technical_name}" contains no null or blank values')
def step_impl(context, technical_name):
    bad_rows = validators.find_nulls(context.df, technical_name)
    assert not bad_rows, (
        f'Column "{technical_name}" is required (NOT NULL) but has null/blank values '
        f'in {len(bad_rows)} row(s), e.g. rows {bad_rows[:10]}'
    )


@then('the column "{technical_name}" is allowed to contain null values')
def step_impl(context, technical_name):
    assert technical_name in context.df.columns, f'Column "{technical_name}" was not found in the file'


@then('the column "{technical_name}" values match its defined format')
def step_impl(context, technical_name):
    bad_rows = validators.find_format_violations(context.df, technical_name)
    assert not bad_rows, (
        f'Column "{technical_name}" has values that do not match its defined format '
        f'in {len(bad_rows)} row(s), e.g. rows {bad_rows[:10]}'
    )


@then('the column "ACTIVE" only contains the values "TRUE" or "FALSE"')
def step_impl(context):
    bad_rows = validators.find_disallowed_values(context.df, "ACTIVE", {"TRUE", "FALSE"})
    assert not bad_rows, f'Column "ACTIVE" has disallowed values in {len(bad_rows)} row(s), e.g. rows {bad_rows[:10]}'


@then('the column "NDC11" values are exactly 11 digits long')
def step_impl(context):
    bad_rows = validators.find_ndc11_violations(context.df, "NDC11")
    assert not bad_rows, f'Column "NDC11" is not 11 digits in {len(bad_rows)} row(s), e.g. rows {bad_rows[:10]}'


@then("the column \"EXPORT_DATE\" values are not later than today's date")
def step_impl(context):
    bad_rows = validators.find_future_dates(context.df, "EXPORT_DATE")
    assert not bad_rows, f'Column "EXPORT_DATE" has future dates in {len(bad_rows)} row(s), e.g. rows {bad_rows[:10]}'


# ---------------------------------------------------------------------------
# Source reconciliation against Snowflake view OOTB_MEDICAID_DISPUTE_SUMMARY
# ---------------------------------------------------------------------------

def _source_df(context):
    """Queries the view once per run (cached on context) for the client
    derived from the extract file name."""
    if "df" not in context.source_cache:
        context.source_cache["df"] = snowflake_source.load_view(
            context.client,
            connection_name=context.config.userdata.get("sf_connection"),
            view_name=context.config.userdata.get("sf_view", snowflake_source.DEFAULT_VIEW),
        )
    return context.source_cache["df"]


@given('the source data is read from the Snowflake view for the client in the file name')
def step_impl(context):
    assert context.client, f'Could not derive client from file name: {context.client_error}'
    df = _source_df(context)
    assert len(df) > 0, f'Snowflake view returned no rows for CLIENT = "{context.client}" (case-insensitive)'


@then('every CLIENT value in the file matches the client in the file name')
def step_impl(context):
    series = context.df["CLIENT"].astype(str).str.strip().str.lower()
    bad_rows = context.df.index[series.ne(context.client.lower())].tolist()
    assert not bad_rows, (
        f'CLIENT does not match file-name client "{context.client}" in {len(bad_rows)} row(s), '
        f'e.g. rows {bad_rows[:10]}'
    )


@then('the file row count matches the Snowflake view row count')
def step_impl(context):
    file_count, source_count = len(context.df), len(_source_df(context))
    assert file_count == source_count, (
        f'Row count mismatch for client "{context.client}": file={file_count}, view={source_count}'
    )


@then('the file columns match the Snowflake view columns')
def step_impl(context):
    file_cols, view_cols = list(context.df.columns), list(_source_df(context).columns)
    assert file_cols == view_cols, (
        f'Column mismatch. Only in file: {[c for c in file_cols if c not in view_cols]}; '
        f'only in view: {[c for c in view_cols if c not in file_cols]}; '
        f'order equal: {sorted(file_cols) == sorted(view_cols)}'
    )


@then('every file row matches a row in the Snowflake view')
def step_impl(context):
    only_file, only_view, columns = validators.compare_with_source(context.df, _source_df(context))
    assert not only_file and not only_view, (
        f'Data mismatch for client "{context.client}" '
        f'(compared {len(columns)} columns, excluding {sorted(validators.SOURCE_COMPARE_EXCLUDED)}).\n'
        f'{sum(only_file.values())} row(s) only in file:\n{validators.format_row_diff(only_file, columns)}\n'
        f'{sum(only_view.values())} row(s) only in view:\n{validators.format_row_diff(only_view, columns)}'
    )
