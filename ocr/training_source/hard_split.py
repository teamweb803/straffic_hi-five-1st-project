"""
Phase 1 #3 — Hard Validation 자동 분리 (250 dev + 250 final)
조건 (OR):
  기본:
    - plate height ≤ HARD_PLATE_H_MAX (40)
    - Laplacian variance < HARD_LAPLACIAN_MAX (100)
    - skew angle > HARD_SKEW_MIN_DEG (15°)
    - rare hangul 포함
    - visible char ratio < HARD_VISIBLE_MAX (0.85)
  고속도로 추가:
    - plate height ≤ HW_PLATE_H_MAX (32) → "small_plate"
    - horizontal motion blur (kernel-1D 응답)  → "motion_blur"
    - low contrast (std luma < threshold)        → "night"
    - crop margin 부족 (글자 영역이 가장자리)    → "crop_cut"
    - JPEG block artifact (heuristic)
카테고리 분류 (각 250장):
  small_plate 25%  motion_blur 25%  night 20%  crop_cut 15%  skew 10%  rare 5%
group leakage 방지: 같은 plate label 은 dev/final 합쳐 1개만 사용.
출력:
  artifacts/splits/hard_dev_indices.json
  artifacts/splits/hard_final_indices.json
"""
import sys, json, math, random
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from . import config as C
from .vocab import load_rare


# ---------- 메트릭 ----------
def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def laplacian_var(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def skew_angle_deg(gray):
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(bw > 0))
    if coords.shape[0] < 50: return 0.0
    rect = cv2.minAreaRect(coords[:, ::-1])
    angle = rect[-1]
    if angle < -45: angle = 90 + angle
    return float(abs(angle))


def visible_ratio(gray):
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return float(bw.mean() / 255.0)


def horizontal_motion_score(gray):
    """horizontal sobel response — 수평 motion blur 면 vertical edge 가 흐려져서 |Sx| 가 작음"""
    sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    sx_m = float(np.abs(sx).mean())
    sy_m = float(np.abs(sy).mean())
    if sy_m < 1e-3: return 0.0
    return sx_m / sy_m       # 작을수록 horizontal blur 의심 (보통 0.6 미만이면 강한 수평 blur)


def luma_std(bgr):
    luma = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(luma.std())


def crop_edge_cut(gray):
    """
    가장자리 1px 변 의 fg(글자) 비율이 HW_CROP_EDGE_RATIO 이상인 변 개수 ≥ HW_CROP_MIN_SIDES
    → 실제 글자 영역이 잘려나간 가능성. 단순 근접만으로는 hit 안 됨.
    """
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = bw.shape
    if h < 4 or w < 4: return False
    fracs = [
        float(bw[:, 0].sum()  / (255.0 * h)),    # left
        float(bw[:, -1].sum() / (255.0 * h)),    # right
        float(bw[0, :].sum()  / (255.0 * w)),    # top
        float(bw[-1, :].sum() / (255.0 * w)),    # bot
    ]
    hits = sum(1 for f in fracs if f >= C.HW_CROP_EDGE_RATIO)
    return hits >= C.HW_CROP_MIN_SIDES


def evaluate(path):
    img = imread_unicode(path)
    if img is None: return None
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "h": h, "w": w,
        "lap":     laplacian_var(gray),
        "skew":    skew_angle_deg(gray),
        "vis":     visible_ratio(gray),
        "hmotion": horizontal_motion_score(gray),
        "luma":    luma_std(img),
        "edge_cut": crop_edge_cut(gray),
    }


# ---------- 카테고리 ----------
CATEGORY_PRIORITY = ("small_plate", "motion_blur", "night",
                     "skew", "rare", "crop_cut")


def classify(metrics, label, rare_set):
    """
    카테고리 모두 평가하여 (primary, all_tags) 반환. 매치 없으면 (None, []).
    primary 는 CATEGORY_PRIORITY 순서로 가장 먼저 매치된 것 (crop_cut 은 마지막).
    """
    if metrics is None: return None, []
    tags = []
    if metrics["h"] <= C.HARD_PLATE_H_MAX:                  tags.append("small_plate")
    if metrics["hmotion"] < 0.6 and metrics["lap"] < 200:   tags.append("motion_blur")
    if metrics["luma"]    < C.HW_LOW_CONTRAST_MAX:          tags.append("night")
    if metrics["skew"]    > C.HARD_SKEW_MIN_DEG:            tags.append("skew")
    if any(c in rare_set for c in label):                   tags.append("rare")
    if metrics.get("edge_cut", False):                      tags.append("crop_cut")
    if not tags: return None, []
    primary = next((k for k in CATEGORY_PRIORITY if k in tags), tags[0])
    return primary, tags


# ---------- 분리 ----------
def quota_per_set(total, dist):
    """dist: {cat: ratio} → {cat: count}, 합 == total 보정"""
    raw = {k: int(round(total * v)) for k, v in dist.items()}
    diff = total - sum(raw.values())
    if diff != 0:
        # 가장 큰 카테고리에 보정
        big = max(raw, key=raw.get)
        raw[big] += diff
    return raw


def build():
    rare = set(load_rare())

    # 모든 train + train-new 이미지 평가 (시간 소요)
    files = []
    for d in C.REAL_DIRS:
        if not d.exists(): continue
        for f in d.glob("*.jpg"):
            lab = C.label_from_stem(f.stem)
            if lab:
                files.append((str(f), lab))
    print(f"[hard] real total={len(files):,} 평가 시작...")

    by_cat = defaultdict(list)
    multi_tag_count = Counter_count([])         # placeholder
    multi_tag_total = defaultdict(int)
    n_eval = 0
    for path, label in files:
        m = evaluate(path)
        primary, tags = classify(m, label, rare)
        n_eval += 1
        if primary is not None:
            by_cat[primary].append({
                "path": path, "label": label,
                "category": primary,
                "categories": tags,        # 멀티 태그 (metric 용)
                "metrics": m,
            })
            for t in tags: multi_tag_total[t] += 1
        if n_eval % 5000 == 0:
            print(f"  {n_eval:,}/{len(files):,}  primary={ {k: len(v) for k, v in by_cat.items()} }")
    print(f"[hard] 평가 완료.")
    print(f"  primary 분포: { {k: len(v) for k, v in by_cat.items()} }")
    print(f"  멀티태그(중복포함): { dict(multi_tag_total) }")

    # group dedup: 같은 plate label 은 카테고리 안에서 1번만
    for k in list(by_cat.keys()):
        seen, dedup = set(), []
        for it in by_cat[k]:
            if it["label"] in seen: continue
            seen.add(it["label"]); dedup.append(it)
        by_cat[k] = dedup

    # dev / final quota
    dev_q   = quota_per_set(C.HARD_DEV_TOTAL,   C.HARD_CATEGORY_QUOTA)
    final_q = quota_per_set(C.HARD_FINAL_TOTAL, C.HARD_CATEGORY_QUOTA)
    print(f"[hard] dev quota   = {dev_q}")
    print(f"[hard] final quota = {final_q}")

    rng = random.Random(42)
    dev_picks, final_picks = [], []
    used_labels = set()
    shortage = {}

    # 1차: primary 카테고리 별 quota 채우기
    for cat in C.HARD_CATEGORY_QUOTA.keys():
        pool = [it for it in by_cat.get(cat, []) if it["label"] not in used_labels]
        rng.shuffle(pool)
        need = dev_q[cat] + final_q[cat]
        chosen = pool[:need]
        if len(chosen) < need:
            shortage[cat] = need - len(chosen)
        for it in chosen: used_labels.add(it["label"])
        dev_picks.extend(chosen[:dev_q[cat]])
        final_picks.extend(chosen[dev_q[cat]:dev_q[cat] + final_q[cat]])

    # 2차: 250/250 부족 시 멀티태그 매칭으로 보충 (해당 cat 가 categories 에 들어있는 항목)
    target_dev   = C.HARD_DEV_TOTAL
    target_final = C.HARD_FINAL_TOTAL
    if len(dev_picks) < target_dev or len(final_picks) < target_final:
        candidates = []
        for cat in C.HARD_CATEGORY_QUOTA.keys():
            for primary_cat, items in by_cat.items():
                for it in items:
                    if it["label"] in used_labels: continue
                    if cat in it["categories"] and primary_cat != cat:
                        candidates.append(it)
        # dedup
        seen, uniq = set(), []
        for it in candidates:
            key = it["path"]
            if key in seen: continue
            seen.add(key); uniq.append(it)
        rng.shuffle(uniq)
        for it in uniq:
            if it["label"] in used_labels: continue
            if len(dev_picks) < target_dev:
                dev_picks.append(it); used_labels.add(it["label"])
            elif len(final_picks) < target_final:
                final_picks.append(it); used_labels.add(it["label"])
            else: break

    # save
    payload_dev = {
        "n": len(dev_picks),
        "by_category": dict(Counter_count(it["category"] for it in dev_picks)),
        "items": dev_picks,
    }
    payload_final = {
        "n": len(final_picks),
        "by_category": dict(Counter_count(it["category"] for it in final_picks)),
        "items": final_picks,
    }
    with open(C.HARD_DEV_IDX, "w", encoding="utf-8") as f:
        json.dump(payload_dev, f, ensure_ascii=False, indent=2)
    with open(C.HARD_FINAL_IDX, "w", encoding="utf-8") as f:
        json.dump(payload_final, f, ensure_ascii=False, indent=2)

    print(f"\n[hard] dev   {len(dev_picks)}장 → {C.HARD_DEV_IDX}")
    print(f"[hard] final {len(final_picks)}장 → {C.HARD_FINAL_IDX}")
    if shortage:
        print(f"[hard] WARN 부족: {shortage}")
    return payload_dev, payload_final


def Counter_count(it):
    from collections import Counter
    return Counter(it)


if __name__ == "__main__":
    build()
