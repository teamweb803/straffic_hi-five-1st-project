from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


IMG_H = 48
IMG_W = 160


class STN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.localization = nn.Sequential(
            nn.Conv2d(3, 16, 7, padding=3),
            nn.BatchNorm2d(16),
            nn.ReLU(True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.AdaptiveAvgPool2d((4, 12)),
        )
        self.fc_loc = nn.Sequential(
            nn.Linear(64 * 4 * 12, 128),
            nn.ReLU(True),
            nn.Linear(128, 64),
            nn.ReLU(True),
            nn.Linear(64, 6),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        xs = self.localization(x).flatten(1)
        theta = self.fc_loc(xs).view(-1, 2, 3)
        grid = F.affine_grid(theta, x.size(), align_corners=False)
        return F.grid_sample(x, grid, align_corners=False)


class Backbone(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.b1 = nn.Sequential(
            nn.Conv2d(3, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.MaxPool2d(2),
        )
        self.b2 = nn.Sequential(
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.Conv2d(128, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.MaxPool2d(2),
        )
        self.b3 = nn.Sequential(
            nn.Conv2d(128, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.Conv2d(256, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1)),
        )
        self.b4 = nn.Sequential(
            nn.Conv2d(256, 512, 3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.Conv2d(512, 512, 3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.MaxPool2d((6, 1)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.b4(self.b3(self.b2(self.b1(x))))


class ChannelAttention(nn.Module):
    def __init__(self, channels: int, reduction: int = 16) -> None:
        super().__init__()
        hidden = channels // reduction
        self.fc = nn.Sequential(
            nn.Conv2d(channels, hidden, 1, bias=False),
            nn.ReLU(True),
            nn.Conv2d(hidden, channels, 1, bias=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = torch.mean(x, dim=(2, 3), keepdim=True)
        mx = torch.amax(x, dim=(2, 3), keepdim=True)
        attn = torch.sigmoid(self.fc(avg) + self.fc(mx))
        return x * attn


class SpatialAttention(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Conv2d(2, 1, 7, padding=3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = torch.mean(x, dim=1, keepdim=True)
        mx, _ = torch.max(x, dim=1, keepdim=True)
        attn = torch.sigmoid(self.conv(torch.cat([avg, mx], dim=1)))
        return x * attn


class CBAM(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.ca = ChannelAttention(channels)
        self.sa = SpatialAttention()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.sa(self.ca(x))


class HifiveOcrNet(nn.Module):
    def __init__(self, num_classes: int) -> None:
        super().__init__()
        self.stn = STN()
        self.backbone = Backbone()
        self.cbam = CBAM(512)
        self.bilstm = nn.LSTM(
            512,
            256,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
            dropout=0.1,
        )
        self.classifier = nn.Linear(512, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stn(x)
        x = self.backbone(x)
        x = self.cbam(x)
        x = x.squeeze(2).permute(0, 2, 1)
        x, _ = self.bilstm(x)
        return self.classifier(x)


class OcrExportModel(nn.Module):
    def __init__(self, model: nn.Module, output_kind: str) -> None:
        super().__init__()
        self.model = model
        self.output_kind = output_kind

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        logits = self.model(images)
        if self.output_kind == "logits":
            return logits
        return torch.softmax(logits, dim=-1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export HI-FIVE OCR checkpoint to ONNX")
    parser.add_argument("--checkpoint", default=r"C:\kmj\hi-five\ocr.pt")
    parser.add_argument("--output", default=r"C:\kmj\hi-five\ocr.onnx")
    parser.add_argument("--metadata-output", default=r"C:\kmj\hi-five\ocr_metadata.json")
    parser.add_argument("--vocab-file", default="")
    parser.add_argument("--output-kind", choices=("probs", "logits"), default="probs")
    parser.add_argument("--opset", type=int, default=18)
    return parser.parse_args()


def load_vocab(path: str) -> list[str]:
    if not path:
        return []
    body = Path(path).read_text(encoding="utf-8").strip()
    if not body:
        return []
    if path.endswith(".json"):
        data = json.loads(body)
        vocab = data.get("vocab", data)
        return list(vocab)
    return list(body)


def find_vocab(checkpoint_path: Path, num_classes: int) -> list[str]:
    candidates = []
    candidates.extend(checkpoint_path.parent.glob("ocr_vocab.json"))
    candidates.extend(checkpoint_path.parent.rglob("ocr_vocab.json"))
    candidates.extend(Path(r"C:\kmj\hi-five").rglob("ocr_vocab.json"))

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        chars = data.get("chars") or data.get("vocab") or []
        if len(chars) + 1 == num_classes:
            return [str(char) for char in chars]
    return []


def main() -> None:
    args = parse_args()
    checkpoint_path = Path(args.checkpoint)
    output_path = Path(args.output)
    metadata_path = Path(args.metadata_output)

    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state_dict = checkpoint["model"]
    num_classes = int(state_dict["classifier.weight"].shape[0])

    model = HifiveOcrNet(num_classes)
    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    if missing or unexpected:
        raise RuntimeError(f"state_dict mismatch: missing={missing}, unexpected={unexpected}")
    model.eval()

    export_model = OcrExportModel(model, args.output_kind).eval()
    dummy = torch.zeros((1, 3, IMG_H, IMG_W), dtype=torch.float32)
    with torch.no_grad():
        y = export_model(dummy)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        export_model,
        dummy,
        output_path,
        input_names=["images"],
        output_names=[args.output_kind],
        opset_version=args.opset,
        dynamo=True,
        external_data=False,
    )

    vocab = load_vocab(args.vocab_file) if args.vocab_file else find_vocab(checkpoint_path, num_classes)
    metadata = {
        "checkpoint": str(checkpoint_path),
        "onnx": str(output_path),
        "input": {"name": "images", "shape": [1, 3, IMG_H, IMG_W]},
        "output": {"name": args.output_kind, "shape": list(y.shape)},
        "num_classes": num_classes,
        "blank_index": 0,
        "vocab": vocab,
        "scores": checkpoint.get("scores", {}),
        "score_adj": checkpoint.get("score_adj"),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"checkpoint: {checkpoint_path}")
    print(f"onnx: {output_path}")
    print(f"metadata: {metadata_path}")
    print(f"output: {args.output_kind} {list(y.shape)}")
    if not vocab:
        print("warning: vocab is empty; decoding text requires the training vocabulary order.")


if __name__ == "__main__":
    main()
