"""
Inference 설정:
  - resize bilinear (학습과 동일)
  - normalization 학습과 동일
  - max seq len = 40
  - beam width = 10 (grammar decoder 통합)

TensorRT export 보조 (export_onnx 만 제공; trt 빌드는 외부 trtexec 또는 polygraphy 사용).
"""
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from . import config as C
from .model import V5OCR
from .vocab import load_vocab
from .grammar import grammar_decode_batch
from .loss import ctc_decode


def preprocess(bgr):
    img = cv2.resize(bgr, (C.IMG_W, C.IMG_H), interpolation=cv2.INTER_LINEAR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = (img - 0.5) / 0.5
    return img.transpose(2, 0, 1)


class V5Inference:
    def __init__(self, ckpt_path=None, device=None, use_grammar=True, beam_width=10):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        chars, char2idx, idx2char, num_classes = load_vocab()
        self.idx2char = idx2char
        self.use_grammar = use_grammar
        self.beam_width = beam_width
        self.model = V5OCR(num_classes=num_classes).to(self.device).eval()
        if ckpt_path:
            ck = torch.load(ckpt_path, map_location=self.device, weights_only=False)
            sd = ck.get("ema") or ck["model"]                 # EMA 우선
            self.model.load_state_dict(sd)

    @torch.no_grad()
    def predict(self, bgr_list):
        x = np.stack([preprocess(b) for b in bgr_list])
        x = torch.from_numpy(x).to(self.device)
        with torch.amp.autocast("cuda", enabled=(self.device.type == "cuda")):
            logits = self.model(x)
            log_probs = F.log_softmax(logits, dim=-1)
        if self.use_grammar:
            return grammar_decode_batch(log_probs, self.idx2char, self.beam_width)
        return [(t, None) for t in ctc_decode(log_probs.permute(1, 0, 2), self.idx2char)]


def export_onnx(ckpt_path, onnx_path, opset=17):
    """TensorRT용 ONNX export"""
    chars, _, _, num_classes = load_vocab()
    model = V5OCR(num_classes=num_classes).eval()
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sd = ck.get("ema") or ck["model"]
    model.load_state_dict(sd)
    dummy = torch.randn(1, 3, C.IMG_H, C.IMG_W)
    torch.onnx.export(
        model, dummy, onnx_path,
        input_names=["input"], output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=opset,
    )
    print(f"[onnx] saved {onnx_path}")


if __name__ == "__main__":
    print("V5Inference 로드 테스트만:")
    print("  사용:  inf = V5Inference('checkpoints_v5/best.pt')")
    print("        results = inf.predict([cv2.imread('plate.jpg')])")
