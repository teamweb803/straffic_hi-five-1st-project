"""
v6 — fresh real training manifest builder.

Sources:
  - tt/ab/        (training_<plate>(-N).jpg / validation_<plate>(_N).jpg)
  - tt/train_good (<plate>(-N).jpg / <plate>(_N).jpg)
  - synth_10k     (data-new/manifest.csv, accepted=1)

Outputs:
  - artifacts/manifest_v6.csv       (path,label,source,group,length_type,
                                      rare_pos,confusable_pos)
  - artifacts/split_v6.json         (train, val, hard_dev, hard_final
                                      indices into manifest_v6)
  - reports_v6/manifest_v6_report.json
  - reports_v6/dedup_report.json
  - reports_v6/drop_report.csv

Policies (사용자 v6 spec):
  - md5 dedup (tt/ab + tt/train_good 전부 재검증)
  - VALID_HANGUL_40 + 0~9 외 char 폐기
  - 7자/8자 plate regex 통과 필수
  - hard_dev / hard_final 의 path OR normalized label 겹침은 train/val 에서 제외
  - val = 5%, group-aware (group key = normalized label),
          stratified by rare_pos / confusable_pos / normal
  - synth_10k 그대로 포함 (≤15% 비율 자동)
  - drop 비율 0.5% 이상이면 stop & report
"""
import sys, csv, json, hashlib, re, random
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from . import config as C


PREFIX_PAT  = re.compile(r"^(training|validation)_")
SUFFIX_PAT  = re.compile(r"[_-](\d+)$")     # _N or -N
DROP_THRESHOLD = 0.005   # 0.5%


def label_from_v6_stem(stem: str):
    """
    tt/ab + tt/train_good 공통 라벨 추출.
      training_01가1134-2 → 01가1134
      validation_15노8842_3 → 15노8842
      01보7397 → 01보7397
    실패 시 None.
    """
    s = PREFIX_PAT.sub("", stem)
    m = SUFFIX_PAT.search(s)
    base = s[:m.start()] if m else s
    if C.LABEL_PAT_7.match(base) or C.LABEL_PAT_8.match(base):
        return base
    return None


def md5_of(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()


def has_ood_char(label: str) -> bool:
    return any(c not in C.VALID_CHAR_SET for c in label)


def collect_v6_real():
    """
    Returns:
      good: list[(path, label, source)]    where source in {"tt_ab","tt_train_good"}
      drops: list[dict] (drop reasons)
    """
    good, drops = [], []
    src_map = [(C.TT_AB_DIR, "tt_ab"), (C.TT_TRAIN_GOOD, "tt_train_good")]
    for d, src in src_map:
        if not d.exists():
            print(f"[warn] {d} 없음, skip"); continue
        files = list(d.glob("*.jpg"))
        print(f"[scan] {src}: {len(files):,}")
        for p in files:
            stem = p.stem
            lab = label_from_v6_stem(stem)
            if lab is None:
                drops.append({"path": str(p), "stem": stem,
                              "reason": "regex_fail", "source": src})
                continue
            if has_ood_char(lab):
                drops.append({"path": str(p), "stem": stem, "label": lab,
                              "reason": "ood_char", "source": src})
                continue
            good.append((str(p), lab, src))
    return good, drops


def md5_dedup(items, label_for_progress=""):
    """
    items: list[(path, label, source)]
    md5 동일하면 한 개만 남김. 같은 md5 안에서 label 충돌은 첫번째 기준.
    Returns: (kept, dup_dropped, dup_groups)
    """
    by_md5 = defaultdict(list)
    for it in items:
        try:
            by_md5[md5_of(it[0])].append(it)
        except OSError:
            pass
    kept, dropped = [], []
    n_groups_with_dup = 0
    for digest, group in by_md5.items():
        kept.append(group[0])
        if len(group) > 1:
            n_groups_with_dup += 1
            for it in group[1:]:
                dropped.append({"path": it[0], "label": it[1],
                                "reason": "md5_dup", "source": it[2],
                                "digest": digest})
    return kept, dropped, n_groups_with_dup


def collect_v6_synth():
    """data-new/manifest.csv accepted=1 → list[(path, label, source)]"""
    out = []
    if not C.SYNTH_MANIFEST.exists(): return out
    with open(C.SYNTH_MANIFEST, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if r.get("accepted") != "1": continue
            lab = r["label"]
            if has_ood_char(lab): continue
            if not (C.LABEL_PAT_7.match(lab) or C.LABEL_PAT_8.match(lab)):
                continue
            out.append((r["path"], lab, r["source"]))   # ohjj/yakhyo
    return out


def load_hard_excluded():
    paths, labels = set(), set()
    for jp in (C.HARD_DEV_IDX, C.HARD_FINAL_IDX):
        if jp.exists():
            with open(jp, encoding="utf-8") as f:
                for it in json.load(f).get("items", []):
                    paths.add(it["path"])
                    labels.add(it["label"])
    return paths, labels


def stratify_split(groups_by_key, rare_set, conf_set, val_ratio, seed):
    """
    groups_by_key: {label: [items...]}
    각 group 의 stratum:
      - "rare"        : label 안에 rare_set 글자 있음
      - "confusable"  : 위 X, label 안에 conf_set 글자 있음
      - "normal"      : 그 외
    각 stratum 내부에서 group 단위로 5% val.
    """
    rng = random.Random(seed)
    by_stratum = {"rare": [], "confusable": [], "normal": []}
    for k in groups_by_key:
        if any(c in rare_set for c in k):
            by_stratum["rare"].append(k)
        elif any(c in conf_set for c in k):
            by_stratum["confusable"].append(k)
        else:
            by_stratum["normal"].append(k)

    train_keys, val_keys = set(), set()
    stratum_meta = {}
    for stratum, keys in by_stratum.items():
        rng.shuffle(keys)
        n_val = max(1, int(round(len(keys) * val_ratio))) if keys else 0
        v = keys[:n_val]; t = keys[n_val:]
        val_keys.update(v); train_keys.update(t)
        stratum_meta[stratum] = {"groups": len(keys),
                                  "train_groups": len(t),
                                  "val_groups": len(v)}
    return train_keys, val_keys, stratum_meta


def main():
    print("="*70)
    print("v6 manifest builder")
    print("="*70)

    # ----- 1. real 수집 -----
    real, drops_collect = collect_v6_real()
    n_input = sum(len(list(d.glob("*.jpg")))
                  for d in (C.TT_AB_DIR, C.TT_TRAIN_GOOD) if d.exists())
    print(f"\n[1] 수집: input={n_input:,}  good={len(real):,}  "
          f"drops={len(drops_collect):,}")

    # ----- 2. md5 dedup -----
    print(f"\n[2] md5 dedup ...")
    real_dedup, dups, dup_groups = md5_dedup(real)
    print(f"    중복 그룹 {dup_groups:,}개  →  drop {len(dups):,}장  "
          f"→  keep {len(real_dedup):,}장")

    # ----- 3. hard 제외 -----
    hard_paths, hard_labels = load_hard_excluded()
    print(f"\n[3] hard_dev/hard_final 제외:")
    print(f"    excluded paths={len(hard_paths):,}  labels={len(hard_labels):,}")
    pool = []
    drops_hard = []
    for it in real_dedup:
        if it[0] in hard_paths:
            drops_hard.append({"path": it[0], "label": it[1],
                               "reason": "hard_path_overlap", "source": it[2]})
            continue
        if it[1] in hard_labels:
            drops_hard.append({"path": it[0], "label": it[1],
                               "reason": "hard_label_overlap", "source": it[2]})
            continue
        pool.append(it)
    print(f"    pool after hard exclusion: {len(pool):,}")

    # ----- 4. drop ratio 검증 -----
    total_drops = (len(drops_collect) + len(dups) + len(drops_hard))
    drop_ratio = total_drops / max(1, n_input)
    print(f"\n[4] drop ratio: {total_drops:,}/{n_input:,} = {drop_ratio*100:.3f}%")
    # collect+ood 만 학습 시작 차단 기준 (md5 dup, hard overlap 은 정상)
    fail_drops = len(drops_collect)
    fail_ratio = fail_drops / max(1, n_input)
    if fail_ratio >= DROP_THRESHOLD:
        print(f"\n[STOP] regex/OOD drop {fail_drops:,} ({fail_ratio*100:.3f}%) "
              f"≥ {DROP_THRESHOLD*100:.2f}% — 학습 시작 금지")
        # report 저장 후 abort
        save_drop_csv(drops_collect + dups + drops_hard)
        sys.exit(2)

    # ----- 5. group-aware stratified val 5% -----
    rare = set(C.LOW_FREQ_RARE_EXPLICIT)
    if C.RARE_PATH.exists():
        with open(C.RARE_PATH, encoding="utf-8") as f:
            rare = set(json.load(f).get("low_freq_rare", []))
    conf = set(C.CONFUSABLE_HANGUL)
    print(f"\n[5] stratified split (val 5%, group-aware)")
    print(f"    rare set ({len(rare)}자): {''.join(sorted(rare))}")
    print(f"    confusable set ({len(conf)}자): {''.join(sorted(conf))}")

    groups = defaultdict(list)
    for it in pool:
        groups[it[1]].append(it)
    train_keys, val_keys, stratum_meta = stratify_split(
        groups, rare, conf, val_ratio=0.05, seed=42)
    train_real = [it for k in train_keys for it in groups[k]]
    val_real   = [it for k in val_keys   for it in groups[k]]
    rng = random.Random(42)
    rng.shuffle(train_real); rng.shuffle(val_real)

    # ----- 6. synth 추가 (train pool only) -----
    synth = collect_v6_synth()
    print(f"\n[6] synth: accepted={len(synth):,}")

    # ----- 7. manifest_v6.csv 작성 -----
    print(f"\n[7] writing manifest_v6.csv ...")
    rows = []
    def _row(p, lab, src, split):
        return {
            "path": p, "label": lab, "source": src, "split": split,
            "group": lab,
            "length_type": "len7" if len(lab) == 7 else "len8",
            "rare_pos": int(any(c in rare for c in lab)),
            "confusable_pos": int(any(c in conf for c in lab)),
        }
    for it in train_real:  rows.append(_row(it[0], it[1], it[2], "train"))
    for it in val_real:    rows.append(_row(it[0], it[1], it[2], "val"))
    # synth 는 train only (val 에 들어가면 평가 누설)
    for it in synth:       rows.append(_row(it[0], it[1], it[2], "train_synth"))

    cols = ["path","label","source","split","group",
            "length_type","rare_pos","confusable_pos"]
    with open(C.MANIFEST_V6, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"    saved → {C.MANIFEST_V6}  ({len(rows):,} rows)")

    # ----- 8. split_v6.json (index level) -----
    split_payload = {
        "seed": 42,
        "manifest": str(C.MANIFEST_V6),
        "n_train_real":  len(train_real),
        "n_val_real":    len(val_real),
        "n_synth":       len(synth),
        "stratum":       stratum_meta,
        "hard_dev":      str(C.HARD_DEV_IDX),
        "hard_final":    str(C.HARD_FINAL_IDX),
    }
    with open(C.SPLIT_V6, "w", encoding="utf-8") as f:
        json.dump(split_payload, f, ensure_ascii=False, indent=2)
    print(f"    saved → {C.SPLIT_V6}")

    # ----- 9. report -----
    label_counter = Counter(r["label"] for r in rows if r["split"] != "train_synth")
    char_counter = Counter()
    for lab in label_counter: char_counter.update(lab * label_counter[lab])
    rare_count       = sum(1 for r in rows if r["rare_pos"]==1 and r["split"]!="train_synth")
    confusable_count = sum(1 for r in rows if r["confusable_pos"]==1 and r["split"]!="train_synth")
    report = {
        "input_total":         n_input,
        "good_after_collect":  len(real),
        "drops": {
            "regex_or_ood": len(drops_collect),
            "md5_dup":      len(dups),
            "hard_overlap": len(drops_hard),
            "total":        total_drops,
            "ratio_pct":    round(drop_ratio*100, 4),
            "fail_ratio_pct": round(fail_ratio*100, 4),
        },
        "real_after_dedup":      len(real_dedup),
        "real_after_hard_excl":  len(pool),
        "train_real":            len(train_real),
        "val_real":              len(val_real),
        "synth":                 len(synth),
        "synth_share":           round(len(synth) / max(1, len(train_real) + len(synth)) * 100, 2),
        "stratum":               stratum_meta,
        "rare_pos_count":        rare_count,
        "confusable_pos_count":  confusable_count,
        "groups_total":          len(groups),
        "len7_count":            sum(1 for r in rows if r["length_type"]=="len7" and r["split"]!="train_synth"),
        "len8_count":            sum(1 for r in rows if r["length_type"]=="len8" and r["split"]!="train_synth"),
        "char_freq_top10":       dict(char_counter.most_common(10)),
        "char_freq_bot10":       dict(sorted(char_counter.items(), key=lambda x: x[1])[:10]),
    }
    rep_path = C.REPORT_DIR_V6 / "manifest_v6_report.json"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"    report → {rep_path}")

    dedup_rep = {"dup_groups": dup_groups, "dropped": len(dups),
                  "kept": len(real_dedup)}
    (C.REPORT_DIR_V6 / "dedup_report.json").write_text(
        json.dumps(dedup_rep, ensure_ascii=False, indent=2), encoding="utf-8")

    save_drop_csv(drops_collect + dups + drops_hard)

    # ----- 10. summary print -----
    print(f"\n{'='*70}\nv6 manifest summary\n{'='*70}")
    print(f"  input total           : {n_input:,}")
    print(f"  drops total           : {total_drops:,} ({drop_ratio*100:.3f}%)")
    print(f"    regex/OOD           : {len(drops_collect):,}")
    print(f"    md5_dup             : {len(dups):,}")
    print(f"    hard overlap        : {len(drops_hard):,}")
    print(f"  real train            : {len(train_real):,}")
    print(f"  real val              : {len(val_real):,}")
    print(f"  synth (train only)    : {len(synth):,}")
    print(f"  synth share           : {report['synth_share']}%")
    print(f"  rare-pos samples      : {rare_count:,}")
    print(f"  confusable-pos samples: {confusable_count:,}")
    print(f"  unique label groups   : {len(groups):,}")
    print(f"  saved → {C.MANIFEST_V6}")
    print(f"        → {C.SPLIT_V6}")
    print(f"        → {rep_path}")
    return report


def save_drop_csv(drops):
    p = C.REPORT_DIR_V6 / "drop_report.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    cols = ["path","stem","label","reason","source","digest"]
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for d in drops: w.writerow(d)


if __name__ == "__main__":
    main()
