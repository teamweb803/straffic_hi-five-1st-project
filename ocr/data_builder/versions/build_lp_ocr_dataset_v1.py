"""
[OCR Builder v1 — 초기]

policy:
  - text 에 한글 1자 이상 있으면 keep (느슨한 필터)
  - plate bbox 영역 crop
  - JPG q=90

문제:
  - "159x" 같이 한글 없고 x 만 있는 케이스는 거부되지만,
    "x허" 처럼 x + 한글 섞인 케이스 keep (의도와 다름)
  - 2줄 plate 도 keep (잘못된 학습 데이터)
"""
import sys, os, json, csv, re, argparse, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

HANGUL_PAT = re.compile(r"[가-힣]")


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite_jpg(path, img, quality=90):
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
    ap.add_argument("--quality", type=int, default=90)
    args = ap.parse_args()

    src = Path(args.src); out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "images"
    img_dir.mkdir(exist_ok=True)
    csv_path = out / "labels.csv"

    print(f"[init v1] src={src}\n           out={out}\n           quality={args.quality}")
    print("\n[1/2] 파일 매칭 ...")
    pairs = find_jpg_label_pairs(src)
    print(f"  pairs: {len(pairs):,}")

    print("\n[2/2] 한글 plate crop + 라벨 추출 ...")
    saved = 0
    n_no_hangul = 0
    n_skip_bbox = 0
    n_skip_load = 0
    t0 = time.time()
    csv_f = open(csv_path, "w", encoding="utf-8", newline="")
    csv_w = csv.writer(csv_f)
    csv_w.writerow(["filename", "text", "source_jpg"])

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
                # v1: 한글 1자 이상 있으면 OK (느슨)
                if not HANGUL_PAT.search(text):
                    n_no_hangul += 1
                    continue
                plate_entries.append((text, bbox))
        if not plate_entries: continue

        img = imread_unicode(jpg_path)
        if img is None:
            n_skip_load += 1
            continue
        H, W = img.shape[:2]

        for idx, (text, bbox) in enumerate(plate_entries):
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
            csv_w.writerow([out_name, text, str(jpg_path)])
            saved += 1

        if (i + 1) % 5000 == 0:
            el = time.time() - t0
            rate = (i + 1) / max(1, el)
            csv_f.flush()
            print(f"  scanned={i+1:,}/{len(pairs):,}  saved={saved:,}  "
                   f"no_hangul={n_no_hangul:,}  ({rate:.0f}/s)")

    csv_f.close()
    elapsed = time.time() - t0
    print(f"\n=== v1 완료 ({elapsed/60:.1f}분) ===")
    print(f"  scanned:    {len(pairs):,}")
    print(f"  saved:      {saved:,}")
    print(f"  no_hangul:  {n_no_hangul:,}")
    print(f"  bbox skip:  {n_skip_bbox:,}")
    print(f"  load skip:  {n_skip_load:,}")


if __name__ == "__main__":
    main()
