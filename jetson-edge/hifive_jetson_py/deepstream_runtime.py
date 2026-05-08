from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .config import RuntimeConfig
from .models import BBox, PlateObservation


ObservationHandler = Callable[[PlateObservation], None]


@dataclass
class DeepStreamRuntime:
    config: RuntimeConfig
    on_observation: ObservationHandler

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
                self._handle_frame_meta(pyds, gst_buffer, frame_meta)
                frame_list = frame_list.next
            return self._gst_ok()

        return _probe

    def _handle_frame_meta(self, pyds, gst_buffer, frame_meta) -> None:
        object_list = frame_meta.obj_meta_list
        while object_list is not None:
            obj_meta = pyds.NvDsObjectMeta.cast(object_list.data)
            if int(obj_meta.class_id) == self.config.plate_class_id:
                observation = self._observation_from_meta(pyds, gst_buffer, frame_meta, obj_meta)
                self.on_observation(observation)
            object_list = object_list.next

    def _observation_from_meta(self, pyds, gst_buffer, frame_meta, obj_meta) -> PlateObservation:
        rect = obj_meta.rect_params
        plate_text, plate_conf = self._read_ocr_label(pyds, obj_meta)
        object_id = int(getattr(obj_meta, "object_id", -1))
        local_track_id = str(object_id if object_id >= 0 else f"frame-{int(frame_meta.frame_num)}")
        return PlateObservation(
            source_id=int(frame_meta.source_id),
            frame_num=int(frame_meta.frame_num),
            local_track_id=local_track_id,
            bbox=BBox(
                x=int(round(rect.left)),
                y=int(round(rect.top)),
                w=int(round(rect.width)),
                h=int(round(rect.height)),
                coord="original_frame",
            ),
            vehicle_confidence=float(getattr(obj_meta, "confidence", 0.0) or 0.0),
            plate_text=plate_text,
            plate_confidence=plate_conf,
            timestamp_ns=time.time_ns(),
        )

    def _read_ocr_label(self, pyds, obj_meta) -> tuple[str, float]:
        cls_list = obj_meta.classifier_meta_list
        while cls_list is not None:
            cls_meta = pyds.NvDsClassifierMeta.cast(cls_list.data)
            label_list = cls_meta.label_info_list
            while label_list is not None:
                label = pyds.NvDsLabelInfo.cast(label_list.data)
                text = getattr(label, "result_label", "") or ""
                confidence = float(getattr(label, "result_prob", 0.0) or 0.0)
                if text:
                    return str(text), confidence
                label_list = label_list.next
            cls_list = cls_list.next
        return "", 0.0

    def _on_bus_message(self, bus, message, loop) -> None:  # type: ignore[no-untyped-def]
        Gst, _, _ = self._load_deepstream()
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"GStreamer error: {err}; debug={debug}")
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
