from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PassageEventCodec:
    schema_version: str = "hifive.edge.v1"

    def __post_init__(self) -> None:
        self._event_cls = None

    def encode(self, event: dict[str, Any]) -> bytes:
        msg = self._event_cls_cached()()
        msg.event_id = str(event["event_id"])
        msg.device_id = str(event["device_id"])
        msg.camera_id = str(event["camera_id"])
        msg.camera_group_id = str(event["camera_group_id"])
        msg.camera_role = str(event["camera_role"])
        msg.lane_no = int(event["lane_no"])
        msg.global_lane_no = int(event["global_lane_no"])
        msg.local_track_id = str(event["local_track_id"])
        msg.vehicle_pass_id = str(event.get("vehicle_pass_id") or "")
        msg.timestamp = str(event["timestamp"])
        msg.direction = str(event["direction"])
        msg.vehicle_confidence = float(event.get("vehicle_confidence") or 0.0)
        msg.needs_review = bool(event["needs_review"])
        msg.review_reason = str(event.get("review_reason") or "")
        msg.payload_format = "protobuf"
        msg.schema_version = self.schema_version

        plate = event["plate"]
        msg.plate.text = str(plate["text"])
        msg.plate.confidence = float(plate["confidence"])
        msg.plate.candidate_count = int(plate["candidate_count"])
        msg.plate.agreement_ratio = float(plate["agreement_ratio"])

        bbox = event["plate_bbox"]
        msg.plate_bbox.x = int(bbox["x"])
        msg.plate_bbox.y = int(bbox["y"])
        msg.plate_bbox.w = int(bbox["w"])
        msg.plate_bbox.h = int(bbox["h"])
        msg.plate_bbox.unit = str(bbox.get("unit", "pixel"))
        msg.plate_bbox.coord = str(bbox.get("coord", "original_frame"))
        return msg.SerializeToString()

    def _event_cls_cached(self):
        if self._event_cls is None:
            self._event_cls = self._build_dynamic_event_cls()
        return self._event_cls

    def _build_dynamic_event_cls(self):
        from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
        from google.protobuf.descriptor_pb2 import FieldDescriptorProto as F

        file_desc = descriptor_pb2.FileDescriptorProto()
        file_desc.name = "passage_event.proto"
        file_desc.package = "hifive.edge.v1"
        file_desc.syntax = "proto3"

        bbox = file_desc.message_type.add()
        bbox.name = "BBox"
        self._field(bbox, "x", 1, F.TYPE_INT32)
        self._field(bbox, "y", 2, F.TYPE_INT32)
        self._field(bbox, "w", 3, F.TYPE_INT32)
        self._field(bbox, "h", 4, F.TYPE_INT32)
        self._field(bbox, "unit", 5, F.TYPE_STRING)
        self._field(bbox, "coord", 6, F.TYPE_STRING)

        plate = file_desc.message_type.add()
        plate.name = "PlateInfo"
        self._field(plate, "text", 1, F.TYPE_STRING)
        self._field(plate, "confidence", 2, F.TYPE_FLOAT)
        self._field(plate, "candidate_count", 3, F.TYPE_UINT32)
        self._field(plate, "agreement_ratio", 4, F.TYPE_FLOAT)

        event = file_desc.message_type.add()
        event.name = "PassageEvent"
        fields = [
            ("event_id", 1, F.TYPE_STRING, None),
            ("device_id", 2, F.TYPE_STRING, None),
            ("camera_id", 3, F.TYPE_STRING, None),
            ("camera_group_id", 4, F.TYPE_STRING, None),
            ("camera_role", 5, F.TYPE_STRING, None),
            ("lane_no", 6, F.TYPE_UINT32, None),
            ("global_lane_no", 7, F.TYPE_UINT32, None),
            ("local_track_id", 8, F.TYPE_STRING, None),
            ("vehicle_pass_id", 9, F.TYPE_STRING, None),
            ("timestamp", 10, F.TYPE_STRING, None),
            ("direction", 11, F.TYPE_STRING, None),
            ("plate", 12, F.TYPE_MESSAGE, ".hifive.edge.v1.PlateInfo"),
            ("plate_bbox", 14, F.TYPE_MESSAGE, ".hifive.edge.v1.BBox"),
            ("needs_review", 15, F.TYPE_BOOL, None),
            ("review_reason", 16, F.TYPE_STRING, None),
            ("payload_format", 17, F.TYPE_STRING, None),
            ("schema_version", 18, F.TYPE_STRING, None),
            ("vehicle_confidence", 20, F.TYPE_FLOAT, None),
        ]
        for name, number, field_type, type_name in fields:
            self._field(event, name, number, field_type, type_name)

        pool = descriptor_pool.DescriptorPool()
        pool.Add(file_desc)
        desc = pool.FindMessageTypeByName("hifive.edge.v1.PassageEvent")
        return message_factory.GetMessageClass(desc)

    def _field(self, msg, name: str, number: int, field_type: int, type_name: str | None = None) -> None:
        from google.protobuf.descriptor_pb2 import FieldDescriptorProto

        field = msg.field.add()
        field.name = name
        field.number = number
        field.label = FieldDescriptorProto.LABEL_OPTIONAL
        field.type = field_type
        if type_name:
            field.type_name = type_name

