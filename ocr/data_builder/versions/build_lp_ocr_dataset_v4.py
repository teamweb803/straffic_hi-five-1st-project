"""
AI-Hub 901K frames 에서 한글 plate crop + text 라벨 → OCR 데이터셋.

policy (엄격):
  - text 패턴 정확히 ^\d{2,3}[가-힣]$ 만 keep
    → "23호", "159가" 같은 형태만
    → "159x", "23x", "허23", "23호1234", "23 호" 모두 skip
    → x 한 글자라도 들어가면 skip
  - per-char bbox 검사: 한글이 모든 숫자보다 x축 뒤(오른쪽) 에 있을 때만 keep
    → 2줄 plate (한글이 다른 줄에 있어 x 좌측) skip
    → 비정상 정렬 skip
  - plate bbox 영역 그대로 crop (padding 0%)
  - JPG q=100 (사용자 결정)
  - 저장: D:/leb/
    images/<id>.jpg
    labels.csv  (filename, text, source_jpg)

usage:
  python tools/build_lp_ocr_dataset.py \
      --src "D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터" \
      --out D:/leb \
      --quality 100
"""
import sys, os, json, csv, re, argparse, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

HANGUL_RE = re.compile(r"[가-힣]")
# 엄격한 패턴: 숫자 2~3개 + 한글 1자 (정확히 일치)
OCR_PAT = re.compile(r"^\d{2,3}[가-힣]$")


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite_jpg(path, img, quality=90):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]
    enc.tofile(str(path))


def find_jpg_label_pairs(src: Path):
    """src/01-1.정식개방데이터/{Training,Validation}/01.원천데이터 등"""
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
    ap.add_argument("--quality", type=int, default=100)
    args = ap.parse_args()

    src = Path(args.src); out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "images"
    img_dir.mkdir(exist_ok=True)
    csv_path = out / "labels.csv"

    print(f"[init] src={src}\n       out={out}\n       quality={args.quality}")

    print("\n[1/2] 파일 매칭 ...")
    pairs = find_jpg_label_pairs(src)
    print(f"  pairs: {len(pairs):,}")

    print("\n[2/2] 엄격 패턴 plate crop + 라벨 추출 ...")
    print("       허용 패턴: ^\\d{2,3}[가-힣]$")
    saved = 0
    n_pattern_fail = 0      # text 패턴 미일치
    n_layout_fail = 0       # 한글이 숫자 앞 (2줄 등)
    n_skip_bbox = 0
    n_skip_load = 0
    t0 = time.time()
    csv_f = open(csv_path, "w", encoding="utf-8", newline="")
    csv_w = csv.writer(csv_f)
    csv_w.writerow(["filename", "text", "class_id", "source_jpg"])

    for i, (jpg_path, json_path) in enumerate(pairs):
        try:
            with open(json_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        annotations = meta.get("Learning_Data_Info", {}).get("annotations", [])

        # plate 후보 검증 (이미지 안 열어도 됨)
        plate_entries = []
        for a in annotations:
            char_list = a.get("license_plate_number", [])
            for lp in a.get("license_plate", []):
                text = lp.get("text", "")
                bbox = lp.get("bbox")
                if not text or not bbox or len(bbox) != 4:
                    continue
                # 1. 엄격 텍스트 패턴 검사 (^\d{2,3}[가-힣]$)
                if not OCR_PAT.match(text):
                    n_pattern_fail += 1
                    continue
                # 2. per-char bbox 검사: 같은 plate (index 일치) 의 char 만 비교
                #    한글이 그 plate 안 모든 숫자보다 x축 뒤에 있어야 함
                plate_idx = lp.get("index")
                same_plate_chars = [c for c in char_list
                                     if c.get("index") == plate_idx]
                hg_chars = [c for c in same_plate_chars
                             if HANGUL_RE.search(c.get("text", ""))]
                dg_chars = [c for c in same_plate_chars
                             if c.get("text", "").isdigit()]
                if not hg_chars or not dg_chars:
                    n_layout_fail += 1
                    continue
                hg_x_min = min(c["bbox"][0] for c in hg_chars
                                if isinstance(c.get("bbox"), list)
                                and len(c["bbox"]) == 4)
                dg_x_max = max(c["bbox"][0] + c["bbox"][2] for c in dg_chars
                                if isinstance(c.get("bbox"), list)
                                and len(c["bbox"]) == 4)
                if hg_x_min < dg_x_max:
                    # 한글이 같은 plate 안의 어떤 숫자보다 좌측 → 2줄 plate
                    n_layout_fail += 1
                    continue
                cls_id = lp.get("class_ID", "unknown")
                plate_entries.append((text, bbox, cls_id))
        if not plate_entries: continue

        # 이미지 한 번 로드
        img = imread_unicode(jpg_path)
        if img is None:
            n_skip_load += 1
            continue
        H, W = img.shape[:2]

        for idx, (text, bbox, cls_id) in enumerate(plate_entries):
            x, y, w, h = bbox
            # clamp
            x0 = max(0, int(x)); y0 = max(0, int(y))
            x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
            if x1 <= x0 or y1 <= y0:
                n_skip_bbox += 1
                continue
            crop = img[y0:y1, x0:x1]
            if crop.size == 0:
                n_skip_bbox += 1
                continue

            # 파일명: {원본 stem}_p{idx}.jpg
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
                   f"pattern_fail={n_pattern_fail:,}  layout_fail={n_layout_fail:,}  "
                   f"({rate:.0f}/s)")

    csv_f.close()
    elapsed = time.time() - t0
    print(f"\n=== 완료 ({elapsed/60:.1f}분) ===")
    print(f"  scanned:        {len(pairs):,}")
    print(f"  saved:          {saved:,}  ⭐ OCR 데이터 (엄격 패턴 + 1줄 plate)")
    print(f"  pattern_fail:   {n_pattern_fail:,}  (x 포함 / 길이 / 형태 등 텍스트 미일치)")
    print(f"  layout_fail:    {n_layout_fail:,}  (한글이 숫자 앞 = 2줄 plate 등)")
    print(f"  bbox skip:      {n_skip_bbox:,}")
    print(f"  load skip:      {n_skip_load:,}")
    print(f"  → {img_dir}")
    print(f"  → {csv_path}")


if __name__ == "__main__":
    main()
