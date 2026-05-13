"""
3-run 재현성 검증 — per-seed 디렉토리.
- seed 별 best.pt 가 이미 존재하면 train 스킵 (재사용)
- eval_final 항상 갱신
- summary: operational_hard_score 주, hard_overall/hard_no_small/category 부

판단:
  mean operational_hard_score ≥ 0.987     : 목표 달성
  mean 0.980~0.987                         : 배포 후보 + 오답 분석
  std  ≤ 0.001  (=0.10pp)                  : 안정
  std  > 0.0015 (=0.15pp)                  : seed 안정성 검토
"""
import argparse, json, subprocess, sys
from pathlib import Path
from statistics import mean, stdev

sys.stdout.reconfigure(encoding="utf-8")

from . import config as C


def _run_tolerant(cmd, label, success_check):
    """
    Python 정상 종료 후에도 Windows 가 STATUS_STACK_BUFFER_OVERRUN(0xC0000409)
    같은 비정상 종료 코드를 반환하는 경우가 있음. success_check() 가 True 면
    rc != 0 이라도 정상 처리.
    """
    print(f"\n===== {label} =====")
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        return
    if success_check():
        print(f"[warn] {label} rc={rc} 비정상 종료지만 산출물 확인 → 정상 처리")
        return
    raise RuntimeError(f"{label} 실패 rc={rc} (산출물 미확인)")


def run_train(seed: int, force: bool):
    paths = C.seed_paths(seed)
    if paths["best_pt"].exists() and not force:
        print(f"\n===== seed {seed} train SKIP (best.pt 존재: {paths['best_pt']}) =====")
        return
    cmd = [sys.executable, "-m", "v5.train", "--seed", str(seed)]
    _run_tolerant(cmd, f"seed {seed} train",
                  success_check=lambda: paths["best_pt"].exists())


def run_eval_final(seed: int):
    paths = C.seed_paths(seed)
    cmd = [sys.executable, "-m", "v5.eval_final", "--seed", str(seed)]
    _run_tolerant(cmd, f"seed {seed} eval_final",
                  success_check=lambda: paths["eval_json"].exists())


def load_final(seed: int):
    p = C.seed_paths(seed)["eval_json"]
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_metrics(seed: int):
    p = C.seed_paths(seed)["metrics_json"]
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def best_epoch_info(metrics_log):
    bests = [e for e in metrics_log if e.get("is_best")]
    return bests[-1] if bests else {}


def stat_block(values, label):
    vals = [v for v in values if v is not None]
    if not vals:
        return {"mean": None, "std": None, "all": values, "label": label}
    return {
        "mean": mean(vals),
        "std":  stdev(vals) if len(vals) > 1 else 0.0,
        "all":  values,
        "label": label,
    }


def main(force_retrain=False, skip_train_seeds=()):
    seeds = C.SEEDS_3RUN
    skip_set = set(skip_train_seeds)
    for s in seeds:
        if s in skip_set:
            print(f"\n===== seed {s} train SKIP (사용자 지정) =====")
        else:
            run_train(s, force=force_retrain)
        run_eval_final(s)

    # ---- 집계 ----
    runs = []
    for s in seeds:
        ev = load_final(s)
        m = load_metrics(s)
        if ev is None:
            print(f"[warn] seed {s} eval_final 누락"); continue
        be = best_epoch_info(m)
        runs.append((s, ev, be))

    if not runs:
        print("[error] no runs"); return

    overall   = [r[1]["overall"]["greedy"] for r in runs]
    op_score  = [r[1].get("operational_hard_score") for r in runs]
    no_small  = [r[1].get("hard_without_small", {}).get("acc") for r in runs]
    rare_v    = [r[1].get("rare") for r in runs]
    confus    = [r[1].get("confusable") for r in runs]
    ece_v     = [r[1].get("ece") for r in runs]
    n_errs    = [r[1].get("n_errors") for r in runs]
    best_ep   = [r[2].get("epoch") for r in runs]
    best_comp = [r[2].get("comp_adj", r[2].get("comp")) for r in runs]
    cats = ("small_plate", "motion_blur", "night", "crop_cut", "skew", "rare")
    cat_vals = {c: [r[1]["categories"].get(c, {}).get("acc") for r in runs] for c in cats}

    # ---- confusable pair 별 오인 합산 (seed 합계) ----
    pair_agg = {}
    for s, ev, _ in runs:
        for k, d in (ev.get("conf_pair_errors") or {}).items():
            row = pair_agg.setdefault(k, {"a_to_b": 0, "b_to_a": 0,
                                           "pair_samples": 0, "per_seed": {}})
            row["a_to_b"]     += d.get("a_to_b", 0)
            row["b_to_a"]     += d.get("b_to_a", 0)
            row["pair_samples"] += d.get("total_pair_samples", 0)
            row["per_seed"][s] = (d.get("a_to_b", 0), d.get("b_to_a", 0))

    summary = {
        "seeds": [s for s, _, _ in runs],
        "operational_hard_score": stat_block(op_score, "operational_hard_score"),
        "hard_final_overall":     stat_block(overall, "hard_final_overall"),
        "hard_without_small":     stat_block(no_small, "hard_without_small"),
        "rare":                   stat_block(rare_v, "rare"),
        "confusable":             stat_block(confus, "confusable"),
        "ece":                    stat_block(ece_v, "ece"),
        "categories":             {c: stat_block(cat_vals[c], c) for c in cats},
        "best_epoch":             {"all": best_ep},
        "composite_score":        stat_block(best_comp, "composite_score"),
        "n_errors":               {"all": n_errs},
        "operational_weights":    C.OPERATIONAL_HARD_WEIGHTS,
        "confusable_pair_errors_3seed": pair_agg,
    }
    out = C.LOG_DIR / "3run_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 출력 ----
    def fmt(b):
        if b["mean"] is None: return "n/a"
        all_str = "[" + ", ".join(f"{v:.4f}" if v is not None else "None" for v in b["all"]) + "]"
        return f"mean={b['mean']:.4f}  std={b['std']:.4f}  vals={all_str}"

    print("\n===== 3-run 요약 =====")
    print(f"  seeds: {summary['seeds']}")
    print(f"  best_epoch: {best_ep}")
    print(f"  n_errors:   {n_errs}")
    print(f"  composite_score        : {fmt(summary['composite_score'])}")
    print(f"\n  operational_hard_score : {fmt(summary['operational_hard_score'])}  ⭐ 주")
    print(f"  hard_final_overall     : {fmt(summary['hard_final_overall'])}")
    print(f"  hard_without_small     : {fmt(summary['hard_without_small'])}")
    print(f"  rare                   : {fmt(summary['rare'])}")
    print(f"  confusable             : {fmt(summary['confusable'])}")
    print(f"  ece                    : {fmt(summary['ece'])}")
    print(f"\n  [categories — small_plate 보조]")
    for c in cats:
        flag = "  (보조)" if c == "small_plate" else ""
        print(f"    {c:>11s}: {fmt(summary['categories'][c])}{flag}")

    print(f"\n  [confusable pair errors — 3-seed 합계]")
    if pair_agg:
        for k, d in sorted(pair_agg.items(),
                           key=lambda kv: -(kv[1]['a_to_b'] + kv[1]['b_to_a'])):
            tot = d["a_to_b"] + d["b_to_a"]
            per = ", ".join(f"s{s}={ab}+{ba}" for s, (ab, ba) in d["per_seed"].items())
            print(f"    {k}: total_err={tot}  (a→b={d['a_to_b']}, b→a={d['b_to_a']}, "
                  f"samples={d['pair_samples']}) [{per}]")
    else:
        print("    (no pair-error data)")

    # ---- 판정 ----
    op = summary["operational_hard_score"]
    print("\n=== 판정 ===")
    if op["mean"] is not None:
        m_pct = op["mean"] * 100
        s_pct = op["std"]  * 100
        if op["mean"] >= 0.987:
            verdict = "🟢 목표 달성 (mean ≥ 98.7%)"
        elif op["mean"] >= 0.980:
            verdict = "🟡 배포 후보 + 오답 분석 병행 (mean 98.0~98.7%)"
        else:
            verdict = "🔴 튜닝 우선 (mean < 98.0%)"
        if op["std"] <= 0.001:
            stab = "🟢 안정 (std ≤ 0.10pp)"
        elif op["std"] <= 0.0015:
            stab = "🟡 보통 (std ≤ 0.15pp)"
        else:
            stab = "🔴 seed 안정성 검토 (std > 0.15pp)"
        print(f"  mean = {m_pct:.2f}% → {verdict}")
        print(f"  std  = {s_pct:.3f}pp → {stab}")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="기존 best.pt 가 있어도 강제 재학습")
    ap.add_argument("--skip-train", type=int, nargs="*", default=[],
                    help="train 스킵할 seed 들 (eval 만 수행)")
    args = ap.parse_args()
    main(force_retrain=args.force, skip_train_seeds=args.skip_train)
