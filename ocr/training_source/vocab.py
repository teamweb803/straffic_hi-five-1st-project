"""
Phase 1 #2 — Vocab + Rare 산출
Real (train) + Synth (manifest accepted=1) 전체 라벨 기반.
출력:
  artifacts/vocab.json         {chars, num_classes, char_freq, n_real, n_synth}
  artifacts/rare_chars.json    {rare_chars, from_freq_quantile, from_explicit}
"""
import sys, json, csv
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from . import config as C


def collect_real_labels():
    out = []
    for d in C.REAL_DIRS:
        if not d.exists(): continue
        for f in d.glob("*.jpg"):
            lab = C.label_from_stem(f.stem)
            if lab:
                out.append((str(f), lab, "real"))
    return out


def collect_synth_labels():
    out = []
    if not C.SYNTH_MANIFEST.exists(): return out
    with open(C.SYNTH_MANIFEST, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if r["accepted"] != "1": continue
            out.append((r["path"], r["label"], r["source"]))   # source=ohjj/yakhyo
    return out


def build_vocab():
    real = collect_real_labels()
    synth = collect_synth_labels()
    print(f"[vocab] real={len(real):,}  synth={len(synth):,}")

    counter = Counter()
    for _, lab, _ in real + synth:
        counter.update(lab)

    # Valid set 으로 강제 — 데이터 외부 문자가 발견돼도 vocab 변동 없음
    chars = sorted(C.VALID_CHAR_SET)
    dropped = {c: counter[c] for c in counter if c not in C.VALID_CHAR_SET}
    if dropped:
        print(f"[vocab] dropped (out-of-valid): {dropped}")
    total = sum(counter[c] for c in chars)

    # 한글만 빈도 순 정렬해서 quantile 계산 (digits 제외 — 의미 없음)
    hangul_freq = sorted(
        [(c, counter[c]) for c in chars if c in C.VALID_HANGUL],
        key=lambda x: x[1],
    )
    cutoff = int(len(hangul_freq) * C.LOW_FREQ_RARE_QUANTILE)
    low_freq_rare = sorted({c for c, _ in hangul_freq[:cutoff]}.union(
        set(C.LOW_FREQ_RARE_EXPLICIT)
    ).intersection(set(chars)))

    confusable = sorted(set(C.CONFUSABLE_HANGUL).intersection(set(chars)))

    vocab = {
        "chars": chars,
        "num_classes": len(chars) + 1,
        "char_freq": dict(counter),
        "total_chars": total,
        "n_real": len(real),
        "n_synth": len(synth),
    }
    rare_payload = {
        "low_freq_rare":      low_freq_rare,
        "low_freq_quantile":  C.LOW_FREQ_RARE_QUANTILE,
        "confusable_hangul":  confusable,
        "confusable_pairs":   [list(p) for p in C.CONFUSABLE_PAIRS],
        # 하위 호환: 'rare_chars' = low_freq_rare 만 (sample weight 적용 대상)
        "rare_chars":         low_freq_rare,
    }

    with open(C.VOCAB_PATH, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    with open(C.RARE_PATH, "w", encoding="utf-8") as f:
        json.dump(rare_payload, f, ensure_ascii=False, indent=2)

    print(f"[vocab] chars={len(chars)}  num_classes={vocab['num_classes']}")
    print(f"[low_freq_rare]   {len(low_freq_rare)}자: {''.join(low_freq_rare)}")
    print(f"[confusable]      {len(confusable)}자: {''.join(confusable)}")
    print(f"[vocab] saved → {C.VOCAB_PATH}")
    print(f"[rare]  saved → {C.RARE_PATH}")
    return vocab, rare_payload


def load_vocab():
    with open(C.VOCAB_PATH, encoding="utf-8") as f:
        v = json.load(f)
    chars = v["chars"]
    char2idx = {c: i + 1 for i, c in enumerate(chars)}
    idx2char = {i + 1: c for i, c in enumerate(chars)}
    idx2char[0] = ""
    return chars, char2idx, idx2char, v["num_classes"]


def load_rare():
    """sample weight 적용용 — low_freq_rare 만 반환 (= 'rare_chars' alias)"""
    with open(C.RARE_PATH, encoding="utf-8") as f:
        return json.load(f)["low_freq_rare"]


def load_confusable():
    with open(C.RARE_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("confusable_hangul", []), [tuple(p) for p in d.get("confusable_pairs", [])]


if __name__ == "__main__":
    build_vocab()
