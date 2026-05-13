"""
Phase 2 #2 — FocalCTC γ=1.2 + Sample Reweight (rare hangul ×1.2) + Label Smoothing toggle
greedy CTC decoder helper 포함.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

from . import config as C


class FocalCTC(nn.Module):
    """
    log_probs: (T, B, V)         — log_softmax 적용된 입력
    targets:    (sum lengths,)   — flattened
    input_lengths:  (B,) = T
    target_lengths: (B,)
    sample_weight:  (B,) optional — rare 포함 시 RARE_REWEIGHT
    """
    def __init__(self, gamma=C.FOCAL_GAMMA, blank=0, label_smooth=C.LABEL_SMOOTH):
        super().__init__()
        self.gamma = gamma
        self.blank = blank
        self.label_smooth = label_smooth
        self.ctc = nn.CTCLoss(blank=blank, reduction="none", zero_infinity=True)

    def forward(self, log_probs, targets, input_lengths, target_lengths,
                sample_weight=None):
        loss = self.ctc(log_probs, targets, input_lengths, target_lengths)   # (B,)
        with torch.no_grad():
            mod = (1.0 - torch.exp(-loss)).clamp(min=0.0).pow(self.gamma)
        loss = loss * mod
        if self.label_smooth > 0:
            uniform = -log_probs.mean(dim=-1)        # (T, B)
            ls_loss = uniform.mean(dim=0)            # (B,)
            loss = (1 - self.label_smooth) * loss + self.label_smooth * ls_loss
        if sample_weight is not None:
            loss = loss * sample_weight.to(loss.device)
        return loss.mean()


def make_sample_weights(labels, rare_set):
    """labels: list[str]; rare_set: set[str] → tensor(B,)"""
    w = [C.RARE_REWEIGHT if any(c in rare_set for c in lab) else 1.0
         for lab in labels]
    return torch.tensor(w, dtype=torch.float32)


def ctc_decode(log_probs, idx2char, blank=0):
    """log_probs (T,B,V) → list[str] (greedy)"""
    pred = log_probs.argmax(-1).T.detach().cpu().numpy()      # (B,T)
    out = []
    for row in pred:
        s, prev = [], blank
        for v in row:
            v = int(v)
            if v != prev and v != blank:
                s.append(idx2char.get(v, ""))
            prev = v
        out.append("".join(s))
    return out
