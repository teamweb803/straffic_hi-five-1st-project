"""Realtime LP detection + OCR with OC-SORT tracking.

Pipeline (per frame):
  1) cv2.VideoCapture -> 1920x1080 BGR uint8 (single CPU read; only required CPU step)
  2) torch.from_numpy(...).to(cuda)  ->  single H2D upload
  3) GPU slice/concat: bottom-half left/right -> 960x960 stack (lane1 top, lane2 bottom)
  4) YOLO TRT (FP16, end2end NMS) directly fed via tensor data_ptr -> dets on GPU
  5) OC-SORT update on CPU (small box-only payload)
  6) Per track: GPU crop view -> resize/normalize on GPU -> OCR TRT (FP16) -> CTC greedy
  7) Single GPU->CPU download of stacked 960x960 for cv2 drawing + Tk display

UI: Tkinter, two buttons (01.mp4 / 02.mp4), FPS overlay top-left.
"""
from __future__ import annotations

import ctypes
import json
import re
import sys
import time
import tkinter as tk
from pathlib import Path

# Make this process DPI-aware so 960px image == 960 physical pixels on a 4K/HiDPI screen.
if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

import cv2
import numpy as np
import tensorrt as trt
import torch
import torch.nn.functional as F
import torchvision
from boxmot.trackers.ocsort.ocsort import OcSort
from PIL import Image, ImageDraw, ImageFont, ImageTk

ROOT = Path(__file__).resolve().parent
DEVICE = torch.device("cuda")
KOREAN_FONT = Path("C:/Windows/Fonts/malgun.ttf")

PAT_7 = re.compile(r"^\d{2}[가-힣]\d{4}$")
PAT_8 = re.compile(r"^\d{3}[가-힣]\d{4}$")


def is_valid_lp(s: str) -> bool:
    return bool(PAT_7.match(s) or PAT_8.match(s))


def _load_trt_engine(path: Path) -> trt.ICudaEngine:
    """Deserialize a TRT engine; transparently strip the ultralytics JSON header if present."""
    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    raw = path.read_bytes()
    if len(raw) > 4:
        meta_len = int.from_bytes(raw[:4], "little")
        if 0 < meta_len < 100_000 and 4 + meta_len < len(raw):
            head = raw[4 : 4 + meta_len]
            try:
                head.decode("utf-8")
                raw = raw[4 + meta_len :]
            except UnicodeDecodeError:
                pass
    engine = runtime.deserialize_cuda_engine(raw)
    if engine is None:
        raise RuntimeError(f"Failed to deserialize engine: {path}")
    return engine


class YOLODetector:
    """YOLO TRT engine — handles both end2end (1, max_det, 6) and raw (1, 4+nc, N) outputs.

    The detector takes a (1, 3, 960, 960) RGB float[0,1] tensor (the stacked frame).
    If the engine's native input is smaller (e.g., 640), the input is bilinearly
    downsampled, and output boxes are scaled back to 960-space.
    """

    PIPELINE_SIZE = 960

    def __init__(self, engine_path: Path, conf_thresh: float = 0.30, iou_nms: float = 0.45):
        self.engine = _load_trt_engine(engine_path)
        self.ctx = self.engine.create_execution_context()

        # Input shape: (1, 3, H, W) — assume square
        in_shape = tuple(self.engine.get_tensor_shape("images"))
        self.input_size = int(in_shape[2])
        self.input = torch.empty(in_shape, device=DEVICE, dtype=torch.float32)
        self.ctx.set_tensor_address("images", self.input.data_ptr())

        # Output shape detection — end2end vs raw
        out_shape = tuple(self.engine.get_tensor_shape("output0"))
        self.output_shape = out_shape
        self.output = torch.empty(out_shape, device=DEVICE, dtype=torch.float32)
        self.ctx.set_tensor_address("output0", self.output.data_ptr())
        # End2end shape: (1, max_det, 6) — last dim is 6 (xyxy + conf + cls)
        # Raw shape:     (1, 4+nc, N) — typically (1, 5, 8400) for 1-class YOLO11
        self.is_end2end = (len(out_shape) == 3 and out_shape[2] == 6)

        self.conf_thresh = conf_thresh
        self.iou_nms = iou_nms
        self.last_ms: float = 0.0
        self._scale = self.PIPELINE_SIZE / self.input_size

    @torch.no_grad()
    def __call__(self, img_chw_norm: torch.Tensor) -> torch.Tensor:
        # Downsample to engine's native input size if needed
        if self.input_size != self.PIPELINE_SIZE:
            img = F.interpolate(
                img_chw_norm,
                size=(self.input_size, self.input_size),
                mode="bilinear",
                align_corners=False,
            )
        else:
            img = img_chw_norm
        self.input.copy_(img.contiguous())

        stream = torch.cuda.current_stream()
        t0 = time.perf_counter()
        ok = self.ctx.execute_async_v3(stream.cuda_stream)
        if not ok:
            raise RuntimeError("YOLO TRT execute failed")
        stream.synchronize()
        self.last_ms = (time.perf_counter() - t0) * 1000.0

        if self.is_end2end:
            det = self.output[0]                          # (max_det, 6)
            keep = det[:, 4] >= self.conf_thresh
            det = det[keep]
        else:
            # raw (1, 4+nc, N) -> permute to (N, 4+nc)
            raw = self.output[0].permute(1, 0)            # (N, 4+nc)
            cls_scores = raw[:, 4:]
            if cls_scores.shape[1] == 1:
                conf = cls_scores[:, 0]
                cls_id = torch.zeros_like(conf, dtype=torch.long)
            else:
                conf, cls_id = cls_scores.max(dim=1)
            keep = conf >= self.conf_thresh
            if not keep.any():
                return torch.empty((0, 6), device=DEVICE, dtype=torch.float32)
            preds = raw[keep]
            conf = conf[keep]
            cls_id = cls_id[keep]
            cx, cy, w, h = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
            x1 = cx - w * 0.5
            y1 = cy - h * 0.5
            x2 = cx + w * 0.5
            y2 = cy + h * 0.5
            boxes = torch.stack([x1, y1, x2, y2], dim=1)
            keep_idx = torchvision.ops.nms(boxes, conf, self.iou_nms)
            boxes = boxes[keep_idx]
            conf = conf[keep_idx]
            cls_id = cls_id[keep_idx]
            det = torch.cat([boxes, conf.unsqueeze(1), cls_id.unsqueeze(1).float()], dim=1)

        # Scale boxes back to pipeline (960) space if input was downsampled
        if self._scale != 1.0:
            det = det.clone()
            det[:, :4] *= self._scale
        return det


class OCREngine:
    """V5OCR TRT engine. Input (1,3,48,160) normalized RGB. Output (1,40,51)."""

    INPUT_H = 48
    INPUT_W = 160
    SEQ_LEN = 40
    NUM_CLASSES = 51
    BLANK = 0

    def __init__(self, engine_path: Path, vocab_path: Path):
        self.engine = _load_trt_engine(engine_path)
        self.ctx = self.engine.create_execution_context()
        self.input = torch.empty(
            (1, 3, self.INPUT_H, self.INPUT_W), device=DEVICE, dtype=torch.float32
        )
        self.output = torch.empty(
            (1, self.SEQ_LEN, self.NUM_CLASSES), device=DEVICE, dtype=torch.float32
        )
        self.ctx.set_tensor_address("images", self.input.data_ptr())
        self.ctx.set_tensor_address("logits", self.output.data_ptr())
        with open(vocab_path, "r", encoding="utf-8") as f:
            v = json.load(f)
        chars = v["chars"]
        self.idx2char = {i + 1: c for i, c in enumerate(chars)}
        self.last_ms: float = 0.0

    @torch.no_grad()
    def __call__(self, crop_hwc_uint8: torch.Tensor) -> str:
        # crop is a GPU view (H, W, 3) uint8 BGR
        chw = crop_hwc_uint8.permute(2, 0, 1).unsqueeze(0).float()  # (1,3,H,W) BGR
        chw = chw[:, [2, 1, 0]]  # BGR -> RGB
        chw = F.interpolate(
            chw, size=(self.INPUT_H, self.INPUT_W), mode="bilinear", align_corners=False
        )
        chw = (chw / 255.0 - 0.5) / 0.5
        self.input.copy_(chw.contiguous())
        stream = torch.cuda.current_stream()
        t0 = time.perf_counter()
        ok = self.ctx.execute_async_v3(stream.cuda_stream)
        if not ok:
            raise RuntimeError("OCR TRT execute failed")
        stream.synchronize()
        self.last_ms = (time.perf_counter() - t0) * 1000.0
        idx = self.output[0].argmax(-1).cpu().numpy()  # (40,) int
        out = []
        prev = self.BLANK
        for v in idx:
            v = int(v)
            if v != prev and v != self.BLANK:
                out.append(self.idx2char.get(v, ""))
            prev = v
        return "".join(out)


class FrameProcessor:
    def __init__(self, detector: YOLODetector, ocr: OCREngine):
        self.detector = detector
        self.ocr = ocr
        self.use_tracking: bool = True
        self.tracker = self._make_tracker()
        self.id_text: dict[int, str] = {}      # latest decoded text per id
        self.id_locked: dict[int, str] = {}    # locked once a valid pattern is seen
        self.id_lane: dict[int, int] = {}      # last seen lane (1 or 2) per id
        self.id_ocr_ms: dict[int, float] = {}  # latest OCR latency per id
        # Translate internal OcSort id -> human-friendly display id (assigned only on first valid OCR)
        self.tid_to_display: dict[int, int] = {}
        self._next_display_id: int = 1
        # Plate-text dedup: same plate seen within window reuses its display id
        # plate_text -> (display_id, last_seen_monotonic)
        self.plate_dedup: dict[str, tuple[int, float]] = {}
        self.PLATE_REUSE_WINDOW: float = 5.0  # seconds
        # Per-track streak: same valid plate held >= duration thresholds
        self.id_streak: dict[int, tuple[str, float]] = {}    # tid -> (text, streak_start)
        self.id_displayed_text: dict[int, str] = {}          # tid -> text shown on screen (>=DISPLAY_DURATION)
        self.id_applied: dict[int, str] = {}                  # tid -> confirmed plate (>=CONFIRM_DURATION)
        self.id_changed: dict[int, bool] = {}                 # tid -> True if applied changed
        self.DISPLAY_DURATION: float = 0.2  # seconds of consistent OCR to start drawing the box+text
        self.CONFIRM_DURATION: float = 1.0  # seconds of consistent OCR to assign display ID
        self.last_yolo_ms: float = 0.0
        self.last_ocr_ms: float = 0.0          # max OCR latency in the current frame
        # cumulative latency stats (since last reset)
        self.yolo_ms_sum: float = 0.0
        self.yolo_calls: int = 0
        self.ocr_ms_sum: float = 0.0
        self.ocr_calls: int = 0
        self.font_label = ImageFont.truetype(str(KOREAN_FONT), size=20)
        self.font_lane = ImageFont.truetype(str(KOREAN_FONT), size=18)

    @staticmethod
    def _make_tracker() -> OcSort:
        return OcSort(
            det_thresh=0.30,      # match YOLO conf so low-conf dets reach the tracker
            max_age=1200,         # 10s @ 119.95 fps — keep ID across detection gaps
            min_hits=2,
            iou_threshold=0.20,
            delta_t=3,
            inertia=0.2,
            use_byte=False,
            asso_func="iou",
        )

    def reset(self) -> None:
        self.tracker = self._make_tracker()
        self.id_text.clear()
        self.id_locked.clear()
        self.id_lane.clear()
        self.id_ocr_ms.clear()
        self.tid_to_display.clear()
        self._next_display_id = 1
        self.plate_dedup.clear()
        self.id_streak.clear()
        self.id_displayed_text.clear()
        self.id_applied.clear()
        self.id_changed.clear()
        self.last_yolo_ms = 0.0
        self.last_ocr_ms = 0.0
        self.yolo_ms_sum = 0.0
        self.yolo_calls = 0
        self.ocr_ms_sum = 0.0
        self.ocr_calls = 0

    @torch.no_grad()
    def process(self, frame_bgr_np: np.ndarray) -> Image.Image:
        # 1) single H2D upload
        gpu_full = torch.from_numpy(frame_bgr_np).to(DEVICE, non_blocking=True)  # (1080,1920,3) u8

        # 2) GPU slice + stack -> 960x960 BGR uint8
        lane1 = gpu_full[600:1080, 0:960]
        lane2 = gpu_full[600:1080, 960:1920]
        stacked = torch.cat([lane1, lane2], dim=0).contiguous()

        # 3) GPU normalize -> YOLO input (BGR -> RGB, /255)
        yolo_in = (
            stacked[..., [2, 1, 0]]
            .permute(2, 0, 1)
            .unsqueeze(0)
            .float()
            .div_(255.0)
        ).contiguous()

        # 4) Detect (zero-copy)
        dets_gpu = self.detector(yolo_in)
        self.last_yolo_ms = self.detector.last_ms
        self.yolo_ms_sum += self.detector.last_ms
        self.yolo_calls += 1
        self.last_ocr_ms = 0.0
        n_dets = int(dets_gpu.shape[0])

        # 5) Single D2H download. Use RGB (flip channel before download via the same trick).
        rgb_gpu = stacked[..., [2, 1, 0]].contiguous()  # GPU (960,960,3) u8 RGB
        rgb_np = rgb_gpu.cpu().numpy()
        img = Image.fromarray(rgb_np)
        draw = ImageDraw.Draw(img)

        if n_dets:
            dets_cpu = dets_gpu.cpu().numpy().astype(np.float32)
        else:
            dets_cpu = np.empty((0, 6), dtype=np.float32)

        if self.use_tracking:
            tracks = self.tracker.update(dets_cpu, rgb_np)
            if tracks.ndim != 2 or tracks.shape[0] == 0:
                tracks = np.empty((0, 8), dtype=np.float32)
        else:
            # Tracker bypass: synthesize "tracks" with id=-1, det_idx as enumerator
            if len(dets_cpu):
                ids = -np.ones((len(dets_cpu), 1), dtype=np.float32)
                det_idx = np.arange(len(dets_cpu), dtype=np.float32).reshape(-1, 1)
                tracks = np.concatenate(
                    [dets_cpu[:, :4], ids, dets_cpu[:, 4:5], dets_cpu[:, 5:6], det_idx],
                    axis=1,
                )
            else:
                tracks = np.empty((0, 8), dtype=np.float32)

        # 6) OCR per track on GPU; draw labels via PIL (Korean-capable)
        for trk in tracks:
            x1, y1, x2, y2 = (int(round(trk[i])) for i in range(4))
            tid = int(trk[4])
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(960, x2); y2 = min(960, y2)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue

            tracked = tid >= 0
            if tracked:
                cy = (y1 + y2) // 2
                self.id_lane[tid] = 1 if cy < 480 else 2

            box_h_int = int(y2 - y1)

            # Small box (<20px height): red box, NO OCR, only px label
            if box_h_int < 20:
                red = (220, 0, 0)
                draw.rectangle([x1, y1, x2, y2], outline=red, width=2)
                px_label = f"{box_h_int}px"
                tb_p = draw.textbbox((0, 0), px_label, font=self.font_label)
                plw = tb_p[2] - tb_p[0]
                plh = tb_p[3] - tb_p[1]
                pty1 = min(960 - plh - 8, y2 + 4)
                draw.rectangle([x1, pty1, x1 + plw + 8, pty1 + plh + 8], fill=red)
                draw.text((x1 + 4, pty1 + 2), px_label, fill=(0, 0, 0), font=self.font_label)
                continue

            # Normal-sized box (>=20px): run OCR
            crop = stacked[y1:y2, x1:x2]
            text = self.ocr(crop)
            self.last_ocr_ms = max(self.last_ocr_ms, self.ocr.last_ms)
            self.ocr_ms_sum += self.ocr.last_ms
            self.ocr_calls += 1
            if tracked:
                self.id_ocr_ms[tid] = self.ocr.last_ms
                if text:
                    self.id_text[tid] = text

                # Streak update — only valid OCR participates. Invalid OCR neither
                # extends nor breaks the streak (acts as "no observation").
                now = time.monotonic()
                if text and is_valid_lp(text):
                    streak = self.id_streak.get(tid)
                    if streak is None or streak[0] != text:
                        self.id_streak[tid] = (text, now)
                    else:
                        duration = now - streak[1]
                        if duration >= self.DISPLAY_DURATION:
                            self.id_displayed_text[tid] = text
                        if duration >= self.CONFIRM_DURATION and tid not in self.id_applied:
                            existing = self.plate_dedup.get(text)
                            if existing is not None:
                                disp_id = existing[0]
                            else:
                                disp_id = self._next_display_id
                                self._next_display_id += 1
                            self.id_applied[tid] = text
                            self.id_locked[tid] = text
                            self.tid_to_display[tid] = disp_id
                            self.plate_dedup[text] = (disp_id, now)

                if tid not in self.id_displayed_text:
                    continue
                shown = self.id_displayed_text[tid]
                if tid in self.id_applied:
                    self.plate_dedup[self.id_applied[tid]] = (
                        self.tid_to_display[tid], time.monotonic()
                    )
            else:
                # No tracking — only draw if current OCR is valid
                if not (text and is_valid_lp(text)):
                    continue
                shown = text

            color = (0, 220, 0)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

            # ---- ABOVE box: #ID only (no distance label) ----
            if tracked and tid in self.id_applied:
                disp_id = self.tid_to_display[tid]
                id_label = f"#{disp_id}"
                tb = draw.textbbox((0, 0), id_label, font=self.font_label)
                ilw = tb[2] - tb[0]
                ilh = tb[3] - tb[1]
                ity1 = max(0, y1 - ilh - 8)
                draw.rectangle([x1, ity1, x1 + ilw + 8, ity1 + ilh + 8], fill=color)
                draw.text((x1 + 4, ity1 + 2), id_label, fill=(0, 0, 0), font=self.font_label)

            # ---- BELOW box: stack downward [box] -> OCR -> px ----
            tb2 = draw.textbbox((0, 0), shown, font=self.font_label)
            olw = tb2[2] - tb2[0]
            olh = tb2[3] - tb2[1]
            oty1 = min(960 - olh - 8, y2)
            draw.rectangle([x1, oty1, x1 + olw + 8, oty1 + olh + 8], fill=color)
            draw.text((x1 + 4, oty1 + 2), shown, fill=(0, 0, 0), font=self.font_label)
            stack_bot = oty1 + olh + 8

            px_label = f"{box_h_int}px"
            tb_p = draw.textbbox((0, 0), px_label, font=self.font_label)
            plw = tb_p[2] - tb_p[0]
            plh = tb_p[3] - tb_p[1]
            pty1 = min(960 - plh - 8, stack_bot + 2)
            draw.rectangle([x1, pty1, x1 + plw + 8, pty1 + plh + 8], fill=color)
            draw.text((x1 + 4, pty1 + 2), px_label, fill=(0, 0, 0), font=self.font_label)

        draw.line([(0, 480), (960, 480)], fill=(255, 255, 255), width=1)
        draw.text((870, 5), "Lane 1", fill=(255, 255, 255), font=self.font_lane,
                  stroke_width=2, stroke_fill=(0, 0, 0))
        draw.text((870, 485), "Lane 2", fill=(255, 255, 255), font=self.font_lane,
                  stroke_width=2, stroke_fill=(0, 0, 0))
        return img


START_OFFSETS = {"01.mp4": 25.0}  # seconds to seek into the video on start


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("LP Detection — Idle")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initial window size — comfortable on most screens, scales up on resize
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        init_w = min(1400, max(900, sw - 200))
        init_h = min(1080, max(700, sh - 150))
        root.geometry(f"{init_w}x{init_h}")

        # ---- Top toolbar: buttons + FPS readout + status ----
        ctrl = tk.Frame(root)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)
        for name in ("01.mp4", "02.mp4"):
            tk.Button(
                ctrl, text=name, width=12, font=("Segoe UI", 11),
                command=lambda p=ROOT / name: self.start(p),
            ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            ctrl, text="Stop", width=8, font=("Segoe UI", 11),
            command=self.stop,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            ctrl, text="원본 보기", width=10, font=("Segoe UI", 10),
            command=self._toggle_orig,
        ).pack(side=tk.LEFT, padx=4)
        self.record_btn = tk.Button(
            ctrl, text="● 녹화", width=10, font=("Segoe UI", 10),
            command=self._toggle_record,
        )
        self.record_btn.pack(side=tk.LEFT, padx=4)
        tk.Button(
            ctrl, text="Clear log", width=10, font=("Segoe UI", 10),
            command=self._clear_log,
        ).pack(side=tk.LEFT, padx=4)

        # Model radio buttons (one of three TRT engines)
        tk.Label(ctrl, text="Model:", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(16, 4))
        self.model_var = tk.StringVar(value="lp")
        for key, label in [("lp", "LP custom"), ("11n", "YOLO11n"), ("11s", "YOLO11s")]:
            tk.Radiobutton(
                ctrl, text=label, variable=self.model_var, value=key,
                command=self._on_model_change, font=("Segoe UI", 10),
            ).pack(side=tk.LEFT, padx=2)

        # Tracking on/off
        self.tracking_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl, text="Track", variable=self.tracking_var,
            command=self._on_tracking_toggle, font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(12, 4))

        self.fps_var = tk.StringVar(value="FPS: 0.0")
        tk.Label(
            ctrl, textvariable=self.fps_var,
            font=("Segoe UI", 14, "bold"), fg="#0066cc",
        ).pack(side=tk.LEFT, padx=20)

        self.timing_var = tk.StringVar(value="YOLO 0.00 / OCR 0.00 ms")
        tk.Label(
            ctrl, textvariable=self.timing_var,
            font=("Consolas", 12, "bold"), fg="#222",
        ).pack(side=tk.LEFT, padx=10)

        self.status = tk.Label(ctrl, text="idle", font=("Segoe UI", 10), fg="gray")
        self.status.pack(side=tk.LEFT, padx=12)

        # ---- Content: cropped (left, fills) + log (right, fixed) ----
        content = tk.Frame(root)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.image_frame = tk.Frame(content, bg="black")
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.label = tk.Label(self.image_frame, bg="black")
        self.label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.tk_image: ImageTk.PhotoImage | None = None
        self.crop_target_size: int = 960
        self.image_frame.bind("<Configure>", self._on_image_resize)

        # Original video popup state
        self.orig_window: tk.Toplevel | None = None
        self.orig_label: tk.Label | None = None
        self.tk_image_orig: ImageTk.PhotoImage | None = None
        self.orig_target: tuple[int, int] = (1280, 720)

        log_frame = tk.Frame(content, width=380)
        log_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=8)
        log_frame.pack_propagate(False)
        tk.Label(log_frame, text="Detection Log",
                 font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        log_inner = tk.Frame(log_frame)
        log_inner.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_inner)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box = tk.Text(
            log_inner, width=36, height=40,
            font=("Consolas", 11), wrap=tk.NONE,
            yscrollcommand=scrollbar.set,
        )
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_box.yview)
        self.log_box.tag_configure("locked", foreground="green")
        self.log_box.tag_configure("appear", foreground="gray")
        self.log_box.config(state=tk.DISABLED)

        # ---- Engines: load all available YOLO variants up-front ----
        print("[init] loading TRT engines...")
        self.detectors: dict[str, YOLODetector] = {}
        for key, fname in [("lp", "yolo.engine"),
                           ("11n", "yolo11n.engine"),
                           ("11s", "yolo11s.engine")]:
            p = ROOT / fname
            if p.exists():
                self.detectors[key] = YOLODetector(p, conf_thresh=0.30)
                d = self.detectors[key]
                print(f"  - {key:3s} ({fname}): input {d.input_size}, "
                      f"end2end={d.is_end2end}, out{d.output_shape}")
            else:
                print(f"  - {key:3s} ({fname}): NOT FOUND, skipped")
        if "lp" not in self.detectors:
            raise RuntimeError("yolo.engine missing — required as default model")
        self.ocr = OCREngine(ROOT / "ocr.engine", ROOT / "ocr_vocab.json")
        self.processor = FrameProcessor(self.detectors["lp"], self.ocr)
        self.font_fps = ImageFont.truetype(str(KOREAN_FONT), size=26)
        print("[init] ready.")

        # ---- Per-session state ----
        self.cap: cv2.VideoCapture | None = None
        self.fps_buf: list[float] = []
        self.scheduled: str | None = None
        self.start_frame: int = 0
        self.logged_appeared: set[int] = set()
        self.logged_locked: set[int] = set()
        self.logged_disp_ids: set[int] = set()  # display ids already logged

        # Recording state
        self.writer: cv2.VideoWriter | None = None
        self.record_path: Path | None = None
        self.writer: cv2.VideoWriter | None = None
        self.record_path: Path | None = None

    # ---- model selection ----
    def _on_model_change(self) -> None:
        key = self.model_var.get()
        if key not in self.detectors:
            self.status.configure(text=f"model {key} not loaded", fg="red")
            return
        self.processor.detector = self.detectors[key]
        self.processor.reset()
        self.logged_appeared.clear()
        self.logged_locked.clear()
        self.logged_disp_ids.clear()
        self._log(f"--- model switched to {key} ---")

    # ---- recording ----
    def _toggle_record(self) -> None:
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            self.record_btn.configure(text="● 녹화", fg="black")
            saved = self.record_path
            self.record_path = None
            self._log(f"--- saved {saved.name if saved else '<unknown>'} ---")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = ROOT / f"record_{ts}.mp4"
        src_fps = (self.cap.get(cv2.CAP_PROP_FPS) if self.cap is not None else 0.0) or 30.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, src_fps, (960, 960))
        if not writer.isOpened():
            self.status.configure(text="recording open failed", fg="red")
            return
        self.writer = writer
        self.record_path = path
        self.record_btn.configure(text="■ 중지", fg="red")
        self._log(f"--- recording to {path.name} @ {src_fps:.1f} fps ---")

    # ---- tracking toggle ----
    def _on_tracking_toggle(self) -> None:
        on = bool(self.tracking_var.get())
        self.processor.use_tracking = on
        self.processor.reset()
        self.logged_appeared.clear()
        self.logged_locked.clear()
        self.logged_disp_ids.clear()
        self._log(f"--- tracking {'ON' if on else 'OFF'} ---")

    # ---- resize handlers ----
    def _on_image_resize(self, event: tk.Event) -> None:
        if event.widget is not self.image_frame:
            return
        sz = min(event.width, event.height) - 12
        if sz > 100:
            self.crop_target_size = sz

    def _on_orig_resize(self, event: tk.Event) -> None:
        if self.orig_window is None or event.widget is not self.orig_window:
            return
        w, h = max(1, event.width), max(1, event.height)
        # Fit 16:9 inside the popup window
        target_h = w * 9 // 16
        if target_h <= h:
            self.orig_target = (w, target_h)
        else:
            self.orig_target = (h * 16 // 9, h)

    # ---- original popup ----
    def _toggle_orig(self) -> None:
        if self.orig_window is not None:
            try:
                if self.orig_window.winfo_exists():
                    self.orig_window.destroy()
            except Exception:
                pass
            self.orig_window = None
            self.orig_label = None
            return
        win = tk.Toplevel(self.root)
        win.title("Original 1920×1080")
        win.geometry("1280x720")
        win.protocol("WM_DELETE_WINDOW", self._toggle_orig)
        win.bind("<Configure>", self._on_orig_resize)
        lbl = tk.Label(win, bg="black")
        lbl.pack(fill=tk.BOTH, expand=True)
        self.orig_window = win
        self.orig_label = lbl
        self.orig_target = (1280, 720)

    # ---- log helpers ----
    def _log(self, text: str, tag: str = "") -> None:
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, text + "\n", tag)
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)

    # ---- video lifecycle ----
    def start(self, video_path: Path) -> None:
        self.stop()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.status.configure(text=f"cannot open {video_path.name}", fg="red")
            return
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        offset_sec = START_OFFSETS.get(video_path.name, 0.0)
        self.start_frame = int(offset_sec * src_fps)
        if self.start_frame > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
        self.cap = cap
        self.processor.reset()
        self.fps_buf.clear()
        self.logged_appeared.clear()
        self.logged_locked.clear()
        self.logged_disp_ids.clear()
        self.root.title(f"LP Detection — {video_path.name}")
        self.status.configure(
            text=f"playing {video_path.name} (from {offset_sec:.0f}s)",
            fg="green",
        )
        self._log(f"=== start {video_path.name} @ {offset_sec:.1f}s ===")
        self._loop()

    def stop(self) -> None:
        if self.scheduled is not None:
            try:
                self.root.after_cancel(self.scheduled)
            except Exception:
                pass
            self.scheduled = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status.configure(text="idle", fg="gray")
        self.fps_var.set("FPS: 0.0")

    def _loop(self) -> None:
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
            self.processor.reset()
            self.logged_appeared.clear()
            self.logged_locked.clear()
            self._log("--- loop ---")
            self.scheduled = self.root.after(1, self._loop)
            return

        t0 = time.perf_counter()
        img = self.processor.process(frame)  # PIL.Image (RGB, 960x960)
        dt = time.perf_counter() - t0

        self.fps_buf.append(dt)
        if len(self.fps_buf) > 30:
            self.fps_buf.pop(0)
        fps = len(self.fps_buf) / max(sum(self.fps_buf), 1e-6)
        self.fps_var.set(f"FPS: {fps:5.1f}")
        yc = max(self.processor.yolo_calls, 1)
        oc = max(self.processor.ocr_calls, 1)
        yolo_avg = self.processor.yolo_ms_sum / yc
        ocr_avg = self.processor.ocr_ms_sum / oc
        self.timing_var.set(
            f"YOLO {yolo_avg:5.2f} / OCR {ocr_avg:5.2f} ms"
        )

        # On-image FPS overlay + YOLO/OCR avg ms with call counts
        draw = ImageDraw.Draw(img)
        overlay = (
            f"FPS: {fps:5.1f}   "
            f"YOLO {yolo_avg:5.2f} ms ({self.processor.yolo_calls})   "
            f"OCR {ocr_avg:5.2f} ms ({self.processor.ocr_calls})"
        )
        draw.text((10, 6), overlay, fill=(255, 255, 0),
                  font=self.font_fps, stroke_width=3, stroke_fill=(0, 0, 0))

        # Write frame to recording (native 960×960 with all annotations)
        if self.writer is not None:
            self.writer.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

        # Log only validated tracks (one line per track on first valid OCR)
        ts = time.strftime("%H:%M:%S")
        yolo_ms = self.processor.last_yolo_ms
        for tid, plate in self.processor.id_locked.items():
            if tid in self.logged_locked:
                continue
            self.logged_locked.add(tid)
            disp = self.processor.tid_to_display.get(tid, tid)
            # Skip duplicate-display-id locks (same plate seen again within 5s reuses id)
            if disp in self.logged_disp_ids:
                continue
            self.logged_disp_ids.add(disp)
            lane = self.processor.id_lane.get(tid, 0)
            ocr_ms = self.processor.id_ocr_ms.get(tid, 0.0)
            self._log(
                f"[{ts}] L{lane} #{disp:<3} = {plate}  "
                f"(yolo: {yolo_ms:5.2f}ms, ocr: {ocr_ms:5.2f}ms)",
                tag="locked",
            )

        # Resize cropped image to fit current frame size (responsive to fullscreen)
        sz = self.crop_target_size
        if sz != 960 and sz > 100:
            img = img.resize((sz, sz), Image.BILINEAR)
        self.tk_image = ImageTk.PhotoImage(img)
        self.label.configure(image=self.tk_image)

        # Update original popup if open
        if self.orig_window is not None and self.orig_label is not None:
            try:
                if self.orig_window.winfo_exists():
                    rgb_orig = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    orig_img = Image.fromarray(rgb_orig)
                    if self.orig_target != (1920, 1080):
                        orig_img = orig_img.resize(self.orig_target, Image.BILINEAR)
                    self.tk_image_orig = ImageTk.PhotoImage(orig_img)
                    self.orig_label.configure(image=self.tk_image_orig)
                else:
                    self.orig_window = None
                    self.orig_label = None
            except Exception:
                self.orig_window = None
                self.orig_label = None

        self.scheduled = self.root.after(1, self._loop)

    def on_close(self) -> None:
        self.stop()
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
