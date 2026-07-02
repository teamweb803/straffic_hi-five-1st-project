from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """FastAPI 분석 서버 설정. 모든 값은 환경 변수로 주입한다(가이드 §12)."""

    # --- Spring 연동 ---
    spring_base_url: str = "http://localhost:8585"
    request_timeout_seconds: float = 10.0
    request_max_retries: int = 2
    request_retry_backoff_seconds: float = 0.5

    # --- 스케줄러 ---
    scheduler_autostart: bool = True
    analysis_interval_seconds: int = 600  # 운영 10분 / 시연 60
    demo_seed_enabled: bool = True         # 시연용: 자동 분석 전 현재 버킷 더미 데이터 생성
    compare_event_interval_seconds: int = 10
    compare_passes_per_tick: int = 2

    # --- 기동 시 백필: 서버가 꺼져 있던 구간 품질지표를 메워 추세선을 연속으로 ---
    backfill_on_start: bool = True
    backfill_minutes: int = 360            # 최근 6시간 버킷을 연속으로 채움

    # --- 분석 구간 (가이드 §6) ---
    analysis_window_minutes: int = 60   # 결과로 보고하는 공식 분석 창
    fetch_history_minutes: int = 2880   # 시연 샘플 포함용 2일 history (LSTM-AE 연속 window 확보)
    bucket_minutes: int = 10

    # --- 전처리 / 모델 ---
    event_count_min: int = 10
    window_size: int = 6

    # --- 분석 대상: "cameraId:laneId,cameraId:laneId,..." ---
    targets: str = "1:1,2:1,3:3,4:3,5:5"

    # --- 중복 저장 방지(재시작 내성) ---
    dedup_db_path: str = "outputs/pdm_dedup.sqlite3"

    # --- Spring DB 계약에 맞춘 enum 경계 매핑 ---
    collapse_high_to_critical: bool = True  # riskLevel 4단계 → 3단계 (ERD: NORMAL/WARNING/CRITICAL)
    lstm_wire_model_type: str = "LSTM_AE"   # Spring Boot 허용 modelType

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        g = os.getenv
        return cls(
            spring_base_url=g("SPRING_BASE_URL", d.spring_base_url),
            request_timeout_seconds=float(g("PDM_REQUEST_TIMEOUT_SECONDS", d.request_timeout_seconds)),
            request_max_retries=int(g("PDM_REQUEST_MAX_RETRIES", d.request_max_retries)),
            request_retry_backoff_seconds=float(
                g("PDM_REQUEST_RETRY_BACKOFF_SECONDS", d.request_retry_backoff_seconds)
            ),
            scheduler_autostart=_get_bool("PDM_SCHEDULER_AUTOSTART", d.scheduler_autostart),
            analysis_interval_seconds=int(g("PDM_ANALYSIS_INTERVAL_SECONDS", d.analysis_interval_seconds)),
            demo_seed_enabled=_get_bool("PDM_DEMO_SEED_ENABLED", d.demo_seed_enabled),
            compare_event_interval_seconds=int(
                g("PDM_COMPARE_EVENT_INTERVAL_SECONDS", d.compare_event_interval_seconds)
            ),
            compare_passes_per_tick=int(
                g("PDM_COMPARE_PASSES_PER_TICK", d.compare_passes_per_tick)
            ),
            backfill_on_start=_get_bool("PDM_BACKFILL_ON_START", d.backfill_on_start),
            backfill_minutes=int(g("PDM_BACKFILL_MINUTES", d.backfill_minutes)),
            analysis_window_minutes=int(g("PDM_ANALYSIS_WINDOW_MINUTES", d.analysis_window_minutes)),
            fetch_history_minutes=int(g("PDM_FETCH_HISTORY_MINUTES", d.fetch_history_minutes)),
            bucket_minutes=int(g("PDM_BUCKET_MINUTES", d.bucket_minutes)),
            event_count_min=int(g("PDM_EVENT_COUNT_MIN", d.event_count_min)),
            window_size=int(g("PDM_WINDOW_SIZE", d.window_size)),
            targets=g("PDM_TARGETS", d.targets),
            dedup_db_path=g("PDM_DEDUP_DB_PATH", d.dedup_db_path),
            collapse_high_to_critical=_get_bool(
                "PDM_COLLAPSE_HIGH_TO_CRITICAL", d.collapse_high_to_critical
            ),
            lstm_wire_model_type=g("PDM_LSTM_WIRE_MODEL_TYPE", d.lstm_wire_model_type),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
