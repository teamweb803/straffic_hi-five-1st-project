"""가상 통과선(Crossing Line) 판정 알고리즘.

핵심 아이디어
-------------
- 각 track_id 별로 직전 프레임 중심좌표(prev_cx, prev_cy)를 보관한다.
- 현재 프레임 중심좌표와 직전 프레임 중심좌표를 잇는 선분이
  설정된 가상 통과선과 교차하면 통과 이벤트로 판정한다.
- 교차 방향(법선 부호)을 이용해 ENTRY / EXIT 를 구분한다.
- 같은 트랙이 여러 번 통과로 판정되지 않도록 cooldown 을 둔다.

본 알고리즘은 GPS 와 무관하게 영상 좌표계 기반으로만 동작한다.
GPS 결합은 grpc_client 에서 이벤트를 만들 때 수행한다.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from app.core.config import Settings
from app.models.schemas import YoloDetection

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# 기하 유틸
# ------------------------------------------------------------------ #
def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """벡터 외적의 z 성분. 부호로 좌/우 판정 가능."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
) -> bool:
    """선분 p1p2 와 p3p4 가 교차하는지 여부."""
    d1 = _ccw(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = _ccw(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = _ccw(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = _ccw(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


# ------------------------------------------------------------------ #
# 트랙별 상태
# ------------------------------------------------------------------ #
@dataclass
class TrackState:
    track_id: int
    last_cx: float
    last_cy: float
    last_seen: float = field(default_factory=time.monotonic)
    crossed_at: Optional[float] = None  # 마지막 통과 판정 시각 (cooldown 용)


# ------------------------------------------------------------------ #
# 판정 결과
# ------------------------------------------------------------------ #
@dataclass
class CrossingDecision:
    crossed: bool
    direction: str  # "entry" | "exit" | "unknown"
    crossing_ratio: float  # 통과선 위 어느 지점에서 교차했는지 0~1


# ------------------------------------------------------------------ #
# 메인 클래스
# ------------------------------------------------------------------ #
class CrossingLineDetector:
    """차로별로 1개 인스턴스를 두거나, lane_id 키로 다중 인스턴스 관리."""

    TRACK_TTL_SEC = 5.0           # 5초 안 보이면 잊는다
    CROSS_COOLDOWN_SEC = 2.0      # 같은 트랙 재판정 방지

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._line_p1: Tuple[float, float] = (
            float(settings.crossing_line_p1_x),
            float(settings.crossing_line_p1_y),
        )
        self._line_p2: Tuple[float, float] = (
            float(settings.crossing_line_p2_x),
            float(settings.crossing_line_p2_y),
        )
        self._tracks: dict[int, TrackState] = {}

    # -------------------------------------------------------------- #
    def update_line(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> None:
        """관리자 대시보드에서 통과선을 동적으로 변경할 때 사용."""
        self._line_p1, self._line_p2 = p1, p2
        logger.info("Crossing line updated: %s -> %s", p1, p2)

    # -------------------------------------------------------------- #
    def evaluate(self, det: YoloDetection) -> CrossingDecision:
        """단일 검출에 대해 통과 여부를 판정한다."""
        cx, cy = det.bbox.cx, det.bbox.cy
        now = time.monotonic()
        self._gc(now)

        prev = self._tracks.get(det.track_id)
        decision = CrossingDecision(crossed=False, direction="unknown", crossing_ratio=0.0)

        if prev is None:
            self._tracks[det.track_id] = TrackState(det.track_id, cx, cy, now)
            return decision

        # cooldown 중이면 통과 처리 X (상태만 갱신)
        if prev.crossed_at and (now - prev.crossed_at) < self.CROSS_COOLDOWN_SEC:
            prev.last_cx, prev.last_cy, prev.last_seen = cx, cy, now
            return decision

        crossed = _segments_intersect(
            (prev.last_cx, prev.last_cy),
            (cx, cy),
            self._line_p1,
            self._line_p2,
        )

        if crossed:
            # 진행 방향 판정: 이전 점이 통과선 어느쪽에 있었는지
            side_prev = _ccw(
                self._line_p1[0], self._line_p1[1],
                self._line_p2[0], self._line_p2[1],
                prev.last_cx, prev.last_cy,
            )
            direction = "entry" if side_prev < 0 else "exit"
            ratio = self._compute_crossing_ratio(prev.last_cx, prev.last_cy, cx, cy)
            prev.crossed_at = now
            decision = CrossingDecision(crossed=True, direction=direction, crossing_ratio=ratio)
            logger.info(
                "[CROSSED] track_id=%s lane=%s direction=%s plate=%s",
                det.track_id, det.lane_id, direction, det.plate_text,
            )

        prev.last_cx, prev.last_cy, prev.last_seen = cx, cy, now
        return decision

    # -------------------------------------------------------------- #
    def _gc(self, now: float) -> None:
        stale = [tid for tid, st in self._tracks.items() if now - st.last_seen > self.TRACK_TTL_SEC]
        for tid in stale:
            self._tracks.pop(tid, None)

    # -------------------------------------------------------------- #
    def _compute_crossing_ratio(
        self, ax: float, ay: float, bx: float, by: float
    ) -> float:
        """통과선 위에서 교차점이 차지하는 위치 비율(0~1)을 근사 계산.

        선분 p1p2 위의 매개변수 t ∈ [0,1] 를 구한다.
        두 직선의 교차점 공식을 사용.
        """
        x1, y1 = self._line_p1
        x2, y2 = self._line_p2
        denom = (x1 - x2) * (ay - by) - (y1 - y2) * (ax - bx)
        if denom == 0:
            return 0.0
        t_num = (x1 - ax) * (ay - by) - (y1 - ay) * (ax - bx)
        t = t_num / denom
        return max(0.0, min(1.0, t))
