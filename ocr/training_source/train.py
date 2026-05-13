"""
Phase 3 #3 — Train Loop (v5.final 고속도로)
- AMP + grad clip 5.0
- EMA epoch 10 이후
- 매 epoch 끝에 val + hard_dev 평가 (hard_final 절대 미사용)
- composite + ECE penalty 기준 best 선택
- early stopping patience 10
- log: logs_v5/train_seed{seed}.csv (per-epoch) + train_seed{seed}_metrics.json (전체)
- 옵션: --debug (1 epoch), --epochs N (제한 학습)

사전 조건 (artifacts 모두 freeze):
  artifacts/vocab.json, rare_chars.json,
  artifacts/splits/{train_indices, hard_dev_indices, hard_final_indices}.json
"""
import argparse, csv, json, random, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from . import config as C
from .vocab import load_vocab, load_rare, load_confusable
from .dataset import (LPDataset, load_train_indices, collate_fn,
                       imread_unicode, load_v6_samples)
from .augmentation import make_augment
from .model import V5OCR, count_params
from .loss import FocalCTC, make_sample_weights, ctc_decode
from .optimizer_ema import make_optimizer, make_scheduler, make_scaler, ModelEMA
from .metrics import (seq_accuracy, rare_accuracy, confidence_per_sample,
                      ece, confidence_histogram, composite_score,
                      all_category_accuracies,
                      confusable_accuracy, confusable_pair_errors)
from .checkpoint import CheckpointSelector


def set_seed(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True


# ---------- 평가 helper ----------
@torch.no_grad()
def eval_loader(model, loader, idx2char, rare_set, conf_set, conf_pairs,
                device, amp_on):
    model.eval()
    preds, gts, conf_v, corr = [], [], [], []
    for imgs, tgts, lens, labels, _srcs in loader:
        imgs = imgs.to(device, non_blocking=True)
        with torch.amp.autocast("cuda", enabled=amp_on and device.type == "cuda"):
            logits = model(imgs)
            log_probs = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
        p = ctc_decode(log_probs, idx2char)
        preds.extend(p); gts.extend(labels)
        conf_v.extend(confidence_per_sample(log_probs).tolist())
        corr.extend([1 if pp == gg else 0 for pp, gg in zip(p, labels)])
    return {
        "overall":      seq_accuracy(preds, gts),
        "rare":         rare_accuracy(preds, gts, rare_set),
        "confusable":   confusable_accuracy(preds, gts, conf_set),
        "conf_pairs":   confusable_pair_errors(preds, gts, conf_pairs),
        "ece":          ece(conf_v, corr, n_bins=15),
        "hist":         confidence_histogram(conf_v),
        "n":            len(preds),
    }


@torch.no_grad()
def eval_hard(model, hard_items, idx2char, rare_set, device, amp_on, batch=64):
    """hard_dev_indices.json items 직접 로드 평가 + 카테고리 별 정확도"""
    if not hard_items:
        return {"overall": 0.0, "rare": None, "ece": 0.0, "n": 0,
                "categories": {}}
    model.eval()
    arr_imgs = []; gts = []
    for it in hard_items:
        img = imread_unicode(it["path"])
        if img is None: continue
        import cv2
        img = cv2.resize(img, (C.IMG_W, C.IMG_H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        arr_imgs.append(img.transpose(2, 0, 1))
        gts.append(it["label"])
    if not arr_imgs:
        return {"overall": 0.0, "rare": None, "ece": 0.0, "n": 0, "categories": {}}

    preds, conf, corr = [], [], []
    for i in range(0, len(arr_imgs), batch):
        x = torch.from_numpy(np.stack(arr_imgs[i:i + batch])).to(device)
        with torch.amp.autocast("cuda", enabled=amp_on and device.type == "cuda"):
            logits = model(x)
            log_probs = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
        p = ctc_decode(log_probs, idx2char)
        preds.extend(p)
        conf.extend(confidence_per_sample(log_probs).tolist())
        corr.extend([1 if pp == gg else 0 for pp, gg in zip(p, gts[i:i + batch])])
    cats = all_category_accuracies(preds, gts, hard_items)
    return {
        "overall":    seq_accuracy(preds, gts),
        "rare":       rare_accuracy(preds, gts, rare_set),
        "ece":        ece(conf, corr, 15),
        "n":          len(preds),
        "categories": cats,
    }


# ---------- 메인 ----------
def main(seed=42, debug=False, max_epochs=None, v6=False):
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[init] device={device}  seed={seed}  debug={debug}  v6={v6}")

    # 사전 조건
    if v6:
        required = (C.VOCAB_PATH, C.RARE_PATH, C.MANIFEST_V6, C.HARD_DEV_IDX)
    else:
        required = (C.VOCAB_PATH, C.RARE_PATH, C.TRAIN_INDICES, C.HARD_DEV_IDX)
    for p in required:
        if not p.exists():
            raise FileNotFoundError(f"필수 산출물 없음: {p}.")

    chars, char2idx, idx2char, num_classes = load_vocab()
    rare_set = set(load_rare())
    conf_chars, conf_pairs = load_confusable()
    conf_set = set(conf_chars)
    with open(C.HARD_DEV_IDX, encoding="utf-8") as f:
        hard_dev = json.load(f)["items"]

    if v6:
        real_train, real_val, synth = load_v6_samples()
        print(f"[data v6] train={len(real_train):,} val={len(real_val):,} "
              f"synth={len(synth):,} hard_dev={len(hard_dev)} "
              f"rare={len(rare_set)}({''.join(sorted(rare_set))}) "
              f"num_classes={num_classes}")
    else:
        splits = load_train_indices()
        real_train = [(p, lab, src) for p, lab, src in splits["train"]]
        real_val   = [(p, lab, src) for p, lab, src in splits["val"]]
        from .dataset import collect_synth
        synth = collect_synth()
        print(f"[data] train={splits['n_train']:,} val={splits['n_val']:,} "
              f"hard_dev={len(hard_dev)} rare={len(rare_set)}({''.join(sorted(rare_set))}) "
              f"confusable={len(conf_set)}({''.join(sorted(conf_set))}) "
              f"num_classes={num_classes}")
    print(f"[synth] pool={len(synth):,} (with-replacement oversampling)")

    aug = make_augment(deterministic_seed=seed if debug else None)
    synth_fn = C.synth_ratio_v6 if v6 else C.synth_ratio
    train_ds = LPDataset(real_train, synth, char2idx, augment=aug,
                         train=True, deterministic_seed=seed,
                         synth_ratio_fn=synth_fn)
    val_ds   = LPDataset(real_val,   [],     char2idx, augment=None, train=False)

    train_dl = DataLoader(train_ds, batch_size=C.BATCH_SIZE, shuffle=False,
                          num_workers=C.NUM_WORKERS, collate_fn=collate_fn,
                          pin_memory=True, drop_last=True)
    val_dl   = DataLoader(val_ds, batch_size=C.BATCH_SIZE, shuffle=False,
                          num_workers=C.NUM_WORKERS, collate_fn=collate_fn,
                          pin_memory=True)

    model = V5OCR(num_classes=num_classes).to(device)
    print(f"[model] params={count_params(model):,}")

    optim = make_optimizer(model)
    sched = make_scheduler(optim, C.MAX_EPOCHS, C.WARMUP_EPOCHS)
    scaler = make_scaler(device)
    crit = FocalCTC(gamma=C.FOCAL_GAMMA, blank=0,
                    label_smooth=C.LABEL_SMOOTH).to(device)
    ema = None
    paths = C.seed_paths_v6(seed) if v6 else C.seed_paths(seed)
    selector = CheckpointSelector(paths["ckpt_dir"])
    print(f"[paths] ckpt={paths['ckpt_dir']}  log={paths['log_dir']}")

    log_csv  = paths["train_csv"]
    log_json = paths["metrics_json"]
    csv_f = open(log_csv, "w", encoding="utf-8", newline="")
    csv_w = csv.writer(csv_f)
    csv_w.writerow([
        "epoch","loss","lr","val_overall","val_rare","val_confusable","val_ece",
        "hard_overall","hard_rare","hard_ece",
        "h_small","h_blur","h_night","h_crop","h_skew","h_rare",
        "comp","comp_adj","is_best","forbid","gap","elapsed_s",
    ])
    metrics_log = []

    best_ema_acc = 0.0
    no_improve = 0
    epochs = max_epochs or C.MAX_EPOCHS
    if debug: epochs = 1

    for ep in range(1, epochs + 1):
        train_ds.set_epoch(ep)
        model.train()
        t0 = time.time()
        losses = []
        for imgs, tgts, lens, labels, _srcs in train_dl:
            imgs = imgs.to(device, non_blocking=True)
            tgts = tgts.to(device); lens = lens.to(device)
            sw = make_sample_weights(labels, rare_set).to(device)

            with torch.amp.autocast("cuda", enabled=C.AMP_ENABLED and device.type == "cuda"):
                logits = model(imgs)
                log_probs = F.log_softmax(logits.permute(1, 0, 2), dim=-1)
                T = log_probs.shape[0]
                input_lengths = torch.full((imgs.size(0),), T, dtype=torch.long, device=device)
                loss = crit(log_probs, tgts, input_lengths, lens, sample_weight=sw)

            optim.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optim)
            torch.nn.utils.clip_grad_norm_(model.parameters(), C.GRAD_CLIP)
            scaler.step(optim); scaler.update()
            losses.append(float(loss.item()))

        sched.step()

        # EMA
        if ep >= C.EMA_START_EP:
            if ema is None: ema = ModelEMA(model)
            ema.update(model)

        eval_model = ema.module if ema is not None else model
        v = eval_loader(eval_model, val_dl, idx2char, rare_set, conf_set, conf_pairs,
                        device, C.AMP_ENABLED)
        h = eval_hard  (eval_model, hard_dev, idx2char, rare_set, device, C.AMP_ENABLED)

        loss_mean = float(np.mean(losses)) if losses else float("nan")
        gap = max(0.0, (1.0 - min(1.0, loss_mean)) - v["overall"])    # 임시 proxy
        comp = composite_score(v["overall"], h["overall"], v["rare"],
                               C.W_HARD, C.W_RARE, C.W_OVERALL)
        scores = {
            "overall":         v["overall"],
            "hard":            h["overall"],
            "rare":            v["rare"],
            "confusable":      v["confusable"],
            "conf_pair_errors": {f"{a}->{b}": d for (a,b),d in v["conf_pairs"].items()},
            "ece":             v["ece"],
            "comp":            comp,
            "gap":             gap,
            "hard_categories": h["categories"],
            "hard_ece":        h["ece"],
            "val_hist":        v["hist"],
        }
        if selector.baseline_ece is None and ema is not None:
            selector.baseline(v["ece"])
        is_best, comp_adj, forbid = selector.update(
            ep, scores,
            model_state=model.state_dict(),
            ema_state=(ema.state_dict() if ema is not None else None),
        )

        if v["overall"] > best_ema_acc:
            best_ema_acc = v["overall"]; no_improve = 0
        else:
            no_improve += 1

        elapsed = time.time() - t0
        rstr = f"{v['rare']:.4f}" if v["rare"] is not None else "n/a"
        cstr = f"{v['confusable']:.4f}" if v["confusable"] is not None else "n/a"
        cat = h["categories"]
        def cv(k): return f"{cat[k]['acc']:.3f}" if cat.get(k, {}).get("acc") is not None else "n/a"
        # confusable pair top errors (정렬 후 상위 3쌍)
        pair_str = " ".join(
            f"{a}>{b}={d['a_to_b']}/{b}>{a}={d['b_to_a']}"
            for (a,b),d in sorted(v["conf_pairs"].items(),
                                   key=lambda x: -(x[1]["a_to_b"]+x[1]["b_to_a"]))[:3]
        )
        print(
            f"[ep {ep:3d}] loss={loss_mean:.4f} lr={optim.param_groups[0]['lr']:.5f}  "
            f"val={v['overall']:.4f}  hard={h['overall']:.4f}  rare={rstr}  conf={cstr}  "
            f"ece={v['ece']:.4f}  comp={comp:.4f}{' (BEST)' if is_best else ''}"
            f"{' (FORBID)' if forbid else ''}  "
            f"S={cv('small_plate')} B={cv('motion_blur')} N={cv('night')} "
            f"C={cv('crop_cut')} K={cv('skew')} R={cv('rare')}  "
            f"pair[{pair_str}]  {elapsed:.0f}s",
            flush=True,
        )
        csv_w.writerow([
            ep, loss_mean, optim.param_groups[0]['lr'],
            v["overall"], v["rare"], v["confusable"], v["ece"],
            h["overall"], h["rare"], h["ece"],
            cat.get("small_plate", {}).get("acc"),
            cat.get("motion_blur", {}).get("acc"),
            cat.get("night", {}).get("acc"),
            cat.get("crop_cut", {}).get("acc"),
            cat.get("skew", {}).get("acc"),
            cat.get("rare", {}).get("acc"),
            comp, comp_adj, int(is_best), int(forbid), gap, elapsed,
        ])
        csv_f.flush()
        metrics_log.append({"epoch": ep, **scores, "loss": loss_mean,
                            "lr": optim.param_groups[0]['lr'],
                            "elapsed_s": elapsed,
                            "is_best": is_best, "forbid": forbid})
        with open(log_json, "w", encoding="utf-8") as f:
            json.dump(metrics_log, f, ensure_ascii=False, indent=2)

        if no_improve >= C.PATIENCE and not debug:
            print(f"[early-stop] no_improve={no_improve} >= patience={C.PATIENCE}")
            break

    csv_f.close()
    print(f"\n[done] best comp={selector.best:.4f} → {selector.best_path}")
    print(f"[done] log csv → {log_csv}")
    print(f"[done] log json → {log_json}")
    return selector.best, selector.best_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--v6", action="store_true",
                    help="v6 fresh real training (manifest_v6.csv 기반, "
                         "checkpoints_v6/logs_v6 사용)")
    args = ap.parse_args()
    main(seed=args.seed, debug=args.debug, max_epochs=args.epochs, v6=args.v6)
