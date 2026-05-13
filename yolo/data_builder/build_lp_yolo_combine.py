"""
901K FHD+UHD frames → Lane-stack + jitter combined images for YOLO training.

policy:
  - 모든 plate 가 anchor 가 됨 (frame 의 N plate → N strips)
  - strip 위치 = plate FHD 위치에 따라 가능 범위 안 random (영역 밖 X)
  - strip 안 다른 plate visibility ≥ 70% 면 라벨 포함
  - 2 strip → 960×960 vstack
  - JPG q=90
  - 저장: C: 우선 → C: free < 30GB 면 D: spillover

usage:
  python tools/build_lp_yolo_combine.py \
      --src D:/lp_yolo_aihub \
      --out_c C:/Users/3900X/Desktop/crop \
      --out_d D:/crop \
      --c_min_free_gb 30 \
      --quality 90
"""
import sys, os, json, csv, re, random, shutil, argparse, time
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

NIDX_PAT = re.compile(r"_N(\d+)$")
CROP_W, CROP_H = 960, 480
COMBINE_H = 960    # 480 + 480
VIS_MIN = 0.70


# ---------- IO ----------
def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite_jpg(path, img, quality=90):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]
    enc.tofile(str(path))


def free_gb(path):
    """Return free space in GB."""
    try:
        return shutil.disk_usage(str(path)).free / (1024**3)
    except OSError:
        return 0


def raw_id_of(stem: str):
    m = NIDX_PAT.search(stem)
    return stem[:m.start()] if m else stem


# ---------- label parsing ----------
def load_labels(txt_path: Path, W: int, H: int):
    """YOLO normalized → list of plate bboxes in pixel coords"""
    plates = []
    if not txt_path.exists(): return plates
    with open(txt_path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5: continue
            cls = int(float(parts[0]))
            cx_n, cy_n, w_n, h_n = map(float, parts[1:])
            plates.append({
                "cx": cx_n * W, "cy": cy_n * H,
                "w":  w_n * W,  "h":  h_n * H,
            })
    return plates


# ---------- strip generation ----------
def compute_strip_position(plate, img_w, img_h, rng):
    """plate 가 FHD 안에서 strip 가능 범위 안 random 위치
    영역 밖 절대 X (sx ∈ [0, W-CROP_W], plate 가 strip 안에 완전히 들어감)"""
    cx, cy = plate["cx"], plate["cy"]
    bw, bh = plate["w"],  plate["h"]

    # strip 시작 가능 범위
    sx_min = max(0.0, cx + bw / 2 - CROP_W)
    sx_max = min(img_w - CROP_W, cx - bw / 2)
    sy_min = max(0.0, cy + bh / 2 - CROP_H)
    sy_max = min(img_h - CROP_H, cy - bh / 2)

    # 가능 범위 없으면 None (plate 너무 큼 or 위치 이상)
    if sx_min > sx_max or sy_min > sy_max: return None
    if img_w < CROP_W or img_h < CROP_H:   return None

    sx = rng.uniform(sx_min, sx_max)
    sy = rng.uniform(sy_min, sy_max)
    return int(sx), int(sy)


def crop_strip_with_labels(img, plates, anchor_idx, rng):
    """anchor plate 기준 strip 생성 + 보이는 plate 들 라벨"""
    H, W = img.shape[:2]
    anchor = plates[anchor_idx]
    pos = compute_strip_position(anchor, W, H, rng)
    if pos is None: return None
    sx, sy = pos
    strip = img[sy:sy + CROP_H, sx:sx + CROP_W]
    if strip.shape[0] != CROP_H or strip.shape[1] != CROP_W: return None

    # 모든 plate 의 visibility 검사 → keep
    bboxes = []
    for p in plates:
        x1 = p["cx"] - p["w"] / 2 - sx
        y1 = p["cy"] - p["h"] / 2 - sy
        x2 = p["cx"] + p["w"] / 2 - sx
        y2 = p["cy"] + p["h"] / 2 - sy
        # strip 안 visible 영역
        vx1 = max(0, x1); vy1 = max(0, y1)
        vx2 = min(CROP_W, x2); vy2 = min(CROP_H, y2)
        if vx2 <= vx1 or vy2 <= vy1: continue
        visible = (vx2 - vx1) * (vy2 - vy1)
        original = p["w"] * p["h"]
        if visible / original < VIS_MIN: continue
        bboxes.append((vx1, vy1, vx2, vy2))    # in strip coords [0,960]×[0,480]
    return strip, bboxes


# ---------- combine + save ----------
def combine_and_label(strip_a, bboxes_a, strip_b, bboxes_b):
    """vstack 위(2차선) + 아래(1차선) → 960×960 + YOLO 라벨"""
    combined = np.vstack([strip_a, strip_b])    # 960×960
    H_total, W_total = combined.shape[:2]
    yolo_lines = []
    # top strip: y 그대로
    for x1, y1, x2, y2 in bboxes_a:
        cx = (x1 + x2) / 2 / W_total
        cy = (y1 + y2) / 2 / H_total
        w  = (x2 - x1) / W_total
        h  = (y2 - y1) / H_total
        yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    # bottom strip: y += CROP_H
    for x1, y1, x2, y2 in bboxes_b:
        y1n = y1 + CROP_H
        y2n = y2 + CROP_H
        cx = (x1 + x2) / 2 / W_total
        cy = (y1n + y2n) / 2 / H_total
        w  = (x2 - x1) / W_total
        h  = (y2n - y1n) / H_total
        yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return combined, yolo_lines


# ---------- 메인 ----------
def process_split(split_name, frame_list, args, out_paths, stats):
    """frame_list 를 sequential 처리하면서 strip buffer 로 pairing"""
    print(f"\n[{split_name}] frames={len(frame_list):,}")
    rng = random.Random(args.seed + (1 if split_name == "val" else 0))
    rng.shuffle(frame_list)

    out_image_dir, out_label_dir = out_paths[split_name]
    out_image_dir.mkdir(parents=True, exist_ok=True)
    out_label_dir.mkdir(parents=True, exist_ok=True)

    strip_buffer = []           # list of (strip, bboxes, raw_id)
    saved = 0
    skipped_frames = 0
    total_strips = 0
    t0 = time.time()
    out_disk = "C"               # 시작은 C

    for fi, (jpg_path, txt_path, raw_id) in enumerate(frame_list):
        img = imread_unicode(jpg_path)
        if img is None: continue
        H, W = img.shape[:2]
        plates = load_labels(txt_path, W, H)
        if not plates: continue
        # 각 plate 를 anchor 로 strip 생성
        for ai in range(len(plates)):
            res = crop_strip_with_labels(img, plates, ai, rng)
            if res is None: continue
            strip, bboxes = res
            if not bboxes: continue
            strip_buffer.append((strip, bboxes, raw_id))
            total_strips += 1

        # buffer 에 2개 이상 있으면 pair → save
        while len(strip_buffer) >= 2:
            # 디스크 free 체크 → spillover 결정
            cur_out = args.out_c if out_disk == "C" else args.out_d
            free = free_gb(args.out_c if out_disk == "C" else args.out_d)
            if out_disk == "C" and free < args.c_min_free_gb:
                out_disk = "D"
                cur_out = args.out_d
                # 새 split 디렉토리 생성
                (cur_out / "images" / split_name).mkdir(parents=True, exist_ok=True)
                (cur_out / "labels" / split_name).mkdir(parents=True, exist_ok=True)
                print(f"  [spillover] C: free {free:.1f}GB < {args.c_min_free_gb}GB → D:")

            a = strip_buffer.pop(0)
            b = strip_buffer.pop(0)
            combined, lines = combine_and_label(a[0], a[1], b[0], b[1])

            # 저장 경로 결정
            base_out = args.out_c if out_disk == "C" else args.out_d
            img_out = base_out / "images" / split_name / f"c_{saved:07d}.jpg"
            lbl_out = base_out / "labels" / split_name / f"c_{saved:07d}.txt"

            imwrite_jpg(img_out, combined, args.quality)
            lbl_out.write_text("\n".join(lines), encoding="utf-8")
            saved += 1

            if saved % 1000 == 0:
                el = time.time() - t0
                rate = saved / max(1, el)
                eta = (frame_list and (len(frame_list) - fi)) / max(rate, 1) if rate else 0
                print(f"  [{split_name}] saved={saved:,}  "
                       f"({rate:.0f}/s, frames {fi+1:,}/{len(frame_list):,}, "
                       f"buffer={len(strip_buffer)}, disk={out_disk})")

    # buffer flush
    while len(strip_buffer) >= 2:
        a = strip_buffer.pop(0); b = strip_buffer.pop(0)
        combined, lines = combine_and_label(a[0], a[1], b[0], b[1])
        base_out = args.out_c if out_disk == "C" else args.out_d
        img_out = base_out / "images" / split_name / f"c_{saved:07d}.jpg"
        lbl_out = base_out / "labels" / split_name / f"c_{saved:07d}.txt"
        imwrite_jpg(img_out, combined, args.quality)
        lbl_out.write_text("\n".join(lines), encoding="utf-8")
        saved += 1

    elapsed = time.time() - t0
    print(f"\n[{split_name}] 완료: {saved:,} combined images "
           f"({total_strips:,} strips, {elapsed/60:.1f}분)")
    stats[split_name] = {"saved": saved, "strips": total_strips,
                          "elapsed_min": round(elapsed / 60, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out_c", required=True, help="primary save path (C:)")
    ap.add_argument("--out_d", required=True, help="spillover save path (D:)")
    ap.add_argument("--c_min_free_gb", type=float, default=30.0)
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    args.src   = Path(args.src)
    args.out_c = Path(args.out_c)
    args.out_d = Path(args.out_d)

    # 1. (jpg, txt) pairs 수집 (D:/lp_yolo_aihub 의 train, val 그대로 사용)
    print("[1] 파일 매칭 ...")
    splits = {}
    for split_name in ("train", "val"):
        labs = list((args.src / "labels" / split_name).glob("*.txt"))
        items = []
        for lab in labs:
            jpg = args.src / "images" / split_name / f"{lab.stem}.jpg"
            if not jpg.exists(): continue
            items.append((jpg, lab, raw_id_of(lab.stem)))
        splits[split_name] = items
        print(f"  {split_name}: {len(items):,}")

    # 2. 출력 디렉토리 준비
    args.out_c.mkdir(parents=True, exist_ok=True)
    args.out_d.mkdir(parents=True, exist_ok=True)
    out_paths = {
        "train": (args.out_c / "images" / "train", args.out_c / "labels" / "train"),
        "val":   (args.out_c / "images" / "val",   args.out_c / "labels" / "val"),
    }

    # 3. lp.yaml 작성
    yaml_path = args.out_c / "lp.yaml"
    yaml_path.write_text(
        f"path: {args.out_c.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n\n"
        f"nc: 1\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    print(f"  saved → {yaml_path}")

    # 4. 처리
    stats = {}
    for split_name in ("train", "val"):
        process_split(split_name, splits[split_name], args, out_paths, stats)

    # 5. 요약
    print("\n=== 요약 ===")
    for s, v in stats.items():
        print(f"  {s}: {v['saved']:,} combined  ({v['strips']:,} strips, {v['elapsed_min']}분)")
    print(f"  → {args.out_c} (+ spillover {args.out_d})")
    print(f"  → {yaml_path}")


if __name__ == "__main__":
    main()
