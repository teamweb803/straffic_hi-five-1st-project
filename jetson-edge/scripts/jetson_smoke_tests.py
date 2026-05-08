from __future__ import annotations

import shutil
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from hifive_jetson_py.event_builder import PassageEventBuilder
from hifive_jetson_py.framing import pack_event_frame, unpack_ready_event_frame
from hifive_jetson_py.lane_yolo_input import TwoLaneYoloInputComposer
from hifive_jetson_py.models import BBox, PlateDecision, PlateObservation, YoloDetection
from hifive_jetson_py.ocr_rules import OcrCandidateBuffer
from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.shared_crop_ipc import SharedPlateCropWriter, open_shared_plate_crop
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.transport import DryRunSender
from hifive_jetson_py.config import RuntimeConfig


def test_framing() -> None:
    packed = pack_event_frame("evt-1", b"payload")
    buf = bytearray(packed[:3])
    assert unpack_ready_event_frame(buf) is None
    buf.extend(packed[3:])
    frame = unpack_ready_event_frame(buf)
    assert frame is not None
    assert frame.event_id == "evt-1"
    assert frame.payload == b"payload"
    assert len(buf) == 0
    print("framing ok")


def test_yolo_canvas(config: RuntimeConfig) -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[60:540, 0:960] = (10, 20, 30)
    frame[60:540, 960:1920] = (40, 50, 60)
    composer = TwoLaneYoloInputComposer(config.cameras[0])
    canvas = composer.compose(frame)
    assert canvas.shape == (960, 960, 3)
    assert tuple(canvas[10, 10]) == (10, 20, 30)
    assert tuple(canvas[500, 10]) == (40, 50, 60)

    restored = composer.restore_bbox(BBox(100, 100, 50, 20, coord="yolo_input"))
    assert restored is not None
    bbox, lane_no, global_lane_no = restored
    assert (bbox.x, bbox.y, bbox.w, bbox.h) == (100, 160, 50, 20)
    assert (lane_no, global_lane_no) == (1, 1)
    print("960x960 yolo canvas + bbox restore ok")


def test_shared_memory_crop() -> None:
    frame = np.arange(100 * 200 * 3, dtype=np.uint8).reshape((100, 200, 3))
    detection = YoloDetection(
        source_id=0,
        frame_num=7,
        local_track_id="track-1",
        bbox=BBox(10, 20, 30, 40),
        confidence=0.88,
        timestamp_ns=time.time_ns(),
        lane_no=1,
        global_lane_no=1,
    )
    writer = SharedPlateCropWriter()
    task = writer.write_from_frame(frame, detection)
    assert task is not None
    with open_shared_plate_crop(task) as crop:
        assert crop.shape == (40, 30, 3)
        assert np.array_equal(crop, frame[20:60, 10:40])
    print("shared memory crop ok")


def test_spool_transport_event(config: RuntimeConfig) -> None:
    spool_root = Path.home() / "hifive" / "spool_smoke"
    shutil.rmtree(spool_root, ignore_errors=True)
    config = replace(config, spool_dir=str(spool_root))
    spool = FileSpool(spool_root)
    sender = DryRunSender(spool)
    codec = PassageEventCodec(schema_version=config.schema_version)
    builder = PassageEventBuilder(config=config, codec=codec, sender=sender)

    decision = PlateDecision(
        text="12가3456",
        confidence=0.91,
        valid_pattern=True,
        needs_review=False,
        review_reason="",
        candidate_count=2,
        agreement_ratio=1.0,
    )
    observation = PlateObservation(
        source_id=0,
        frame_num=10,
        local_track_id="track-1",
        bbox=BBox(100, 160, 120, 40),
        vehicle_confidence=0.87,
        plate_text="12가3456",
        plate_confidence=0.91,
        timestamp_ns=time.time_ns(),
    )
    event = builder.build_and_submit(observation, lane_no=1, global_lane_no=1, decision=decision)
    assert event["plate"]["text"] == "12가3456"
    assert spool.count() == 1
    item = spool.iter_items()[0]
    item = spool.record_attempt(item)
    assert item.attempts == 1
    spool.ack(item)
    assert spool.count() == 0
    shutil.rmtree(spool_root, ignore_errors=True)
    print("protobuf + dry-run transport spool/ack ok")


def test_ocr_buffer() -> None:
    buffer = OcrCandidateBuffer(min_candidates=2, confidence_threshold=0.70)
    buffer.add("track-1", "12가3456", 0.91)
    buffer.add("track-1", "12가3456", 0.84)
    decision = buffer.decide("track-1")
    assert decision.text == "12가3456"
    assert not decision.needs_review
    print("ocr candidate voting ok")


def main() -> None:
    config = RuntimeConfig.from_python_file("example_runtime_config.py")
    test_framing()
    test_yolo_canvas(config)
    test_shared_memory_crop()
    test_ocr_buffer()
    test_spool_transport_event(config)
    print("all smoke tests ok")


if __name__ == "__main__":
    main()
