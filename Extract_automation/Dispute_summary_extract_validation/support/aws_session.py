"""Shared AWS session/profile resolution for every boto3 client in this
project (Secrets Manager for Snowflake auth, S3 for extract downloads).

Credentials come from the AWS_PROFILE env var if set, otherwise this falls
back to a known-good developer profile - set AWS_PROFILE yourself to use a
different one (CI, another developer, etc).
"""

import os

DEFAULT_AWS_PROFILE = "687531504312_AWSIAMBPaaSCnPDeveloper"


def get_session():
    import boto3

    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", DEFAULT_AWS_PROFILE))
