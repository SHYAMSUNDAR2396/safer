import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def client(settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name="us-east-1",
        config=Config(
            # Checksums are sent explicitly (SHA-256) so non-AWS stores verify the exact bytes.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


def ensure_bucket(s3, bucket: str):
    try:
        s3.create_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    if s3.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
        raise RuntimeError("Document storage must be versioned.")
