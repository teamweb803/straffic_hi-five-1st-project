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
    srt_host: str = ""
    srt_port: int = 0
    srt_bitrate_kbps: int = 2500
    srt_latency_ms: int = 120
    srt_iframe_interval: int = 15
    srt_fps: int = 30
    srt_width: int = 720
    srt_height: int = 720


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
    sink_part = _sink_part(
        display=options.display,
        display_sink=options.display_sink,
        srt_host=options.srt_host,
        srt_port=options.srt_port,
        srt_bitrate_kbps=options.srt_bitrate_kbps,
        srt_latency_ms=options.srt_latency_ms,
        srt_iframe_interval=options.srt_iframe_interval,
        srt_fps=options.srt_fps,
        srt_width=options.srt_width,
        srt_height=options.srt_height,
    )
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


def _sink_part(
    *,
    display: bool,
    display_sink: str,
    srt_host: str,
    srt_port: int,
    srt_bitrate_kbps: int,
    srt_latency_ms: int,
    srt_iframe_interval: int,
    srt_fps: int,
    srt_width: int,
    srt_height: int,
) -> str:
    srt_branch = _srt_branch(
        srt_host=srt_host,
        srt_port=srt_port,
        bitrate_kbps=srt_bitrate_kbps,
        latency_ms=srt_latency_ms,
        iframe_interval=srt_iframe_interval,
        fps=srt_fps,
        width=srt_width,
        height=srt_height,
    )
    if not display and not srt_branch:
        return "fakesink sync=false"

    visual_branches: list[str] = []
    if display:
        visual_branches.append(_display_branch(display_sink))
    if srt_branch:
        visual_branches.append(srt_branch)

    return (
        "tee name=post_yolo_tee "
        "post_yolo_tee. ! queue ! fakesink sync=false "
        "post_yolo_tee. ! queue ! nvdsosd name=display_osd "
        "process-mode=0 display-bbox=1 display-text=1 ! tee name=visual_tee "
        + " ".join(visual_branches)
    )


def _display_branch(display_sink: str) -> str:
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
        "visual_tee. ! queue ! "
        f"{sink}"
    )


def _srt_branch(
    *,
    srt_host: str,
    srt_port: int,
    bitrate_kbps: int,
    latency_ms: int,
    iframe_interval: int,
    fps: int,
    width: int,
    height: int,
) -> str:
    if not srt_host and srt_port <= 0:
        return ""
    if not srt_host or srt_port <= 0:
        raise RuntimeError("SRT output requires both srt_host and srt_port")
    latency = max(20, int(latency_ms))
    iframe = max(1, int(iframe_interval))
    stream_fps = min(60, max(1, int(fps)))
    stream_width = max(160, int(width))
    stream_height = max(160, int(height))
    uri = f"srt://{srt_host}:{srt_port}?mode=caller&transtype=live&latency={latency}"
    return (
        "visual_tee. ! queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! "
        f"nvvideoconvert ! video/x-raw,format=I420,width={stream_width},height={stream_height} ! "
        f"videorate drop-only=true ! video/x-raw,format=I420,width={stream_width},height={stream_height},framerate={stream_fps}/1 ! "
        f"x264enc tune=zerolatency speed-preset=ultrafast byte-stream=true option-string=\"repeat-headers=1\" bitrate={max(64, int(bitrate_kbps))} key-int-max={iframe} ! "
        "video/x-h264,stream-format=byte-stream ! "
        "h264parse config-interval=-1 ! mpegtsmux alignment=7 ! "
        f"srtsink uri=\"{uri}\" wait-for-connection=true sync=true"
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
