from __future__ import annotations

import logging

logger = logging.getLogger("pdm.targets")


def parse_targets(raw: str) -> list[tuple[int, int]]:
    """"1:1,1:2,2:1" 형태 문자열을 [(cameraId, laneId), ...] 로 파싱한다.

    잘못된 항목은 건너뛰고 경고 로그를 남긴다(전체 실행을 막지 않음).
    """
    targets: list[tuple[int, int]] = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            logger.warning("잘못된 target '%s' (형식: cameraId:laneId) -> skip", chunk)
            continue
        camera_str, lane_str = chunk.split(":", 1)
        try:
            targets.append((int(camera_str.strip()), int(lane_str.strip())))
        except ValueError:
            logger.warning("잘못된 target '%s' (정수 아님) -> skip", chunk)
    return targets
