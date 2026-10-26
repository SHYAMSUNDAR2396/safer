import base64
import hashlib
import io
import json

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from safer.keys import MAX_BYTES, EnvelopeCipher, KeyServiceError, TransitKeys


def client(settings):
    raw = boto3.client(
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

    if settings.object_encryption == "transit":
        return EncryptedObjects(
            raw,
            EnvelopeCipher(
                TransitKeys(
                    settings.transit_address,
                    settings.transit_token_file,
                    local_compose=settings.local_transport == "compose",
                )
            ),
        )
    return raw


class EncryptedStorageError(BotoCoreError):
    fmt = "Encrypted storage could not verify content or reach the key service."


class EncryptedObjects:
    """Opt-in new-bucket profile. Plaintext legacy versions fail closed; no silent migration."""

    def __init__(self, raw, cipher: EnvelopeCipher):
        self.raw, self.cipher = raw, cipher

    def __getattr__(self, name):
        return getattr(self.raw, name)

    @staticmethod
    def context(bucket: str, key: str) -> dict:
        return {
            "institution_id": key.split("/", 1)[0],
            "object_id": f"{bucket}/{key}",
            "purpose": "stored-object",
        }

    def put_object(self, **kwargs):
        body = kwargs["Body"]
        try:
            if not isinstance(body, bytes) or len(body) > MAX_BYTES:
                raise KeyServiceError("Invalid content size")
            expected = kwargs.get("ChecksumSHA256")
            if expected and expected != base64.b64encode(hashlib.sha256(body).digest()).decode():
                raise KeyServiceError("Content checksum mismatch")
            envelope = self.cipher.encrypt(body, self.context(kwargs["Bucket"], kwargs["Key"]))
            encoded = json.dumps(envelope, separators=(",", ":")).encode()
            metadata = dict(kwargs.get("Metadata", {})) | {
                "safer-envelope": "1",
                "safer-content-type": kwargs.get("ContentType", "application/octet-stream"),
            }
            return self.raw.put_object(
                **(
                    kwargs
                    | {
                        "Body": encoded,
                        "ContentType": "application/json",
                        "Metadata": metadata,
                        "ChecksumSHA256": base64.b64encode(
                            hashlib.sha256(encoded).digest()
                        ).decode(),
                    }
                )
            )
        except (KeyServiceError, ValueError, TypeError, KeyError):
            raise EncryptedStorageError() from None

    def get_object(self, **kwargs):
        result = self.raw.get_object(**kwargs)
        try:
            if result.get("Metadata", {}).get("safer-envelope") != "1":
                raise KeyServiceError("Legacy plaintext is disabled")
            with result["Body"] as stream:
                encoded = stream.read(2 * MAX_BYTES + 1)
            if len(encoded) > 2 * MAX_BYTES:
                raise KeyServiceError("Encrypted object too large")
            body = self.cipher.decrypt(
                json.loads(encoded), self.context(kwargs["Bucket"], kwargs["Key"])
            )
            return result | {
                "Body": io.BytesIO(body),
                "ContentLength": len(body),
                "ContentType": result["Metadata"]["safer-content-type"],
            }
        except (KeyServiceError, ValueError, TypeError, KeyError):
            raise EncryptedStorageError() from None


def ensure_bucket(s3, bucket: str):
    try:
        s3.create_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    if s3.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
        raise RuntimeError("Document storage must be versioned.")
