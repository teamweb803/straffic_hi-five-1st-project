"""
실제 운영 crop (YOLO 등) OCR 평가
입력: CSV (path, label) — 그 외 컬럼은 무시
또는 image directory (label 미지원, accuracy 계산 X)

출력:
  overall accuracy
  greedy / beam / grammar accuracy
  invalid grammar count
  confidence 분포
  errors.csv

사용:
  python -m v5.eval_real_crops --csv d:/aa/real_eval/labels.csv \
        --ckpt d:/aa/training/checkpoints_v5/deploy_candidate_seed42.pt
  python -m v5.eval_real_crops --dir d:/aa/real_eval/images \
        --ckpt d:/aa/training/checkpoints_v5/deploy_candidate_seed42.pt
"""
import argparse, csv, json, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from . import config as C
from .vocab import load_vocab, load_rare, load_confusable
from .model import V5OCR
from .loss import ctc_decode
from .grammar import beam_search_decode, is_valid_kr_plate
from .metrics import (seq_accuracy, rare_accuracy, confidence_per_sample,
                      ece, confidence_histogram, confusable_accuracy,
                      confusable_pair_errors)


def imread_unicode(path):
    try:
        return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (FileNotFoundError, OSError):
        return None


def collect_from_csv(csv_path: Path):
    items = []
    with open(csv_path, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        if "path" not in rd.fieldnames:
            raise ValueError("CSV에 'path' 컬럼 필수")
        has_label = "label" in rd.fieldnames
        for r in rd:
            p = r["path"].strip().strip('"')
            if not p: continue
            items.append({"path": p, "label": (r["label"].strip() if has_label else None)})
    return items, has_label


def collect_from_dir(dir_path: Path):
    items = []
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        items.extend({"path": str(p), "label": None}
                     for p in dir_path.rglob(f"*{ext}"))
    return items, False


@torch.no_grad()
def main(ckpt_path: Path, csv_path: Path = None, dir_path: Path = None,
         output: Path = None, beam_width=10, batch=64):
    if csv_path:
        items, has_label = collect_from_csv(csv_path)
        src_label = f"csv={csv_path}"
    elif dir_path:
        items, has_label = collect_from_dir(dir_path)
        src_label = f"dir={dir_path}"
    else:
        raise ValueError("--csv 또는 --dir 둘 중 하나 필수")
    print(f"[eval-real] {src_label}  items={len(items)}  has_label={has_label}")
    if not items:
        print("[error] 항목 없음"); return

    chars, char2idx, idx2char, num_classes = load_vocab()
    rare_set = set(load_rare())
    conf_chars, conf_pairs = load_confusable()
    conf_set = set(conf_chars)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt_path, map_location=device, weights_only=False)
    state = ck.get("ema") or ck["model"]
    model = V5OCR(num_classes=num_classes).to(device).eval()
    try:
        model.load_state_dict(state, strict=True)
    except Exception:
        model.load_state_dict(state, strict=False)
    print(f"[eval-real] loaded {ckpt_path.name} epoch={ck.get('epoch')} "
          f"weight={'EMA' if ck.get('ema') else 'model'}")

    # 전처리
    arr_imgs, paths, labels, bad_load = [], [], [], 0
    for it in items:
        img = imread_unicode(it["path"])
        if img is None:
            bad_load += 1; continue
        img = cv2.resize(img, (C.IMG_W, C.IMG_H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        arr_imgs.append(img.transpose(2, 0, 1))
        paths.append(it["path"]); labels.append(it["label"])

    print(f"[eval-real] loaded {len(arr_imgs)} (bad_load={bad_load})")

    pred_g, pred_b, pred_gr = [], [], []
    grammar_valid_flags, conf_per = [], []
    t0 = time.time()
    for i in range(0, len(arr_imgs), batch):
        x = torch.from_numpy(np.stack(arr_imgs[i:i + batch])).to(device)
        with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
            logits = model(x)
            log_probs = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
        pred_g.extend(ctc_decode(log_probs, idx2char))
        conf_per.extend(confidence_per_sample(log_probs).tolist())
        log_BTV = log_probs.permute(1, 0, 2).cpu().numpy()
        for b in range(log_BTV.shape[0]):
            cands = beam_search_decode(log_BTV[b], idx2char, beam_width=beam_width)
            top = cands[0][0] if cands else ""
            pred_b.append(top)
            chosen = next((s for s, _ in cands if is_valid_kr_plate(s)), top)
            valid = any(is_valid_kr_plate(s) for s, _ in cands)
            pred_gr.append(chosen if valid else top)
            grammar_valid_flags.append(valid)
    elapsed = time.time() - t0

    invalid = sum(1 for v in grammar_valid_flags if not v)

    rep = {
        "ckpt": str(ckpt_path), "epoch": ck.get("epoch"),
        "n_items": len(items), "n_loaded": len(arr_imgs), "bad_load": bad_load,
        "elapsed_s": round(elapsed, 1),
        "grammar_invalid": invalid,
        "grammar_invalid_pct": invalid / max(1, len(arr_imgs)) * 100,
        "conf_hist": confidence_histogram(conf_per),
    }

    if has_label:
        gts = labels
        cg = [int(p == g) for p, g in zip(pred_g, gts)]
        cb = [int(p == g) for p, g in zip(pred_b, gts)]
        cgr = [int(p == g) for p, g in zip(pred_gr, gts)]
        pair_err = confusable_pair_errors(pred_g, gts, conf_pairs)
        rep.update({
            "acc_greedy":  sum(cg) / len(cg),
            "acc_beam":    sum(cb) / len(cb),
            "acc_grammar": sum(cgr) / len(cgr),
            "rare_acc":    rare_accuracy(pred_g, gts, rare_set),
            "confusable_acc": confusable_accuracy(pred_g, gts, conf_set),
            "ece":         ece(conf_per, cg, n_bins=15),
            "conf_pair_errors": {f"{a}->{b}": d for (a, b), d in pair_err.items()},
        })
        # confusable pair 별 오인 카운트 CSV (real_eval)
        pair_csv = C.REPORTS_DIR / "confusable_pair_errors.csv"
        pair_csv_exists = pair_csv.exists()
        with open(pair_csv, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if not pair_csv_exists:
                w.writerow(["seed", "ckpt", "split", "a", "b",
                            "a_to_b", "b_to_a", "pair_samples"])
            for (a, b), d in pair_err.items():
                w.writerow(["-", str(ckpt_path), "real_eval", a, b,
                            d["a_to_b"], d["b_to_a"], d["total_pair_samples"]])
        print(f"[confusable] pair-error CSV → {pair_csv}")

    # errors.csv
    if output is None:
        out_dir = C.REPORTS_DIR / "real_eval"
        out_dir.mkdir(parents=True, exist_ok=True)
        err_csv = out_dir / "errors.csv"
        rep_json = out_dir / "summary.json"
    else:
        rep_json = Path(output)
        err_csv = rep_json.with_name(rep_json.stem + "_errors.csv")
        rep_json.parent.mkdir(parents=True, exist_ok=True)

    with open(err_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path","label","pred_greedy","pred_beam","pred_grammar",
                    "confidence","grammar_valid","is_error"])
        for p, lab, pg, pb, pgr, cf, vg in zip(paths, labels, pred_g, pred_b,
                                                pred_gr, conf_per,
                                                grammar_valid_flags):
            err = (lab is not None) and (pg != lab)
            if has_label and not err: continue
            w.writerow([p, lab or "", pg, pb, pgr, f"{cf:.4f}",
                        int(vg), int(err)])

    rep["errors_csv"] = str(err_csv)
    rep_json.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    # 출력
    print(f"\n=== 결과 (n={len(arr_imgs)}, {elapsed:.1f}s) ===")
    if has_label:
        print(f"  acc_greedy:  {rep['acc_greedy']:.4f}")
        print(f"  acc_beam:    {rep['acc_beam']:.4f}")
        print(f"  acc_grammar: {rep['acc_grammar']:.4f}")
        rs = (f"{rep['rare_acc']:.4f}" if rep['rare_acc'] is not None else "n/a")
        cs = (f"{rep['confusable_acc']:.4f}" if rep['confusable_acc'] is not None else "n/a")
        print(f"  rare:        {rs}")
        print(f"  confusable:  {cs}")
        print(f"  ECE:         {rep['ece']:.4f}")
    print(f"  grammar invalid: {invalid} / {len(arr_imgs)} "
          f"({rep['grammar_invalid_pct']:.2f}%)")
    print(f"\n[saved] {rep_json}")
    print(f"[saved] {err_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=str, help="CSV with path[,label] columns")
    src.add_argument("--dir", type=str, help="image directory (no labels)")
    ap.add_argument("--ckpt", type=str, required=True)
    ap.add_argument("--output", type=str, default=None,
                    help="summary json path (default: reports_v5/real_eval/summary.json)")
    args = ap.parse_args()
    main(
        ckpt_path=Path(args.ckpt),
        csv_path=Path(args.csv) if args.csv else None,
        dir_path=Path(args.dir) if args.dir else None,
        output=Path(args.output) if args.output else None,
    )
