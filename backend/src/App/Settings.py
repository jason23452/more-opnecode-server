from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
