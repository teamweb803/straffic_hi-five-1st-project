"""
50K pilot subset 빌더 — D:/lp_yolo_aihub 의 train pool 에서 추출.
group-aware (raw_data_ID = video unit) + 간단 stratification.

사용:
  python tools/build_lp_yolo_pilot_50k.py \
      --src D:/lp_yolo_aihub --out D:/lp_yolo_aihub_50k \
      --target 50000 --val_ratio 0.10 --link_mode hardlink

전략:
  1. src/labels/train 의 모든 .txt 수집
  2. raw_data_ID (= filename 의 _NXXXX 앞 부분) 으로 group
  3. 각 video 의 min_plate_h_norm 계산 (label 의 가장 작은 plate height)
  4. video 를 small_video (h_norm 작은 25%) vs normal_video 로 분리
  5. 25% small + 75% normal 비율로 video sampling → 누적 frame 50K 도달 시 중단
  6. 선택된 video 들 내부에서 group-aware train/val 분리 (90/10)
  7. labels 복사 + images hardlink → out/

출력:
  out/
    images/{train,val}/
    labels/{train,val}/
    lp.yaml
    pilot_summary.json
"""
import sys, os, json, csv, re, random, shutil, argparse, time
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

NIDX_PAT = re.compile(r"_N(\d+)$")


def link_or_copy(src: Path, dst: Path, mode: str) -> str:
    if dst.exists(): return "skip_exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "hardlink":
        try: os.link(str(src), str(dst)); return "hardlink"
        except OSError: mode = "symlink"
    if mode == "symlink":
        try: os.symlink(str(src), str(dst)); return "symlink"
        except OSError: mode = "copy"
    if mode == "copy":
        shutil.copy2(str(src), str(dst)); return "copy"
    return "fail"


def read_label(p: Path):
    """Returns list of (cls, cx, cy, w, h) tuples."""
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5: continue
                out.append(tuple(float(v) for v in parts))
    except OSError: pass
    return out


def raw_id_of(stem: str):
    m = NIDX_PAT.search(stem)
    return stem[:m.start()] if m else stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=int, default=50000)
    ap.add_argument("--val_ratio", type=float, default=0.10)
    ap.add_argument("--small_ratio", type=float, default=0.25,
                    help="small_video 가 차지할 비율 (default 0.25)")
    ap.add_argument("--small_h_threshold", type=float, default=0.022,
                    help="h_norm 이 이 값 미만이면 small (default ≈ 24px on 1080p)")
    ap.add_argument("--link_mode", choices=["hardlink","symlink","copy"], default="hardlink")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src = Path(args.src); out = Path(args.out)
    label_train_dir = src / "labels" / "train"
    image_train_dir = src / "images" / "train"
    if not label_train_dir.exists():
        print(f"[error] {label_train_dir} 없음"); sys.exit(2)

    print(f"[init] src={src}  out={out}")
    print(f"[init] target={args.target}  val_ratio={args.val_ratio}  small={args.small_ratio:.0%}")

    # 1. 모든 label 수집 + group + min h_norm
    print(f"\n[1/4] label 스캔 + group ...")
    t0 = time.time()
    by_video = defaultdict(list)        # raw_data_ID → [(stem, min_h_norm), ...]
    n_total = 0
    for lab in label_train_dir.glob("*.txt"):
        rows = read_label(lab)
        if not rows: continue
        h_min = min(r[4] for r in rows)
        rid = raw_id_of(lab.stem)
        by_video[rid].append((lab.stem, h_min))
        n_total += 1
        if n_total % 100000 == 0:
            print(f"  scan {n_total:,} ({(n_total/(time.time()-t0)):.0f}/s)")
    print(f"  total labels: {n_total:,}  videos: {len(by_video):,}")

    # 2. 각 video 의 대표 h_norm = 영상 안 frame 들의 median min_h
    video_meta = {}
    for rid, lst in by_video.items():
        lst.sort()    # by stem
        hs = sorted(h for _, h in lst)
        video_meta[rid] = {
            "n_frames": len(lst),
            "h_median": hs[len(hs) // 2],
            "frames": [s for s, _ in lst],
        }

    # 3. small_video vs normal_video 분류
    rng = random.Random(args.seed)
    small_videos = [rid for rid, m in video_meta.items()
                     if m["h_median"] < args.small_h_threshold]
    normal_videos = [rid for rid, m in video_meta.items()
                     if m["h_median"] >= args.small_h_threshold]
    rng.shuffle(small_videos)
    rng.shuffle(normal_videos)
    print(f"\n[2/4] video 분류:")
    print(f"  small (h<{args.small_h_threshold}): {len(small_videos):,} videos")
    print(f"  normal:                            {len(normal_videos):,} videos")

    # 4. video 단위로 누적 sampling
    target = args.target
    target_small = int(target * args.small_ratio)
    target_normal = target - target_small
    selected = []        # raw_data_IDs picked
    n_small = n_normal = 0

    def take_until(pool, target_n, current_n):
        out = []; cur = current_n
        for rid in pool:
            if cur >= target_n: break
            n = video_meta[rid]["n_frames"]
            out.append(rid); cur += n
        return out, cur

    pick_small, n_small = take_until(small_videos, target_small, 0)
    pick_normal, n_normal = take_until(normal_videos, target_normal, 0)
    selected = pick_small + pick_normal
    rng.shuffle(selected)
    n_picked_frames = sum(video_meta[r]["n_frames"] for r in selected)
    print(f"\n[3/4] 선택:")
    print(f"  small videos: {len(pick_small):,}  frames: {n_small:,}")
    print(f"  normal videos: {len(pick_normal):,}  frames: {n_normal:,}")
    print(f"  total picked: {len(selected):,} videos / {n_picked_frames:,} frames")

    # 5. pilot train/val split (group-aware, video 단위)
    rng.shuffle(selected)
    n_val_videos = max(1, int(len(selected) * args.val_ratio))
    pilot_val   = set(selected[:n_val_videos])
    pilot_train = set(selected[n_val_videos:])

    # 6. linking
    print(f"\n[4/4] linking ({args.link_mode}) ...")
    out.mkdir(parents=True, exist_ok=True)
    (out / "images" / "train").mkdir(parents=True, exist_ok=True)
    (out / "images" / "val").mkdir(parents=True, exist_ok=True)
    (out / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (out / "labels" / "val").mkdir(parents=True, exist_ok=True)
    n_train_files = n_val_files = 0
    link_counter = defaultdict(int)
    for rid in selected:
        split = "val" if rid in pilot_val else "train"
        for stem in video_meta[rid]["frames"]:
            jpg_src = image_train_dir / f"{stem}.jpg"
            lbl_src = label_train_dir / f"{stem}.txt"
            jpg_dst = out / "images" / split / f"{stem}.jpg"
            lbl_dst = out / "labels" / split / f"{stem}.txt"
            if jpg_src.exists():
                m = link_or_copy(jpg_src, jpg_dst, args.link_mode)
                link_counter[m] += 1
            if lbl_src.exists():
                shutil.copy2(str(lbl_src), str(lbl_dst))
            if split == "train": n_train_files += 1
            else: n_val_files += 1

    # 7. lp.yaml
    yaml_path = out / "lp.yaml"
    yaml_path.write_text(
        f"path: {out.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"\n"
        f"nc: 1\n"
        f"names:\n"
        f"  0: license_plate\n",
        encoding="utf-8",
    )

    # 8. summary
    summary = {
        "src": str(src), "out": str(out),
        "target": target,
        "small_ratio": args.small_ratio,
        "small_h_threshold": args.small_h_threshold,
        "val_ratio": args.val_ratio,
        "videos_total":  len(video_meta),
        "videos_small":  len(small_videos),
        "videos_normal": len(normal_videos),
        "picked_videos_small":  len(pick_small),
        "picked_videos_normal": len(pick_normal),
        "picked_frames_total":  n_picked_frames,
        "pilot_train_files": n_train_files,
        "pilot_val_files":   n_val_files,
        "pilot_train_videos": len(pilot_train),
        "pilot_val_videos":   len(pilot_val),
        "link_modes_used":   dict(link_counter),
    }
    (out / "pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 9. 출력
    print(f"\n=== Pilot 50K 요약 ===")
    print(f"  videos: {len(selected):,}  (small {len(pick_small):,} + normal {len(pick_normal):,})")
    print(f"  pilot_train: {n_train_files:,} ({len(pilot_train):,} videos)")
    print(f"  pilot_val:   {n_val_files:,} ({len(pilot_val):,} videos)")
    print(f"  link modes: {dict(link_counter)}")
    print(f"  saved → {out}/lp.yaml + pilot_summary.json")


if __name__ == "__main__":
    main()
