"""
hard_final integrity check (v6 보조 도구)
- 250 items 의 path 존재/사이즈/cv2/PIL 검사
- 실패 사유 분류
- 가능한 대체 경로 (filename stem 기반) 후보 출력
- d:/aa/training/reports_v6/hard_final_missing_or_unreadable.csv 저장
"""
import sys, csv, json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

from . import config as C


def cv2_imread_unicode(path):
    try:
        a = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        return (a is not None and a.size > 0), a
    except Exception:
        return False, None


def pil_open(path):
    try:
        from PIL import Image
        with Image.open(str(path)) as im:
            im.load()
        return True
    except Exception:
        return False


# 대체 경로 검색 풀
SEARCH_DIRS = [
    Path(r"C:/Users/3900X/Desktop/tt/ab"),
    Path(r"C:/Users/3900X/Desktop/tt/train_good"),
    Path(r"C:/Users/3900X/Desktop/tt/aa"),
    Path(r"C:/Users/3900X/Desktop/tt/ad"),
    Path(r"C:/Users/3900X/Desktop/tt/end"),
    Path(r"d:/aa/last/train"),
    Path(r"d:/aa/last/train-new"),
    Path(r"d:/aa/aa"),
    Path(r"d:/aa/ab"),
    Path(r"d:/aa/ac"),
    Path(r"d:/aa/ad"),
]


def find_replacement(item):
    """원래 stem 기반으로 다른 폴더에서 같은 이미지를 찾기"""
    orig = Path(item["path"])
    stem = orig.stem
    label = item.get("label", "")
    cands = []
    for d in SEARCH_DIRS:
        if not d.exists(): continue
        # stem 정확 일치
        for ext in (".jpg", ".jpeg", ".png"):
            p = d / f"{stem}{ext}"
            if p.exists() and p != orig:
                cands.append(str(p))
        # training_/validation_ prefix 변형
        for prefix in ("training_", "validation_"):
            for ext in (".jpg", ".jpeg", ".png"):
                p = d / f"{prefix}{stem}{ext}"
                if p.exists():
                    cands.append(str(p))
    # 라벨 기준 부분일치 (label 이 stem 안에 있는 파일)
    if label and len(cands) == 0:
        for d in SEARCH_DIRS:
            if not d.exists(): continue
            try:
                for p in d.glob(f"*{label}*.jpg"):
                    cands.append(str(p))
                    if len(cands) >= 5: break
            except OSError:
                pass
            if len(cands) >= 5: break
    return cands[:5]


def classify(item):
    p = Path(item["path"])
    if not p.exists():
        return "missing_file", 0
    try:
        size = p.stat().st_size
    except OSError:
        return "missing_file", 0
    if size == 0:
        return "corrupted_image", 0
    cv2_ok, _ = cv2_imread_unicode(p)
    pil_ok = pil_open(p)
    if cv2_ok:
        return "ok", size
    if pil_ok:
        return "unicode_read_fail", size  # cv2 unicode 실패 but PIL OK
    return "corrupted_image", size


def main():
    if not C.HARD_FINAL_IDX.exists():
        print(f"[error] {C.HARD_FINAL_IDX} 없음"); sys.exit(2)
    with open(C.HARD_FINAL_IDX, encoding="utf-8") as f:
        items = json.load(f)["items"]
    print(f"[scan] hard_final = {len(items):,}")

    rows = []
    counts = {"ok": 0, "missing_file": 0, "unicode_read_fail": 0,
              "corrupted_image": 0}
    fail_items = []
    for it in items:
        reason, size = classify(it)
        counts[reason] = counts.get(reason, 0) + 1
        if reason != "ok":
            cands = find_replacement(it)
            fail_items.append({
                "path": it["path"], "label": it.get("label", ""),
                "categories": ";".join(it.get("categories", [])),
                "reason": reason, "size": size,
                "replacements": "|".join(cands),
            })

    out_csv = C.REPORT_DIR_V6 / "hard_final_missing_or_unreadable.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = ["path", "label", "categories", "reason", "size", "replacements"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in fail_items: w.writerow(r)

    print(f"\n=== hard_final integrity ===")
    for k, v in counts.items():
        print(f"  {k:<22s}: {v:>3}")
    print(f"\n  실패 총: {sum(v for k, v in counts.items() if k != 'ok')}/{len(items)}")
    print(f"  saved → {out_csv}")
    if fail_items:
        with_repl = sum(1 for r in fail_items if r["replacements"])
        print(f"  대체 후보 발견: {with_repl}/{len(fail_items)}")
        # 카테고리 분포 (편향 확인)
        from collections import Counter
        c = Counter()
        for r in fail_items:
            for tag in r["categories"].split(";"):
                if tag: c[tag] += 1
        print(f"\n  실패 샘플 categories 분포:")
        for k, v in c.most_common():
            print(f"    {k:<11s}: {v}")
    return counts, fail_items


if __name__ == "__main__":
    main()
