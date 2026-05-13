"""
[OCR Builder v2 — 엄격 패턴 추가]

v1 → v2 변경:
  - 엄격 텍스트 패턴 ^\d{2,3}[가-힣]$ 추가
  - JPG q=90 → q=100
  - class_id 컬럼 추가 (CSV)

policy:
  - text 정확히 숫자 2~3개 + 한글 1자 (그 외 모두 skip)
    → "23호" ✓, "159가" ✓
    → "159x" ✗, "허23" ✗, "23호1234" ✗
  - plate bbox 그대로 crop
  - JPG q=100

남은 문제:
  - 2줄 plate (한글이 다른 위치) 도 keep → 학습 혼란 가능
"""
import sys, os, json, csv, re, argparse, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

# v2 신규: 엄격 패턴
OCR_PAT = re.compile(r"^\d{2,3}[가-힣]$")


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite_jpg(path, img, quality=100):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]
    enc.tofile(str(path))


def find_jpg_label_pairs(src: Path):
    base = src / "01-1.정식개방데이터"
    pairs = []
    for split_name, jpg_prefix, json_prefix in (
        ("training",   "TS_", "TL_"),
        ("validation", "VS_", "VL_"),
    ):
        split_root = base / split_name.capitalize()
        if not split_root.exists(): continue
        jpg_root  = split_root / "01.원천데이터"
        json_root = split_root / "02.라벨링데이터"
        for jpg_dir in sorted(jpg_root.iterdir() if jpg_root.exists() else []):
            if not jpg_dir.is_dir() or not jpg_dir.name.startswith(jpg_prefix): continue
            json_dir = json_root / (json_prefix + jpg_dir.name[len(jpg_prefix):])
            if not json_dir.exists(): continue
            for jpg in jpg_dir.glob("*.jpg"):
                jp = json_dir / f"{jpg.stem}.json"
                if jp.exists(): pairs.append((jpg, jp))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=100)    # v2: 기본 100
    args = ap.parse_args()

    src = Path(args.src); out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "images"
    img_dir.mkdir(exist_ok=True)
    csv_path = out / "labels.csv"

    print(f"[init v2] src={src}\n           out={out}\n           quality={args.quality}")
    print("\n[1/2] 파일 매칭 ...")
    pairs = find_jpg_label_pairs(src)
    print(f"  pairs: {len(pairs):,}")

    print("\n[2/2] 엄격 패턴 plate crop + 라벨 추출 ...")
    print("       허용 패턴: ^\\d{2,3}[가-힣]$")
    saved = 0
    n_pattern_fail = 0     # v2 신규: 엄격 패턴 미일치
    n_skip_bbox = 0
    n_skip_load = 0
    t0 = time.time()
    csv_f = open(csv_path, "w", encoding="utf-8", newline="")
    csv_w = csv.writer(csv_f)
    # v2 신규: class_id 컬럼
    csv_w.writerow(["filename", "text", "class_id", "source_jpg"])

    for i, (jpg_path, json_path) in enumerate(pairs):
        try:
            with open(json_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        annotations = meta.get("Learning_Data_Info", {}).get("annotations", [])

        plate_entries = []
        for a in annotations:
            for lp in a.get("license_plate", []):
                text = lp.get("text", "")
                bbox = lp.get("bbox")
                if not text or not bbox or len(bbox) != 4:
                    continue
                # v2 신규: 엄격 패턴 검사
                if not OCR_PAT.match(text):
                    n_pattern_fail += 1
                    continue
                cls_id = lp.get("class_ID", "unknown")
                plate_entries.append((text, bbox, cls_id))
        if not plate_entries: continue

        img = imread_unicode(jpg_path)
        if img is None:
            n_skip_load += 1
            continue
        H, W = img.shape[:2]

        for idx, (text, bbox, cls_id) in enumerate(plate_entries):
            x, y, w, h = bbox
            x0 = max(0, int(x)); y0 = max(0, int(y))
            x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
            if x1 <= x0 or y1 <= y0:
                n_skip_bbox += 1
                continue
            crop = img[y0:y1, x0:x1]
            if crop.size == 0:
                n_skip_bbox += 1
                continue

            out_name = f"{jpg_path.stem}_p{idx}.jpg"
            out_jpg = img_dir / out_name
            imwrite_jpg(out_jpg, crop, args.quality)
            csv_w.writerow([out_name, text, cls_id, str(jpg_path)])
            saved += 1

        if (i + 1) % 5000 == 0:
            el = time.time() - t0
            rate = (i + 1) / max(1, el)
            csv_f.flush()
            print(f"  scanned={i+1:,}/{len(pairs):,}  saved={saved:,}  "
                   f"pattern_fail={n_pattern_fail:,}  ({rate:.0f}/s)")

    csv_f.close()
    elapsed = time.time() - t0
    print(f"\n=== v2 완료 ({elapsed/60:.1f}분) ===")
    print(f"  scanned:        {len(pairs):,}")
    print(f"  saved:          {saved:,}")
    print(f"  pattern_fail:   {n_pattern_fail:,}")


if __name__ == "__main__":
    main()
