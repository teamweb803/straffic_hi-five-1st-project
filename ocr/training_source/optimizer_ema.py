"""
Phase 2 #5 — AdamW + Warmup→Cosine + EMA(decay 0.999, ep10 이후)
+ AMP scaler factory
"""
import copy

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import SequentialLR, LinearLR, CosineAnnealingLR

from . import config as C


def make_optimizer(model):
    return AdamW(model.parameters(), lr=C.LR, weight_decay=C.WEIGHT_DECAY)


def make_scheduler(optimizer, max_epochs=C.MAX_EPOCHS, warmup=C.WARMUP_EPOCHS):
    warm = LinearLR(optimizer, start_factor=1e-2, end_factor=1.0, total_iters=warmup)
    cos  = CosineAnnealingLR(optimizer,
                             T_max=max(1, max_epochs - warmup),
                             eta_min=1e-6)
    return SequentialLR(optimizer, [warm, cos], milestones=[warmup])


def make_scaler(device):
    return torch.amp.GradScaler(
        "cuda",
        enabled=(C.AMP_ENABLED and device.type == "cuda"),
    )


class ModelEMA:
    """epoch 10 이후 update 호출 (train.py 가 통제)"""
    def __init__(self, model, decay=C.EMA_DECAY):
        self.decay = decay
        self.module = copy.deepcopy(model).eval()
        for p in self.module.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model):
        d = self.decay
        msd = model.state_dict()
        for k, v in self.module.state_dict().items():
            if v.dtype.is_floating_point:
                v.mul_(d).add_(msd[k].detach(), alpha=1 - d)
            else:
                v.copy_(msd[k])

    def state_dict(self): return self.module.state_dict()

    def load_state_dict(self, sd): self.module.load_state_dict(sd)
