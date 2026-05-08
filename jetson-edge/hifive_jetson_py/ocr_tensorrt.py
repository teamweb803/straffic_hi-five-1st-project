from __future__ import annotations

import json
from pathlib import Path

from .crnn_ocr import CrnnCtcDecoder, preprocess_plate_bgr
from .tensorrt_engine import FixedShapeTensorRtEngine


class TensorRtOcrRunner:
    def __init__(self, engine_path: str, vocab_path: str) -> None:
        self.engine = FixedShapeTensorRtEngine(engine_path)
        self.decoder = CrnnCtcDecoder(self._load_vocab(vocab_path))

    def predict_crop(self, crop_bgr):
        tensor = preprocess_plate_bgr(crop_bgr)
        probs = self.engine.infer(tensor)[0]
        return self.decoder.decode_probs(probs)

    def _load_vocab(self, vocab_path: str) -> str:
        path = Path(vocab_path)
        if not path.exists():
            raise FileNotFoundError(f"OCR vocab file not found: {path}")
        body = path.read_text(encoding="utf-8").strip()
        if path.suffix.lower() == ".json":
            data = json.loads(body)
            vocab = data.get("vocab", data)
        else:
            vocab = body
        if isinstance(vocab, list):
            vocab = "".join(str(v) for v in vocab)
        if not vocab:
            raise RuntimeError("OCR vocab is empty; training vocabulary order is required for decoding")
        return str(vocab)
