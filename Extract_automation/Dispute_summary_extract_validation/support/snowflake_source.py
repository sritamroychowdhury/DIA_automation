"""Reads the expected Dispute Summary data from the Snowflake source view
OOTB_MEDICAID_DISPUTE_SUMMARY, filtered to the client the extract file
belongs to.

The client is the first underscore-separated token of the extract file
name, e.g. "tolmar_OOTB_MEDICAID_DISPUTE_SUMMARY_PDL_01_....txt" -> "tolmar".
The view exposes MD_CLIENT.PRETTY_NAME ("Tolmar") as CLIENT, so the filter
is case-insensitive.

Auth is RSA key-pair using the service credentials stored in AWS Secrets
Manager (see get_snowflake_secrets). A named connection from
~/.snowflake/connections.toml can still be used as an explicit override.
"""

import base64
import json
import os
from functools import lru_cache

import pandas as pd

DEFAULT_VIEW = "QA_PLATFORM.PLATFORM_EXPORT_ADAPTER.OOTB_MEDICAID_DISPUTE_SUMMARY"


# Same default as PowerBI_automation/utils/secrets_manager.py.
_AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


@lru_cache(maxsize=None)
def _get_secret(secret_name):
    from botocore.exceptions import ClientError

    from support.aws_session import get_session

    client = get_session().client("secretsmanager", region_name=_AWS_REGION)
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        raise RuntimeError(f"Failed to retrieve secret '{secret_name}' from AWS Secrets Manager") from exc

    secret_string = response.get("SecretString")
    if secret_string is None:
        raise RuntimeError(f"Secret '{secret_name}' has no SecretString payload")
    return json.loads(secret_string)


def get_snowflake_secrets() -> dict:
    """Fetch Snowflake connection credentials.

    Auth is RSA key-pair, not password: SNOWFLAKE_KEY is a base64-encoded,
    passphrase-encrypted PEM private key, and SNOWFLAKE_PASS -- despite the
    name -- is that key's decryption passphrase, not a login password.
    See _private_key_der() for where the key is decoded/decrypted.

    Expected secret JSON keys: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
    SNOWFLAKE_KEY, SNOWFLAKE_PASS, PLATFORM_WAREHOUSE, PLATFORM_DATABASE,
    PLATFORM_SCHEMA (optional), PLATFORM_ROLE (optional).
    """
    secret_name = os.environ.get("SNOWFLAKE_SECRET_NAME", "qa/platform/data-export-adapter")
    secret = _get_secret(secret_name)
    return {
        "account": secret["SNOWFLAKE_ACCOUNT"],
        "user": secret["SNOWFLAKE_USER"],
        "private_key": secret["SNOWFLAKE_KEY"],
        "private_key_passphrase": secret["SNOWFLAKE_PASS"],
        "warehouse": secret["PLATFORM_WAREHOUSE"],
        "database": secret["PLATFORM_DATABASE"],
        "schema": secret.get("PLATFORM_SCHEMA"),
        "role": secret.get("PLATFORM_ROLE") or None,
    }


def _private_key_der(b64_pem, passphrase):
    """base64(PEM, encrypted) -> unencrypted PKCS#8 DER bytes, the form
    snowflake.connector expects for `private_key`."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        base64.b64decode(b64_pem),
        password=passphrase.encode() if passphrase else None,
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _connect_kwargs(connection_name=None):
    if connection_name:
        return {"connection_name": connection_name}
    creds = get_snowflake_secrets()
    creds["private_key"] = _private_key_der(creds["private_key"], creds.pop("private_key_passphrase"))
    return {k: v for k, v in creds.items() if v is not None}


def client_from_filename(file_path):
    name = os.path.basename(file_path)
    client = name.split("_", 1)[0].strip()
    if not client or client == name:
        raise ValueError(
            f'Cannot derive client name from file name "{name}" - expected '
            f'"<client>_OOTB_MEDICAID_DISPUTE_SUMMARY_..."'
        )
    return client


def load_view(client, connection_name=None, view_name=DEFAULT_VIEW):
    """Returns the view rows for `client` as an all-string DataFrame
    ("" for NULL), matching how file_loader presents the extract."""
    import snowflake.connector

    # view_name comes from trusted run config (behave -D), not file content;
    # the client value is bound as a parameter.
    sql = f"SELECT * FROM {view_name} WHERE LOWER(CLIENT) = LOWER(%s)"
    with snowflake.connector.connect(**_connect_kwargs(connection_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (client,))
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()

    df = pd.DataFrame(rows, columns=columns, dtype=object)
    return df.apply(lambda s: s.map(_to_str))


def _to_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)
