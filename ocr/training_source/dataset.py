"""
Phase 1 #4 — Group-aware Train/Val Split + Split Freeze
- 동일 plate label 단위 그룹화 (data leakage 방지)
- hard_dev / hard_final 의 path 는 train pool 에서 완전 제외
- 일반 val (5%) 는 라벨 그룹 기반 분리
- splits/train_indices.json + split_summary.json 저장
- LPDataset: source 정보 (real/ohjj/yakhyo) 보존 → augmentation 에서 source 별 prob 적용
"""
import sys, json, csv, random
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from . import config as C
from .vocab import load_vocab


def imread_unicode(path):
    try:
        a = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (FileNotFoundError, OSError):
        return None
    return a


# ---------- 수집 ----------
def collect_real():
    out = []
    for d in C.REAL_DIRS:
        if not d.exists(): continue
        for f in d.glob("*.jpg"):
            lab = C.label_from_stem(f.stem)
            if lab:
                out.append((str(f), lab, "real"))
    return out


def collect_synth():
    out = []
    if not C.SYNTH_MANIFEST.exists(): return out
    with open(C.SYNTH_MANIFEST, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if r["accepted"] == "1":
                out.append((r["path"], r["label"], r["source"]))   # ohjj/yakhyo
    return out


# ---------- split ----------
def build_splits(seed=42, val_ratio=0.05):
    real = collect_real()

    excluded_paths = set()
    excluded_labels = set()
    for p in (C.HARD_DEV_IDX, C.HARD_FINAL_IDX):
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for it in json.load(f).get("items", []):
                    excluded_paths.add(it["path"])
                    excluded_labels.add(it["label"])

    # path 또는 label 어느 하나라도 hard 와 겹치면 train/val pool 에서 제외
    pool = [r for r in real
            if r[0] not in excluded_paths and r[1] not in excluded_labels]
    excluded_label_count = sum(1 for r in real if r[1] in excluded_labels)
    print(f"[splits] real={len(real):,}  "
          f"hard path 제외={len(excluded_paths):,}  "
          f"hard label 제외={excluded_label_count:,}  "
          f"pool={len(pool):,}")

    # group by label
    groups = defaultdict(list)
    for it in pool:
        groups[it[1]].append(it)
    rng = random.Random(seed)
    keys = list(groups.keys())
    rng.shuffle(keys)
    n_val_groups = max(1, int(len(keys) * val_ratio))
    val_keys = set(keys[:n_val_groups])
    train_keys = set(keys[n_val_groups:])

    train_items = [it for k in train_keys for it in groups[k]]
    val_items   = [it for k in val_keys   for it in groups[k]]
    rng.shuffle(train_items); rng.shuffle(val_items)

    payload = {
        "seed": seed,
        "n_real": len(real),
        "n_hard_excluded_paths": len(excluded_paths),
        "n_hard_excluded_labels": len(excluded_labels),
        "n_train": len(train_items),
        "n_val": len(val_items),
        "n_train_groups": len(train_keys),
        "n_val_groups": len(val_keys),
        "train": train_items,
        "val": val_items,
    }
    with open(C.TRAIN_INDICES, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # summary (가벼운 메타만)
    summary = {
        "seed": seed,
        "real_total": len(real),
        "hard_excluded_paths":  len(excluded_paths),
        "hard_excluded_labels": len(excluded_labels),
        "train": len(train_items), "train_groups": len(train_keys),
        "val":   len(val_items),   "val_groups":   len(val_keys),
        "synth_pool":  len(collect_synth()),
        "real_dirs": [str(d) for d in C.REAL_DIRS],
        "synth_manifest": str(C.SYNTH_MANIFEST),
    }
    with open(C.SPLIT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[splits] train={len(train_items):,} ({len(train_keys):,}그룹)  "
          f"val={len(val_items):,} ({len(val_keys):,}그룹)")
    print(f"[splits] saved → {C.TRAIN_INDICES}  /  {C.SPLIT_SUMMARY}")
    return payload


# ---------- Dataset ----------
def encode_label(label, char2idx):
    return [char2idx[c] for c in label if c in char2idx]


class LPDataset(Dataset):
    """
    real_samples + synth_samples 를 epoch ratio 로 동적 mixing.
    augment(img_bgr, source, epoch) → img_bgr.
    synth_ratio_fn: epoch -> ratio (default C.synth_ratio).
                     v6 에서는 C.synth_ratio_v6 (max 15%) 전달.
    """
    def __init__(self, real_samples, synth_samples, char2idx,
                 augment=None, train=True, deterministic_seed=None,
                 synth_ratio_fn=None):
        self.real = real_samples
        self.synth = synth_samples
        self.char2idx = char2idx
        self.augment = augment
        self.train = train
        self.epoch = 1
        self.det_seed = deterministic_seed
        self.synth_ratio_fn = synth_ratio_fn or C.synth_ratio
        self._refresh_indices()

    def set_epoch(self, ep):
        self.epoch = ep
        self._refresh_indices()

    def _refresh_indices(self):
        """
        Synth oversampling with replacement 허용 (target ratio 충족).
        Batch 안에서는 동일 synth 인덱스 중복 금지 (greedy swap).
        Epoch 전체로는 중복 허용.
        """
        if not self.train or not self.synth:
            self._pool = [("real", i) for i in range(len(self.real))]
            return
        n_real = len(self.real)
        r = max(0.0, min(0.95, self.synth_ratio_fn(self.epoch)))
        n_synth = int(round(n_real * r / max(1e-6, 1 - r)))

        idx_ohjj   = [i for i, s in enumerate(self.synth) if s[2] == "ohjj"]
        idx_yakhyo = [i for i, s in enumerate(self.synth) if s[2] == "yakhyo"]
        rng = random.Random(self.epoch * 7919 + (self.det_seed or 0))

        n_o = int(round(n_synth * C.SYNTH_OHJJ_RATIO))
        n_y = n_synth - n_o
        # with replacement
        synth_o = rng.choices(idx_ohjj,   k=n_o) if idx_ohjj   and n_o > 0 else []
        synth_y = rng.choices(idx_yakhyo, k=n_y) if idx_yakhyo and n_y > 0 else []

        pool = (
            [("real",  i) for i in range(n_real)]
            + [("synth", i) for i in synth_o + synth_y]
        )
        rng.shuffle(pool)

        # batch-level dedup: BATCH_SIZE 윈도우 안에 같은 ('synth', i) 가 두 번 안 나오게
        BS = max(1, C.BATCH_SIZE)
        seen = set()
        for k in range(len(pool)):
            if k % BS == 0:
                seen = set()
            item = pool[k]
            if item[0] == "synth" and item in seen:
                # 다음 슬롯 중 batch 충돌 없는 것과 swap
                for j in range(k + 1, len(pool)):
                    cand = pool[j]
                    if cand[0] != "synth" or cand not in seen:
                        pool[k], pool[j] = pool[j], pool[k]
                        item = pool[k]
                        break
            seen.add(item)
        self._pool = pool

    def __len__(self): return len(self._pool)

    def __getitem__(self, idx):
        kind, j = self._pool[idx]
        path, label, src = (self.real[j] if kind == "real" else self.synth[j])
        img = imread_unicode(path)
        if img is None:
            img = np.zeros((C.IMG_H, C.IMG_W, 3), np.uint8)

        if self.augment is not None and self.train:
            img = self.augment(img, src, self.epoch)

        img = cv2.resize(img, (C.IMG_W, C.IMG_H), interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        img = img.transpose(2, 0, 1)
        target = encode_label(label, self.char2idx)
        return (torch.from_numpy(img),
                torch.tensor(target, dtype=torch.long),
                len(target),
                label, src)


def collate_fn(batch):
    imgs, tgts, lens, labels, srcs = zip(*batch)
    return (torch.stack(imgs, 0),
            torch.cat(tgts, 0),
            torch.tensor(lens, dtype=torch.long),
            list(labels), list(srcs))


def load_train_indices():
    with open(C.TRAIN_INDICES, encoding="utf-8") as f: return json.load(f)


# ---------- v6 loader (manifest_v6.csv 기반) ----------
def load_v6_samples():
    """
    manifest_v6.csv 를 split 컬럼 기준으로 분리.
      train_real: split == 'train'
      val_real:   split == 'val'
      synth:      split == 'train_synth'
    Returns:
      (real_train, real_val, synth_pool)
      각 list[(path, label, source)]
    """
    if not C.MANIFEST_V6.exists():
        raise FileNotFoundError(f"manifest_v6 없음 → 먼저 build_manifest_v6 실행: "
                                f"{C.MANIFEST_V6}")
    real_train, real_val, synth_pool = [], [], []
    with open(C.MANIFEST_V6, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            tup = (r["path"], r["label"], r["source"])
            sp = r["split"]
            if sp == "train":         real_train.append(tup)
            elif sp == "val":         real_val.append(tup)
            elif sp == "train_synth": synth_pool.append(tup)
    return real_train, real_val, synth_pool


def verify_v6_no_leakage():
    """
    v6 train/val/hard_dev/hard_final 사이 path / label 누설 0 확인.
    Returns dict of overlap counts. 모두 0 이어야 정상.
    """
    real_train, real_val, synth_pool = load_v6_samples()

    train_paths  = {p for p, _, _ in real_train}
    val_paths    = {p for p, _, _ in real_val}
    train_labels = {l for _, l, _ in real_train}
    val_labels   = {l for _, l, _ in real_val}

    hard_paths, hard_labels = set(), set()
    hard_dev_paths, hard_final_paths = set(), set()
    for jp, dst_p in ((C.HARD_DEV_IDX, hard_dev_paths),
                       (C.HARD_FINAL_IDX, hard_final_paths)):
        if jp.exists():
            with open(jp, encoding="utf-8") as f:
                for it in json.load(f).get("items", []):
                    hard_paths.add(it["path"])
                    hard_labels.add(it["label"])
                    dst_p.add(it["path"])

    overlaps = {
        "train_x_val_path":          len(train_paths & val_paths),
        "train_x_val_label":         len(train_labels & val_labels),
        "train_x_hard_path":         len(train_paths & hard_paths),
        "train_x_hard_label":        len(train_labels & hard_labels),
        "val_x_hard_path":           len(val_paths & hard_paths),
        "val_x_hard_label":          len(val_labels & hard_labels),
        "hard_dev_x_hard_final_path":len(hard_dev_paths & hard_final_paths),
    }
    return overlaps, {
        "train_real": len(real_train), "val_real": len(real_val),
        "synth": len(synth_pool),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest_v6", action="store_true",
                    help="manifest_v6 검증 (leakage + 통계)")
    args = ap.parse_args()
    if args.manifest_v6:
        ov, cnt = verify_v6_no_leakage()
        print("\n=== v6 leakage check ===")
        print(f"  train_real={cnt['train_real']:,}  "
              f"val_real={cnt['val_real']:,}  "
              f"synth={cnt['synth']:,}")
        any_leak = False
        for k, v in ov.items():
            flag = "OK" if v == 0 else "LEAK"
            if v: any_leak = True
            print(f"  {k:<30s}: {v}  [{flag}]")
        if any_leak:
            print("\n[FAIL] 누설 있음 — 학습 시작 금지"); sys.exit(2)
        print("\n[PASS] 모든 path/label 누설 0")
    else:
        build_splits()
