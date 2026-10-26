import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", secrets_dir=os.getenv("SAFER_SECRETS_DIR")
    )
    app_mode: str = "local"
    local_transport: Literal["host", "compose"] = "host"
    oidc_backchannel: str | None = None
    queue_host: str = "127.0.0.1"
    app_origin: str = "http://localhost:5173"
    database_url: SecretStr
    oidc_issuer: str = "http://localhost:8090/realms/safer"
    oidc_client_id: str = "safer-web"
    session_secret: SecretStr
    s3_endpoint: str = "http://127.0.0.1:8333"
    s3_bucket: str = "safer-documents"
    s3_access_key: str
    s3_secret_key: SecretStr
    clamd_host: str = "127.0.0.1"
    clamd_port: int = 3310
    redis_password: SecretStr
    # Only local capture exists; a real provider needs separate authorisation and code review.
    email_mode: Literal["capture"] = "capture"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 51025
    mail_from: str = "SAFER demo <no-reply@safer.invalid>"
    redis_db: int = 0
    explanations_enabled: bool = True
    summaries_enabled: bool = True
    llm_mode: Literal["off", "gemini"] = "off"
    llm_synthetic_egress_approved: bool = False
    llm_api_key_file: Path | None = None
    llm_approved_sources_file: Path | None = None
    llm_monthly_budget_microusd: int = Field(default=2_000_000, ge=0, le=100_000_000)
    object_encryption: Literal["none", "transit"] = "none"
    transit_address: str = "http://127.0.0.1:58200"
    transit_token_file: Path | None = None

    @model_validator(mode="after")
    def local_only(self):
        if self.llm_mode == "gemini" and (
            not self.llm_synthetic_egress_approved
            or not self.llm_api_key_file
            or not self.llm_approved_sources_file
        ):
            raise ValueError(
                "Gemini requires explicit synthetic egress approval and private key/source approval files."
            )
        if self.object_encryption == "transit" and self.transit_token_file is None:
            raise ValueError("Transit requires an owner-only token file outside the repository.")
        if self.app_mode != "local":
            raise ValueError("This synthetic first slice is not approved for production.")
        if urlparse(self.app_origin).hostname not in {"localhost", "127.0.0.1"} or urlparse(
            self.app_origin
        ).scheme not in {"http", "https"}:
            raise ValueError("Local public origin must remain on loopback HTTP/HTTPS.")
        if (
            urlparse(self.oidc_issuer).hostname not in {"localhost", "127.0.0.1"}
            or urlparse(self.oidc_issuer).scheme != "http"
        ):
            raise ValueError("Local identity issuer must remain on loopback HTTP.")
        service_hosts = {"localhost", "127.0.0.1"}
        if self.local_transport == "compose":
            service_hosts |= {"objects", "mail", "scan-relay", "queue", "identity"}
        for url in [self.s3_endpoint] + ([self.oidc_backchannel] if self.oidc_backchannel else []):
            parsed = urlparse(url)
            if (
                parsed.hostname not in service_hosts
                or parsed.scheme != "http"
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Local services must use the explicit loopback/Compose allowlist.")
        if (
            self.smtp_host not in service_hosts
            or self.clamd_host not in service_hosts
            or self.queue_host not in service_hosts
        ):
            raise ValueError("Unknown local service host.")
        if len(self.redis_password.get_secret_value()) < 32:
            raise ValueError("Run scripts/bootstrap.py to generate the queue password.")
        if len(self.session_secret.get_secret_value()) < 32:
            raise ValueError("Generate a session secret of at least 32 characters.")
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL is required.")
        return self

    @property
    def broker_url(self) -> str:
        return f"redis://:{self.redis_password.get_secret_value()}@{self.queue_host}:{6379 if self.local_transport == 'compose' else 56379}/{self.redis_db}"
