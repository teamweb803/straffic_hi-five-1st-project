"""Environment based settings for the Python Ingress server."""
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EDGE_",
        case_sensitive=False,
    )

    edge_node_id: str = Field(default="EDGE-LOCAL-01")

    # WebTransport over QUIC/TLS is the production edge transport.
    webtransport_host: str = Field(default="0.0.0.0")
    webtransport_port: int = Field(default=8443)
    webtransport_cert_path: str | None = Field(default=None)
    webtransport_key_path: str | None = Field(default=None)

    # Python Ingress forwards accepted protobuf bytes to Spring Boot.
    spring_rest_base_url: str = Field(default="http://localhost:8585")
    spring_rest_timeout_sec: float = Field(default=2.0)

    # Chatbot/dashboard queries read the same PostgreSQL operational tables.
    db_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("EDGE_DB_HOST", "DB_HOST"))
    db_port: int = Field(default=5433, validation_alias=AliasChoices("EDGE_DB_PORT", "DB_PORT"))
    db_name: str = Field(default="hifive", validation_alias=AliasChoices("EDGE_DB_NAME", "DB_NAME"))
    db_user: str = Field(default="hifive", validation_alias=AliasChoices("EDGE_DB_USER", "DB_USER"))
    db_password: str = Field(default="1234", validation_alias=AliasChoices("EDGE_DB_PASSWORD", "DB_PASSWORD"))
    db_connect_timeout_sec: int = Field(default=3)
    db_statement_timeout_ms: int = Field(default=5000)

    ingress_video_base_url: str = Field(default="http://127.0.0.1:8000")
    ingress_video_status_path: str = Field(default="/video/status")
    ingress_video_timeout_sec: float = Field(default=1.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
