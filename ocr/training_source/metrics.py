"""
Phase 3 #1 — Metrics
- overall accuracy
- hard accuracy (전체)
- rare hangul accuracy
- ECE (M=15 bins)
- confidence histogram (M=20 bins)
- 카테고리별 hard accuracy (small_plate / motion_blur / night / crop_cut / skew / rare)
  → hard items 의 categories (multi-tag) 기준
"""
from typing import List, Optional

import numpy as np


# ---------- 단순 acc ----------
def seq_accuracy(preds: List[str], gts: List[str]) -> float:
    if not preds: return 0.0
    return sum(p == g for p, g in zip(preds, gts)) / len(preds)


def rare_accuracy(preds, gts, rare_set) -> Optional[float]:
    sub = [(p, g) for p, g in zip(preds, gts) if any(c in rare_set for c in g)]
    if not sub: return None
    return sum(p == g for p, g in sub) / len(sub)


def confusable_accuracy(preds, gts, confusable_set) -> Optional[float]:
    """라벨이 confusable 한글 1자 이상 포함 시 정답율"""
    sub = [(p, g) for p, g in zip(preds, gts) if any(c in confusable_set for c in g)]
    if not sub: return None
    return sum(p == g for p, g in sub) / len(sub)


def confusable_pair_errors(preds, gts, confusable_pairs):
    """
    pair 별로 (a→b 오인, b→a 오인) 카운트.
    confusable_pairs: list[(a, b)]
    return: {(a,b): {'a_to_b': int, 'b_to_a': int, 'total_pair_samples': int}}
    """
    out = {}
    for a, b in confusable_pairs:
        ab = ba = total = 0
        for p, g in zip(preds, gts):
            for i, ch in enumerate(g):
                if ch in (a, b):
                    total += 1
                    if i < len(p):
                        if g[i] == a and p[i] == b: ab += 1
                        elif g[i] == b and p[i] == a: ba += 1
        out[(a, b)] = {"a_to_b": ab, "b_to_a": ba, "total_pair_samples": total}
    return out


# ---------- 카테고리별 hard ----------
def category_accuracy(preds, gts, hard_items, category):
    """
    hard_items: hard_dev_indices.json["items"] 동일 길이의 리스트
                  (path, label, categories=[...]) 순서가 preds/gts 와 동일해야 함.
    category 가 categories 에 들어있는 항목만 부분집합.
    """
    sub = [(p, g) for (p, g, it) in zip(preds, gts, hard_items)
           if category in it.get("categories", [])]
    if not sub: return None, 0
    return sum(p == g for p, g in sub) / len(sub), len(sub)


def all_category_accuracies(preds, gts, hard_items,
                            cats=("small_plate", "motion_blur", "night",
                                  "crop_cut", "skew", "rare")):
    out = {}
    for c in cats:
        acc, n = category_accuracy(preds, gts, hard_items, c)
        out[c] = {"acc": acc, "n": n}
    return out


def hard_without_tag(preds, gts, hard_items, exclude_tag="small_plate"):
    """exclude_tag 가 categories 에 포함된 샘플은 평가에서 제외 → (acc, n)"""
    sub_p, sub_g = [], []
    for p, g, it in zip(preds, gts, hard_items):
        if exclude_tag in it.get("categories", []): continue
        sub_p.append(p); sub_g.append(g)
    if not sub_p: return None, 0
    return sum(p == g for p, g in zip(sub_p, sub_g)) / len(sub_p), len(sub_p)


def operational_hard_score(cat_acc, weights):
    """
    가중평균 — cat_acc[c]['acc'] 가 None 이면 그 가중치 포기하고 재정규화.
    cat_acc: {cat: {'acc':..., 'n':...}}
    weights: {cat: float}
    return: (score or None, weighted_breakdown_dict)
    """
    total_w = 0.0
    total = 0.0
    breakdown = {}
    for c, w in weights.items():
        a = cat_acc.get(c, {}).get("acc")
        if a is None:
            breakdown[c] = {"acc": None, "weight": w, "contribution": None}
            continue
        total += w * a
        total_w += w
        breakdown[c] = {"acc": a, "weight": w, "contribution": w * a}
    score = (total / total_w) if total_w > 0 else None
    return score, breakdown


# ---------- confidence + ECE ----------
def confidence_per_sample(log_probs):
    """log_probs (T,B,V) → (B,) per-sample mean of max-prob across T"""
    p = log_probs.exp()
    max_p, _ = p.max(dim=-1)              # (T, B)
    return max_p.mean(dim=0).detach().cpu().numpy()


def ece(confidences, correctness, n_bins=15):
    confidences = np.asarray(confidences, dtype=np.float64)
    correctness = np.asarray(correctness, dtype=np.float64)
    if len(confidences) == 0: return 0.0
    edges = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.clip(np.digitize(confidences, edges) - 1, 0, n_bins - 1)
    e = 0.0
    for b in range(n_bins):
        mask = bin_idx == b
        if mask.sum() == 0: continue
        e += mask.mean() * abs(confidences[mask].mean() - correctness[mask].mean())
    return float(e)


def confidence_histogram(confidences, n_bins=20):
    h, _ = np.histogram(confidences, bins=n_bins, range=(0.0, 1.0))
    return h.tolist()


# ---------- composite ----------
def composite_score(overall, hard, rare, w_h=0.5, w_r=0.3, w_o=0.2):
    """rare=None 이면 정규화"""
    if rare is None:
        denom = w_h + w_o
        return (w_h * hard + w_o * overall) / denom
    return w_h * hard + w_r * rare + w_o * overall
