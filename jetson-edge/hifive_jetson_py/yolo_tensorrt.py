from __future__ import annotations

import cv2
import numpy as np

from .models import BBox, YoloInputDetection
from .tensorrt_engine import FixedShapeTensorRtEngine


class TensorRtYoloRunner:
    def __init__(
        self,
        engine_path: str,
        confidence_threshold: float,
        input_width: int = 960,
        input_height: int = 960,
    ) -> None:
        self.engine = FixedShapeTensorRtEngine(engine_path)
        self.confidence_threshold = confidence_threshold
        self.input_width = input_width
        self.input_height = input_height

    def infer(self, yolo_input_bgr) -> list[YoloInputDetection]:
        tensor = self._preprocess(yolo_input_bgr)
        output = self.engine.infer(tensor)[0]
        return self._parse_output(output)

    def _preprocess(self, image_bgr) -> np.ndarray:
        image = np.asarray(image_bgr)
        if image.shape[:2] != (self.input_height, self.input_width):
            image = cv2.resize(image, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB)
        tensor = rgb.astype("float32") / 255.0
        return np.ascontiguousarray(tensor.transpose(2, 0, 1)[None, ...])

    def _parse_output(self, output: np.ndarray) -> list[YoloInputDetection]:
        rows = np.asarray(output).reshape(-1, output.shape[-1])
        detections: list[YoloInputDetection] = []
        for row in rows:
            if row.shape[0] < 5:
                continue
            confidence = float(row[4])
            if confidence < self.confidence_threshold:
                continue
            x1, y1, x2, y2 = [float(v) for v in row[:4]]
            if max(x1, y1, x2, y2) <= 1.5:
                x1 *= self.input_width
                x2 *= self.input_width
                y1 *= self.input_height
                y2 *= self.input_height
            if x2 < x1 or y2 < y1:
                cx, cy, w, h = x1, y1, abs(x2), abs(y2)
                x1 = cx - w / 2.0
                y1 = cy - h / 2.0
                x2 = cx + w / 2.0
                y2 = cy + h / 2.0

            x1_i = max(0, min(self.input_width, int(round(x1))))
            y1_i = max(0, min(self.input_height, int(round(y1))))
            x2_i = max(0, min(self.input_width, int(round(x2))))
            y2_i = max(0, min(self.input_height, int(round(y2))))
            if x2_i <= x1_i or y2_i <= y1_i:
                continue
            detections.append(
                YoloInputDetection(
                    bbox=BBox(
                        x=x1_i,
                        y=y1_i,
                        w=x2_i - x1_i,
                        h=y2_i - y1_i,
                        coord="yolo_input",
                    ),
                    confidence=confidence,
                )
            )
        return detections
