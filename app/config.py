import os
from functools import lru_cache

import boto3


@lru_cache
def _ssm():
    return boto3.client("ssm")


def get_secret(env_var: str) -> str:
    value = os.environ[env_var]
    if value.startswith("/"):
        return _ssm().get_parameter(Name=value, WithDecryption=True)["Parameter"]["Value"]
    return value
