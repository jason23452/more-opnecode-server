from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    MAX_UPLOAD_BYTES: ClassVar[int] = 95 * 1024 * 1024
    app_name: str = "Features Base API"
    api_prefix: str = "/api"
    debug: bool = False
    frontend_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    opencode_password: str = ""
    opencode_admin_token: str = ""
    opencode_container_cpu: float = 1.0
    opencode_container_memory: str = "2g"
    opencode_max_containers: int = 4
    opencode_startup_timeout: int = 180
    opencode_image: str = "dynamic-opencode:latest"
    opencode_tunnel_probe_interval: float = 30.0
    opencode_tunnel_failure_threshold: int = 3
    opencode_tunnel_recovery_attempts: int = 3
    opencode_tunnel_recovery_delay: float = 2.0
    opencode_tunnel_retry_initial_delay: int = 5
    opencode_tunnel_retry_max_delay: int = 60
    opencode_upload_max_bytes: int = 95 * 1024 * 1024

    @field_validator("opencode_upload_max_bytes")
    @classmethod
    def validate_upload_max_bytes(cls, value: int) -> int:
        if value <= 0 or value > cls.MAX_UPLOAD_BYTES:
            raise ValueError("opencode_upload_max_bytes must be between 1 and 99614720 bytes (95 MiB ingress cap)")
        return value
    opencode_cli_release_url: str = (
        "https://github.com/jason23452/more-opnecode-server/releases/latest/download"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
