"""
AI-Hub 185 (CCTV 기반 차량정보) → YOLO format 변환.
1-class license_plate detector 학습용.

사용법:
  python tools/aihub_to_yolo.py \
      --src "D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터" \
      --out "D:/lp_yolo_aihub" \
      --dry_run --max_samples 5000 --vis_samples 200 \
      --link_mode hardlink

  python tools/aihub_to_yolo.py --src ... --out ... --full --link_mode hardlink

옵션:
  --src           AI-Hub root (01-1.정식개방데이터 의 부모)
  --out           출력 root
  --dry_run       subset 만 처리
  --max_samples   dry_run 처리 frame 수 (default 5000)
  --vis_samples   bbox 시각화 장수 (default 200)
  --link_mode     hardlink (default) | symlink | copy
                   hardlink → symlink → copy 자동 fallback
  --full          전체 처리 + group-aware split
  --frame_stride  같은 raw_data_ID 안에서 N frame 마다 1 (default 1 = 모두)
  --clamp_threshold  clamp 비율 stop 임계 (default 0.005)
  --val_ratio     full 모드 val 비율 (default 0.1)

산출:
  out/
    images/{train,val}/    (link or copy)
    labels/{train,val}/    (.txt)
    lp.yaml                # nc:1, names:{0:license_plate}
    splits/group_keys_*.json
    reports/
      convert_report.json
      bad_jsons.csv
      suspicious_bboxes.csv
      bbox_height_dist.csv
      group_key_stats.json
      vis_samples/         (200장 시각화)
"""
import sys, os, json, csv, re, random, shutil, argparse, time
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

NIDX_PAT = re.compile(r"_N(\d+)$")


# ---------- 파일 매칭 ----------
def find_jpg_label_pairs(src: Path):
    """
    src/01-1.정식개방데이터/{Training,Validation}/01.원천데이터/<TS_*|VS_*>/<jpg>
    src/01-1.정식개방데이터/{Training,Validation}/02.라벨링데이터/<TL_*|VL_*>/<json>
    Returns: list[(jpg_path, json_path, official_split)]
        official_split ∈ {'training','validation'}
    """
    base = src / "01-1.정식개방데이터"
    pairs = []
    folders_missing = []
    for split_name, jpg_prefix, json_prefix in (
        ("training",   "TS_", "TL_"),
        ("validation", "VS_", "VL_"),
    ):
        split_root = base / split_name.capitalize()
        if not split_root.exists():
            print(f"  [warn] {split_root} 없음, skip"); continue
        jpg_root  = split_root / "01.원천데이터"
        json_root = split_root / "02.라벨링데이터"
        for jpg_dir in sorted(jpg_root.iterdir() if jpg_root.exists() else []):
            if not jpg_dir.is_dir(): continue
            if not jpg_dir.name.startswith(jpg_prefix): continue
            json_dir = json_root / (json_prefix + jpg_dir.name[len(jpg_prefix):])
            if not json_dir.exists():
                folders_missing.append(json_dir); continue
            for jpg in jpg_dir.glob("*.jpg"):
                json_path = json_dir / f"{jpg.stem}.json"
                if json_path.exists():
                    pairs.append((jpg, json_path, split_name))
    return pairs, folders_missing


# ---------- bbox 변환 ----------
def parse_resolution(meta) -> tuple:
    s = meta.get("Raw_Data_Info", {}).get("resolution", "")
    parts = [p.strip() for p in s.replace(",", " ").split()]
    if len(parts) >= 2:
        try: return int(parts[0]), int(parts[1])
        except ValueError: return None
    return None


def yolo_lines_from_meta(meta, resolution):
    """
    Returns: (yolo_lines, n_clamped, n_zero_drop, raw_bboxes_for_report)
    Each yolo_line: "0 cx cy w h"  (class_id 0 = license_plate)
    """
    W, H = resolution
    lines = []
    n_clamped = 0; n_zero = 0
    raw_for_report = []
    for a in meta.get("Learning_Data_Info", {}).get("annotations", []):
        for lp in a.get("license_plate", []):
            bbox = lp.get("bbox")
            if not bbox or len(bbox) != 4: continue
            x, y, w, h = (float(v) for v in bbox)
            x0, y0, x1, y1 = x, y, x + w, y + h
            cx0, cy0 = x0, y0
            # clamp
            x0c = max(0.0, min(W - 1.0, x0))
            y0c = max(0.0, min(H - 1.0, y0))
            x1c = max(0.0, min(float(W), x1))
            y1c = max(0.0, min(float(H), y1))
            wc = x1c - x0c; hc = y1c - y0c
            clamped = (x0c != x0 or y0c != y0 or x1c != x1 or y1c != y1)
            if clamped: n_clamped += 1
            if wc <= 0 or hc <= 0:
                n_zero += 1
                raw_for_report.append({"reason": "zero_after_clamp",
                                        "orig": [x, y, w, h]})
                continue
            cx = (x0c + wc / 2) / W
            cy = (y0c + hc / 2) / H
            wn = wc / W
            hn = hc / H
            lines.append(f"0 {cx:.6f} {cy:.6f} {wn:.6f} {hn:.6f}")
            ar = wc / hc if hc > 0 else 0
            tier = ("tiny"   if hc < 12 else
                    "small"  if hc < 24 else
                    "medium" if hc < 40 else "large")
            raw_for_report.append({
                "h_px": hc, "w_px": wc, "aspect": ar, "tier": tier,
                "clamped": clamped,
            })
    return lines, n_clamped, n_zero, raw_for_report


# ---------- linking ----------
def link_or_copy(src: Path, dst: Path, mode: str) -> str:
    """Returns actual mode used."""
    if dst.exists():
        return "skip_exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "hardlink":
        try:
            os.link(str(src), str(dst))
            return "hardlink"
        except OSError:
            mode = "symlink"
    if mode == "symlink":
        try:
            os.symlink(str(src), str(dst))
            return "symlink"
        except OSError:
            mode = "copy"
    if mode == "copy":
        shutil.copy2(str(src), str(dst))
        return "copy"
    return "fail"


# ---------- group key 분석 ----------
def group_key_stats(samples):
    """samples: list of dicts with raw_data_ID, source_data_ID."""
    by_raw = defaultdict(list)
    for s in samples:
        by_raw[s["raw_data_ID"]].append(s["source_data_ID"])
    sizes = [len(v) for v in by_raw.values()]
    sizes.sort()
    median = sizes[len(sizes) // 2] if sizes else 0
    avg    = (sum(sizes) / len(sizes)) if sizes else 0

    # frame interval analysis
    frame_intervals = []
    seq_runs = 0          # raw_data_ID 안에서 인접 frame_idx (diff=1) 개수
    total_pairs = 0
    for raw, sids in by_raw.items():
        idxs = []
        for sid in sids:
            m = NIDX_PAT.search(sid)
            if m: idxs.append(int(m.group(1)))
        idxs.sort()
        for i in range(1, len(idxs)):
            d = idxs[i] - idxs[i - 1]
            if d > 0:
                frame_intervals.append(d)
                total_pairs += 1
                if d == 1: seq_runs += 1

    interval_counter = Counter(frame_intervals)
    return {
        "raw_data_id_unique": len(by_raw),
        "raw_data_id_size_avg":    round(avg, 2),
        "raw_data_id_size_median": median,
        "raw_data_id_size_max":    sizes[-1] if sizes else 0,
        "raw_data_id_size_min":    sizes[0]  if sizes else 0,
        "raw_data_id_size_p90":    sizes[int(len(sizes) * 0.9)] if sizes else 0,
        "frame_interval_pairs":    total_pairs,
        "frame_interval_sequential_pct": round(seq_runs / max(1, total_pairs) * 100, 2),
        "frame_interval_mode":     interval_counter.most_common(1)[0][0] if interval_counter else None,
        "frame_interval_top5":     interval_counter.most_common(5),
        "single_frame_videos":     sum(1 for s in sizes if s == 1),
    }


# ---------- 시각화 ----------
def vis_one(jpg_path: Path, lines: list, out_path: Path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(jpg_path).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype(r"C:/Windows/Fonts/malgun.ttf", 22)
    except OSError: font = ImageFont.load_default()
    for ln in lines:
        parts = ln.strip().split()
        if len(parts) != 5: continue
        _, cx, cy, w, h = map(float, parts)
        x0 = (cx - w / 2) * W; y0 = (cy - h / 2) * H
        x1 = (cx + w / 2) * W; y1 = (cy + h / 2) * H
        draw.rectangle((x0, y0, x1, y1), outline="cyan", width=4)
        draw.text((x0, max(0, y0 - 26)), "plate", fill="cyan", font=font,
                   stroke_width=2, stroke_fill="black")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=88)


# ---------- 메인 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--full",    action="store_true")
    ap.add_argument("--max_samples",  type=int, default=5000)
    ap.add_argument("--vis_samples",  type=int, default=200)
    ap.add_argument("--link_mode",    choices=["hardlink","symlink","copy"], default="hardlink")
    ap.add_argument("--frame_stride", type=int, default=1)
    ap.add_argument("--clamp_threshold", type=float, default=0.005)
    ap.add_argument("--val_ratio",    type=float, default=0.1)
    args = ap.parse_args()

    if not args.dry_run and not args.full:
        print("[error] --dry_run 또는 --full 중 하나 필요"); sys.exit(2)

    src = Path(args.src); out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = out / "reports"; rep.mkdir(exist_ok=True)
    (out / "splits").mkdir(exist_ok=True)
    (rep / "vis_samples").mkdir(exist_ok=True)

    print(f"[init] src={src}")
    print(f"[init] out={out}")
    print(f"[init] mode={'dry_run' if args.dry_run else 'full'}  link={args.link_mode}")

    # 1. 파일 매칭
    print("\n[1/5] 파일 매칭 ...")
    t0 = time.time()
    pairs, missing = find_jpg_label_pairs(src)
    print(f"  pairs found: {len(pairs):,}  missing json folders: {len(missing)}")

    # 2. dry_run 이면 sample, full 이면 전체
    if args.dry_run:
        rng = random.Random(42); rng.shuffle(pairs)
        pairs = pairs[: args.max_samples]
        print(f"  [dry_run] using first {len(pairs):,}")

    # 3. frame_stride
    if args.frame_stride > 1:
        # raw_data_ID 별로 묶고 stride 적용
        by_raw = defaultdict(list)
        for p in pairs: by_raw[p[0].stem.rsplit("_N", 1)[0]].append(p)
        kept = []
        for k, group in by_raw.items():
            group.sort(key=lambda x: x[0].stem)
            for i, p in enumerate(group):
                if i % args.frame_stride == 0: kept.append(p)
        pairs = kept
        print(f"  [stride={args.frame_stride}] kept {len(pairs):,}")

    # 4. 변환
    print(f"\n[2/5] JSON parse + YOLO 변환 ({len(pairs):,}장) ...")
    bad_jsons = []
    suspicious = []
    bbox_tier_counter = Counter()
    samples_meta = []                # for group key stats + vis
    n_total_bbox = 0
    n_clamped    = 0
    n_zero       = 0
    n_no_plate   = 0       # 라벨 안 되어있는 frame (negative)
    converted    = []      # list of (jpg, json, label_lines, raw_data_ID, official_split)
    t0 = time.time()
    for i, (jpg, jp, off_split) in enumerate(pairs):
        try:
            with open(jp, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            bad_jsons.append({"json": str(jp), "reason": str(e)[:120]})
            continue
        res = parse_resolution(meta)
        if not res:
            bad_jsons.append({"json": str(jp), "reason": "no_resolution"})
            continue

        lines, ncl, nzo, raw = yolo_lines_from_meta(meta, res)
        n_total_bbox += len(lines) + nzo
        n_clamped += ncl
        n_zero    += nzo
        if not lines:
            n_no_plate += 1
        for r in raw:
            tier = r.get("tier")
            if tier: bbox_tier_counter[tier] += 1
            ar = r.get("aspect", 0)
            if r.get("clamped") or (ar and (ar < 2.0 or ar > 7.0)) or r.get("reason"):
                suspicious.append({
                    "jpg": str(jpg),
                    "h_px": r.get("h_px", 0),
                    "w_px": r.get("w_px", 0),
                    "aspect": round(ar, 3) if ar else 0,
                    "tier": tier or "",
                    "clamped": int(r.get("clamped", False)),
                    "reason": r.get("reason", ""),
                })

        rdi = meta.get("Raw_Data_Info", {}).get("raw_data_ID", jpg.stem.rsplit("_N", 1)[0])
        sdi = meta.get("Source_Data_Info", {}).get("source_data_ID", jpg.stem)
        samples_meta.append({"raw_data_ID": rdi, "source_data_ID": sdi})
        converted.append((jpg, jp, lines, rdi, off_split))
        if (i + 1) % 5000 == 0:
            r = (i + 1) / max(1, time.time() - t0)
            print(f"  {i+1:,}/{len(pairs):,}  ({r:.0f}/s)")

    elapsed = time.time() - t0
    print(f"  변환 완료 {elapsed:.0f}s  bbox_total={n_total_bbox:,}  "
          f"clamped={n_clamped:,}  zero={n_zero:,}  no_plate_frames={n_no_plate:,}")

    # clamp 비율 검증
    if n_total_bbox > 0:
        clamp_ratio = n_clamped / n_total_bbox
        print(f"  clamp ratio: {clamp_ratio*100:.3f}%  (threshold {args.clamp_threshold*100:.2f}%)")
        if clamp_ratio > args.clamp_threshold:
            print(f"\n[STOP] clamp ratio 초과 → suspicious_bboxes.csv 확인 후 다시")

    # 5. split 결정 (full 이면 group-aware, dry_run 이면 train 만)
    print(f"\n[3/5] split + linking ...")
    if args.dry_run:
        split_assign = {rdi: "train" for rdi in {c[3] for c in converted}}
    else:
        rng = random.Random(42)
        all_groups = list({c[3] for c in converted})
        rng.shuffle(all_groups)
        n_val = max(1, int(round(len(all_groups) * args.val_ratio)))
        val_groups = set(all_groups[:n_val])
        split_assign = {g: ("val" if g in val_groups else "train") for g in all_groups}

    link_counter = Counter()
    n_label_files = 0
    by_split = defaultdict(int)
    for jpg, jp, lines, rdi, off in converted:
        split = split_assign[rdi]
        by_split[split] += 1
        # image link
        img_dst = out / "images" / split / jpg.name
        m = link_or_copy(jpg, img_dst, args.link_mode)
        link_counter[m] += 1
        # label
        lbl_dst = out / "labels" / split / f"{jpg.stem}.txt"
        lbl_dst.parent.mkdir(parents=True, exist_ok=True)
        with open(lbl_dst, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            if lines: f.write("\n")
        n_label_files += 1

    print(f"  split: {dict(by_split)}")
    print(f"  link mode 사용: {dict(link_counter)}")

    # group key 통계
    print(f"\n[4/5] group key 통계 ...")
    gks = group_key_stats(samples_meta)
    print(f"  raw_data_ID unique: {gks['raw_data_id_unique']:,}")
    print(f"  per-raw frames avg/median/max: "
          f"{gks['raw_data_id_size_avg']:.1f}/{gks['raw_data_id_size_median']}/"
          f"{gks['raw_data_id_size_max']}")
    print(f"  sequential frame ratio (diff=1): "
          f"{gks['frame_interval_sequential_pct']:.1f}%")
    print(f"  frame interval top5: {gks['frame_interval_top5']}")

    # 6. vis_samples
    print(f"\n[5/5] bbox 시각화 ({args.vis_samples}장) ...")
    rng = random.Random(7)
    vis_pool = [c for c in converted if c[2]]   # 라벨 있는 것만
    if len(vis_pool) > args.vis_samples:
        vis_pool = rng.sample(vis_pool, args.vis_samples)
    for jpg, jp, lines, rdi, off in vis_pool:
        try:
            vis_one(jpg, lines, rep / "vis_samples" / f"{jpg.stem}.jpg")
        except Exception as e:
            print(f"  [warn] vis {jpg.name}: {e}")

    # 7. 보고서
    convert_report = {
        "src": str(src), "out": str(out),
        "mode": "dry_run" if args.dry_run else "full",
        "link_mode_request": args.link_mode,
        "link_mode_actual":  dict(link_counter),
        "frame_stride":      args.frame_stride,
        "pairs_found":       len(pairs),
        "bad_jsons":         len(bad_jsons),
        "n_total_bbox":      n_total_bbox,
        "n_clamped":         n_clamped,
        "n_zero_drop":       n_zero,
        "n_no_plate_frames": n_no_plate,
        "clamp_ratio_pct":   round((n_clamped / max(1, n_total_bbox)) * 100, 4),
        "by_split":          dict(by_split),
        "bbox_tiers":        dict(bbox_tier_counter),
        "elapsed_s":         round(elapsed, 1),
    }
    (rep / "convert_report.json").write_text(
        json.dumps(convert_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (rep / "group_key_stats.json").write_text(
        json.dumps(gks, ensure_ascii=False, indent=2), encoding="utf-8")

    # bad_jsons.csv
    with open(rep / "bad_jsons.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["json","reason"]); w.writeheader()
        w.writerows(bad_jsons)

    # suspicious_bboxes.csv
    with open(rep / "suspicious_bboxes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["jpg","h_px","w_px","aspect","tier","clamped","reason"])
        w.writeheader(); w.writerows(suspicious)

    # bbox_height_dist.csv
    with open(rep / "bbox_height_dist.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["tier", "count"])
        for k in ("tiny","small","medium","large"):
            w.writerow([k, bbox_tier_counter.get(k, 0)])

    # lp.yaml
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

    # 8. 요약
    print(f"\n=== 요약 ===")
    print(f"  pairs:          {len(pairs):,}")
    print(f"  bad_jsons:      {len(bad_jsons)}")
    print(f"  bbox_total:     {n_total_bbox:,}")
    print(f"    clamped:      {n_clamped} ({convert_report['clamp_ratio_pct']:.3f}%)")
    print(f"    zero_drop:    {n_zero}")
    print(f"  no_plate frames: {n_no_plate}")
    print(f"  bbox tiers:     {dict(bbox_tier_counter)}")
    print(f"  splits:         {dict(by_split)}")
    print(f"  link modes:     {dict(link_counter)}")
    print(f"  saved:")
    print(f"    {yaml_path}")
    print(f"    {rep}/convert_report.json")
    print(f"    {rep}/group_key_stats.json")
    print(f"    {rep}/vis_samples/  ({len(vis_pool)} 장)")
    print(f"    {rep}/bad_jsons.csv  /  suspicious_bboxes.csv  /  bbox_height_dist.csv")


if __name__ == "__main__":
    main()
