"""
Lane-stack + Jitter 테스트 — 10장 샘플 생성 + bbox 시각화.

입력: D:/lp_yolo_aihub 의 FHD frames + 라벨
처리:
  1. 20개 frame random 샘플 (FHD only)
  2. 두 frame 씩 pair → strip A + strip B → 960×960 합성
  3. plate 가 strip 안 random 위치 (jitter ±200 가로, ±150 세로)
  4. 결과 + bbox overlay 저장

출력: C:/Users/3900X/Desktop/crop_test/
"""
import sys, json, random
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

OUT  = Path(r"C:/Users/3900X/Desktop/crop_test")
OUT.mkdir(parents=True, exist_ok=True)

LABEL_DIR = Path(r"C:/Users/3900X/Desktop/lp_yolo_aihub_50k/labels/train")
IMAGE_DIR = Path(r"C:/Users/3900X/Desktop/lp_yolo_aihub_50k/images/train")

CROP_W, CROP_H = 960, 480     # strip size
JITTER_X = 200                 # ±200 px 좌우
JITTER_Y = 150                 # ±150 px 위아래
N_PAIRS = 10
SEED = 42


def load_label(p: Path):
    """YOLO format → list[(class, cx_norm, cy_norm, w_norm, h_norm)]"""
    out = []
    if not p.exists(): return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5: continue
            out.append([float(v) for v in parts])
    return out


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def make_strip(jpg_path, label_path, rng):
    """
    FHD frame → 960×480 strip (plate 중심 + jitter)
    Returns: (strip_image, list of bbox in strip coords [x1,y1,x2,y2])
    """
    img = imread_unicode(jpg_path)
    if img is None: return None, []
    H, W = img.shape[:2]
    if W < 1900 or H < 1000:
        return None, []   # FHD 만 사용 (UHD 제외)

    labels = load_label(label_path)
    if not labels: return None, []

    # 첫번째 plate 중심으로 strip 위치 결정
    cls, cx_n, cy_n, w_n, h_n = labels[0]
    cx, cy = cx_n * W, cy_n * H

    # Jitter
    offset_x = rng.uniform(-JITTER_X, JITTER_X)
    offset_y = rng.uniform(-JITTER_Y, JITTER_Y)

    # Strip 시작 좌표
    sx = int(np.clip(cx + offset_x - CROP_W / 2, 0, W - CROP_W))
    sy = int(np.clip(cy + offset_y - CROP_H / 2, 0, H - CROP_H))

    strip = img[sy:sy + CROP_H, sx:sx + CROP_W]

    # 모든 plate 의 bbox → strip 좌표계 변환 (visibility 70% 이상)
    out_bboxes = []
    for cls, cx_n, cy_n, w_n, h_n in labels:
        x_orig = cx_n * W
        y_orig = cy_n * H
        bw = w_n * W
        bh = h_n * H

        # 원본 좌표
        x1 = x_orig - bw / 2
        y1 = y_orig - bh / 2
        x2 = x_orig + bw / 2
        y2 = y_orig + bh / 2

        # strip 좌표계로 shift
        nx1 = x1 - sx
        ny1 = y1 - sy
        nx2 = x2 - sx
        ny2 = y2 - sy

        # strip 안 가시 영역
        vx1 = max(0, nx1)
        vy1 = max(0, ny1)
        vx2 = min(CROP_W, nx2)
        vy2 = min(CROP_H, ny2)
        if vx2 <= vx1 or vy2 <= vy1: continue

        visible_area = (vx2 - vx1) * (vy2 - vy1)
        original_area = bw * bh
        if visible_area / original_area < 0.7: continue

        out_bboxes.append([vx1, vy1, vx2, vy2])

    return strip, out_bboxes


def combine_and_visualize(strip_top, bboxes_top, strip_bot, bboxes_bot, idx, vis_dir, label_dir):
    """위 + 아래 strip 합성 → 960×960 + bbox 시각화 저장 + YOLO 라벨 저장"""
    combined = np.vstack([strip_top, strip_bot])    # 960×960
    H, W = combined.shape[:2]

    # YOLO 라벨 (combined 좌표계)
    yolo_lines = []
    for x1, y1, x2, y2 in bboxes_top:
        # y 좌표 그대로 (top strip)
        cx = (x1 + x2) / 2 / W
        cy = (y1 + y2) / 2 / H
        w  = (x2 - x1) / W
        h  = (y2 - y1) / H
        yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    for x1, y1, x2, y2 in bboxes_bot:
        # y 좌표 += CROP_H (bot strip)
        y1_new = y1 + CROP_H
        y2_new = y2 + CROP_H
        cx = (x1 + x2) / 2 / W
        cy = (y1_new + y2_new) / 2 / H
        w  = (x2 - x1) / W
        h  = (y2_new - y1_new) / H
        yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    # 시각화 (오버레이)
    vis = combined.copy()
    # 위/아래 strip 경계선 (참고용)
    cv2.line(vis, (0, CROP_H), (W, CROP_H), (255, 255, 0), 1)

    # bbox 그리기
    for x1, y1, x2, y2 in bboxes_top:
        cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)),
                       (0, 255, 255), 3)    # cyan
        cv2.putText(vis, "plate", (int(x1), max(20, int(y1) - 8)),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    for x1, y1, x2, y2 in bboxes_bot:
        y1_new = y1 + CROP_H
        y2_new = y2 + CROP_H
        cv2.rectangle(vis, (int(x1), int(y1_new)), (int(x2), int(y2_new)),
                       (0, 255, 255), 3)
        cv2.putText(vis, "plate", (int(x1), max(20, int(y1_new) - 8)),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # 정보 overlay
    cv2.putText(vis, f"#{idx:02d}  2lane(top)={len(bboxes_top)}  1lane(bot)={len(bboxes_bot)}",
                 (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(vis, "2lane (lane 2)", (10, 50),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1)
    cv2.putText(vis, "1lane (lane 1)", (10, CROP_H + 30),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1)

    out_vis_path = vis_dir / f"sample_{idx:02d}_visualized.jpg"
    out_clean_path = vis_dir / f"sample_{idx:02d}.jpg"
    out_label_path = label_dir / f"sample_{idx:02d}.txt"

    cv2.imencode(".jpg", vis)[1].tofile(str(out_vis_path))
    cv2.imencode(".jpg", combined)[1].tofile(str(out_clean_path))
    out_label_path.write_text("\n".join(yolo_lines), encoding="utf-8")

    return len(bboxes_top) + len(bboxes_bot)


def main():
    rng = random.Random(SEED)

    # FHD 만 후보 풀에서 sampling
    print("[1/3] FHD frame 후보 수집 ...")
    label_files = list(LABEL_DIR.glob("*.txt"))
    rng.shuffle(label_files)

    candidates = []
    for lab in label_files:
        if len(candidates) >= 50: break    # 후보 50개만
        jpg = IMAGE_DIR / f"{lab.stem}.jpg"
        if not jpg.exists(): continue
        # FHD 확인 (header 없이 빠르게: 파일 사이즈로 추정 + label 0 아닌지)
        labels = load_label(lab)
        if not labels: continue
        candidates.append((jpg, lab))
    print(f"  후보: {len(candidates)} frame")

    # FHD 만 (해상도 검증)
    print("[2/3] FHD 만 필터 ...")
    fhd_pool = []
    for jpg, lab in candidates:
        img = imread_unicode(jpg)
        if img is None: continue
        h, w = img.shape[:2]
        if w == 1920 and h == 1080:
            fhd_pool.append((jpg, lab))
        if len(fhd_pool) >= 30: break
    print(f"  FHD: {len(fhd_pool)} frame")

    if len(fhd_pool) < N_PAIRS * 2:
        print(f"[error] FHD 부족 ({len(fhd_pool)} < {N_PAIRS * 2})")
        sys.exit(2)

    # 20장 → 10 pair
    rng.shuffle(fhd_pool)
    selected = fhd_pool[: N_PAIRS * 2]

    vis_dir = OUT
    label_dir = OUT / "labels"
    label_dir.mkdir(exist_ok=True)

    print(f"[3/3] {N_PAIRS} pair 생성 + 시각화 ...")
    success = 0
    total_bbox = 0
    for i in range(N_PAIRS):
        a = selected[i * 2]
        b = selected[i * 2 + 1]
        strip_a, bb_a = make_strip(a[0], a[1], rng)
        strip_b, bb_b = make_strip(b[0], b[1], rng)
        if strip_a is None or strip_b is None: continue
        if not bb_a and not bb_b: continue
        n_bb = combine_and_visualize(strip_a, bb_a, strip_b, bb_b, i + 1,
                                       vis_dir, label_dir)
        success += 1; total_bbox += n_bb
        print(f"  #{i+1:02d}: top frame {a[0].name} + bot frame {b[0].name}  "
              f"({len(bb_a)}+{len(bb_b)} bboxes)")

    print(f"\n=== 완료 ===")
    print(f"  생성: {success}/{N_PAIRS} 합성 이미지")
    print(f"  bbox 합계: {total_bbox}")
    print(f"  → {vis_dir}/")
    print(f"      sample_NN.jpg                 (학습 input format)")
    print(f"      sample_NN_visualized.jpg      (bbox 그려진 검증용)")
    print(f"      labels/sample_NN.txt          (YOLO 라벨)")


if __name__ == "__main__":
    main()
