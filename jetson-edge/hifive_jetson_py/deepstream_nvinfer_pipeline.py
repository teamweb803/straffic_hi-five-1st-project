from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import CameraConfig, RuntimeConfig
from .deepstream_config_templates import YoloNvinferTemplate


@dataclass(frozen=True)
class DeepStreamNvinferArtifacts:
    pipeline_text: str
    yolo_config_path: Path
    label_path: Path


@dataclass(frozen=True)
class DeepStreamNvinferOptions:
    output_dir: Path
    source_override: str = ""
    yolo_parser_library_path: str = ""
    yolo_parser_function: str = "NvDsInferParseCustomYoloPlate"
    display: bool = False
    display_sink: str = "egl"


def build_deepstream_nvinfer_artifacts(
    config: RuntimeConfig,
    camera: CameraConfig,
    options: DeepStreamNvinferOptions,
) -> DeepStreamNvinferArtifacts:
    _require_file(config.yolo.engine_path, "YOLO engine")
    _require_file(options.yolo_parser_library_path, "YOLO custom parser library")
    _validate_yolo_canvas(config, camera)

    options.output_dir.mkdir(parents=True, exist_ok=True)
    label_path = options.output_dir / "labels_plate.txt"
    yolo_config_path = options.output_dir / "nvinfer_yolo_plate.txt"

    label_path.write_text("plate\n", encoding="utf-8")
    yolo_config_path.write_text(
        YoloNvinferTemplate(
            engine_path=config.yolo.engine_path,
            label_path=str(label_path),
            parser_library_path=options.yolo_parser_library_path,
            parser_function=options.yolo_parser_function,
            precision=config.yolo.precision,
        ).render(),
        encoding="utf-8",
    )

    source = options.source_override or camera.source_uri
    source_part, live_source = _lane_canvas_source_part(source, camera)
    sink_part = _sink_part(display=options.display, display_sink=options.display_sink)
    pipeline_text = (
        f"{source_part} "
        f"nvstreammux name=mux batch-size=1 width={config.yolo.input_width} height={config.yolo.input_height} "
        f"live-source={live_source} batched-push-timeout=40000 ! "
        f"nvinfer name=plate_yolo config-file-path={yolo_config_path} ! "
        "nvvideoconvert ! video/x-raw(memory:NVMM),format=RGBA ! "
        f"identity name=post_yolo_probe ! {sink_part}"
    )
    return DeepStreamNvinferArtifacts(
        pipeline_text=pipeline_text,
        yolo_config_path=yolo_config_path,
        label_path=label_path,
    )


def _lane_canvas_source_part(source: str, camera: CameraConfig) -> tuple[str, int]:
    slots = camera.yolo_input_slots
    if len(slots) != 2:
        raise RuntimeError("DeepStream nvinfer YOLO requires exactly two yolo_input_slots")

    source_head, live_source = _source_head(source, camera)
    sink_props = " ".join(
        f"sink_{index}::xpos={slot.canvas_rect.x} sink_{index}::ypos={slot.canvas_rect.y}"
        for index, slot in enumerate(slots)
    )
    branches = []
    for index, slot in enumerate(slots):
        source_rect = slot.source_rect
        canvas_rect = slot.canvas_rect
        branches.append(
            "lane_tee. ! queue ! "
            f"nvvideoconvert src-crop={source_rect.x}:{source_rect.y}:{source_rect.w}:{source_rect.h} ! "
            f"video/x-raw(memory:NVMM),format=NV12,width={canvas_rect.w},height={canvas_rect.h} ! "
            f"lane_comp.sink_{index}"
        )
    source_part = (
        f"{source_head} tee name=lane_tee "
        f"nvcompositor name=lane_comp {sink_props} ! "
        "video/x-raw(memory:NVMM),format=RGBA,width=960,height=960 ! "
        "nvvideoconvert ! video/x-raw(memory:NVMM),format=NV12,width=960,height=960 ! mux.sink_0 "
        + " ".join(branches)
    )
    return source_part, live_source


def _sink_part(*, display: bool, display_sink: str) -> str:
    if not display:
        return "fakesink sync=false"
    display_sink = display_sink.lower()
    if display_sink == "egl":
        sink = "nvegltransform ! nveglglessink sync=false"
    elif display_sink == "drm":
        sink = "nvdrmvideosink sync=false"
    elif display_sink == "3d":
        sink = "nv3dsink sync=false"
    else:
        raise RuntimeError(f"unsupported DeepStream display sink: {display_sink}")
    return (
        "tee name=post_yolo_tee "
        "post_yolo_tee. ! queue ! fakesink sync=false "
        "post_yolo_tee. ! queue ! nvdsosd name=display_osd ! "
        f"{sink}"
    )


def _source_head(source: str, camera: CameraConfig) -> tuple[str, int]:
    if source.startswith("/dev/video"):
        return (
            f"v4l2src device={source} ! "
            f"image/jpeg,width={camera.frame_width},height={camera.frame_height},framerate=30/1 ! "
            "jpegdec ! nvvideoconvert ! "
            f"video/x-raw(memory:NVMM),format=NV12,width={camera.frame_width},height={camera.frame_height} !",
            1,
        )
    uri = _as_uri(source)
    return (
        f"nvurisrcbin uri={uri} ! queue ! nvvideoconvert ! "
        f"video/x-raw(memory:NVMM),format=NV12,width={camera.frame_width},height={camera.frame_height} !",
        0,
    )


def _as_uri(source: str) -> str:
    if source.startswith("file://") or "://" in source:
        return source
    return f"file://{source}"


def _require_file(path: str, label: str) -> None:
    if not path:
        raise RuntimeError(f"{label} path is required")
    if not Path(path).exists():
        raise RuntimeError(f"{label} not found: {path}")


def _validate_yolo_canvas(config: RuntimeConfig, camera: CameraConfig) -> None:
    if config.yolo.input_width != 960 or config.yolo.input_height != 960:
        raise RuntimeError("DeepStream nvinfer YOLO requires a 960x960 YOLO engine")
    if len(camera.yolo_input_slots) != 2:
        raise RuntimeError("DeepStream nvinfer YOLO requires two yolo_input_slots")
    for slot in camera.yolo_input_slots:
        if slot.source_rect.w != slot.canvas_rect.w or slot.source_rect.h != slot.canvas_rect.h:
            raise RuntimeError(
                "DeepStream nvinfer YOLO canvas must preserve lane crop size without resize"
            )
