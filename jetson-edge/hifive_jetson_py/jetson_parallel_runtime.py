from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue
from typing import Any

from .config import CameraConfig, RuntimeConfig
from .models import PlateObservation
from .yolo_ocr_parallel import OcrLoop, OcrRunner, YoloLoop, YoloRunner


YoloRunnerFactory = Callable[[CameraConfig], YoloRunner]


@dataclass
class GStreamerCameraWorker:
    camera: CameraConfig
    yolo_loop: YoloLoop

    def run(self) -> None:
        import cv2

        pipeline = self._pipeline()
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open GStreamer source for camera_id={self.camera.camera_id}")

        frame_num = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_num += 1
                self.yolo_loop.process_frame(frame, frame_num=frame_num, timestamp_ns=time.time_ns())
        finally:
            cap.release()

    def _pipeline(self) -> str:
        if self.camera.source_pipeline:
            return self.camera.source_pipeline
        if not self.camera.source_uri:
            raise RuntimeError(f"source_uri or source_pipeline is required for camera_id={self.camera.camera_id}")
        if self.camera.source_uri.startswith("gst://"):
            return self.camera.source_uri.removeprefix("gst://")
        if self.camera.source_uri.startswith("/dev/video"):
            return self._usb_camera_pipeline(self.camera.source_uri)
        return self._file_or_uri_pipeline(self.camera.source_uri)

    def _file_or_uri_pipeline(self, source_uri: str) -> str:
        uri = source_uri
        if source_uri.startswith("/"):
            uri = f"file://{source_uri}"
        return (
            f"uridecodebin uri={uri} ! "
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


@dataclass
class JetsonParallelRuntime:
    config: RuntimeConfig
    yolo_runner_factory: YoloRunnerFactory
    ocr_runner: OcrRunner
    on_observation: Callable[[PlateObservation], None]
    queue_maxsize: int = 256
    ocr_worker_count: int = 1

    def run(self) -> None:
        ocr_queue: Queue[Any] = Queue(maxsize=self.queue_maxsize)
        for index in range(self.ocr_worker_count):
            worker = OcrLoop(
                ocr_runner=self.ocr_runner,
                on_observation=self.on_observation,
                input_queue=ocr_queue,
            )
            thread = threading.Thread(target=worker.run_forever, name=f"hifive-ocr-{index}", daemon=True)
            thread.start()

        camera_threads: list[threading.Thread] = []
        for camera in self.config.cameras:
            yolo_loop = YoloLoop(
                camera=camera,
                yolo_runner=self.yolo_runner_factory(camera),
                ocr_queue=ocr_queue,
            )
            camera_worker = GStreamerCameraWorker(camera=camera, yolo_loop=yolo_loop)
            thread = threading.Thread(
                target=camera_worker.run,
                name=f"hifive-yolo-{camera.camera_id}",
                daemon=False,
            )
            thread.start()
            camera_threads.append(thread)

        for thread in camera_threads:
            thread.join()
