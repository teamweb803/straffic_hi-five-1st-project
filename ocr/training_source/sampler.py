"""
Phase 2 #4 — Synthetic Mixing Curriculum helper
실제 mixing 은 LPDataset.set_epoch() 가 처리.
이 모듈은:
  - 외부 검증/시각화용 helper
  - epoch 단위 expected mix 계산
  - source 비율 (ohjj 75% / yakhyo 25%)도 같이 반환
"""
from . import config as C


def expected_mix(epoch: int, n_real: int, n_synth_pool: int,
                 ohjj_pool: int = None, yakhyo_pool: int = None):
    """
    Synth oversampling with replacement 허용.
    n_synth_pool 은 참고용 (어떤 풀에서 with-replacement sampling).
    실제 캡은 없음 (target ratio 그대로 충족).
    """
    r = C.synth_ratio(epoch)
    n_synth = int(round(n_real * r / max(1e-6, 1 - r)))
    n_o = int(round(n_synth * C.SYNTH_OHJJ_RATIO))
    n_y = n_synth - n_o
    total = n_real + n_synth
    return {
        "epoch":          epoch,
        "phase":          C.aug_phase(epoch),
        "ratio_target":   round(r, 3),
        "n_real":         n_real,
        "n_synth_total":  n_synth,
        "n_synth_ohjj":   n_o,
        "n_synth_yakhyo": n_y,
        "ohjj_pool":      ohjj_pool,
        "yakhyo_pool":    yakhyo_pool,
        "ohjj_oversample_x":   round(n_o / max(1, ohjj_pool or 0), 2) if ohjj_pool else None,
        "yakhyo_oversample_x": round(n_y / max(1, yakhyo_pool or 0), 2) if yakhyo_pool else None,
        "total":          total,
        "actual_ratio":   round(n_synth / max(1, total), 3),
    }


if __name__ == "__main__":
    n_real = 62253
    n_synth_pool = 10000
    ohjj_pool, yakhyo_pool = 7500, 2500
    print(f"{'epoch':>5} {'phase':>5} {'r_tgt':>6} {'real':>7} {'synth':>7} "
          f"{'ohjj':>6} {'yakhyo':>6} {'oh×':>5} {'yak×':>5} {'r_act':>6}")
    for ep in (1, 10, 20, 21, 35, 50, 51, 60, 70, 71, 90, 100):
        m = expected_mix(ep, n_real, n_synth_pool, ohjj_pool, yakhyo_pool)
        print(f"{m['epoch']:>5} {m['phase']:>5} {m['ratio_target']:>6} "
              f"{m['n_real']:>7} {m['n_synth_total']:>7} "
              f"{m['n_synth_ohjj']:>6} {m['n_synth_yakhyo']:>6} "
              f"{m['ohjj_oversample_x']:>5} {m['yakhyo_oversample_x']:>5} "
              f"{m['actual_ratio']:>6}")
