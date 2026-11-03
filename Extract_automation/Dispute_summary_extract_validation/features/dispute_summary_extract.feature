# NOTE - open items:
#
# 1. Column identifiers below match the Snowflake source validation
#    document (2026-11-03) - the same tokens as the Snowflake view and the
#    PDL extract file headers.
# 2. Per that document, only CLIENT, DISPUTED_UNITS, and OUTSTANDING_UNITS
#    are NOT NULL; every other column is nullable.
# 3. There is no reconciliation/business-rule validation across the unit
#    and amount columns (DISPUTED_UNITS, PAID_UNITS, DISPUTED_AMOUNT,
#    PAID_AMOUNT, etc.) - removed, since the inferred formulas did not
#    hold against real data and the correct formulas are a business
#    decision, not something this framework should guess at.
# 4. NDC-11 (11-digit) and Active Flag (TRUE/FALSE) checks remain
#    assumptions based on column naming, not something the source
#    document states - it only gives NDC11 as TEXT and ACTIVE as BOOLEAN
#    with no enumerated values or pattern.

Feature: Dispute Summary Extract file validation
  As a data quality analyst
  I want the Dispute Summary Extract file validated against its data dictionary
  So that downstream rebate/dispute reporting is not built on malformed data

  Background:
    Given the latest Dispute Summary Extract file is downloaded from S3
    And a Dispute Summary Extract file is available for validation

  # ---------------------------------------------------------------------
  # Schema / structure
  # ---------------------------------------------------------------------

  @schema
  Scenario: The file contains every column defined in the data dictionary
    Then the file contains all columns defined in the data dictionary

  @schema
  Scenario: The file contains no undefined extra columns
    Then the file does not contain any undefined extra columns

  @schema
  Scenario Outline: Column "<technical_name>" exists in the file
    Then the column "<technical_name>" exists in the file

    Examples: All data-dictionary columns
      | technical_name          |
      | CLIENT                  |
      | STATE                   |
      | PROGRAM                 |
      | PROGRAM_TYPE             |
      | INVOICE_QUARTER         |
      | LABELER                 |
      | NDC11                   |
      | PRODUCT_NAME            |
      | PRODUCT_FAMILY          |
      | SCRIPTS                 |
      | MEDICAID_REIMBURSED     |
      | NON_MEDICAID_REIMBURSED |
      | CALCULATED_URA          |
      | SUBMITTED_UNITS         |
      | DISPUTED_UNITS          |
      | WON_UNITS               |
      | LOST_UNITS              |
      | OUTSTANDING_UNITS       |
      | PAID_UNITS              |
      | REBATE_AMOUNT_REQUESTED |
      | DISPUTED_AMOUNT         |
      | WON_AMOUNT              |
      | LOST_AMOUNT             |
      | OUTSTANDING_AMOUNT      |
      | PAID_AMOUNT             |
      | UPDATE_TIME             |
      | EXPORT_DATE             |
      | ACTIVE                  |

  # ---------------------------------------------------------------------
  # Completeness / nulls
  # ---------------------------------------------------------------------

  @completeness
  Scenario Outline: Required column "<technical_name>" contains no nulls or blanks
    Then the column "<technical_name>" contains no null or blank values

    Examples: NOT NULL columns per the data dictionary
      | technical_name    |
      | CLIENT            |
      | DISPUTED_UNITS    |
      | OUTSTANDING_UNITS |

  @completeness
  Scenario Outline: Optional column "<technical_name>" may contain nulls
    Then the column "<technical_name>" is allowed to contain null values

    Examples: Nullable columns per the data dictionary
      | technical_name           |
      | STATE                    |
      | PROGRAM                  |
      | PROGRAM_TYPE             |
      | INVOICE_QUARTER          |
      | LABELER                  |
      | NDC11                    |
      | PRODUCT_NAME             |
      | PRODUCT_FAMILY           |
      | SCRIPTS                  |
      | MEDICAID_REIMBURSED      |
      | NON_MEDICAID_REIMBURSED  |
      | CALCULATED_URA           |
      | SUBMITTED_UNITS          |
      | WON_UNITS                |
      | LOST_UNITS               |
      | PAID_UNITS               |
      | REBATE_AMOUNT_REQUESTED  |
      | DISPUTED_AMOUNT          |
      | WON_AMOUNT               |
      | LOST_AMOUNT              |
      | OUTSTANDING_AMOUNT       |
      | PAID_AMOUNT              |
      | UPDATE_TIME              |
      | EXPORT_DATE              |
      | ACTIVE                   |

  # ---------------------------------------------------------------------
  # Data type / format
  # ---------------------------------------------------------------------

  @datatype
  Scenario Outline: Column "<technical_name>" values match their defined format
    Then the column "<technical_name>" values match its defined format

    Examples: Columns with a concrete format/precision rule
      | technical_name          |
      | INVOICE_QUARTER         |
      | SCRIPTS                 |
      | MEDICAID_REIMBURSED     |
      | NON_MEDICAID_REIMBURSED |
      | CALCULATED_URA          |
      | SUBMITTED_UNITS         |
      | DISPUTED_UNITS          |
      | WON_UNITS               |
      | LOST_UNITS              |
      | OUTSTANDING_UNITS       |
      | PAID_UNITS              |
      | REBATE_AMOUNT_REQUESTED |
      | DISPUTED_AMOUNT         |
      | WON_AMOUNT              |
      | LOST_AMOUNT             |
      | OUTSTANDING_AMOUNT      |
      | PAID_AMOUNT             |
      | UPDATE_TIME             |
      | EXPORT_DATE             |

  # ---------------------------------------------------------------------
  # Business rules
  # ---------------------------------------------------------------------

  @business-rules
  Scenario: Active flag only contains the documented indicator values
    Then the column "ACTIVE" only contains the values "TRUE" or "FALSE"

  @business-rules
  Scenario: NDC-11 values are well-formed 11-digit codes
    Then the column "NDC11" values are exactly 11 digits long

  @business-rules
  Scenario: Export date is never in the future
    Then the column "EXPORT_DATE" values are not later than today's date

  # ---------------------------------------------------------------------
  # Source reconciliation - Snowflake view OOTB_MEDICAID_DISPUTE_SUMMARY,
  # filtered on CLIENT = first token of the file name (case-insensitive)
  # ---------------------------------------------------------------------

  @source
  Scenario: The file only contains rows for the client in its file name
    Then every CLIENT value in the file matches the client in the file name

  @source
  Scenario: The file has the same columns as the source view
    Given the source data is read from the Snowflake view for the client in the file name
    Then the file columns match the Snowflake view columns

  @source
  Scenario: The file has the same number of rows as the source view
    Given the source data is read from the Snowflake view for the client in the file name
    Then the file row count matches the Snowflake view row count

  @source
  Scenario: The file data matches the source view
    Given the source data is read from the Snowflake view for the client in the file name
    Then every file row matches a row in the Snowflake view
