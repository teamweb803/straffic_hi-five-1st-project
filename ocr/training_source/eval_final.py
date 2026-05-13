"""
Phase 3 #4 — Final Evaluation (hard_final 250 1회만)
요구 (사용자 spec):
  - hard_final overall, categories, rare, confusable, ECE, invalid grammar count
  - 오답 CSV 저장 (path/label/pred_greedy/pred_beam/pred_grammar/conf/tags/error_type)
  - 오답 이미지 복사
  - 결정 기준 출력 (≥98.7% / 98~98.7% / <98%)
"""
import argparse, csv, json, shutil, sys, time
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
from .metrics import (seq_accuracy, rare_accuracy, confidence_per_sample,
                      ece, confidence_histogram, all_category_accuracies,
                      confusable_accuracy, confusable_pair_errors,
                      hard_without_tag, operational_hard_score)
from .grammar import beam_search_decode, grammar_decode, is_valid_kr_plate


def imread_unicode(path):
    try:
        return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (FileNotFoundError, OSError):
        return None


@torch.no_grad()
def main(seed: int = 42, ckpt: Path = None, output: Path = None,
         batch=64, beam_width=10, v6: bool = False):
    paths = C.seed_paths_v6(seed) if v6 else C.seed_paths(seed)
    if ckpt is None:   ckpt   = paths["best_pt"]
    if output is None: output = paths["eval_json"]
    err_csv      = paths["errors_csv"]
    err_imgs_dir = paths["errors_imgs"]
    err_imgs_dir.mkdir(parents=True, exist_ok=True)

    if not C.HARD_FINAL_IDX.exists():
        raise FileNotFoundError(C.HARD_FINAL_IDX)
    if not Path(ckpt).exists():
        raise FileNotFoundError(ckpt)

    chars, char2idx, idx2char, num_classes = load_vocab()
    rare_set = set(load_rare())
    conf_chars, conf_pairs = load_confusable()
    conf_set = set(conf_chars)
    with open(C.HARD_FINAL_IDX, encoding="utf-8") as f:
        items = json.load(f)["items"]
    print(f"[eval-final] hard_final = {len(items)}장")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt, map_location=device, weights_only=False)
    model = V5OCR(num_classes=num_classes).to(device).eval()
    state = ck.get("ema") or ck["model"]
    model.load_state_dict(state)
    using = "EMA" if ck.get("ema") else "model"
    print(f"[eval-final] loaded {ckpt} (epoch {ck.get('epoch','?')}, weight={using})")

    # 이미지 로드 (path 보존). 누락 시 PIL fallback 시도, 둘 다 실패하면 skip + 사유 기록.
    arr_imgs, gts, valid_items = [], [], []
    skipped = []
    for it in items:
        img = imread_unicode(it["path"])
        if img is None:
            # PIL fallback (cv2 unicode 이슈 보정)
            try:
                from PIL import Image
                pil = Image.open(it["path"]).convert("RGB")
                pil_np = np.array(pil)[:, :, ::-1]   # RGB → BGR
                img = pil_np
            except Exception:
                skipped.append({"path": it["path"], "label": it.get("label", ""),
                                 "categories": ";".join(it.get("categories", []))})
                continue
        rs = cv2.resize(img, (C.IMG_W, C.IMG_H))
        rgb = cv2.cvtColor(rs, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgb = (rgb - 0.5) / 0.5
        arr_imgs.append(rgb.transpose(2, 0, 1))
        gts.append(it["label"])
        valid_items.append(it)
    n_total = len(items); n_processed = len(valid_items); n_skipped = len(skipped)
    print(f"[eval-final] processed={n_processed}/{n_total}  skipped={n_skipped}")
    if skipped:
        skip_csv = paths["report_dir"] / "hard_final_skipped.csv"
        skip_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(skip_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["path","label","categories"])
            w.writeheader()
            for r in skipped: w.writerow(r)
        print(f"[eval-final] skipped → {skip_csv}")

    preds_greedy, preds_beam, preds_grammar = [], [], []
    grammar_valid_flags, conf_per_sample = [], []

    t0 = time.time()
    for i in range(0, len(arr_imgs), batch):
        x = torch.from_numpy(np.stack(arr_imgs[i:i + batch])).to(device)
        with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
            logits = model(x)                              # (B, T, V)
            log_probs_TBV = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
        # greedy
        pg = ctc_decode(log_probs_TBV, idx2char)
        preds_greedy.extend(pg)
        # confidence
        conf_per_sample.extend(confidence_per_sample(log_probs_TBV).tolist())
        # beam (no grammar filter — 가장 likely)
        # grammar (KR pattern 통과 first)
        log_probs_BTV = log_probs_TBV.permute(1, 0, 2).cpu().numpy()
        for b in range(log_probs_BTV.shape[0]):
            cands = beam_search_decode(log_probs_BTV[b], idx2char, beam_width=beam_width)
            top1_text = cands[0][0] if cands else ""
            preds_beam.append(top1_text)
            text, valid = grammar_decode(log_probs_BTV[b], idx2char, beam_width=beam_width)
            preds_grammar.append(text)
            grammar_valid_flags.append(valid)

    elapsed = time.time() - t0

    # 정답 비교
    corr_greedy  = [int(p == g) for p, g in zip(preds_greedy,  gts)]
    corr_beam    = [int(p == g) for p, g in zip(preds_beam,    gts)]
    corr_grammar = [int(p == g) for p, g in zip(preds_grammar, gts)]

    overall_greedy  = sum(corr_greedy)  / len(corr_greedy)  if corr_greedy  else 0.0
    overall_beam    = sum(corr_beam)    / len(corr_beam)    if corr_beam    else 0.0
    overall_grammar = sum(corr_grammar) / len(corr_grammar) if corr_grammar else 0.0

    rare_acc = rare_accuracy(preds_greedy, gts, rare_set)
    conf_acc = confusable_accuracy(preds_greedy, gts, conf_set)
    cat_acc  = all_category_accuracies(preds_greedy, gts, valid_items)
    pair_err = confusable_pair_errors(preds_greedy, gts, conf_pairs)
    ece_val  = ece(conf_per_sample, corr_greedy, n_bins=15)
    hist     = confidence_histogram(conf_per_sample)

    # 신규 운영 지표
    overall_no_small, n_no_small = hard_without_tag(
        preds_greedy, gts, valid_items, exclude_tag="small_plate")
    op_score, op_breakdown = operational_hard_score(
        cat_acc, C.OPERATIONAL_HARD_WEIGHTS)

    invalid_grammar = sum(1 for v in grammar_valid_flags if not v)

    # 오답 CSV (greedy 기준 오답)
    n_err = 0
    with open(err_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path","label","pred_greedy","pred_beam","pred_grammar",
                    "confidence","tags","error_type","grammar_valid"])
        for it, g, pg, pb, pgr, cf, vg in zip(valid_items, gts, preds_greedy,
                                              preds_beam, preds_grammar,
                                              conf_per_sample, grammar_valid_flags):
            err_g = (pg != g)
            err_b = (pb != g)
            err_gr = (pgr != g)
            if not err_g: continue
            n_err += 1
            tags = ";".join(it.get("categories", []))
            error_type = []
            if err_g: error_type.append("greedy")
            if err_b: error_type.append("beam")
            if err_gr: error_type.append("grammar")
            w.writerow([it["path"], g, pg, pb, pgr, f"{cf:.4f}",
                        tags, "+".join(error_type), int(vg)])
            # 오답 이미지 복사 (label_pred 형태로)
            try:
                src = Path(it["path"])
                dst_name = f"{g}_pred-{pg or 'EMPTY'}_{src.name}"
                # 중복 회피
                dst = err_imgs_dir / dst_name
                k = 0
                while dst.exists():
                    k += 1
                    dst = err_imgs_dir / f"{Path(dst_name).stem}_{k}{Path(dst_name).suffix}"
                shutil.copy2(str(src), str(dst))
            except Exception:
                pass

    rep = {
        "ckpt": str(ckpt), "epoch": ck.get("epoch"),
        "v6": v6,
        "hard_final_total":     n_total,
        "hard_final_processed": n_processed,
        "hard_final_skipped":   n_skipped,
        "n":   len(preds_greedy),
        "overall": {
            "greedy":  overall_greedy,
            "beam":    overall_beam,
            "grammar": overall_grammar,
        },
        "rare":         rare_acc,
        "confusable":   conf_acc,
        "ece":          ece_val,
        "categories":   cat_acc,
        # 신규 운영 지표
        "hard_without_small": {"acc": overall_no_small, "n": n_no_small},
        "operational_hard_score": op_score,
        "operational_breakdown":  op_breakdown,
        "operational_weights":    C.OPERATIONAL_HARD_WEIGHTS,
        "conf_pair_errors": {f"{a}->{b}": d for (a,b),d in pair_err.items()},
        "grammar_invalid":  invalid_grammar,
        "grammar_valid":    len(grammar_valid_flags) - invalid_grammar,
        "n_errors":     n_err,
        "conf_hist":    hist,
        "elapsed_s":    round(elapsed, 1),
        "errors_csv":   str(err_csv),
        "errors_dir":   str(err_imgs_dir),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    # ----- 출력 -----
    print(f"\n=== hard_final 평가 (processed={n_processed}/{n_total}, "
          f"skipped={n_skipped}, {elapsed:.1f}s) =====")
    print(f"  overall  greedy:        {overall_greedy:.4f}")
    print(f"  overall  beam:          {overall_beam:.4f}")
    print(f"  overall  grammar:       {overall_grammar:.4f}")
    no_small_str = f"{overall_no_small:.4f}" if overall_no_small is not None else "n/a"
    op_str       = f"{op_score:.4f}"         if op_score is not None         else "n/a"
    print(f"  hard_no_small (n={n_no_small}): {no_small_str}")
    print(f"  operational_hard:       {op_str}    ⭐ 주 판단 지표")
    rs = f"{rare_acc:.4f}" if rare_acc is not None else "n/a"
    cs = f"{conf_acc:.4f}" if conf_acc is not None else "n/a"
    print(f"  rare:        {rs}")
    print(f"  confusable:  {cs}")
    print(f"  ECE:         {ece_val:.4f}")
    print(f"  grammar invalid count: {invalid_grammar} / {len(grammar_valid_flags)}")
    print(f"\n[categories]  (small_plate 는 보조 stress)")
    for k, v in cat_acc.items():
        a = f"{v['acc']:.4f}" if v["acc"] is not None else "n/a"
        flag = "  (보조)" if k == "small_plate" else ""
        print(f"  {k:>11s}: {a}  (n={v['n']}){flag}")
    print(f"\n[operational breakdown]")
    for c, d in op_breakdown.items():
        contrib = f"{d['contribution']:.4f}" if d.get('contribution') is not None else "n/a"
        acc = f"{d['acc']:.4f}" if d.get('acc') is not None else "n/a"
        print(f"  {c:>11s}: acc={acc}  ×w={d['weight']:.2f} = {contrib}")
    print(f"\n[confusable pair errors]")
    for (a, b), d in pair_err.items():
        print(f"  {a}>{b}={d['a_to_b']:>3}  {b}>{a}={d['b_to_a']:>3}  "
              f"(pair samples={d['total_pair_samples']})")
    # confusable pair 별 오인 카운트 CSV 저장 (per-seed 누적용)
    pair_csv_root = C.REPORT_DIR_V6 if v6 else C.REPORTS_DIR
    pair_csv = pair_csv_root / "confusable_pair_errors.csv"
    pair_csv_exists = pair_csv.exists()
    with open(pair_csv, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not pair_csv_exists:
            w.writerow(["seed", "ckpt", "split", "a", "b",
                        "a_to_b", "b_to_a", "pair_samples"])
        for (a, b), d in pair_err.items():
            w.writerow([seed, str(ckpt), "hard_final", a, b,
                        d["a_to_b"], d["b_to_a"], d["total_pair_samples"]])
    print(f"[confusable] pair-error CSV → {pair_csv}")
    print(f"\n[errors] {n_err}장 → {err_csv}")
    print(f"[errors] images → {err_imgs_dir}")
    print(f"[saved] {output}")

    # 결정 기준 — operational_hard_score 주, hard_no_small / overall 부
    primary = op_score if op_score is not None else overall_greedy
    print("\n=== 결정 기준 (주: operational_hard_score) ===")
    if primary >= 0.987:
        verdict = "≥ 98.7% — **3-seed 진행 OK**"
    elif primary >= 0.980:
        verdict = "98.0~98.7% — **3-seed 진행 + 오답 분석 병행**"
    else:
        verdict = "< 98.0% — **튜닝 우선**"
    print(f"  operational_hard_score = {primary*100:.2f}% → {verdict}")
    print(f"  (참고) hard_final greedy   = {overall_greedy*100:.2f}%")
    print(f"  (참고) hard_no_small       = {(overall_no_small or 0)*100:.2f}%  (n={n_no_small})")
    print(f"  (보조) small_plate         = {(cat_acc.get('small_plate',{}).get('acc') or 0)*100:.2f}%")

    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed",   type=int, default=42)
    ap.add_argument("--ckpt",   type=str, default=None)
    ap.add_argument("--output", type=str, default=None)
    ap.add_argument("--v6", action="store_true",
                    help="v6 평가 — logs_v6/seed42 + reports_v6/seed42 사용")
    args = ap.parse_args()
    main(seed=args.seed,
         ckpt=Path(args.ckpt) if args.ckpt else None,
         output=Path(args.output) if args.output else None,
         v6=args.v6)
