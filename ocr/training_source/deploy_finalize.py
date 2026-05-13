"""
Phase 4 — ONNX 호환 모델 + parity test
1. STN.AdaptiveAvgPool 제거 + F.interpolate 적용 (model.py 갱신 완료)
2. deploy_candidate_seed42.pt 로드 → hard_final 재평가 (regression check)
3. ONNX export (legacy tracer, dynamo=False)
4. PyTorch ↔ ONNX parity test (logit MSE / argmax mismatch)
"""
import sys, json, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import torch
import torch.nn.functional as F
import cv2

from . import config as C
from .vocab import load_vocab, load_rare
from .model import V5OCR
from .loss import ctc_decode
from .metrics import seq_accuracy, rare_accuracy, ece, all_category_accuracies


DEPLOY_PT   = C.CKPT_DIR / "deploy_candidate_seed42.pt"
DEPLOY_ONNX = C.CKPT_DIR / "deploy_candidate_seed42.onnx"
SUMMARY     = C.LOG_DIR / "deploy_finalize_summary.json"


def imread_unicode(path):
    try:
        return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (FileNotFoundError, OSError):
        return None


def preprocess_pil(items):
    arr_imgs, gts, valid_items = [], [], []
    for it in items:
        img = imread_unicode(it["path"])
        if img is None: continue
        img = cv2.resize(img, (C.IMG_W, C.IMG_H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        arr_imgs.append(img.transpose(2, 0, 1))
        gts.append(it["label"]); valid_items.append(it)
    return arr_imgs, gts, valid_items


@torch.no_grad()
def reeval(model, idx2char, rare_set, items, device, batch=64):
    arr_imgs, gts, valid_items = preprocess_pil(items)
    preds = []
    for i in range(0, len(arr_imgs), batch):
        x = torch.from_numpy(np.stack(arr_imgs[i:i + batch])).to(device)
        with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
            logits = model(x)
            log_probs = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
        preds.extend(ctc_decode(log_probs, idx2char))
    return {
        "n":          len(preds),
        "overall":    seq_accuracy(preds, gts),
        "rare":       rare_accuracy(preds, gts, rare_set),
        "categories": all_category_accuracies(preds, gts, valid_items),
    }, arr_imgs, gts


def export_onnx(model_cpu):
    dummy = torch.randn(1, 3, C.IMG_H, C.IMG_W)
    # opset 20 — affine_grid_generator 지원
    torch.onnx.export(
        model_cpu, dummy, str(DEPLOY_ONNX),
        input_names=["input"], output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=20,
        dynamo=False,
    )


def parity_test(model_cpu, arr_imgs, gts, idx2char, batch=32):
    """PyTorch (CPU) vs onnxruntime: logit diff + argmax mismatch"""
    import onnxruntime as ort
    sess = ort.InferenceSession(str(DEPLOY_ONNX),
                                 providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name

    max_abs_diffs, mean_abs_diffs = [], []
    n_total = 0
    n_argmax_mismatch_per_step = 0
    n_seq_mismatch = 0
    n_correct_pt, n_correct_ort = 0, 0

    model_cpu.eval()
    for i in range(0, len(arr_imgs), batch):
        chunk = arr_imgs[i:i + batch]
        gtchunk = gts[i:i + batch]
        x_np = np.stack(chunk).astype(np.float32)
        x_pt = torch.from_numpy(x_np)

        with torch.no_grad():
            logits_pt = model_cpu(x_pt).cpu().numpy()        # (B, T, V)
        logits_ort = sess.run([out_name], {in_name: x_np})[0]  # (B, T, V)

        diff = np.abs(logits_pt - logits_ort)
        max_abs_diffs.append(float(diff.max()))
        mean_abs_diffs.append(float(diff.mean()))

        # argmax mismatch (per timestep)
        am_pt = logits_pt.argmax(-1)        # (B, T)
        am_ort = logits_ort.argmax(-1)
        n_argmax_mismatch_per_step += int((am_pt != am_ort).sum())
        n_total += am_pt.size

        # 시퀀스 디코딩 비교
        lp_pt = torch.from_numpy(logits_pt).permute(1, 0, 2)
        lp_pt = F.log_softmax(lp_pt, dim=-1)
        lp_ort = torch.from_numpy(logits_ort).permute(1, 0, 2)
        lp_ort = F.log_softmax(lp_ort, dim=-1)
        seq_pt = ctc_decode(lp_pt, idx2char)
        seq_ort = ctc_decode(lp_ort, idx2char)
        for sp, so, g in zip(seq_pt, seq_ort, gtchunk):
            if sp != so: n_seq_mismatch += 1
            if sp == g:  n_correct_pt += 1
            if so == g:  n_correct_ort += 1

    return {
        "n_samples":             len(arr_imgs),
        "n_steps_total":         n_total,
        "max_abs_logit_diff":    float(np.max(max_abs_diffs)),
        "mean_abs_logit_diff":   float(np.mean(mean_abs_diffs)),
        "argmax_mismatch_steps": n_argmax_mismatch_per_step,
        "argmax_mismatch_pct":   n_argmax_mismatch_per_step / max(1, n_total) * 100,
        "seq_mismatch":          n_seq_mismatch,
        "seq_mismatch_pct":      n_seq_mismatch / max(1, len(arr_imgs)) * 100,
        "acc_pt":                n_correct_pt  / max(1, len(arr_imgs)),
        "acc_ort":               n_correct_ort / max(1, len(arr_imgs)),
    }


def main():
    print("=" * 60)
    print(" Deploy Finalize — ONNX 호환 + Parity Test")
    print("=" * 60)
    if not DEPLOY_PT.exists():
        raise FileNotFoundError(DEPLOY_PT)
    if not C.HARD_FINAL_IDX.exists():
        raise FileNotFoundError(C.HARD_FINAL_IDX)

    chars, char2idx, idx2char, num_classes = load_vocab()
    rare_set = set(load_rare())
    items = json.loads(C.HARD_FINAL_IDX.read_text(encoding="utf-8"))["items"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(DEPLOY_PT, map_location=device, weights_only=False)
    state = ck.get("ema") or ck["model"]
    model = V5OCR(num_classes=num_classes).to(device).eval()
    # state_dict 호환 검사
    try:
        model.load_state_dict(state, strict=True)
        load_msg = "strict load OK"
    except Exception as e:
        # AdaptiveAvgPool 제거로 인한 키 차이 가능성
        missing, unexpected = model.load_state_dict(state, strict=False)
        load_msg = f"strict load 실패 → strict=False. missing={len(missing)} unexp={len(unexpected)}"
        print(f"[load] {load_msg}")
        if missing or unexpected:
            print(f"  missing[:5]={missing[:5]}")
            print(f"  unexpected[:5]={unexpected[:5]}")
    else:
        print(f"[load] {load_msg}  epoch={ck.get('epoch')}")

    # 1) 재평가
    print("\n[1] hard_final 재평가 (수정 모델)")
    t0 = time.time()
    rep, _, _ = reeval(model, idx2char, rare_set, items, device)
    rstr = f"{rep['rare']:.4f}" if rep['rare'] is not None else "n/a"
    print(f"  n={rep['n']}  overall={rep['overall']:.4f}  "
          f"rare={rstr}  ({time.time()-t0:.1f}s)")
    for k, v in rep["categories"].items():
        a = f"{v['acc']:.4f}" if v["acc"] is not None else "n/a"
        print(f"    {k:>11s}: {a}  (n={v['n']})")
    baseline_overall = 0.9800
    delta = rep["overall"] - baseline_overall
    print(f"  baseline overall=0.9800  Δ={delta:+.4f}")
    if delta < -0.005:
        print(f"  ⚠️ regression > 0.5pp — 검토 필요")
    else:
        print(f"  ✅ regression 없음 (≥ baseline 또는 미세 차)")

    # 2) ONNX export (CPU 모델)
    print("\n[2] ONNX export")
    model_cpu = V5OCR(num_classes=num_classes).eval()
    model_cpu.load_state_dict(state, strict=False)
    try:
        export_onnx(model_cpu)
        print(f"  ✅ {DEPLOY_ONNX} ({DEPLOY_ONNX.stat().st_size/1024/1024:.1f}MB)")
    except Exception as e:
        print(f"  ❌ export 실패: {e}")
        return

    # 3) Parity test
    print("\n[3] PyTorch (CPU) ↔ onnxruntime Parity Test")
    arr_imgs, gts, _ = preprocess_pil(items)
    parity = parity_test(model_cpu, arr_imgs, gts, idx2char)
    print(f"  samples           : {parity['n_samples']}")
    print(f"  max  |logit diff| : {parity['max_abs_logit_diff']:.6f}")
    print(f"  mean |logit diff| : {parity['mean_abs_logit_diff']:.6f}")
    print(f"  argmax mismatch   : {parity['argmax_mismatch_steps']}/{parity['n_steps_total']} "
          f"({parity['argmax_mismatch_pct']:.4f}%)")
    print(f"  seq    mismatch   : {parity['seq_mismatch']}/{parity['n_samples']} "
          f"({parity['seq_mismatch_pct']:.4f}%)")
    print(f"  acc PyTorch / ORT : {parity['acc_pt']:.4f} / {parity['acc_ort']:.4f}")

    target = 0.1
    if parity["seq_mismatch_pct"] < target:
        print(f"  ✅ seq mismatch < {target}% — 양산 호환 OK")
    else:
        print(f"  ⚠️  seq mismatch ≥ {target}% — parity 미달")

    # 요약
    summary = {
        "deploy_pt":   str(DEPLOY_PT),
        "onnx":        str(DEPLOY_ONNX),
        "load_msg":    load_msg,
        "hard_final_reeval": rep,
        "parity":      parity,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n[saved] {SUMMARY}")
    print(f"\nTensorRT FP16 빌드 명령:")
    print(f"  trtexec --onnx={DEPLOY_ONNX} --fp16 "
          f"--saveEngine={DEPLOY_ONNX.with_suffix('.fp16.engine')}")


if __name__ == "__main__":
    main()
