from __future__ import annotations

import os

from .types import PlateTrack, SharedState


GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
WHITE = (240, 240, 240)
BLACK = (0, 0, 0)
FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgun.ttf",
)
_FONT_CACHE: dict[int, object | None] = {}
_TEXT_RENDER_WARNING_SHOWN = False


def draw_runtime_overlay(
    canvas,
    tracks: list[PlateTrack],
    shared: SharedState,
    height_threshold: int,
    frame_num: int,
) -> None:
    import cv2

    with shared.lock:
        fps = shared.latest_fps
        yolo_ms = shared.latest_yolo_ms
        ocr_ms = shared.latest_ocr_ms
        yolo_count = shared.processed_frames
        ocr_count = shared.processed_ocr_tasks

    draw_text(
        canvas,
        f"FPS {fps:.1f}  YOLO {yolo_ms:.2f} ms ({yolo_count})  OCR {ocr_ms:.2f} ms ({ocr_count})",
        (8, 24),
        0.65,
        YELLOW,
        2,
    )
    draw_text(canvas, "Lane 1", (canvas.shape[1] - 76, 24), 0.5, WHITE, 1)
    draw_text(canvas, "Lane 2", (canvas.shape[1] - 76, 504), 0.5, WHITE, 1)

    for track in tracks:
        if not track.visible:
            continue
        bbox = track.yolo_bbox
        readable = bbox.h >= height_threshold
        has_stable_ocr = bool(track.stable_text)
        color = RED if not readable else GREEN if has_stable_ocr else YELLOW
        cv2.rectangle(canvas, (bbox.x, bbox.y), (bbox.x + bbox.w, bbox.y + bbox.h), color, 2)
        if readable and has_stable_ocr:
            label = f"#{track.display_id} {track.stable_text} h={bbox.h}px"
        else:
            label = f"h={bbox.h}px"
        y = min(canvas.shape[0] - 8, bbox.y + bbox.h + 18)
        draw_text(canvas, label, (bbox.x, y), 0.55, color, 2)


def show_frame(window_name: str, frame, scale: float) -> bool:
    import cv2

    if scale != 1.0:
        frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imshow(window_name, frame)
    key = cv2.waitKey(1) & 0xFF
    return key not in (ord("q"), 27)


def draw_text(frame, text: str, origin: tuple[int, int], scale: float, color, thickness: int = 2) -> None:
    import cv2

    if needs_pil_text(text) and draw_text_pil(frame, text, origin, scale, color):
        return
    x, y = origin
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, BLACK, thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def needs_pil_text(text: str) -> bool:
    return any(ord(char) > 127 for char in text)


def draw_text_pil(frame, text: str, origin: tuple[int, int], scale: float, color) -> bool:
    global _TEXT_RENDER_WARNING_SHOWN
    import cv2
    import numpy as np

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        if not _TEXT_RENDER_WARNING_SHOWN:
            print(f"korean_text_render=disabled reason={exc}")
            _TEXT_RENDER_WARNING_SHOWN = True
        return False

    font_size = max(12, int(round(scale * 34)))
    font = load_display_font(font_size)
    if font is None:
        if not _TEXT_RENDER_WARNING_SHOWN:
            print("korean_text_render=disabled reason=no_cjk_font")
            _TEXT_RENDER_WARNING_SHOWN = True
        return False

    try:
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(image)
        x, y = origin
        top = max(0, y - font_size)
        rgb = (int(color[2]), int(color[1]), int(color[0]))
        draw.text((x + 1, top + 1), text, font=font, fill=(0, 0, 0))
        draw.text((x, top), text, font=font, fill=rgb)
        frame[:, :] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        return True
    except Exception as exc:
        if not _TEXT_RENDER_WARNING_SHOWN:
            print(f"korean_text_render=disabled reason={exc}")
            _TEXT_RENDER_WARNING_SHOWN = True
        return False


def load_display_font(font_size: int):
    if font_size in _FONT_CACHE:
        return _FONT_CACHE[font_size]
    try:
        from PIL import ImageFont
    except ImportError:
        _FONT_CACHE[font_size] = None
        return None
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                _FONT_CACHE[font_size] = font
                return font
            except OSError:
                continue
    _FONT_CACHE[font_size] = None
    return None
