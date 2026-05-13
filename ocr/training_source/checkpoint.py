"""
Phase 3 #2 — Checkpoint Selector
- composite = 0.5*hard + 0.3*rare + 0.2*overall (rare 없으면 정규화)
- ECE 1.5x → -0.005, ECE 2x → forbid (best 후보 제외)
- EMA 가중치 우선 저장
"""
from pathlib import Path

import torch

from . import config as C


class CheckpointSelector:
    def __init__(self, ckpt_dir: Path = C.CKPT_DIR):
        self.ckpt_dir = Path(ckpt_dir)
        self.ckpt_dir.mkdir(parents=True, exist_ok=True)
        self.best       = -1e9
        self.best_path  = None
        self.baseline_ece = None
        self.epochs_since_best = 0

    def baseline(self, ece_val: float):
        self.baseline_ece = float(ece_val)

    def update(self, epoch: int, scores: dict, model_state, ema_state,
               extra: dict = None):
        comp     = scores["comp"]
        ece_now  = scores["ece"]
        forbid   = False
        penalty  = 0.0
        if self.baseline_ece is not None and self.baseline_ece > 0:
            ratio = ece_now / max(1e-6, self.baseline_ece)
            if C.ECE_FORBID_2X and ratio >= 2.0:
                forbid = True
            elif ratio >= 1.5:
                penalty = C.ECE_PENALTY_15X

        comp_adj = comp + penalty
        is_best  = (not forbid) and comp_adj > self.best

        payload = {
            "epoch":     epoch,
            "model":     model_state,
            "ema":       ema_state,
            "scores":    scores,
            "score_adj": comp_adj,
            "baseline_ece": self.baseline_ece,
            **(extra or {}),
        }

        # last 항상 저장
        torch.save(payload, self.ckpt_dir / "last.pt")
        if is_best:
            self.best      = comp_adj
            self.best_path = self.ckpt_dir / "best.pt"
            torch.save(payload, self.best_path)
            self.epochs_since_best = 0
        else:
            self.epochs_since_best += 1
        return is_best, comp_adj, forbid
