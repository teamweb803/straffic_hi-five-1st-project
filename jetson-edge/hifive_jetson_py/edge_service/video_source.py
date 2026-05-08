from __future__ import annotations

from dataclasses import dataclass

from hifive_jetson_py.config import CameraConfig


@dataclass
class FrameSource:
    camera: CameraConfig
    source_override: str = ""
    start_sec: float = 0.0

    def open(self):
        import cv2

        source = self.source_override or self.camera.source_uri
        if self.source_override and not source.startswith("gst://") and not source.startswith("/dev/video"):
            cap = cv2.VideoCapture(source.removeprefix("file://"))
            mode = "opencv-file"
        else:
            cap = cv2.VideoCapture(self._pipeline(source), cv2.CAP_GSTREAMER)
            mode = "gstreamer"
        if not cap.isOpened():
            raise RuntimeError(f"cannot open source for camera_id={self.camera.camera_id}: {source}")
        if self.start_sec > 0:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            if fps > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(self.start_sec * fps)))
        return cap, mode

    def _pipeline(self, source: str) -> str:
        if self.camera.source_pipeline:
            return self.camera.source_pipeline
        if source.startswith("gst://"):
            return source.removeprefix("gst://")
        if source.startswith("/dev/video"):
            return self._usb_camera_pipeline(source)
        if source.startswith("/"):
            source = f"file://{source}"
        return self._file_or_uri_pipeline(source)

    def _file_or_uri_pipeline(self, source_uri: str) -> str:
        return (
            f"uridecodebin uri={source_uri} ! "
            "nvvidconv ! "
            f"video/x-raw,format=BGRx,width={self.camera.frame_width},height={self.camera.frame_height} ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=1 max-buffers=1 sync=false"
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
