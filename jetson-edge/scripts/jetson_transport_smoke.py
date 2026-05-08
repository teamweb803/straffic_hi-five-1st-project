from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.webtransport_transport import WebTransportIngressSender


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send one HI-FIVE WebTransport smoke event")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--path", default="/hifive/edge")
    parser.add_argument("--server-name", default="")
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    return parser.parse_args()


def build_event() -> dict:
    event_id = f"smoke-{time.time_ns()}"
    return {
        "event_id": event_id,
        "device_id": "jetson-orin-nano-01",
        "camera_id": "cam-rear-01",
        "camera_group_id": "gate-a-pair-01",
        "camera_role": "rear",
        "lane_no": 1,
        "global_lane_no": 1,
        "local_track_id": "track-smoke-1",
        "vehicle_pass_id": "",
        "timestamp": "2026-05-06T00:00:00.000+00:00",
        "direction": "rear",
        "vehicle_confidence": 0.87,
        "plate": {
            "text": "12가3456",
            "confidence": 0.91,
            "candidate_count": 2,
            "agreement_ratio": 1.0,
        },
        "plate_bbox": {
            "x": 100,
            "y": 160,
            "w": 120,
            "h": 40,
            "unit": "pixel",
            "coord": "original_frame",
        },
        "needs_review": False,
        "review_reason": "",
        "payload_format": "protobuf",
        "schema_version": "hifive.edge.v1",
    }


def main() -> None:
    args = parse_args()
    spool_root = Path.home() / "hifive" / "spool_transport_smoke"
    shutil.rmtree(spool_root, ignore_errors=True)
    spool = FileSpool(spool_root)
    codec = PassageEventCodec(schema_version="hifive.edge.v1")
    event = build_event()
    payload = codec.encode(event)

    sender = WebTransportIngressSender(
        host=args.host,
        port=args.port,
        path=args.path,
        server_name=args.server_name or args.host,
        verify_tls=False,
        timeout_sec=args.timeout_sec,
        spool=spool,
        retry_enabled=False,
    )
    start = time.perf_counter()
    accepted = sender.submit(payload, event["event_id"])
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(f"accepted={accepted}")
    print(f"event_id={event['event_id']}")
    print(f"spool_count={spool.count()}")
    print(f"elapsed_ms={elapsed_ms:.2f}")


if __name__ == "__main__":
    main()
