from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_mode: str = "local"
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

    @model_validator(mode="after")
    def local_only(self):
        if self.app_mode != "local":
            raise ValueError("This synthetic first slice is not approved for production.")
        for url in (self.app_origin, self.oidc_issuer, self.s3_endpoint):
            parsed = urlparse(url)
            if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.scheme != "http":
                raise ValueError("Local demo URLs must use loopback HTTP.")
        if len(self.redis_password.get_secret_value()) < 32:
            raise ValueError("Run scripts/bootstrap.py to generate the queue password.")
        if self.smtp_host not in {"localhost", "127.0.0.1"}:
            raise ValueError("Email must go to the local capture server on loopback.")
        if self.clamd_host not in {"localhost", "127.0.0.1"}:
            raise ValueError("The local scanner relay must be on loopback.")
        if len(self.session_secret.get_secret_value()) < 32:
            raise ValueError("Generate a session secret of at least 32 characters.")
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL is required.")
        return self

    @property
    def broker_url(self) -> str:
        return f"redis://:{self.redis_password.get_secret_value()}@127.0.0.1:56379/{self.redis_db}"
