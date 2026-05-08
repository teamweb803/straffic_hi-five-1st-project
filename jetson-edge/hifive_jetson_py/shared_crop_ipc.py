from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from multiprocessing import shared_memory
import os

from .models import BBox, YoloDetection


@dataclass(frozen=True)
class SharedPlateCropTask:
    shm_name: str
    shape: tuple[int, ...]
    dtype: str
    source_id: int
    frame_num: int
    local_track_id: str
    bbox: BBox
    vehicle_confidence: float
    timestamp_ns: int
    lane_no: int
    global_lane_no: int


class SharedPlateCropWriter:
    def __init__(self) -> None:
        self._owned: dict[str, shared_memory.SharedMemory] = {}

    def write_from_frame(self, frame_bgr, detection: YoloDetection) -> SharedPlateCropTask | None:
        import numpy as np

        frame = np.asarray(frame_bgr)
        if frame.ndim != 3:
            raise ValueError("frame must be HxWxC")
        clipped = detection.bbox.clipped(frame.shape[1], frame.shape[0])
        if clipped.w <= 0 or clipped.h <= 0:
            return None
        crop = frame[clipped.y : clipped.y + clipped.h, clipped.x : clipped.x + clipped.w].copy()
        shm = shared_memory.SharedMemory(create=True, size=crop.nbytes)
        target = np.ndarray(crop.shape, dtype=crop.dtype, buffer=shm.buf)
        target[:] = crop
        task = SharedPlateCropTask(
            shm_name=shm.name,
            shape=tuple(crop.shape),
            dtype=str(crop.dtype),
            source_id=detection.source_id,
            frame_num=detection.frame_num,
            local_track_id=detection.local_track_id,
            bbox=clipped,
            vehicle_confidence=detection.confidence,
            timestamp_ns=detection.timestamp_ns,
            lane_no=detection.lane_no,
            global_lane_no=detection.global_lane_no,
        )
        if os.name == "nt":
            self._owned[task.shm_name] = shm
        else:
            shm.close()
        return task

    def release(self, task: SharedPlateCropTask) -> None:
        shm = self._owned.pop(task.shm_name, None)
        if shm is not None:
            shm.close()

    def discard(self, task: SharedPlateCropTask) -> None:
        self.release(task)
        try:
            shm = shared_memory.SharedMemory(name=task.shm_name)
        except FileNotFoundError:
            return
        try:
            shm.unlink()
        finally:
            shm.close()


@contextmanager
def open_shared_plate_crop(task: SharedPlateCropTask, unlink: bool = True):
    import numpy as np

    shm = shared_memory.SharedMemory(name=task.shm_name)
    arr = np.ndarray(task.shape, dtype=np.dtype(task.dtype), buffer=shm.buf)
    try:
        yield arr
    finally:
        del arr
        shm.close()
        if unlink:
            try:
                shm.unlink()
            except FileNotFoundError:
                pass
