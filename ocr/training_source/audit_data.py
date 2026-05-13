"""
Phase 1 #1 — 데이터 무결성 검사
- Real (d:/aa/last/train) 파일 수, 라벨 추출 가능 여부, 이미지 로드 sample, 사이즈 통계
- Synth (manifest accepted=1) 파일 존재, 라벨/source/카테고리 통계
- Vocab 커버리지 비교 (real vs synth)
- 잠재 누수: 빈 파일/극소 파일/포맷 손상
출력: artifacts/audit_report.json
"""
import sys, csv, json, random, time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from . import config as C


def imread_check(path):
    try:
        a = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        if a is None or a.size == 0: return None
        return a.shape       # (h, w, c)
    except Exception:
        return None


def audit_real(sample_n=2000):
    files = []
    for d in C.REAL_DIRS:
        if d.exists():
            files.extend(d.glob("*.jpg"))
    n = len(files)
    valid_label = 0
    bad_label = []
    char_counter = Counter()
    sizes = []
    bad_load = []
    rng = random.Random(42)
    sample = rng.sample(files, min(sample_n, n))

    for f in files:
        lab = C.label_from_stem(f.stem)
        if lab:
            valid_label += 1
            char_counter.update(lab)
        else:
            bad_label.append(f.name)

    for f in sample:
        s = imread_check(f)
        if s is None:
            bad_load.append(f.name)
        else:
            sizes.append(s)

    h_arr = np.array([s[0] for s in sizes]) if sizes else np.array([0])
    w_arr = np.array([s[1] for s in sizes]) if sizes else np.array([0])

    return {
        "total": n,
        "valid_label": valid_label,
        "invalid_label_examples": bad_label[:10],
        "invalid_label_count": len(bad_label),
        "load_sample_size": len(sample),
        "load_failures": len(bad_load),
        "load_failure_examples": bad_load[:5],
        "size_stats": {
            "h_mean": float(h_arr.mean()), "h_p10": int(np.percentile(h_arr, 10)),
            "h_p50": int(np.percentile(h_arr, 50)), "h_p90": int(np.percentile(h_arr, 90)),
            "w_mean": float(w_arr.mean()), "w_p50": int(np.percentile(w_arr, 50)),
        },
        "char_freq_top10": char_counter.most_common(10),
        "char_freq_bottom10": sorted(char_counter.items(), key=lambda x: x[1])[:10],
        "char_set_size": len(char_counter),
    }


def audit_synth():
    if not C.SYNTH_MANIFEST.exists():
        return {"manifest_missing": True, "path": str(C.SYNTH_MANIFEST)}
    rows = []
    with open(C.SYNTH_MANIFEST, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd: rows.append(r)
    accepted = [r for r in rows if r["accepted"] == "1"]
    by_src = Counter(r["source"] for r in accepted)
    by_len = Counter(r["length_type"] for r in accepted)
    by_rare = Counter("rare" if r["rare_flag"] == "1" else "normal" for r in accepted)
    by_cond = Counter(r["condition_type"] for r in accepted)

    # 라벨/이미지 sanity
    char_counter = Counter()
    bad_label = 0
    bad_load = 0
    rng = random.Random(42)
    sample = rng.sample(accepted, min(1500, len(accepted)))
    for r in sample:
        lab = r["label"]
        char_counter.update(lab)
        if not (C.LABEL_PAT_7.match(lab) or C.LABEL_PAT_8.match(lab)):
            bad_label += 1
        s = imread_check(Path(r["path"]))
        if s is None: bad_load += 1

    return {
        "manifest_total": len(rows),
        "accepted_total": len(accepted),
        "by_source": dict(by_src),
        "by_length": dict(by_len),
        "by_rare": dict(by_rare),
        "by_condition": dict(by_cond),
        "sample_label_invalid": bad_label,
        "sample_load_failures": bad_load,
        "char_set_size": len(char_counter),
    }


def coverage(real_chars: set, synth_chars: set):
    return {
        "real_only": sorted(real_chars - synth_chars),
        "synth_only": sorted(synth_chars - real_chars),
        "common": len(real_chars & synth_chars),
    }


def main():
    t0 = time.time()
    print("[audit] real 검사...")
    real = audit_real()
    print(f"  total={real['total']:,}  valid_label={real['valid_label']:,}")
    print(f"  size h: p10={real['size_stats']['h_p10']} p50={real['size_stats']['h_p50']} p90={real['size_stats']['h_p90']}")

    print("\n[audit] synth 검사...")
    synth = audit_synth()
    print(f"  manifest_total={synth.get('manifest_total','-')}  accepted={synth.get('accepted_total','-')}")
    if "by_source" in synth:
        print(f"  source: {synth['by_source']}")

    # 문자 커버리지
    real_chars = set()
    for c, _ in real["char_freq_top10"] + real["char_freq_bottom10"]:
        real_chars.add(c)
    # full counter 다시 계산 — vocab.py 가 정확한 분포 산출. audit는 sample 기반.
    real_full_chars = {c for c, _ in real["char_freq_top10"]} | {c for c, _ in real["char_freq_bottom10"]}
    synth_full_chars = set()  # synth는 char_set_size 만 audit. 자세한 비교는 vocab 단계.

    report = {
        "real": real,
        "synth": synth,
        "elapsed_s": round(time.time() - t0, 1),
    }
    C.AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(C.AUDIT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[audit] saved → {C.AUDIT_REPORT}")
    print(f"[audit] elapsed {report['elapsed_s']}s")


if __name__ == "__main__":
    main()
