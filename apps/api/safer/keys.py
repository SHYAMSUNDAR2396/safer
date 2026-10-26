"""Provider-neutral AES-256-GCM envelope encryption with a Transit key adapter.

Only wrapped data keys persist. Application authorization remains mandatory before decryption.
Plaintext/key bytes exist transiently in Python memory; secure zeroization is not claimed.
"""

import base64
import binascii
import json
import os
import re
import stat
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_BYTES = 11 * 1024 * 1024


class KeyServiceError(Exception):
    """Safe, non-sensitive error; caller must fail closed."""


class KeyWrapper(Protocol):
    def wrap(self, plaintext_key: bytes, context: bytes) -> str: ...
    def unwrap(self, wrapped_key: str, context: bytes) -> bytes: ...


def encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def context_bytes(context: dict) -> bytes:
    if set(context) != {"institution_id", "object_id", "purpose"} or any(
        not isinstance(v, str) or not 1 <= len(v) <= 300 for v in context.values()
    ):
        raise KeyServiceError("Invalid encryption context.")
    return json.dumps(
        {"schema": "safer-envelope-1", **context}, sort_keys=True, separators=(",", ":")
    ).encode()


class TransitKeys:
    def __init__(
        self,
        address: str,
        token_file: Path,
        key_name: str = "safer-data",
        *,
        client: httpx.Client | None = None,
        local_compose: bool = False,
    ):
        parsed = urlparse(address)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or (
                parsed.scheme == "http"
                and parsed.hostname
                not in (
                    {"localhost", "127.0.0.1", "key-service"}
                    if local_compose
                    else {"localhost", "127.0.0.1"}
                )
            )
        ):
            raise ValueError(
                "Transit requires HTTPS or loopback HTTP without embedded credentials."
            )
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", key_name):
            raise ValueError("Invalid transit key name.")
        self.address, self.token_file, self.key_name = address.rstrip("/"), token_file, key_name
        self._token()
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(5), trust_env=False, follow_redirects=False
        )

    def _token(self) -> str:
        info = self.token_file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise ValueError("Transit token must be an owner-only regular file.")
        token = self.token_file.read_text().strip()
        if not token or len(token) > 4096 or any(c.isspace() for c in token):
            raise ValueError("Invalid Transit token file.")
        return token

    def _call(self, operation: str, body: dict) -> dict:
        try:
            response = self.client.post(
                f"{self.address}/v1/transit/{operation}/{self.key_name}",
                headers={"X-Vault-Token": self._token()},
                json=body,
                timeout=5,
                follow_redirects=False,
            )
            response.raise_for_status()
            return response.json()["data"]
        except (httpx.HTTPError, KeyError, ValueError, OSError):
            raise KeyServiceError("Key service unavailable or denied the operation.") from None

    def wrap(self, plaintext_key: bytes, context: bytes) -> str:
        data = self._call(
            "encrypt", {"plaintext": encode(plaintext_key), "associated_data": encode(context)}
        )
        wrapped = data.get("ciphertext")
        if not isinstance(wrapped, str) or not re.fullmatch(
            r"vault:v[1-9][0-9]*:[A-Za-z0-9+/=]+", wrapped
        ):
            raise KeyServiceError("Invalid key-service response.")
        return wrapped

    def unwrap(self, wrapped_key: str, context: bytes) -> bytes:
        data = self._call(
            "decrypt", {"ciphertext": wrapped_key, "associated_data": encode(context)}
        )
        try:
            key = decode(data["plaintext"])
            if len(key) != 32:
                raise ValueError
            return key
        except (KeyError, ValueError, TypeError, binascii.Error):
            raise KeyServiceError("Invalid key-service response.") from None


class EnvelopeCipher:
    def __init__(self, keys: KeyWrapper):
        self.keys = keys

    def encrypt(self, plaintext: bytes, context: dict) -> dict:
        if len(plaintext) > MAX_BYTES:
            raise KeyServiceError("Encryption payload limit exceeded.")
        aad = context_bytes(context)
        key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
        wrapped = self.keys.wrap(key, aad)
        payload = AESGCM(key).encrypt(nonce, plaintext, aad)
        return {
            "schema": "safer-envelope-1",
            "wrapped_key": wrapped,
            "nonce": encode(nonce),
            "payload": encode(payload),
        }

    def decrypt(self, envelope: dict, context: dict) -> bytes:
        aad = context_bytes(context)
        try:
            if (
                set(envelope) != {"schema", "wrapped_key", "nonce", "payload"}
                or envelope["schema"] != "safer-envelope-1"
                or len(envelope["payload"]) > 2 * MAX_BYTES
            ):
                raise ValueError
            nonce, payload = decode(envelope["nonce"]), decode(envelope["payload"])
            if len(nonce) != 12 or len(payload) > MAX_BYTES + 16:
                raise ValueError
            key = self.keys.unwrap(envelope["wrapped_key"], aad)
            return AESGCM(key).decrypt(nonce, payload, aad)
        except (InvalidTag, ValueError, TypeError, KeyError, binascii.Error):
            raise KeyServiceError("Encrypted content or scope could not be verified.") from None
