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


@dataclass
class DeepStreamRuntime:
    config: RuntimeConfig
    on_yolo_frame: YoloFrameHandler
    on_frame: FrameHandler | None = None
    on_error: ErrorHandler | None = None
    shared: Any | None = None
    height_threshold: int = 20

    def run(self) -> None:
        Gst, GLib, pyds = self._load_deepstream()

        Gst.init(None)
        pipeline = Gst.parse_launch(self.config.pipeline_text)
        probe_element = pipeline.get_by_name(self.config.probe_element_name)
        if probe_element is None:
            raise RuntimeError(f"probe element not found: {self.config.probe_element_name}")
        src_pad = probe_element.get_static_pad("src")
        if src_pad is None:
            raise RuntimeError(f"probe element has no src pad: {self.config.probe_element_name}")

        src_pad.add_probe(Gst.PadProbeType.BUFFER, self._make_probe(pyds), None)

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
        detections, obj_metas = self._detections_from_meta(pyds, frame_meta)
        frame_bgr = None
        if detections:
            frame_bgr = self._frame_bgr_from_surface(pyds, gst_buffer, frame_meta)
        tracks = self.on_yolo_frame(
            frame_bgr,
            int(frame_meta.frame_num),
            time.time_ns(),
            detections,
        ) or []
        self._apply_object_overlay(obj_metas, tracks)
        self._apply_frame_overlay(pyds, batch_meta, frame_meta)

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

    def _apply_object_overlay(self, obj_metas: list[Any], tracks: list[Any]) -> None:
        for obj_meta, track in zip(obj_metas, tracks):
            bbox = getattr(track, "yolo_bbox", None)
            if bbox is None:
                continue
            readable = int(getattr(bbox, "h", 0) or 0) >= self.height_threshold
            stable_text = str(getattr(track, "stable_text", "") or "")
            display_id = int(getattr(track, "display_id", 0) or 0)
            color = _rgba(1.0, 0.0, 0.0) if not readable else _rgba(0.0, 1.0, 0.0) if stable_text else _rgba(1.0, 0.85, 0.0)
            rect = obj_meta.rect_params
            rect.border_width = 2
            rect.border_color.set(*color)
            text = obj_meta.text_params
            if readable and stable_text:
                label = f"#{display_id} {stable_text} h={bbox.h}px"
            else:
                label = f"h={bbox.h}px"
            text.display_text = label
            text.x_offset = max(0, int(rect.left))
            text.y_offset = min(940, max(0, int(rect.top + rect.height + 18)))
            text.font_params.font_name = "Noto Sans CJK KR"
            text.font_params.font_size = 14
            text.font_params.font_color.set(*color)
            text.set_bg_clr = 1
            text.text_bg_clr.set(0.0, 0.0, 0.0, 0.65)

    def _apply_frame_overlay(self, pyds, batch_meta, frame_meta) -> None:
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        labels = [
            (self._status_line(), 8, 24, 17, _rgba(1.0, 0.85, 0.0)),
            ("Lane 1", 884, 24, 13, _rgba(0.95, 0.95, 0.95)),
            ("Lane 2", 884, 504, 13, _rgba(0.95, 0.95, 0.95)),
        ]
        display_meta.num_labels = len(labels)
        for index, (label, x, y, font_size, color) in enumerate(labels):
            text = display_meta.text_params[index]
            text.display_text = label
            text.x_offset = x
            text.y_offset = y
            text.font_params.font_name = "Noto Sans CJK KR"
            text.font_params.font_size = font_size
            text.font_params.font_color.set(*color)
            text.set_bg_clr = 1
            text.text_bg_clr.set(0.0, 0.0, 0.0, 0.65)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

    def _status_line(self) -> str:
        if self.shared is None:
            return ""
        with self.shared.lock:
            fps = float(getattr(self.shared, "latest_fps", 0.0) or 0.0)
            yolo_ms = float(getattr(self.shared, "latest_yolo_ms", 0.0) or 0.0)
            ocr_ms = float(getattr(self.shared, "latest_ocr_ms", 0.0) or 0.0)
            frames = int(getattr(self.shared, "processed_frames", 0) or 0)
            ocr_count = int(getattr(self.shared, "processed_ocr_tasks", 0) or 0)
        return f"FPS {fps:.1f}  YOLO {yolo_ms:.2f} ms ({frames})  OCR {ocr_ms:.2f} ms ({ocr_count})"

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
