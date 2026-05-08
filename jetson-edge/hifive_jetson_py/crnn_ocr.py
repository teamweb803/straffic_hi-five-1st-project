from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ocr_rules import valid_korean_plate


@dataclass(frozen=True)
class CrnnDecodeResult:
    text: str
    confidence: float
    valid_pattern: bool


class CrnnCtcDecoder:
    def __init__(self, vocabulary: str, blank_index: int = 0) -> None:
        self.blank_index = blank_index
        self.idx_to_char = {i + 1: char for i, char in enumerate(vocabulary)}
        self.idx_to_char[blank_index] = ""

    def decode_probs(self, probs: Any) -> CrnnDecodeResult:
        import numpy as np

        arr = np.asarray(probs)
        if arr.ndim != 2:
            raise ValueError("CRNN probability output must be [time, classes]")

        indexes = arr.argmax(axis=-1).tolist()
        max_probs = arr.max(axis=-1).tolist()
        chars: list[str] = []
        confs: list[float] = []
        previous = -1
        for raw_index, raw_confidence in zip(indexes, max_probs):
            index = int(raw_index)
            if index != previous and index != self.blank_index:
                chars.append(self.idx_to_char.get(index, ""))
                confs.append(float(raw_confidence))
            previous = index

        text = "".join(chars)
        confidence = sum(confs) / len(confs) if confs else 0.0
        return CrnnDecodeResult(
            text=text,
            confidence=max(0.0, min(1.0, confidence)),
            valid_pattern=valid_korean_plate(text),
        )


def preprocess_plate_bgr(crop_bgr: Any, width: int = 160, height: int = 48) -> Any:
    import cv2
    import numpy as np

    arr = np.asarray(crop_bgr)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("plate crop must be HxWx3 BGR")
    rgb = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_LINEAR)
    tensor = resized.astype("float32") / 255.0
    tensor = (tensor - 0.5) / 0.5
    return tensor.transpose(2, 0, 1)[None, ...]


class CrnnTensorRtBoundary:
    """Boundary for a future TensorRT CRNN runner.

    The preferred Jetson path is DeepStream SGIE OCR metadata. Use this class
    only if CRNN logits need to be pulled and decoded in Python.
    """

    def __init__(self, engine_path: str, vocabulary: str) -> None:
        self.engine_path = engine_path
        self.decoder = CrnnCtcDecoder(vocabulary)

    def predict_crop(self, crop_bgr: Any) -> CrnnDecodeResult:
        tensor = preprocess_plate_bgr(crop_bgr)
        probs = self.infer_probs(tensor)
        return self.decoder.decode_probs(probs)

    def infer_probs(self, tensor: Any) -> Any:
        raise NotImplementedError(
            "Wire TensorRT bindings here if DeepStream SGIE cannot expose OCR text metadata."
        )

