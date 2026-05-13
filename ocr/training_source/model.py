"""
Phase 2 #1 — v5 Enhanced STN + VGG + CBAM + 2-layer BiLSTM
입력 (B,3,48,160) → 출력 (B,40,num_classes)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------- STN ----------
class STN(nn.Module):
    """Conv 3→16→32→64+BN, → bilinear interpolate (4,12), FC 3072→128→64→6, identity init.

    AdaptiveAvgPool2d((4,12)) → F.interpolate(size=(4,12), mode='bilinear') 로 변경 — ONNX 호환.
    state_dict 호환 유지 (양쪽 모두 weight 없음).
    """
    def __init__(self):
        super().__init__()
        self.localization = nn.Sequential(
            nn.Conv2d(3, 16, 7, padding=3), nn.BatchNorm2d(16), nn.MaxPool2d(2), nn.ReLU(True),
            nn.Conv2d(16, 32, 5, padding=2), nn.BatchNorm2d(32), nn.MaxPool2d(2), nn.ReLU(True),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(True),
        )
        self.fc_loc = nn.Sequential(
            nn.Linear(64 * 4 * 12, 128), nn.ReLU(True),
            nn.Linear(128, 64), nn.ReLU(True),
            nn.Linear(64, 6),
        )
        last = self.fc_loc[-1]
        last.weight.data.zero_()
        last.bias.data.copy_(torch.tensor([1, 0, 0, 0, 1, 0], dtype=torch.float))

    def forward(self, x):
        xs = self.localization(x)
        xs = F.interpolate(xs, size=(4, 12), mode="bilinear", align_corners=False)
        xs = xs.flatten(1)
        theta = self.fc_loc(xs).view(-1, 2, 3)
        grid = F.affine_grid(theta, x.size(), align_corners=False)
        return F.grid_sample(x, grid, align_corners=False)


# ---------- Backbone ----------
class Backbone(nn.Module):
    """VGG-like 4 stage. (3,48,160) → (512,1,40)"""
    def __init__(self):
        super().__init__()
        self.b1 = nn.Sequential(
            nn.Conv2d(3, 64, 3, padding=1),  nn.BatchNorm2d(64),  nn.ReLU(True),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64),  nn.ReLU(True),
            nn.MaxPool2d(2),                                          # 24×80
        )
        self.b2 = nn.Sequential(
            nn.Conv2d(64, 128, 3, padding=1),  nn.BatchNorm2d(128), nn.ReLU(True),
            nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(True),
            nn.MaxPool2d(2),                                          # 12×40
        )
        self.b3 = nn.Sequential(
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(True),
            nn.Conv2d(256, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(True),
            nn.MaxPool2d((2, 1)),                                      # 6×40
        )
        self.b4 = nn.Sequential(
            nn.Conv2d(256, 512, 3, padding=1), nn.BatchNorm2d(512), nn.ReLU(True),
            nn.Conv2d(512, 512, 3, padding=1), nn.BatchNorm2d(512), nn.ReLU(True),
            nn.MaxPool2d((6, 1)),                                      # 1×40
        )

    def forward(self, x):
        return self.b4(self.b3(self.b2(self.b1(x))))


# ---------- CBAM ----------
class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(channels, channels // reduction, 1, bias=False),
            nn.ReLU(True),
            nn.Conv2d(channels // reduction, channels, 1, bias=False),
        )

    def forward(self, x):
        a = self.fc(self.avg_pool(x))
        m = self.fc(self.max_pool(x))
        return x * torch.sigmoid(a + m)


class SpatialAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, 7, padding=3)

    def forward(self, x):
        a = torch.mean(x, dim=1, keepdim=True)
        m, _ = torch.max(x, dim=1, keepdim=True)
        return x * torch.sigmoid(self.conv(torch.cat([a, m], dim=1)))


class CBAM(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.ca = ChannelAttention(channels)
        self.sa = SpatialAttention()

    def forward(self, x):
        return self.sa(self.ca(x))


# ---------- 메인 모델 ----------
class V5OCR(nn.Module):
    def __init__(self, num_classes, use_cbam=True):
        super().__init__()
        self.stn = STN()
        self.backbone = Backbone()
        self.use_cbam = use_cbam
        if use_cbam:
            self.cbam = CBAM(512)
        self.bilstm = nn.LSTM(
            input_size=512, hidden_size=256, num_layers=2,
            bidirectional=True, batch_first=True, dropout=0.1,
        )
        self.classifier = nn.Linear(512, num_classes)

    def forward(self, x):
        x = self.stn(x)
        x = self.backbone(x)
        if self.use_cbam:
            x = self.cbam(x)
        x = x.squeeze(2).permute(0, 2, 1)            # (B, 40, 512)
        x, _ = self.bilstm(x)
        return self.classifier(x)                     # (B, 40, num_classes)


def count_params(m):
    return sum(p.numel() for p in m.parameters() if p.requires_grad)


if __name__ == "__main__":
    m = V5OCR(num_classes=52)
    x = torch.randn(2, 3, 48, 160)
    y = m(x)
    print("output:", tuple(y.shape), "params:", count_params(m))
