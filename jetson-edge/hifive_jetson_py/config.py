from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import BBox


Point = tuple[float, float]


@dataclass(frozen=True)
class LaneRegion:
    lane_no: int
    global_lane_no: int
    polygon: tuple[Point, ...]
    crossing_line: tuple[Point, Point]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LaneRegion":
        line = data.get("crossing_line") or [[0, 720], [1920, 720]]
        return cls(
            lane_no=int(data["lane_no"]),
            global_lane_no=int(data.get("global_lane_no", data["lane_no"])),
            polygon=tuple((float(p[0]), float(p[1])) for p in data.get("polygon", [])),
            crossing_line=(
                (float(line[0][0]), float(line[0][1])),
                (float(line[1][0]), float(line[1][1])),
            ),
        )


@dataclass(frozen=True)
class YoloInputSlot:
    lane_no: int
    global_lane_no: int
    source_rect: BBox
    canvas_rect: BBox

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YoloInputSlot":
        source = data["source_rect"]
        canvas = data["canvas_rect"]
        return cls(
            lane_no=int(data["lane_no"]),
            global_lane_no=int(data.get("global_lane_no", data["lane_no"])),
            source_rect=BBox(
                x=int(source["x"]),
                y=int(source["y"]),
                w=int(source["w"]),
                h=int(source["h"]),
                coord="original_frame",
            ),
            canvas_rect=BBox(
                x=int(canvas["x"]),
                y=int(canvas["y"]),
                w=int(canvas["w"]),
                h=int(canvas["h"]),
                coord="yolo_input",
            ),
        )


@dataclass(frozen=True)
class CameraConfig:
    source_id: int
    camera_id: str
    camera_group_id: str
    camera_role: str
    direction: str
    source_uri: str
    source_pipeline: str
    frame_width: int
    frame_height: int
    crop_rect: BBox
    lane_regions: tuple[LaneRegion, ...]
    yolo_input_slots: tuple[YoloInputSlot, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraConfig":
        crop = data.get("crop_rect") or {}
        lane_regions = tuple(LaneRegion.from_dict(v) for v in data.get("lane_regions", []))
        yolo_input_slots = tuple(
            YoloInputSlot.from_dict(v) for v in data.get("yolo_input_slots", [])
        )
        if not yolo_input_slots:
            yolo_input_slots = cls._default_yolo_input_slots(data, lane_regions)
        return cls(
            source_id=int(data["source_id"]),
            camera_id=str(data["camera_id"]),
            camera_group_id=str(data["camera_group_id"]),
            camera_role=str(data.get("camera_role", "rear")),
            direction=str(data.get("direction", data.get("camera_role", "rear"))),
            source_uri=str(data.get("source_uri", "")),
            source_pipeline=str(data.get("source_pipeline", "")),
            frame_width=int(data.get("frame_width", 1920)),
            frame_height=int(data.get("frame_height", 1080)),
            crop_rect=BBox(
                x=int(crop.get("x", 480)),
                y=int(crop.get("y", 60)),
                w=int(crop.get("w", 960)),
                h=int(crop.get("h", 960)),
                coord="original_frame",
            ),
            lane_regions=lane_regions,
            yolo_input_slots=yolo_input_slots,
        )

    @staticmethod
    def _default_yolo_input_slots(
        data: dict[str, Any],
        lane_regions: tuple[LaneRegion, ...],
    ) -> tuple[YoloInputSlot, ...]:
        if int(data.get("frame_width", 1920)) != 1920 or int(data.get("frame_height", 1080)) != 1080:
            return ()
        if len(lane_regions) < 2:
            return ()
        return (
            YoloInputSlot(
                lane_no=lane_regions[0].lane_no,
                global_lane_no=lane_regions[0].global_lane_no,
                source_rect=BBox(0, 540, 960, 480, coord="original_frame"),
                canvas_rect=BBox(0, 0, 960, 480, coord="yolo_input"),
            ),
            YoloInputSlot(
                lane_no=lane_regions[1].lane_no,
                global_lane_no=lane_regions[1].global_lane_no,
                source_rect=BBox(960, 540, 960, 480, coord="original_frame"),
                canvas_rect=BBox(0, 480, 960, 480, coord="yolo_input"),
            ),
        )


@dataclass(frozen=True)
class EngineConfig:
    engine_path: str
    precision: str
    input_width: int
    input_height: int
    confidence_threshold: float = 0.25
    nms_iou_threshold: float = 0.45

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_w: int, default_h: int) -> "EngineConfig":
        return cls(
            engine_path=str(data.get("engine_path", "")),
            precision=str(data.get("precision", "fp16")),
            input_width=int(data.get("input_width", default_w)),
            input_height=int(data.get("input_height", default_h)),
            confidence_threshold=float(data.get("confidence_threshold", 0.25)),
            nms_iou_threshold=float(data.get("nms_iou_threshold", 0.45)),
        )


@dataclass(frozen=True)
class OcrConfig(EngineConfig):
    min_crop_width: int = 100
    min_crop_height: int = 32
    vocab_path: str = "/home/jetson/hifive/models/ocr_vocab.json"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OcrConfig":
        base = EngineConfig.from_dict(data, default_w=160, default_h=48)
        return cls(
            engine_path=base.engine_path,
            precision=base.precision,
            input_width=base.input_width,
            input_height=base.input_height,
            confidence_threshold=float(data.get("confidence_threshold", 0.70)),
            nms_iou_threshold=base.nms_iou_threshold,
            min_crop_width=int(data.get("min_crop_width", 100)),
            min_crop_height=int(data.get("min_crop_height", 32)),
            vocab_path=str(data.get("vocab_path", "/home/jetson/hifive/models/ocr_vocab.json")),
        )


@dataclass(frozen=True)
class TransportConfig:
    kind: str
    endpoint: str
    timeout_sec: float
    dry_run: bool = False
    ingress_host: str = ""
    ingress_port: int = 4433
    webtransport_path: str = "/hifive/edge"
    server_name: str = ""
    verify_tls: bool = True
    retry_enabled: bool = True
    retry_initial_sec: float = 1.0
    retry_max_sec: float = 30.0
    retry_max_items_per_cycle: int = 16

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransportConfig":
        return cls(
            kind=str(data.get("kind", "webtransport_ingress")),
            endpoint=str(data.get("endpoint", "")),
            timeout_sec=float(data.get("timeout_sec", 3.0)),
            dry_run=bool(data.get("dry_run", False)),
            ingress_host=str(data.get("ingress_host", "")),
            ingress_port=int(data.get("ingress_port", 4433)),
            webtransport_path=str(data.get("webtransport_path", data.get("path", "/hifive/edge"))),
            server_name=str(data.get("server_name", "")),
            verify_tls=bool(data.get("verify_tls", True)),
            retry_enabled=bool(data.get("retry_enabled", True)),
            retry_initial_sec=float(data.get("retry_initial_sec", 1.0)),
            retry_max_sec=float(data.get("retry_max_sec", 30.0)),
            retry_max_items_per_cycle=int(data.get("retry_max_items_per_cycle", 16)),
        )


@dataclass(frozen=True)
class RuntimeConfig:
    device_id: str
    schema_version: str
    pipeline_text: str
    probe_element_name: str
    plate_class_id: int
    spool_dir: str
    yolo: EngineConfig
    ocr: OcrConfig
    transport: TransportConfig
    cameras: tuple[CameraConfig, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeConfig":
        return cls(
            device_id=str(data["device_id"]),
            schema_version=str(data.get("schema_version", "hifive.edge.v1")),
            pipeline_text=str(data.get("pipeline_text", "")),
            probe_element_name=str(data.get("probe_element_name", "plate_yolo")),
            plate_class_id=int(data.get("plate_class_id", 0)),
            spool_dir=str(data.get("spool_dir", "/var/lib/hifive-edge/spool")),
            yolo=EngineConfig.from_dict(data.get("yolo", {}), default_w=960, default_h=960),
            ocr=OcrConfig.from_dict(data.get("ocr", {})),
            transport=TransportConfig.from_dict(data.get("transport", {})),
            cameras=tuple(CameraConfig.from_dict(v) for v in data.get("cameras", [])),
        )

    @classmethod
    def from_python_file(cls, path: str | Path) -> "RuntimeConfig":
        config_path = Path(path)
        spec = importlib.util.spec_from_file_location("hifive_runtime_config", config_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load config: {config_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = getattr(module, "CONFIG")
        return cls.from_dict(data)

    def camera_by_source_id(self, source_id: int) -> CameraConfig | None:
        for camera in self.cameras:
            if camera.source_id == int(source_id):
                return camera
        return None
