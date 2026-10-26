"""Envelope confidentiality, tenant binding, tamper rejection and provider failure."""

import base64
import json

import httpx
import pytest


def adapter(tmp_path):
    from safer.keys import TransitKeys

    token = tmp_path / "token"
    token.write_text("synthetic-test-token")
    token.chmod(0o600)

    def handler(request):
        data = json.loads(request.content)
        if "/encrypt/" in request.url.path:
            return httpx.Response(
                200, json={"data": {"ciphertext": "vault:v1:" + data["plaintext"]}}
            )
        return httpx.Response(
            200, json={"data": {"plaintext": data["ciphertext"].split(":", 2)[2]}}
        )

    return TransitKeys(
        "http://127.0.0.1:58200", token, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_envelope_roundtrip_and_plaintext_key_never_serialized(tmp_path):
    from safer.keys import EnvelopeCipher

    cipher = EnvelopeCipher(adapter(tmp_path))
    context = {"institution_id": "synthetic-a", "object_id": "receipt-001", "purpose": "document"}
    envelope = cipher.encrypt(b"synthetic receipt bytes", context)
    assert "plaintext_key" not in envelope
    assert base64.b64encode(b"synthetic receipt bytes").decode() not in json.dumps(envelope)
    assert cipher.decrypt(envelope, context) == b"synthetic receipt bytes"


def test_wrong_scope_and_modified_ciphertext_are_rejected(tmp_path):
    from safer.keys import EnvelopeCipher, KeyServiceError

    cipher = EnvelopeCipher(adapter(tmp_path))
    context = {"institution_id": "a", "object_id": "receipt", "purpose": "document"}
    envelope = cipher.encrypt(b"synthetic", context)
    with pytest.raises(KeyServiceError):
        cipher.decrypt(envelope, context | {"institution_id": "b"})
    corrupt = envelope | {"payload": base64.b64encode(b"corrupt").decode()}
    with pytest.raises(KeyServiceError):
        cipher.decrypt(corrupt, context)


def test_insecure_remote_url_and_world_readable_token_rejected(tmp_path):
    from safer.keys import TransitKeys

    token = tmp_path / "token"
    token.write_text("private")
    token.chmod(0o600)
    with pytest.raises(ValueError):
        TransitKeys("http://remote.invalid:8200", token)
    token.chmod(0o644)
    with pytest.raises(ValueError):
        TransitKeys("http://127.0.0.1:58200", token)


def test_provider_failure_does_not_expose_token_or_plaintext(tmp_path):
    from safer.keys import EnvelopeCipher, KeyServiceError, TransitKeys

    token = tmp_path / "token"
    token.write_text("private-token")
    token.chmod(0o600)
    keys = TransitKeys(
        "http://127.0.0.1:58200",
        token,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(403, text="sensitive provider body")
            )
        ),
    )
    with pytest.raises(KeyServiceError) as exc:
        EnvelopeCipher(keys).encrypt(
            b"private document", {"institution_id": "a", "object_id": "x", "purpose": "document"}
        )
    assert "private" not in str(exc.value) and "sensitive" not in str(exc.value)


def test_encrypted_objects_roundtrip_and_fail_closed_on_plaintext(s3, settings, tmp_path):
    from safer.keys import EnvelopeCipher
    from safer.storage import EncryptedObjects, EncryptedStorageError

    wrapped = EncryptedObjects(s3, EnvelopeCipher(adapter(tmp_path)))
    key = "synthetic-a/receipt-1/doc-1"
    result = wrapped.put_object(
        Bucket=settings.s3_bucket, Key=key, Body=b"%PDF-synthetic", ContentType="application/pdf"
    )
    raw = s3.get_object(Bucket=settings.s3_bucket, Key=key, VersionId=result["VersionId"])[
        "Body"
    ].read()
    assert b"%PDF-synthetic" not in raw and b"safer-envelope-1" in raw
    clear = wrapped.get_object(Bucket=settings.s3_bucket, Key=key, VersionId=result["VersionId"])
    assert clear["Body"].read() == b"%PDF-synthetic" and clear["ContentType"] == "application/pdf"
    legacy = s3.put_object(Bucket=settings.s3_bucket, Key="legacy", Body=b"plaintext")
    with pytest.raises(EncryptedStorageError):
        wrapped.get_object(Bucket=settings.s3_bucket, Key="legacy", VersionId=legacy["VersionId"])
    s3.put_object(
        Bucket=settings.s3_bucket,
        Key="synthetic-b/receipt-1/doc-1",
        Body=raw,
        Metadata={"safer-envelope": "1"},
    )
    with pytest.raises(EncryptedStorageError):
        wrapped.get_object(Bucket=settings.s3_bucket, Key="synthetic-b/receipt-1/doc-1")
