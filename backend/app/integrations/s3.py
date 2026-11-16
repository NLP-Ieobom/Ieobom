import os
import uuid

import boto3
from botocore.exceptions import ClientError

_client = boto3.client("s3", region_name=os.environ["AWS_REGION"])


def _bucket() -> str:
    return os.environ["S3_BUCKET_NAME"]


def build_object_key(document_id: uuid.UUID, filename: str) -> str:
    return f"documents/{document_id}/{filename}"


def create_presigned_put_url(key: str, content_type: str) -> str:
    return _client.generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type},
        ExpiresIn=int(os.environ["S3_PRESIGNED_PUT_EXPIRE"]),
    )


def create_presigned_get_url(key: str) -> str:
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=int(os.environ["S3_PRESIGNED_GET_EXPIRE"]),
    )


def head_object(key: str):
    """객체가 없으면 None. 그 외 에러는 그대로 올린다."""
    try:
        return _client.head_object(Bucket=_bucket(), Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return None
        raise
