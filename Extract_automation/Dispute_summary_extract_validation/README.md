# Dispute_summary_extract_validation

BDD (behave/Gherkin) validation suite for the Dispute Summary Extract file,
driven by the data dictionary in `support/data_dictionary.py`.

## Setup

```
pip install -r requirements.txt
```

## Running

By default, the Background auto-downloads the latest matching extract from
S3 before every run - no manual file placement needed:

```
behave
```

This finds the most recently modified object under
`s3://icyte-sparc/qa/medi/output/report_extract/tolmar/` whose name contains
`OOTB_MEDICAID_DISPUTE_SUMMARY` (only `.txt`/`.pdl`/`.csv`/`.parquet`
extensions are eligible - exports also drop a same-named `.ctl` control file
a few seconds later, which is excluded so "latest" can't resolve to it),
downloads it into `data/`, and validates that. Options:

```
behave -D s3_file_name=<exact object name>   # download that one instead of "latest"
behave -D s3_bucket=<bucket> -D s3_prefix=<prefix/>   # a different client/path
```

The download only happens once per run even though the Background step
fires before every scenario (cached on `context.s3_download_cache`).

To validate an already-local file instead and skip S3 entirely, pass
`-D file_path` explicitly - this takes priority over auto-download:

```
behave -D file_path=./data/dispute_summary_extract.parquet
behave -D file_path=./data/dispute_summary_extract.txt
```

Format is auto-detected from the file extension (`.parquet` -> parquet,
`.txt`/`.pdl`/`.csv` -> pipe-delimited, i.e. PDL content shipped with a
`.txt` extension); pass `-D file_format=parquet|pdl` to override if a file
ever arrives with a different/no extension.

If neither a local file nor an S3 object can be found, scenarios are
**skipped** (not failed), with a message explaining why.

Run a subset by tag, e.g. just the format checks:

```
behave --tags=@datatype
```

## Source reconciliation (Snowflake)

`@source` scenarios compare the file to the Snowflake view
`QA_PLATFORM.PLATFORM_EXPORT_ADAPTER.OOTB_MEDICAID_DISPUTE_SUMMARY`, filtered
on `CLIENT` = the first `_`-separated token of the file name
(`tolmar_OOTB_...txt` -> `tolmar`, matched case-insensitively against `Tolmar`).
Checks: CLIENT values match the file name, same columns, same row count, and
row-by-row data match. `UPDATE_TIME` / `EXPORT_DATE` are excluded from the data
match because the view returns `CURRENT_TIMESTAMP()`.

```
behave --tags=@source -D file_path=./data/tolmar_OOTB_MEDICAID_DISPUTE_SUMMARY_PDL_01_2026-11-03_09_50_00.txt
```

Snowflake auth is RSA key-pair with the service credentials in AWS Secrets
Manager secret `qa/platform/data-export-adapter` (override with env var
`SNOWFLAKE_SECRET_NAME`). AWS region defaults to `us-east-1` (override with
`AWS_REGION`). AWS credentials come from the `AWS_PROFILE` env var if set,
otherwise `support/snowflake_source.py` falls back to the
`687531504312_AWSIAMBPaaSCnPDeveloper` profile in `~/.aws` - set
`AWS_PROFILE` yourself to use a different one (CI, another developer, etc).
`-D sf_connection=<name>` uses a named connection from
`~/.snowflake/connections.toml` instead; `-D sf_view=<DB.SCHEMA.VIEW>`
overrides the view.

## Project layout

```
features/
  dispute_summary_extract.feature   Gherkin scenarios (schema, completeness, format,
                                     and a small set of standalone business rules)
  environment.py                    Loads the file once per run (before_all)
  steps/validation_steps.py         Step definitions, call into support/validators.py
support/
  data_dictionary.py                Single source of truth for expected columns,
                                     types, lengths, nullability
  file_loader.py                    Reads parquet or pipe-delimited files
  validators.py                     Reusable check functions (schema, nulls, format)
  aws_session.py                    Shared boto3 session/profile resolution
  s3_source.py                      Finds/downloads the latest extract from S3
  snowflake_source.py                Reads the expected data from the Snowflake view
data/                               S3 downloads (and any manually-placed file) land here -
                                     gitignored in spirit, nothing is checked in
```

There is intentionally no cross-column reconciliation validation (e.g.
checking that Disputed Units equals Won + Lost + Outstanding Units) - an
earlier attempt at this was removed because the inferred formulas didn't
hold against real data, and the correct formulas are a business decision
this framework shouldn't guess at.

## Column naming

`support/data_dictionary.py` is driven by the Snowflake source validation
document (2026-11-03), which gives the authoritative column list, Snowflake
types (`TEXT`, `NUMBER(precision, scale)`, `TIMESTAMP_LTZ`, `BOOLEAN`), and
nullability. Column identifiers are the literal tokens used by both the
Snowflake view and the PDL extract file. If the source changes, update this
file to match.

`NUMBER(precision, scale)` columns are validated as "up to `scale` decimal
digits, extra digits past that must be trailing zeros" - Snowflake does not
necessarily trim trailing zeros on export, so e.g. a `NUMBER(38,2)` column
may contain `4183.52` or `4183.5200`, but not `4183.5201`.

## Open items to confirm with the business

1. **NDC-11 (11-digit) and Active Flag (TRUE/FALSE only)** checks are
   still assumptions based on column naming, not literal spec constraints -
   the source document only says NDC11 is `TEXT` and ACTIVE is `BOOLEAN`,
   with no enumerated values or pattern given.

## Known finding: LOST_AMOUNT vs LOST_UNIT

The source document's Technical Column Name for this column is
`LOST_AMOUNT` (Business Column Name `LOST_UNIT`), and `support/data_dictionary.py`
uses `LOST_AMOUNT` accordingly. The real PDL file's header for this column
is literally `LOST_UNIT`, confirmed by direct byte-level inspection of the
file - not yet corrected upstream. The Snowflake view agrees with the
document (`LOST_AMOUNT`), so this is a genuine extraction bug, not a
documentation error: the file disagrees with both the spec and its own
source view. This is left as a genuine, expected failure (5 `@schema`
scenarios plus the `@source` "same columns as the view" scenario) rather
than renamed to match the file, since the goal is to flag the real defect,
not hide it.

