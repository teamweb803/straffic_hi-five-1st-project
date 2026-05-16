from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import RuntimeConfig
from .models import BBox, YoloInputDetection


YoloFrameHandler = Callable[[Any | None, int, int, list[YoloInputDetection]], Any]
FrameHandler = Callable[[int], None]
ErrorHandler = Callable[[str], None]


def _rgba(red: float, green: float, blue: float, alpha: float = 1.0) -> tuple[float, float, float, float]:
    return red, green, blue, alpha


MAX_DISPLAY_META_ITEMS = 16


@dataclass
class DeepStreamRuntime:
    config: RuntimeConfig
    on_yolo_frame: YoloFrameHandler
    on_frame: FrameHandler | None = None
    on_error: ErrorHandler | None = None
    shared: Any | None = None
    height_threshold: int = 20
    always_extract_frame: bool = False
    _last_status_at: float = 0.0
    _overlay_fps: float = 0.0
    _overlay_yolo_ms: float = 0.0
    _overlay_yolo_count: int = 0

    def run(self) -> None:
        Gst, GLib, pyds = self._load_deepstream()

        Gst.init(None)
        pipeline = Gst.parse_launch(self.config.pipeline_text)
        probe_element = pipeline.get_by_name("display_osd")
        if probe_element is not None:
            probe_pad = probe_element.get_static_pad("sink")
            probe_label = "display_osd.sink"
        else:
            probe_element = pipeline.get_by_name(self.config.probe_element_name)
            if probe_element is None:
                raise RuntimeError(f"probe element not found: {self.config.probe_element_name}")
            probe_pad = probe_element.get_static_pad("src")
            probe_label = f"{self.config.probe_element_name}.src"
        if probe_pad is None:
            raise RuntimeError(f"probe pad not found: {probe_label}")

        probe_pad.add_probe(Gst.PadProbeType.BUFFER, self._make_probe(pyds), None)

        loop = GLib.MainLoop()
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message, loop)

        pipeline.set_state(Gst.State.PLAYING)
        try:
            loop.run()
        finally:
            pipeline.set_state(Gst.State.NULL)

    def _make_probe(self, pyds):
        def _probe(pad, info, user_data):  # type: ignore[no-untyped-def]
            gst_buffer = info.get_buffer()
            if not gst_buffer:
                return self._gst_ok()
            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
            if batch_meta is None:
                return self._gst_ok()

            frame_list = batch_meta.frame_meta_list
            while frame_list is not None:
                frame_meta = pyds.NvDsFrameMeta.cast(frame_list.data)
                frame_num = int(frame_meta.frame_num)
                if self.on_frame is not None:
                    self.on_frame(frame_num)
                try:
                    self._handle_frame_meta(pyds, gst_buffer, batch_meta, frame_meta)
                except Exception as exc:
                    detail = f"DeepStream probe error frame={frame_num}: {exc}"
                    print(detail)
                    if self.on_error is not None:
                        self.on_error(detail)
                frame_list = frame_list.next
            return self._gst_ok()

        return _probe

    def _handle_frame_meta(self, pyds, gst_buffer, batch_meta, frame_meta) -> None:
        frame_start = time.perf_counter()
        self._update_overlay_fps(frame_start)
        detections, obj_metas = self._detections_from_meta(pyds, frame_meta)
        frame_bgr = None
        if detections or self.always_extract_frame:
            frame_bgr = self._frame_bgr_from_surface(pyds, gst_buffer, frame_meta)
        yolo_start = time.perf_counter()
        tracks = self.on_yolo_frame(
            frame_bgr,
            int(frame_meta.frame_num),
            time.time_ns(),
            detections,
        ) or []
        self._overlay_yolo_ms = (time.perf_counter() - yolo_start) * 1000.0
        if detections:
            self._overlay_yolo_count += 1
        self._suppress_default_object_overlay(obj_metas)
        self._apply_display_overlay(pyds, batch_meta, frame_meta, tracks)

    def _detections_from_meta(self, pyds, frame_meta) -> tuple[list[YoloInputDetection], list[Any]]:
        detections: list[YoloInputDetection] = []
        obj_metas: list[Any] = []
        object_list = frame_meta.obj_meta_list
        while object_list is not None:
            obj_meta = pyds.NvDsObjectMeta.cast(object_list.data)
            if int(obj_meta.class_id) == self.config.plate_class_id:
                rect = obj_meta.rect_params
                obj_metas.append(obj_meta)
                detections.append(
                    YoloInputDetection(
                        bbox=BBox(
                            x=int(round(rect.left)),
                            y=int(round(rect.top)),
                            w=int(round(rect.width)),
                            h=int(round(rect.height)),
                            coord="yolo_input",
                        ),
                        confidence=float(getattr(obj_meta, "confidence", 0.0) or 0.0),
                    )
                )
            object_list = object_list.next
        return detections, obj_metas

    def _suppress_default_object_overlay(self, obj_metas: list[Any]) -> None:
        for obj_meta in obj_metas:
            rect = obj_meta.rect_params
            rect.border_width = 0
            text = obj_meta.text_params
            text.display_text = ""

    def _apply_display_overlay(self, pyds, batch_meta, frame_meta, tracks: list[Any]) -> None:
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        visible_tracks = [track for track in tracks if getattr(track, "visible", True)]
        rect_count = min(len(visible_tracks), MAX_DISPLAY_META_ITEMS)
        display_meta.num_rects = rect_count

        labels = [
            (self._status_line(), 8, 24, 17, _rgba(1.0, 0.85, 0.0)),
            ("Lane 1", 884, 24, 13, _rgba(0.95, 0.95, 0.95)),
            ("Lane 2", 884, 504, 13, _rgba(0.95, 0.95, 0.95)),
        ]
        for index, track in enumerate(visible_tracks[:rect_count]):
            bbox = getattr(track, "yolo_bbox", None)
            if bbox is None:
                continue
            readable = int(getattr(bbox, "h", 0) or 0) >= self.height_threshold
            stable_text = str(getattr(track, "stable_text", "") or "")
            live_text = str(getattr(track, "live_text", "") or "")
            display_id = int(getattr(track, "display_id", 0) or 0)
            color = (
                _rgba(1.0, 0.0, 0.0)
                if not readable
                else _rgba(0.0, 1.0, 0.0)
                if stable_text
                else _rgba(0.0, 0.45, 1.0)
            )
            rect = display_meta.rect_params[index]
            rect.left = float(bbox.x)
            rect.top = float(bbox.y)
            rect.width = float(bbox.w)
            rect.height = float(bbox.h)
            rect.border_width = 2
            rect.border_color.set(*color)
            rect.has_bg_color = 0
            label_text = stable_text or live_text
            if readable and label_text:
                label = f"#{display_id}\n{label_text}\n{bbox.h}px"
            else:
                label = f"#{display_id}\n{bbox.h}px" if display_id > 0 else f"{bbox.h}px"
            labels.append((label, max(0, bbox.x), min(940, max(0, bbox.y + bbox.h + 18)), 14, color))

        labels = labels[:MAX_DISPLAY_META_ITEMS]
        display_meta.num_labels = len(labels)
        for index, (label, x, y, font_size, color) in enumerate(labels):
            text = display_meta.text_params[index]
            text.display_text = label
            text.x_offset = x
            text.y_offset = y
            text.font_params.font_name = "Serif"
            text.font_params.font_size = font_size
            text.font_params.font_color.set(*color)
            text.set_bg_clr = 1
            text.text_bg_clr.set(0.0, 0.0, 0.0, 0.65)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

    def _status_line(self) -> str:
        fps = self._overlay_fps
        yolo_ms = self._overlay_yolo_ms
        yolo_count = self._overlay_yolo_count
        ocr_ms = 0.0
        ocr_count = 0
        if self.shared is not None:
            with self.shared.lock:
                fps = float(getattr(self.shared, "latest_fps", 0.0) or fps)
                yolo_ms = float(getattr(self.shared, "latest_yolo_ms", 0.0) or yolo_ms)
                yolo_count = int(getattr(self.shared, "yolo_detections", 0) or yolo_count)
                ocr_ms = float(getattr(self.shared, "latest_ocr_ms", 0.0) or 0.0)
                ocr_count = int(getattr(self.shared, "processed_ocr_tasks", 0) or 0)
        return f"FPS: {fps:.1f}   YOLO  {yolo_ms:.2f} ms ({yolo_count})   OCR  {ocr_ms:.2f} ms ({ocr_count})"

    def _update_overlay_fps(self, now: float) -> None:
        if self._last_status_at <= 0.0:
            self._last_status_at = now
            return
        dt = max(1e-6, now - self._last_status_at)
        self._last_status_at = now
        instant_fps = 1.0 / dt
        self._overlay_fps = (
            instant_fps
            if self._overlay_fps <= 0.0
            else self._overlay_fps * 0.85 + instant_fps * 0.15
        )

    def _frame_bgr_from_surface(self, pyds, gst_buffer, frame_meta):
        import cv2
        import numpy as np

        surface = pyds.get_nvds_buf_surface(hash(gst_buffer), frame_meta.batch_id)
        frame = np.array(surface, copy=True, order="C")
        if frame.ndim == 2:
            if frame.shape[0] % 3 == 0:
                return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_NV12)
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.ndim != 3:
            raise RuntimeError(f"unexpected DeepStream frame shape: {frame.shape}")
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        if frame.shape[2] == 3:
            return frame
        raise RuntimeError(f"unexpected DeepStream channel count: {frame.shape}")

    def _on_bus_message(self, bus, message, loop) -> None:  # type: ignore[no-untyped-def]
        Gst, _, _ = self._load_deepstream()
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            detail = f"GStreamer error: {err}; debug={debug}"
            print(detail)
            if self.on_error is not None:
                self.on_error(detail)
            loop.quit()

    def _gst_ok(self):
        Gst, _, _ = self._load_deepstream()
        return Gst.PadProbeReturn.OK

    def _load_deepstream(self):
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import GLib, Gst
            import pyds
        except ImportError as exc:
            raise RuntimeError(
                "DeepStream Python runtime requires gi.repository.Gst and pyds on Jetson"
            ) from exc
        return Gst, GLib, pyds
