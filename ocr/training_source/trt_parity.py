"""
PyTorch ↔ ONNX ↔ TensorRT 3-way parity test
hard_final 250장 기준 logit 차이 + argmax mismatch + seq accuracy 비교

실행 환경: TensorRT 가 설치된 머신 (Jetson Orin Nano 또는 호스트의 GPU)
필요 패키지: tensorrt, onnxruntime, pycuda 또는 tensorrt python API

사용:
  python -m v5.trt_parity \
        --pt   d:/aa/training/checkpoints_v5/deploy_candidate_seed42.pt \
        --onnx d:/aa/training/checkpoints_v5/deploy_candidate_seed42.onnx \
        --trt  d:/aa/training/checkpoints_v5/deploy_candidate_seed42.fp16.engine
"""
import argparse, json, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from . import config as C
from .vocab import load_vocab, load_rare
from .model import V5OCR
from .loss import ctc_decode
from .metrics import seq_accuracy, all_category_accuracies


def imread_unicode(path):
    try:
        return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (FileNotFoundError, OSError):
        return None


def preprocess(items):
    imgs, gts, valid = [], [], []
    for it in items:
        img = imread_unicode(it["path"])
        if img is None: continue
        img = cv2.resize(img, (C.IMG_W, C.IMG_H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        imgs.append(img.transpose(2, 0, 1))
        gts.append(it["label"]); valid.append(it)
    return imgs, gts, valid


# ---------- PyTorch ----------
@torch.no_grad()
def run_pt(model, imgs_np, batch=64, device="cpu"):
    out = []
    for i in range(0, len(imgs_np), batch):
        x = torch.from_numpy(np.stack(imgs_np[i:i + batch])).to(device)
        with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
            logits = model(x).float().cpu().numpy()
        out.append(logits)
    return np.concatenate(out, axis=0)


# ---------- ONNX runtime ----------
def run_ort(onnx_path, imgs_np, batch=64, providers=None):
    import onnxruntime as ort
    if providers is None:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess = ort.InferenceSession(str(onnx_path), providers=providers)
    in_name = sess.get_inputs()[0].name; out_name = sess.get_outputs()[0].name
    out = []
    for i in range(0, len(imgs_np), batch):
        x = np.stack(imgs_np[i:i + batch]).astype(np.float32)
        out.append(sess.run([out_name], {in_name: x})[0])
    return np.concatenate(out, axis=0)


# ---------- TensorRT ----------
class TRTRunner:
    def __init__(self, engine_path):
        import tensorrt as trt
        import pycuda.driver as cuda
        import pycuda.autoinit  # noqa: F401  (드라이버 초기화)
        logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(logger)
        with open(engine_path, "rb") as f:
            self.engine = runtime.deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()
        # IO 텐서 이름 추출
        self.input_name = None
        self.output_name = None
        for i in range(self.engine.num_io_tensors):
            n = self.engine.get_tensor_name(i)
            if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT:
                self.input_name = n
            else:
                self.output_name = n
        self.cuda = cuda
        # IO shape 출력
        ishape = self.engine.get_tensor_shape(self.input_name)
        oshape = self.engine.get_tensor_shape(self.output_name)
        precision = "FP16" if any(
            self.engine.get_tensor_dtype(n) == trt.float16
            for n in (self.input_name, self.output_name)) else "FP32"
        print(f"[trt] input  {self.input_name}: shape={ishape}")
        print(f"[trt] output {self.output_name}: shape={oshape}")
        print(f"[trt] precision: {precision}")

    def infer(self, imgs_np, batch=64):
        import tensorrt as trt
        out_logits = []
        for i in range(0, len(imgs_np), batch):
            x = np.stack(imgs_np[i:i + batch]).astype(np.float32)
            B = x.shape[0]
            self.context.set_input_shape(self.input_name, (B, 3, C.IMG_H, C.IMG_W))
            # 출력 shape 결정
            oshape = tuple(self.context.get_tensor_shape(self.output_name))
            d_in  = self.cuda.mem_alloc(x.nbytes)
            o = np.empty(oshape, dtype=np.float32)
            d_out = self.cuda.mem_alloc(o.nbytes)
            self.cuda.memcpy_htod(d_in, x)
            self.context.set_tensor_address(self.input_name, int(d_in))
            self.context.set_tensor_address(self.output_name, int(d_out))
            stream = self.cuda.Stream()
            self.context.execute_async_v3(stream.handle)
            stream.synchronize()
            self.cuda.memcpy_dtoh(o, d_out)
            out_logits.append(o.copy())
            del d_in, d_out
        return np.concatenate(out_logits, axis=0)


# ---------- Compare ----------
def compare(name_a, logits_a, name_b, logits_b, idx2char, gts):
    diff = np.abs(logits_a - logits_b)
    am_a = logits_a.argmax(-1); am_b = logits_b.argmax(-1)
    n_steps = am_a.size
    n_step_mismatch = int((am_a != am_b).sum())
    lp_a = F.log_softmax(torch.from_numpy(logits_a).permute(1, 0, 2), dim=-1)
    lp_b = F.log_softmax(torch.from_numpy(logits_b).permute(1, 0, 2), dim=-1)
    seq_a = ctc_decode(lp_a, idx2char)
    seq_b = ctc_decode(lp_b, idx2char)
    seq_mismatch = sum(1 for a, b in zip(seq_a, seq_b) if a != b)
    acc_a = sum(1 for s, g in zip(seq_a, gts) if s == g) / max(1, len(gts))
    acc_b = sum(1 for s, g in zip(seq_b, gts) if s == g) / max(1, len(gts))
    return {
        "pair": f"{name_a} vs {name_b}",
        "max_abs_logit_diff":   float(diff.max()),
        "mean_abs_logit_diff":  float(diff.mean()),
        "argmax_mismatch":      n_step_mismatch,
        "argmax_mismatch_pct":  n_step_mismatch / max(1, n_steps) * 100,
        "seq_mismatch":         seq_mismatch,
        "seq_mismatch_pct":     seq_mismatch / max(1, len(seq_a)) * 100,
        "acc_a":                acc_a,
        "acc_b":                acc_b,
    }


def main(pt_path, onnx_path, trt_path, output: Path = None):
    chars, _, idx2char, num_classes = load_vocab()
    items = json.loads(C.HARD_FINAL_IDX.read_text(encoding="utf-8"))["items"]
    imgs, gts, valid = preprocess(items)
    print(f"[data] hard_final {len(imgs)}장")

    # PyTorch
    print("\n[1] PyTorch (CPU)")
    device = torch.device("cpu")
    ck = torch.load(pt_path, map_location=device, weights_only=False)
    state = ck.get("ema") or ck["model"]
    pt_model = V5OCR(num_classes=num_classes).eval()
    pt_model.load_state_dict(state, strict=False)
    t0 = time.time(); logits_pt = run_pt(pt_model, imgs, device=device); t_pt = time.time() - t0
    print(f"  shape={logits_pt.shape}  elapsed={t_pt:.1f}s")

    # ONNX
    print("\n[2] ONNX Runtime")
    t0 = time.time(); logits_ort = run_ort(onnx_path, imgs); t_ort = time.time() - t0
    print(f"  shape={logits_ort.shape}  elapsed={t_ort:.1f}s")

    # TensorRT
    print("\n[3] TensorRT engine")
    trt_runner = TRTRunner(trt_path)
    t0 = time.time(); logits_trt = trt_runner.infer(imgs); t_trt = time.time() - t0
    print(f"  shape={logits_trt.shape}  elapsed={t_trt:.1f}s")

    # 비교
    print("\n[4] Pair-wise comparison")
    cmp1 = compare("PT",  logits_pt,  "ORT", logits_ort, idx2char, gts)
    cmp2 = compare("ORT", logits_ort, "TRT", logits_trt, idx2char, gts)
    cmp3 = compare("PT",  logits_pt,  "TRT", logits_trt, idx2char, gts)
    for c in (cmp1, cmp2, cmp3):
        print(f"\n  {c['pair']}")
        print(f"    max  |Δ|: {c['max_abs_logit_diff']:.6f}")
        print(f"    mean |Δ|: {c['mean_abs_logit_diff']:.6f}")
        print(f"    argmax mismatch: {c['argmax_mismatch']}/{logits_pt.size//logits_pt.shape[-1]}  "
              f"({c['argmax_mismatch_pct']:.4f}%)")
        print(f"    seq    mismatch: {c['seq_mismatch']}/{len(gts)}  ({c['seq_mismatch_pct']:.4f}%)")
        print(f"    acc {c['pair'].split(' vs ')[0]}={c['acc_a']:.4f}  "
              f"{c['pair'].split(' vs ')[1]}={c['acc_b']:.4f}")

    summary = {
        "pt_path":    str(pt_path),
        "onnx_path":  str(onnx_path),
        "trt_path":   str(trt_path),
        "n_samples":  len(gts),
        "elapsed_s":  {"pt": t_pt, "ort": t_ort, "trt": t_trt},
        "PT_vs_ORT":  cmp1,
        "ORT_vs_TRT": cmp2,
        "PT_vs_TRT":  cmp3,
    }
    if output is None:
        output = C.LOG_DIR / "trt_parity_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"\n[saved] {output}")

    # 판정
    print("\n=== 판정 ===")
    target_pct = 0.1
    pt_trt_ok = cmp3["seq_mismatch_pct"] < target_pct
    print(f"  PT vs TRT seq mismatch < {target_pct}% : "
          f"{'✅' if pt_trt_ok else '⚠️'}  ({cmp3['seq_mismatch_pct']:.4f}%)")
    print(f"  acc 차이 ≤ 0.5pp : "
          f"{'✅' if abs(cmp3['acc_a']-cmp3['acc_b']) <= 0.005 else '⚠️'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt",   default=str(C.CKPT_DIR / "deploy_candidate_seed42.pt"))
    ap.add_argument("--onnx", default=str(C.CKPT_DIR / "deploy_candidate_seed42.onnx"))
    ap.add_argument("--trt",  default=str(C.CKPT_DIR / "deploy_candidate_seed42.fp16.engine"))
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    main(Path(args.pt), Path(args.onnx), Path(args.trt),
         Path(args.output) if args.output else None)
