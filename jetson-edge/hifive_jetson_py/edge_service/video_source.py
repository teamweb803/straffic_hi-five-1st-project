from __future__ import annotations

from dataclasses import dataclass

from hifive_jetson_py.config import CameraConfig


@dataclass
class FrameSource:
    camera: CameraConfig
    source_override: str = ""
    start_sec: float = 0.0
    input_backend: str = "deepstream"

    def open(self):
        import cv2

        source = self.source_override or self.camera.source_uri
        backend = self.input_backend.lower()
        if backend == "opencv" and self.source_override and not source.startswith("gst://") and not source.startswith("/dev/video"):
            cap = cv2.VideoCapture(source.removeprefix("file://"))
            mode = "opencv-file"
        else:
            tried: list[str] = []
            cap = None
            mode = backend
            for pipeline in self._pipelines(source, backend):
                tried.append(pipeline)
                candidate = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                if candidate.isOpened():
                    cap = candidate
                    break
                candidate.release()
            if cap is None:
                detail = "\n--- tried pipeline ---\n".join(tried)
                raise RuntimeError(
                    f"cannot open source for camera_id={self.camera.camera_id}: {source}\n"
                    f"--- tried pipeline ---\n{detail}"
                )
        if not cap.isOpened():
            raise RuntimeError(f"cannot open source for camera_id={self.camera.camera_id}: {source}")
        if self.start_sec > 0:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            if fps > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(self.start_sec * fps)))
        return cap, mode

    def _pipelines(self, source: str, backend: str) -> list[str]:
        if self.camera.source_pipeline:
            return [self.camera.source_pipeline]
        if source.startswith("gst://"):
            return [source.removeprefix("gst://")]
        if source.startswith("/dev/video"):
            if backend == "deepstream":
                return [self._deepstream_usb_camera_pipeline(source), self._usb_camera_pipeline(source)]
            return [self._usb_camera_pipeline(source)]
        if source.startswith("/"):
            source = f"file://{source}"
        if backend == "deepstream":
            return [
                self._deepstream_file_or_uri_pipeline(source),
                *self._nvdecoder_file_pipelines(source),
                self._file_or_uri_pipeline(source),
                self._software_file_pipeline(source),
            ]
        return [
            *self._nvdecoder_file_pipelines(source),
            self._file_or_uri_pipeline(source),
            self._software_file_pipeline(source),
        ]

    def _pipeline(self, source: str, backend: str) -> str:
        if self.camera.source_pipeline:
            return self.camera.source_pipeline
        if source.startswith("gst://"):
            return source.removeprefix("gst://")
        if backend == "deepstream":
            return self._deepstream_pipeline(source)
        if source.startswith("/dev/video"):
            return self._usb_camera_pipeline(source)
        if source.startswith("/"):
            source = f"file://{source}"
        return self._file_or_uri_pipeline(source)

    def _deepstream_pipeline(self, source: str) -> str:
        if source.startswith("/dev/video"):
            return self._deepstream_usb_camera_pipeline(source)
        return self._deepstream_file_or_uri_pipeline(self._as_uri(source))

    def _as_uri(self, source: str) -> str:
        if source.startswith("file://") or "://" in source:
            return source
        if source.startswith("/"):
            return f"file://{source}"
        return f"file://{source}"

    def _deepstream_file_or_uri_pipeline(self, source_uri: str) -> str:
        return (
            f"nvurisrcbin uri={source_uri} ! queue ! mux.sink_0 "
            f"nvstreammux name=mux batch-size=1 width={self.camera.frame_width} height={self.camera.frame_height} "
            "live-source=0 batched-push-timeout=40000 ! "
            "nvvideoconvert ! video/x-raw(memory:NVMM),format=RGBA ! "
            "nvvideoconvert ! video/x-raw,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=true max-buffers=1 sync=false"
        )

    def _deepstream_usb_camera_pipeline(self, device: str) -> str:
        return (
            f"nvstreammux name=mux batch-size=1 width={self.camera.frame_width} height={self.camera.frame_height} "
            "live-source=1 batched-push-timeout=40000 ! "
            "nvvideoconvert ! video/x-raw(memory:NVMM),format=RGBA ! "
            "nvvideoconvert ! video/x-raw,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=true max-buffers=1 sync=false "
            f"v4l2src device={device} ! "
            f"image/jpeg,width={self.camera.frame_width},height={self.camera.frame_height},framerate=30/1 ! "
            "jpegdec ! nvvideoconvert ! video/x-raw(memory:NVMM),format=NV12 ! mux.sink_0"
        )

    def _file_or_uri_pipeline(self, source_uri: str) -> str:
        return (
            f"uridecodebin uri={source_uri} ! "
            "nvvideoconvert ! "
            f"video/x-raw,format=BGRx,width={self.camera.frame_width},height={self.camera.frame_height} ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=1 max-buffers=1 sync=false"
        )

    def _nvdecoder_file_pipelines(self, source_uri: str) -> list[str]:
        location = source_uri.removeprefix("file://")
        tail = (
            "nvv4l2decoder ! nvvideoconvert ! "
            f"video/x-raw,format=BGRx,width={self.camera.frame_width},height={self.camera.frame_height} ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=true max-buffers=1 sync=false"
        )
        return [
            f"filesrc location={location} ! qtdemux name=demux demux.video_0 ! queue ! h265parse ! {tail}",
            f"filesrc location={location} ! qtdemux name=demux demux.video_0 ! queue ! h264parse ! {tail}",
            f"filesrc location={location} ! qtdemux ! h265parse ! {tail}",
            f"filesrc location={location} ! qtdemux ! h264parse ! {tail}",
        ]

    def _software_file_pipeline(self, source_uri: str) -> str:
        return (
            f"uridecodebin uri={source_uri} ! "
            f"videoconvert ! videoscale ! "
            f"video/x-raw,format=BGR,width={self.camera.frame_width},height={self.camera.frame_height} ! "
            "appsink drop=true max-buffers=1 sync=false"
        )

    def _usb_camera_pipeline(self, device: str) -> str:
        return (
            f"v4l2src device={device} ! "
            f"image/jpeg,width={self.camera.frame_width},height={self.camera.frame_height},framerate=30/1 ! "
            "jpegdec ! nvvidconv ! "
            f"video/x-raw,format=BGRx,width={self.camera.frame_width},height={self.camera.frame_height} ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=1 max-buffers=1 sync=false"
        )
