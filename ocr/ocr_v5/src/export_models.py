from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def export_yolo(weights: Path, imgsz: int, workspace: float, device: str) -> None:
    model = YOLO(str(weights))
    model.export(
        format="onnx",
        imgsz=imgsz,
        half=False,
        simplify=True,
        opset=17,
        device=device,
        dynamic=False,
        batch=1,
    )
    model = YOLO(str(weights))
    model.export(
        format="engine",
        imgsz=imgsz,
        half=True,
        simplify=True,
        device=device,
        dynamic=False,
        batch=1,
        workspace=workspace,
    )


def _manual_affine_grid(theta, size, align_corners=False):
    """Trace-friendly replacement for F.affine_grid (TRT 10 has no AffineGrid op)."""
    import torch

    N, _, H, W = size
    device = theta.device
    dtype = theta.dtype
    if align_corners:
        ys = torch.linspace(-1.0, 1.0, H, device=device, dtype=dtype)
        xs = torch.linspace(-1.0, 1.0, W, device=device, dtype=dtype)
    else:
        ys = torch.linspace(-1.0 + 1.0 / H, 1.0 - 1.0 / H, H, device=device, dtype=dtype)
        xs = torch.linspace(-1.0 + 1.0 / W, 1.0 - 1.0 / W, W, device=device, dtype=dtype)
    grid_y, grid_x = torch.meshgrid(ys, xs, indexing="ij")
    ones = torch.ones_like(grid_x)
    base = torch.stack([grid_x, grid_y, ones], dim=-1).reshape(1, H * W, 3)
    base = base.expand(N, -1, -1)
    grid = base.bmm(theta.transpose(1, 2))
    return grid.reshape(N, H, W, 2)


def export_ocr(weights: Path, onnx_out: Path, engine_out: Path, workspace: float) -> None:
    import json

    import torch
    import torch.nn.functional as F
    import tensorrt as trt

    from v5_model import V5OCR

    vocab_path = PROJECT_ROOT / "ocr_vocab.json"
    with open(vocab_path, "r", encoding="utf-8") as f:
        vocab = json.load(f)
    num_classes = vocab["num_classes"]

    ckpt = torch.load(str(weights), map_location="cpu", weights_only=False)
    state = ckpt["model"]
    model = V5OCR(num_classes=num_classes, use_cbam=True)
    missing, unexpected = model.load_state_dict(state, strict=True)
    if missing or unexpected:
        raise RuntimeError(f"state_dict mismatch: missing={missing}, unexpected={unexpected}")
    model.eval()

    dummy = torch.randn(1, 3, 48, 160)
    with torch.no_grad():
        out = model(dummy)
    print(f"[ocr] sanity forward output shape: {tuple(out.shape)} (expected (1, 40, {num_classes}))")

    orig_affine_grid = F.affine_grid
    F.affine_grid = _manual_affine_grid
    with torch.no_grad():
        ref = model(dummy)
    diff = (ref - out).abs().max().item()
    print(f"[ocr] affine_grid patch parity max-abs-diff: {diff:.2e}")
    if diff > 1e-3:
        F.affine_grid = orig_affine_grid
        raise RuntimeError(f"manual affine_grid diverges from torch impl ({diff})")

    try:
        torch.onnx.export(
            model,
            dummy,
            str(onnx_out),
            input_names=["images"],
            output_names=["logits"],
            opset_version=17,
            dynamic_axes=None,
            do_constant_folding=True,
            dynamo=False,
            verbose=False,
        )
    finally:
        F.affine_grid = orig_affine_grid
    print(f"[ocr] ONNX written: {onnx_out}")

    try:
        import onnxslim

        onnxslim.slim(str(onnx_out), str(onnx_out))
        print("[ocr] ONNX simplified via onnxslim")
    except Exception as e:
        print(f"[ocr] onnxslim skipped: {e}")

    trt_logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(trt_logger)
    network = builder.create_network()
    parser = trt.OnnxParser(network, trt_logger)
    with open(onnx_out, "rb") as f:
        if not parser.parse(f.read()):
            errs = "\n".join(str(parser.get_error(i)) for i in range(parser.num_errors))
            raise RuntimeError(f"ONNX parse failed:\n{errs}")
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, int(workspace * (1 << 30)))
    if not builder.platform_has_fast_fp16:
        raise RuntimeError("Platform does not support fast FP16")
    config.set_flag(trt.BuilderFlag.FP16)
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT engine build returned None")
    with open(engine_out, "wb") as f:
        f.write(bytes(serialized))
    size_mb = engine_out.stat().st_size / 1e6
    print(f"[ocr] TRT FP16 engine written: {engine_out} ({size_mb:.1f} MB)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export yolo.pt and/or ocr.pt to ONNX + TensorRT FP16 engine.")
    parser.add_argument("--target", choices=["yolo", "ocr", "all"], default="ocr")
    parser.add_argument("--yolo", type=Path, default=Path("yolo.pt"))
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--workspace", type=float, default=4.0)
    parser.add_argument("--device", default="0")
    parser.add_argument("--ocr", type=Path, default=Path("ocr.pt"))
    parser.add_argument("--ocr-onnx", type=Path, default=Path("ocr.onnx"))
    parser.add_argument("--ocr-engine", type=Path, default=Path("ocr.engine"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.target in ("yolo", "all"):
        export_yolo(args.yolo, args.imgsz, args.workspace, args.device)
    if args.target in ("ocr", "all"):
        export_ocr(args.ocr, args.ocr_onnx, args.ocr_engine, args.workspace)


if __name__ == "__main__":
    main()
