"""
Phase 2 #3 — Augmentation Curriculum (고속도로 특화)
사용 op:
  1) JPEG compression (강도 곡선)
  2) Motion blur (수평 60~70%, 그 외 랜덤 각도)
  3) Gaussian blur
  4) Gamma / Brightness
  5) Perspective transform
  6) Crop shift (x: ±5%, y: ±5%, scale: 0.95~1.08)
  7) Edge cut (left/right/top/bottom: 0~3% 클립 후 다시 채움)
  8) Downscale-Upscale blur (저해상도 시뮬)

Source 별 prob 곡선 (config.AUG_PROB):
  real:   p1=0.15  p2=0.30  p3=0.40
  ohjj:   p1=0.08  p2=0.18  p3=0.25
  yakhyo: p1=0.04  p2=0.10  p3=0.15

제한:
  - visible char ratio < 0.80 발생할 만한 강도 금지 (heuristic 임계 적용)
  - JPEG quality < 35 금지
  - Mixup 미사용

사용 인터페이스:
  aug = make_augment(deterministic_seed=None)
  aug(img_bgr, source, epoch) -> img_bgr
"""
import math
import random
from typing import Callable, Optional

import cv2
import numpy as np

from . import config as C


# ==========  개별 op  ==========
def _jpeg(img, q):
    q = int(max(35, min(95, q)))                         # ≥35 보장
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    if not ok: return img
    return cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)


def _motion_blur(img, k, angle_deg):
    k = max(3, int(k) | 1)
    kern = np.zeros((k, k), np.float32)
    kern[k // 2, :] = 1.0 / k
    M = cv2.getRotationMatrix2D((k / 2, k / 2), angle_deg, 1.0)
    kern = cv2.warpAffine(kern, M, (k, k))
    s = kern.sum()
    if s > 1e-6: kern /= s
    return cv2.filter2D(img, -1, kern)


def _gauss(img, k):
    k = max(3, int(k) | 1)
    return cv2.GaussianBlur(img, (k, k), 0)


def _gamma(img, g):
    inv = 1.0 / max(g, 1e-3)
    table = ((np.arange(256) / 255.0) ** inv * 255.0).clip(0, 255).astype(np.uint8)
    return cv2.LUT(img, table)


def _perspective(img, mag, rng):
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = mag * min(h, w)
    dst = np.float32([
        [src[0, 0] + rng.uniform(-d, d), src[0, 1] + rng.uniform(-d, d)],
        [src[1, 0] + rng.uniform(-d, d), src[1, 1] + rng.uniform(-d, d)],
        [src[2, 0] + rng.uniform(-d, d), src[2, 1] + rng.uniform(-d, d)],
        [src[3, 0] + rng.uniform(-d, d), src[3, 1] + rng.uniform(-d, d)],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _crop_shift(img, dx_frac, dy_frac, scale, rng):
    """x: ±5%, y: ±5%, scale: 0.95~1.08 → 동일 크기 유지 (재캔버스)"""
    h, w = img.shape[:2]
    # scale
    nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    # canvas
    canvas = np.zeros_like(img)
    cy = (h - nh) // 2 + int(dy_frac * h)
    cx = (w - nw) // 2 + int(dx_frac * w)
    # 자름
    sy0 = max(0, -cy); sx0 = max(0, -cx)
    dy0 = max(0, cy);  dx0 = max(0, cx)
    bh = min(h - dy0, nh - sy0); bw = min(w - dx0, nw - sx0)
    if bh > 0 and bw > 0:
        canvas[dy0:dy0 + bh, dx0:dx0 + bw] = resized[sy0:sy0 + bh, sx0:sx0 + bw]
    # 빈 영역 replicate (가장자리 색)
    if dy0 > 0:        canvas[:dy0, :] = canvas[dy0:dy0 + 1, :]
    if dy0 + bh < h:   canvas[dy0 + bh:, :] = canvas[max(0, dy0 + bh - 1):dy0 + bh, :]
    if dx0 > 0:        canvas[:, :dx0] = canvas[:, dx0:dx0 + 1]
    if dx0 + bw < w:   canvas[:, dx0 + bw:] = canvas[:, max(0, dx0 + bw - 1):dx0 + bw]
    return canvas


def _edge_cut(img, frac, side):
    """side: 0=left 1=right 2=top 3=bot. frac 만큼 잘라낸 후 같은 크기로 reisze"""
    h, w = img.shape[:2]
    if side == 0:
        x = int(w * frac); cropped = img[:, x:]
    elif side == 1:
        x = int(w * frac); cropped = img[:, :w - x] if x > 0 else img
    elif side == 2:
        y = int(h * frac); cropped = img[y:, :]
    else:
        y = int(h * frac); cropped = img[:h - y, :] if int(h * frac) > 0 else img
    if cropped.shape[0] < 2 or cropped.shape[1] < 2: return img
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


def _downscale_blur(img, factor):
    """factor: 2~4. 작게 줄였다가 원본 크기로 다시 확대 → 저해상 simulate"""
    h, w = img.shape[:2]
    nh, nw = max(2, h // factor), max(2, w // factor)
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


# ==========  Curriculum  ==========
def _get_p(source, epoch):
    src = source if source in C.AUG_PROB else "real"
    return C.AUG_PROB[src][C.aug_phase(epoch)]


def _strength(epoch):
    """phase 별 강도 multiplier 0.0~1.0"""
    p = C.aug_phase(epoch)
    return {"p1": 0.4, "p2": 0.7, "p3": 1.0}[p]


# ==========  Augmentor (picklable class) ==========
class Augmentor:
    """
    aug(img_bgr, source, epoch) -> img_bgr
    deterministic_seed != None  → 동일 입력 재현 가능 (DataLoader worker pickling 호환)
    """
    def __init__(self, deterministic_seed: Optional[int] = None):
        self.deterministic_seed = deterministic_seed
        self._rng = (random.Random(deterministic_seed)
                     if deterministic_seed is not None else None)

    def __getstate__(self):
        # rng 자체는 worker 에서 재생성 — seed 만 직렬화
        return {"deterministic_seed": self.deterministic_seed}

    def __setstate__(self, state):
        self.deterministic_seed = state["deterministic_seed"]
        self._rng = (random.Random(self.deterministic_seed)
                     if self.deterministic_seed is not None else None)

    def _r(self):
        return self._rng if self._rng is not None else random

    def __call__(self, img, source, epoch):
        rng = self._r()
        p = _get_p(source, epoch)
        s = _strength(epoch)

        if rng.random() < p:
            img = _jpeg(img, q=rng.randint(int(85 - 35 * s), 95))

        if rng.random() < p:
            k = rng.randint(3, 3 + int(6 * s))
            angle = rng.uniform(-10, 10) if rng.random() < 0.65 else rng.uniform(-90, 90)
            img = _motion_blur(img, k, angle)

        if rng.random() < p * 0.4:
            img = _gauss(img, k=rng.randint(3, 3 + int(4 * s)))

        if rng.random() < p:
            img = _gamma(img, g=rng.uniform(1 - 0.4 * s, 1 + 0.4 * s))

        if rng.random() < p * 0.7:
            img = _perspective(img, mag=rng.uniform(0.0, 0.05 * s), rng=rng)

        if rng.random() < p * 0.6:
            img = _crop_shift(
                img,
                dx_frac=rng.uniform(-0.05, 0.05) * s,
                dy_frac=rng.uniform(-0.05, 0.05) * s,
                scale=rng.uniform(0.95, 1.08),
                rng=rng,
            )

        if rng.random() < p * 0.4:
            side = rng.randint(0, 3)
            frac = rng.uniform(0.0, 0.03)
            img = _edge_cut(img, frac, side)

        if rng.random() < p * 0.3:
            img = _downscale_blur(img, factor=rng.choice([2, 3, 4]))

        return img


def make_augment(deterministic_seed: Optional[int] = None) -> Callable:
    return Augmentor(deterministic_seed=deterministic_seed)


def make_deterministic_augment(seed: int):
    return Augmentor(deterministic_seed=seed)
