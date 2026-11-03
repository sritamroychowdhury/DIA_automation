"""Data dictionary for the Dispute Summary Extract file.

Source: the Snowflake source validation document (2026-11-03), which gives
the authoritative column list, Snowflake types, precision/scale, and
nullability. Column identifiers (technical_name) are the literal header
tokens used both in the Snowflake view and the PDL extract file.

NUMBER(precision, scale) columns are validated as "up to `scale` decimal
digits, extra digits past that must be trailing zeros" - Snowflake NUMBER
columns do not necessarily trim trailing zeros on export, so e.g. a
NUMBER(38,2) column may contain "4183.52" or "4183.5200", but not
"4183.5201".
"""

DISPUTE_SUMMARY_EXTRACT_COLUMNS = [
    dict(technical_name="CLIENT", business_name="CLIENT",
         format_type="varchar", max_length=None, nullable=False, default=None),
    dict(technical_name="STATE", business_name="STATE",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="PROGRAM", business_name="PROGRAM",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="PROGRAM_TYPE", business_name="PROGRAM_TYPE",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="INVOICE_QUARTER", business_name="INVOICE_QUARTER",
         format_type="quarter", max_length=None, nullable=True, default=None),
    dict(technical_name="LABELER", business_name="LABELER",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="NDC11", business_name="NDC11",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="PRODUCT_NAME", business_name="PRODUCT_NAME",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="PRODUCT_FAMILY", business_name="PRODUCT_FAMILY",
         format_type="varchar", max_length=None, nullable=True, default=None),
    dict(technical_name="SCRIPTS", business_name="SCRIPTS",
         format_type="numeric", precision=12, scale=2, nullable=True, default=None),
    dict(technical_name="MEDICAID_REIMBURSED", business_name="MEDICAID_REIMBURSED",
         format_type="numeric", precision=12, scale=2, nullable=True, default=None),
    dict(technical_name="NON_MEDICAID_REIMBURSED", business_name="NON_MEDICAID_REIMBURSED",
         format_type="numeric", precision=12, scale=2, nullable=True, default=None),
    dict(technical_name="CALCULATED_URA", business_name="CALCULATED_URA",
         format_type="numeric", precision=16, scale=6, nullable=True, default=None),
    dict(technical_name="SUBMITTED_UNITS", business_name="SUBMITTED_UNITS",
         format_type="numeric", precision=12, scale=3, nullable=True, default=None),
    dict(technical_name="DISPUTED_UNITS", business_name="DISPUTED_UNITS",
         format_type="numeric", precision=26, scale=3, nullable=False, default=None),
    dict(technical_name="WON_UNITS", business_name="WON_UNITS",
         format_type="numeric", precision=36, scale=3, nullable=True, default=None),
    dict(technical_name="LOST_UNITS", business_name="LOST_UNITS",
         format_type="numeric", precision=36, scale=3, nullable=True, default=None),
    dict(technical_name="OUTSTANDING_UNITS", business_name="OUTSTANDING_UNITS",
         format_type="numeric", precision=24, scale=3, nullable=False, default=None),
    dict(technical_name="PAID_UNITS", business_name="PAID_UNITS",
         format_type="numeric", precision=24, scale=3, nullable=True, default=None),
    dict(technical_name="REBATE_AMOUNT_REQUESTED", business_name="REBATE_AMOUNT_REQUESTED",
         format_type="numeric", precision=28, scale=9, nullable=True, default=None),
    dict(technical_name="DISPUTED_AMOUNT", business_name="DISPUTED_AMOUNT",
         format_type="numeric", precision=38, scale=2, nullable=True, default=None),
    dict(technical_name="WON_AMOUNT", business_name="WON_AMOUNT",
         format_type="numeric", precision=38, scale=2, nullable=True, default=None),
    # The source document's Technical Column Name is "LOST_AMOUNT" (Business
    # Column Name "LOST_UNIT"). The real PDL file's header for this column is
    # literally "LOST_UNIT" - confirmed by direct byte-level inspection of
    # the file, not yet corrected upstream. Kept as "LOST_AMOUNT" here (the
    # documented/expected name) so the schema check correctly keeps failing
    # against the file until that's fixed upstream - see the README.
    dict(technical_name="LOST_AMOUNT", business_name="LOST_UNIT",
         format_type="numeric", precision=38, scale=2, nullable=True, default=None),
    dict(technical_name="OUTSTANDING_AMOUNT", business_name="OUTSTANDING_AMOUNT",
         format_type="numeric", precision=38, scale=2, nullable=True, default=None),
    dict(technical_name="PAID_AMOUNT", business_name="PAID_AMOUNT",
         format_type="numeric", precision=38, scale=2, nullable=True, default=None),
    dict(technical_name="UPDATE_TIME", business_name="UPDATE_TIME",
         format_type="timestamp", max_length=None, nullable=True, default=None),
    dict(technical_name="EXPORT_DATE", business_name="EXPORT_DATE",
         format_type="timestamp", max_length=None, nullable=True, default=None),
    dict(technical_name="ACTIVE", business_name="ACTIVE",
         format_type=None, max_length=None, nullable=True, default=None),
]


def by_technical_name(name):
    for col in DISPUTE_SUMMARY_EXTRACT_COLUMNS:
        if col["technical_name"] == name:
            return col
    raise KeyError(f'No data dictionary entry for column "{name}"')


def all_columns():
    return [c["technical_name"] for c in DISPUTE_SUMMARY_EXTRACT_COLUMNS]


def required_columns():
    """Columns whose dictionary entry says NOT NULL."""
    return [c["technical_name"] for c in DISPUTE_SUMMARY_EXTRACT_COLUMNS if c["nullable"] is False]


def nullable_columns():
    return [c["technical_name"] for c in DISPUTE_SUMMARY_EXTRACT_COLUMNS if c["nullable"] is True]


def format_checked_columns():
    """Columns with a concrete format/precision rule worth asserting."""
    return [c["technical_name"] for c in DISPUTE_SUMMARY_EXTRACT_COLUMNS if c["format_type"] is not None]
