"""애플리케이션 설정 (환경변수 기반).

운영 환경에서는 .env 또는 컨테이너의 환경변수로 주입한다.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EDGE_",
        case_sensitive=False,
    )

    # --- 엣지 노드 식별 ---
    edge_node_id: str = Field(default="EDGE-LOCAL-01")

    # --- gRPC 백엔드(Spring Boot) ---
    grpc_target: str = Field(default="localhost:9090")
    grpc_use_tls: bool = Field(default=False)
    grpc_ca_cert_path: str | None = Field(default=None)
    grpc_max_retries: int = Field(default=5)
    grpc_initial_backoff_sec: float = Field(default=0.5)
    grpc_max_backoff_sec: float = Field(default=8.0)
    grpc_request_timeout_sec: float = Field(default=2.0)

    # --- 가상 통과선 알고리즘 ---
    # 통과선 양 끝 좌표(이미지 픽셀 기준). 차로별로 동적으로 변경 가능.
    crossing_line_p1_x: int = Field(default=0)
    crossing_line_p1_y: int = Field(default=540)
    crossing_line_p2_x: int = Field(default=1920)
    crossing_line_p2_y: int = Field(default=540)
    # 트랙이 ENTRY/EXIT으로 판정될 최소 신뢰도
    min_track_confidence: float = Field(default=0.35)
    # 검수 큐로 보낼 OCR 신뢰도 임계값
    low_ocr_confidence_threshold: float = Field(default=0.70)

    # --- 송신 큐 ---
    send_queue_max_size: int = Field(default=10_000)

    # --- Spring Boot REST ingest ---
    spring_rest_base_url: str = Field(default="http://localhost:8585")
    spring_rest_timeout_sec: float = Field(default=2.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
