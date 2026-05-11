from __future__ import annotations

from .config import CameraConfig, LaneRegion
from .models import BBox


def point_in_polygon(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        pj = polygon[j]
        xi, yi = pi
        xj, yj = pj
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def lane_for_bbox(camera: CameraConfig, bbox: BBox) -> LaneRegion:
    center = bbox.center()
    for lane in camera.lane_regions:
        if point_in_polygon(center, lane.polygon):
            return lane
    if camera.lane_regions:
        return camera.lane_regions[0]
    return LaneRegion(
        lane_no=1,
        global_lane_no=1,
        polygon=(),
        crossing_line=((0.0, 720.0), (1920.0, 720.0)),
    )


def reject_small_plate(bbox: BBox, min_w: int = 100, min_h: int = 32) -> str | None:
    if bbox.w < min_w:
        return "plate_crop_width_too_small"
    if bbox.h < min_h:
        return "plate_crop_height_too_small"
    return None

