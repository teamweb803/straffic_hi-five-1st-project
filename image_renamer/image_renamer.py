"""
이미지 뷰어 + 크롭 + v5 OCR + 파일명 수정 UI
- 폴더 → 좌측 파일 리스트
- 가운데 캔버스: 줌(25~500%), 드래그 크롭 선택
- 우측: 파일명 입력, v5 OCR 자동 입력, 크롭 적용, 이전/다음
"""
import sys, os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

# 한글 폰트 (셀 라벨용)
def _load_korean_font(size):
    for path in ("C:/Windows/Fonts/malgun.ttf",
                 "C:/Windows/Fonts/NanumGothic.ttf",
                 r"d:/aa/synth_tools/ohjj-gen/fonts/NotoSansKR-Medium.ttf"):
        try: return ImageFont.truetype(path, size)
        except Exception: continue
    return ImageFont.load_default()

import re
SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _bundled_path(rel_path: str) -> Path:
    """PyInstaller 번들이면 _MEIPASS, 아니면 스크립트 폴더 기준."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / rel_path
        if p.exists(): return p
    # 개발 모드: 스크립트 위치 기준
    return Path(__file__).parent / rel_path


def _resolve_ckpt() -> str:
    """CKPT 위치: 번들 → 스크립트 옆 → 기본 d:/aa 경로 순"""
    for cand in ("checkpoints_v5/deploy_candidate_seed42.pt",
                 "deploy_candidate_seed42.pt"):
        p = _bundled_path(cand)
        if p.exists(): return str(p)
    return r"d:/aa/training/checkpoints_v5/deploy_candidate_seed42.pt"


def _resolve_vocab() -> str:
    for cand in ("v5/artifacts/vocab.json", "vocab.json"):
        p = _bundled_path(cand)
        if p.exists(): return str(p)
    return r"d:/aa/training/v5/artifacts/vocab.json"
SAVE_SUBDIR = "save"        # 저장 시 자동 생성 + 이동
DEL_SUBDIR  = "del"         # 삭제 시 자동 생성 + 이동
SUBDIR_SET  = {SAVE_SUBDIR, DEL_SUBDIR}
GROUP_SUFFIX_PAT = re.compile(r"^(?P<base>.+?)_\d+$")    # name_N → base 추출


# ===== v5 OCR — ONNX Runtime (가벼운 추론, torch/cv2 의존 X) =====
def _resolve_onnx() -> str:
    for cand in ("checkpoints_v5/deploy_candidate_seed42.onnx",
                 "deploy_candidate_seed42.onnx"):
        p = _bundled_path(cand)
        if p.exists(): return str(p)
    return r"d:/aa/training/checkpoints_v5/deploy_candidate_seed42.onnx"


def _add_cuda_dll_dirs():
    """ORT-GPU 가 cuDNN/CUDA DLL 을 찾도록 site-packages 의 nvidia/* /bin 을 PATH + add_dll_directory 둘 다 등록"""
    bases = []
    try:
        import site
        candidates = list(sys.path)
        try:
            candidates.append(site.getusersitepackages())
            candidates.extend(site.getsitepackages())
        except Exception: pass
        seen = set()
        for sp in candidates:
            if not sp or sp in seen: continue
            seen.add(sp)
            nv = Path(sp) / "nvidia"
            if nv.is_dir(): bases.append(nv)
    except Exception: pass
    added = []
    for base in bases:
        for sub in base.iterdir():
            for cand in (sub / "bin", sub):
                if cand.is_dir() and any(cand.glob("*.dll")):
                    s = str(cand)
                    if s in added: continue
                    added.append(s)
                    if hasattr(os, "add_dll_directory"):
                        try: os.add_dll_directory(s)
                        except OSError: pass
                    # PATH 에도 추가 (ORT 의 LoadLibrary 가 PATH 검색)
                    cur = os.environ.get("PATH", "")
                    if s not in cur:
                        os.environ["PATH"] = s + os.pathsep + cur
    return added


class V5OCRLoader:
    """ONNX Runtime + PIL 기반 경량 OCR 로더 (PyTorch 의존 X)."""
    def __init__(self, onnx_path=None, vocab_path=None):
        import json, numpy as np
        _add_cuda_dll_dirs()
        import onnxruntime as ort
        if onnx_path is None:   onnx_path = _resolve_onnx()
        if vocab_path is None:  vocab_path = _resolve_vocab()

        # CUDA 가능하면 GPU, 아니면 CPU 자동 fallback
        avail = ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {})] if "CUDAExecutionProvider" in avail else []) \
                    + [("CPUExecutionProvider", {})]
        self.sess = ort.InferenceSession(onnx_path, providers=[p[0] for p in providers])
        self.input_name = self.sess.get_inputs()[0].name
        self.output_name = self.sess.get_outputs()[0].name
        self.providers_active = self.sess.get_providers()
        self.device = (
            "cuda" if "CUDAExecutionProvider" in self.providers_active else "cpu"
        )

        with open(vocab_path, encoding="utf-8") as f:
            v = json.load(f)
        chars = v["chars"]
        self.idx2char = {i + 1: c for i, c in enumerate(chars)}
        self.idx2char[0] = ""
        self.num_classes = v["num_classes"]
        self.H, self.W = 48, 160
        self._np = np

    def predict_pil(self, pil_img):
        np = self._np
        im = pil_img.convert("RGB").resize((self.W, self.H), Image.BILINEAR)
        arr = (np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5
        x = arr.transpose(2, 0, 1)[None, ...]                # (1,3,48,160)
        logits = self.sess.run([self.output_name], {self.input_name: x})[0]  # (1,T,V)
        # numpy log_softmax + greedy CTC decode
        m = logits.max(axis=-1, keepdims=True)
        log_probs = logits - m - np.log(np.exp(logits - m).sum(axis=-1, keepdims=True))
        pred = log_probs.argmax(axis=-1)[0]                  # (T,)
        s, prev = [], 0
        for v_ in pred:
            v_ = int(v_)
            if v_ != prev and v_ != 0:
                s.append(self.idx2char.get(v_, ""))
            prev = v_
        return "".join(s)


V3OCR = V5OCRLoader


# ===== 메인 앱 =====
class App:
    def __init__(self, root):
        self.root = root
        root.title("하이파이브 OCR 라벨링")
        root.geometry("1320x860")

        self.folder = None
        self.files = []
        self.idx = -1
        self.pil_image = None      # 현재 PIL 이미지 (편집 후 상태)
        self.tk_image = None
        self.zoom = 100
        self._render_off = (0, 0)         # 캔버스 중앙 배치용 오프셋
        self.crop_box = None        # (x1,y1,x2,y2) in PIL coords
        self._drag_start = None
        self._drag_rect_id = None
        self._image_rect = None     # canvas 좌표계 이미지 경계 (ox, oy, ox+nw, oy+nh)
        self._edge_drag_mode = None # None | 'L'|'R'|'T'|'B'|'TL'|'TR'|'BL'|'BR'
        self.edited_names = set()
        self.grid_n = 3
        self._grid_cells = []           # 셀별 layout 정보
        self._hover_rect_id = None      # 호버 하이라이트 캔버스 객체
        self._crop_undo_stack = []      # [(path_str, PIL.Image)] 최대 30
        self._view_stack = []           # 더블클릭으로 1x1 진입 시 이전 grid_n 푸시
        self._unselected_marks = set()  # 그리드 셀 중 사용자가 클릭으로 해제한 file_idx
        self._grid_view_idx = []        # 그리드 채우기로 고정된 표시 file_idx 리스트 (선택과 별개)
        self.ocr = None

        self._build_ui()
        self._bind_keys()

    # ---------- UI ----------
    def _build_ui(self):
        top = ttk.Frame(self.root); top.pack(side="top", fill="x", padx=6, pady=4)
        ttk.Button(top, text="📂 폴더 (Ctrl+O)", command=self.open_folder).pack(side="left")
        ttk.Button(top, text="◀ 패널", command=self._toggle_right_panel).pack(side="left", padx=6)
        self.folder_label = ttk.Label(top, text="(폴더 없음)", foreground="gray")
        self.folder_label.pack(side="left", padx=10)
        self.count_label = ttk.Label(top, text="")
        self.count_label.pack(side="right")

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=4)

        # 좌측 — 단일 리스트 (현재 폴더 직속 파일만, save/del 서브폴더 제외)
        left = ttk.Frame(body, width=240)
        body.add(left, weight=0)
        self.upper_label = ttk.Label(left, text="📂 대기 (0)")
        self.upper_label.pack(anchor="w")
        lf = ttk.Frame(left); lf.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(lf, activestyle="dotbox", font=("Consolas", 9),
                                  selectmode="extended")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        # 좌측 파일명 클릭 시 그리드 모드면 그 파일 기준으로 NxN 채움
        self.listbox.bind("<ButtonRelease-1>", self._on_listbox_click)

        # 가운데 — 캔버스 (스크롤바 없음) + (사진 바로 아래) 파일명 + 줌
        center = ttk.Frame(body)
        body.add(center, weight=4)
        cf = ttk.Frame(center); cf.pack(side="top", fill="both", expand=True)
        self.canvas = tk.Canvas(cf, background="#222", cursor="cross",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._drag_begin)
        self.canvas.bind("<B1-Motion>",      self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel_zoom)
        self.canvas.bind("<Button-3>",       self._on_right_click)
        self.canvas.bind("<Motion>",         self._on_hover)
        self.canvas.bind("<Leave>",          self._on_canvas_leave)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_dblclick)
        self._build_canvas_menu()

        # 파일명 입력란 제거 — 이름 수정은 좌측 listbox 에서 F2 (또는 더블클릭)
        # (호환을 위해 더미 위젯 유지)
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(center)
        self.ext_label = ttk.Label(center)
        self._last_ocr_text = ""

        # ---- 줌 바 ----
        zb = ttk.Frame(center); zb.pack(side="top", fill="x", pady=4)
        ttk.Label(zb, text="줌:").pack(side="left", padx=4)
        self.zoom_var = tk.IntVar(value=100)
        self.zoom_scale = ttk.Scale(zb, from_=25, to=500, orient="horizontal",
                                    variable=self.zoom_var, command=self._on_zoom)
        self.zoom_scale.pack(side="left", fill="x", expand=True, padx=4)
        self.zoom_label = ttk.Label(zb, text="100%", width=6)
        self.zoom_label.pack(side="left", padx=4)
        for v in (100, 200, 300, 500):
            ttk.Button(zb, text=f"{v}%", width=5,
                       command=lambda x=v: self._set_zoom(x)).pack(side="left", padx=1)
        ttk.Button(zb, text="화면맞춤", command=self.fit_to_window).pack(side="left", padx=4)

        ttk.Label(zb, text="그리드(+/-):").pack(side="left", padx=(8, 2))
        ttk.Button(zb, text="−", width=2, command=lambda: self._adjust_grid(-1)).pack(side="left")
        self.grid_var = tk.StringVar(value=f"{self.grid_n}x{self.grid_n}")
        grid_cb = ttk.Combobox(zb, textvariable=self.grid_var, width=6, state="readonly",
                                values=[f"{i}x{i}" for i in range(1, 11)])
        grid_cb.pack(side="left", padx=2)
        grid_cb.bind("<<ComboboxSelected>>", self._on_grid_change)
        ttk.Button(zb, text="+", width=2, command=lambda: self._adjust_grid(+1)).pack(side="left")

        # 우측 — 컨트롤 (OCR / 크롭 / 네비)
        self._body_paned = body
        right = ttk.Frame(body, width=320)
        self._right_panel = right
        body.add(right, weight=0)
        self._right_panel_visible = True

        # OCR
        ttk.Label(right, text="🔍 v5 OCR", font=("", 10, "bold")).pack(anchor="w")
        # 디바이스 표시 (ONNX Runtime providers 기준)
        try:
            import onnxruntime as _ort
            _avail = _ort.get_available_providers()
            _has_cuda = "CUDAExecutionProvider" in _avail
        except Exception:
            _has_cuda = False
        self.ocr_device_label = ttk.Label(
            right,
            text="🟢 GPU 사용 가능 (ORT-CUDA)" if _has_cuda else "🟡 CPU 모드 (GPU 미가용)",
            foreground=("#080" if _has_cuda else "#a60"),
        )
        self.ocr_device_label.pack(anchor="w")
        ocr_row = ttk.Frame(right); ocr_row.pack(fill="x", pady=2)
        ttk.Button(ocr_row, text="OCR 실행 (1)",
                   command=self.run_ocr).pack(side="left", expand=True, fill="x")
        self.ocr_use_crop = tk.BooleanVar(value=True)
        ttk.Checkbutton(ocr_row, text="크롭 영역만",
                        variable=self.ocr_use_crop).pack(side="left", padx=4)
        self.ocr_result = ttk.Label(right, text="(결과)", foreground="#06c",
                                    font=("Consolas", 14))
        self.ocr_result.pack(anchor="w", pady=2)
        ttk.Button(right, text="↳ 결과를 파일명으로 사용",
                   command=self.use_ocr_as_name).pack(fill="x")

        ttk.Separator(right).pack(fill="x", pady=8)

        # 일괄 저장/삭제 (선택분 전체 → save/del)
        ttk.Label(right, text="📦 일괄", font=("", 10, "bold")).pack(anchor="w")
        bulk_row = ttk.Frame(right); bulk_row.pack(fill="x", pady=2)
        ttk.Button(bulk_row, text="💾 선택분 일괄 저장 → save/",
                   command=self.save_rename).pack(side="left", expand=True, fill="x")
        bulk_row2 = ttk.Frame(right); bulk_row2.pack(fill="x", pady=2)
        ttk.Button(bulk_row2, text="🗑 선택분 일괄 삭제 → del/",
                   command=self.delete_current).pack(side="left", expand=True, fill="x")

        ttk.Separator(right).pack(fill="x", pady=8)

        # 크롭
        ttk.Label(right, text="✂ 크롭", font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(right, text="이미지에서 좌클릭 드래그로 영역 선택",
                  foreground="#666").pack(anchor="w")
        self.crop_info = ttk.Label(right, text="(선택 없음)", foreground="#888",
                                   font=("Consolas", 9))
        self.crop_info.pack(anchor="w")
        crow1 = ttk.Frame(right); crow1.pack(fill="x", pady=2)
        ttk.Button(crow1, text="✂ 크롭 적용 (c)",
                   command=self.apply_crop_overwrite).pack(side="left", expand=True, fill="x")
        crow2 = ttk.Frame(right); crow2.pack(fill="x", pady=2)
        ttk.Button(crow2, text="📋 다른이름 저장",
                   command=self.apply_crop_save_as).pack(side="left", expand=True, fill="x")
        ttk.Button(crow2, text="✗ 선택 해제",
                   command=self.clear_crop).pack(side="left", padx=4)

        ttk.Separator(right).pack(fill="x", pady=8)

        # 네비
        nav = ttk.Frame(right); nav.pack(fill="x")
        ttk.Button(nav, text="◀ 이전 (←)",
                   command=self.prev_image).pack(side="left", expand=True, fill="x")
        ttk.Button(nav, text="다음 (→) ▶",
                   command=self.next_image).pack(side="left", expand=True, fill="x", padx=4)

        # 정보
        ttk.Separator(right).pack(fill="x", pady=8)
        self.info_label = ttk.Label(right, text="", justify="left",
                                    font=("Consolas", 9), foreground="#444")
        self.info_label.pack(anchor="w")

        ttk.Separator(right).pack(fill="x", pady=8)
        ttk.Label(right, text=("단축키:\n"
                                "  ←/→/↑/↓ 이동\n"
                                "  Shift+↑↓ 다중 선택\n"
                                "  Ctrl+클릭 다중 선택\n"
                                "  Ctrl+A 전체 선택\n"
                                "  1  v5 OCR\n"
                                "  2 / Ctrl+S 저장 → save/\n"
                                "  Enter 저장 (입력 중)\n"
                                "  Del → del/\n"
                                "  c 크롭 적용\n"
                                "  테두리 드래그 → 크롭 박스 조정\n"
                                "  Esc 선택해제   Ctrl+휠 줌"),
                  foreground="#666", justify="left").pack(anchor="w")

        bottom_bar = ttk.Frame(self.root); bottom_bar.pack(side="bottom", fill="x")
        self.status = ttk.Label(bottom_bar, text="", anchor="w", background="#eee")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Label(bottom_bar, text="주환님 열심히좀 하세요ㅋㅋㅋ",
                  background="#eee", foreground="#c00",
                  font=("맑은 고딕", 10, "bold")).pack(side="right", padx=8)

    def _bind_keys(self):
        # 좌/우/상/하 모두 이전/다음
        self.root.bind("<Left>",  lambda e: self._maybe_nav(self.prev_image, e))
        self.root.bind("<Right>", lambda e: self._maybe_nav(self.next_image, e))
        self.root.bind("<Up>",    lambda e: self._maybe_nav(self.prev_image, e))
        self.root.bind("<Down>",  lambda e: self._maybe_nav(self.next_image, e))
        self.root.bind("<Control-o>", lambda e: self.open_folder())
        self.root.bind("<Control-O>", lambda e: self.open_folder())
        # 저장: 숫자키 2 + Ctrl+S / OCR: 숫자키 1
        self.root.bind("<Key-1>", lambda e: self._maybe_action(self.run_ocr, e))
        self.root.bind("<KP_1>",  lambda e: self._maybe_action(self.run_ocr, e))
        self.root.bind("<Key-2>", lambda e: self._maybe_action(self.save_rename, e))
        self.root.bind("<KP_2>",  lambda e: self._maybe_action(self.save_rename, e))
        self.root.bind("<Key-3>", lambda e: self._maybe_action(self.rename_to_ocr, e))
        self.root.bind("<KP_3>",  lambda e: self._maybe_action(self.rename_to_ocr, e))
        # Ctrl+S 는 입력란 포커스 여부 무관하게 저장
        self.root.bind_all("<Control-s>", lambda e: self.save_rename())
        self.root.bind_all("<Control-S>", lambda e: self.save_rename())
        # Ctrl+Z: 통합 undo (1x1 진입 복귀 우선, 없으면 크롭 undo)
        self.root.bind_all("<Control-z>", lambda e: self.undo())
        self.root.bind_all("<Control-Z>", lambda e: self.undo())
        # 그리드 +/- (텐키 포함)
        self.root.bind("<plus>",       lambda e: self._adjust_grid(+1))
        self.root.bind("<KP_Add>",     lambda e: self._adjust_grid(+1))
        self.root.bind("<equal>",      lambda e: self._adjust_grid(+1))    # = (Shift 없이 +)
        self.root.bind("<minus>",      lambda e: self._adjust_grid(-1))
        self.root.bind("<KP_Subtract>",lambda e: self._adjust_grid(-1))
        # F2: 좌측 listbox 선택 항목 rename
        self.root.bind("<F2>",         lambda e: self.rename_selected_via_dialog())
        self.listbox.bind("<F2>",      lambda e: (self.rename_selected_via_dialog(), "break")[1])
        # 더블클릭으로도 rename
        self.listbox.bind("<Double-Button-1>",
                          lambda e: (self.rename_selected_via_dialog(), "break")[1])
        # 크롭: c 키 (입력란 포커스 시엔 무시)
        self.root.bind("<c>", lambda e: self._maybe_action(self.apply_crop_overwrite, e))
        self.root.bind("<C>", lambda e: self._maybe_action(self.apply_crop_overwrite, e))
        self.root.bind("<Escape>", lambda e: self.clear_crop())
        self.root.bind("<Delete>", lambda e: self._maybe_action(self.delete_current, e))
        # listbox 단순 방향키 → 우리 prev/next. Shift+방향키는 listbox 기본 동작(범위 확장) 유지.
        for k in ("<Up>", "<Down>", "<Left>", "<Right>"):
            fn = self.prev_image if k in ("<Up>", "<Left>") else self.next_image
            self.listbox.bind(k, lambda e, f=fn: (f(), "break")[1])
        # Shift + 방향키: 다중 선택 확장. Listbox 기본 동작 유지하고 끝에 _on_select 강제 호출
        for k in ("<Shift-Up>", "<Shift-Down>"):
            self.listbox.bind(k, lambda e: self.root.after(1, lambda: self._on_select(None)))
        self.listbox.bind("<Delete>", lambda e: (self.delete_current(), "break")[1])
        # Ctrl+A: 전체 선택
        self.listbox.bind("<Control-a>", lambda e: (self._select_all(), "break")[1])
        self.listbox.bind("<Control-A>", lambda e: (self._select_all(), "break")[1])
        # 윈도 리사이즈 시 자동 fit
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _maybe_nav(self, fn, evt):
        if self.root.focus_get() is self.name_entry: return
        fn()

    def _on_canvas_resize(self, _evt):
        # 캔버스 크기 변동 시 자동 fit (사용자가 직접 줌 조정한 상태가 아닐 때만)
        if self.pil_image is None: return
        # 한 박자 미뤄서 winfo_width 안정화
        self.root.after(10, self.fit_to_window)

    def _maybe_action(self, fn, evt):
        if self.root.focus_get() is self.name_entry: return
        fn()

    # ---------- 폴더 ----------
    def open_folder(self):
        d = filedialog.askdirectory(title="폴더 선택")
        if not d: return
        self.folder = Path(d)
        self.folder_label.configure(text=str(self.folder), foreground="black")
        self._reload_list()

    def _reload_list(self, select_name=None):
        if not self.folder: return
        # folder 직속 파일만 (save/del 서브폴더는 제외 — 별도 폴더 열기 필요)
        files = sorted([p for p in self.folder.iterdir()
                        if p.is_file() and p.suffix.lower() in SUPPORTED])
        self.files = files
        self.listbox.delete(0, "end")
        for p in files: self.listbox.insert("end", p.name)
        self.count_label.configure(text=f"{len(files):,}장")
        self.upper_label.configure(text=f"📂 대기 ({len(files):,})")
        if not files:
            self.idx = -1; self._clear_view(); return
        if select_name:
            names = [p.name for p in files]
            if select_name in names:
                self._select_index(names.index(select_name)); return
        i = max(0, min(self.idx, len(files) - 1))
        self._select_index(i)

    def _select_index(self, i):
        self.idx = i
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(i)
        self.listbox.see(i)
        self._load_current()

    def _on_select(self, _e):
        sel = self.listbox.curselection()
        if not sel: return
        # fixed_grid 모드면 그리드 view 유지, 빨강/노랑 테두리만 갱신
        if self._grid_view_idx and self.grid_n > 1:
            self._render()
            return
        new_idx = sel[0]
        if new_idx != self.idx or len(sel) > 1:
            self.idx = new_idx
            self._load_current()

    def _on_listbox_click(self, evt):
        """좌측 listbox 마우스 클릭 → 그리드 모드면 그 파일 기준으로 NxN 채움"""
        if self.grid_n <= 1: return
        idx = self.listbox.nearest(evt.y)
        if idx < 0 or idx >= len(self.files): return
        self.idx = idx
        self.fill_grid_from_current()

    # ---------- 우클릭 메뉴 / 호버 ----------
    def _build_canvas_menu(self):
        # placeholder — 실제 메뉴는 클릭 위치에 따라 _build_canvas_menu_for_target 가 만든다
        self._canvas_menu = tk.Menu(self.canvas, tearoff=0)
        self._menu_target_idx = -1

    def _build_canvas_menu_for_target(self, target_idx):
        m = tk.Menu(self.canvas, tearoff=0)
        target_name = (self.files[target_idx].name
                        if 0 <= target_idx < len(self.files) else "(없음)")
        m.add_command(label="🧱 그리드 채우기 (현재 위치부터 N²장)",
                      command=self.fill_grid_from_current)
        m.add_separator()
        m.add_command(label=f"✏ 이 파일만 이름 변경  [{target_name}]",
                      command=lambda: self._rename_one(target_idx))
        m.add_command(label=f"🗑 이 파일만 삭제 → del/  [{target_name}]",
                      command=lambda: self._delete_one(target_idx))
        m.add_command(label=f"💾 이 파일만 저장 → save/  [{target_name}]",
                      command=lambda: self._save_one(target_idx))
        m.add_separator()
        m.add_command(label="✂ 크롭 적용", command=self.apply_crop_overwrite)
        m.add_command(label="🔍 v5 OCR", command=self.run_ocr)
        self._canvas_menu = m

    def _rename_one(self, idx):
        if not (0 <= idx < len(self.files)): return
        # 단일 파일만 선택 후 rename 다이얼로그
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.idx = idx
        self.rename_selected_via_dialog()

    def _delete_one(self, idx):
        if not (0 <= idx < len(self.files)): return
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.idx = idx
        self.delete_current()

    def _save_one(self, idx):
        if not (0 <= idx < len(self.files)): return
        # 이름 입력
        p = self.files[idx]
        m_ = GROUP_SUFFIX_PAT.match(p.stem)
        default = m_.group("base") if m_ else p.stem
        new_stem = simpledialog.askstring("이 파일만 저장 (save/)",
                                           f"새 base 이름 (확장자 제외):\n{p.name}",
                                           initialvalue=default, parent=self.root)
        if not new_stem: return
        new_stem = new_stem.strip()
        bad = set('<>:"/\\|?*')
        if any(c in bad for c in new_stem):
            messagebox.showwarning("잘못된 문자", '< > : " / \\ | ? *  사용 불가'); return
        save_dir = self.folder / SAVE_SUBDIR
        save_dir.mkdir(exist_ok=True)
        target = save_dir / (new_stem + p.suffix)
        if target.exists():
            n = 1
            while True:
                n += 1
                cand = save_dir / f"{new_stem}_{n}{p.suffix}"
                if not cand.exists(): target = cand; break
        try:
            import shutil; shutil.move(str(p), str(target))
        except OSError as e:
            messagebox.showerror("이동 실패", str(e)); return
        prev = idx
        self.idx = -1
        self._reload_list()
        if self.files:
            self._select_index(min(prev, len(self.files) - 1))
        self.status.configure(text=f"✔ save/{target.name}")

    def _cell_to_file_index(self, evt):
        """캔버스 좌표 → (cell_row, cell_col, files_index) 또는 None.
        self._grid_cells (compose 시점에 고정된 셀별 file_idx) 를 사용해
        선택 상태와 무관하게 항상 같은 위치 = 같은 파일."""
        if self.pil_image is None or not self._image_rect: return None
        x1, y1, x2, y2 = self._image_rect
        if not (x1 <= evt.x <= x2 and y1 <= evt.y <= y2):
            return None
        n = self.grid_n
        cw_img = max(1, x2 - x1)
        ch_img = max(1, y2 - y1)
        col = min(n - 1, max(0, int((evt.x - x1) * n / cw_img)))
        row = min(n - 1, max(0, int((evt.y - y1) * n / ch_img)))
        cell_idx = row * n + col if n > 1 else 0
        # _grid_cells (compose 시점) 우선 사용
        if self._grid_cells and cell_idx < len(self._grid_cells):
            target_i = self._grid_cells[cell_idx]["file_idx"]
            if 0 <= target_i < len(self.files):
                return (row, col, target_i)
        # fallback (단일 표시)
        if cell_idx == 0 and 0 <= self.idx < len(self.files):
            return (row, col, self.idx)
        return None

    def _on_right_click(self, evt):
        """그리드 모드: 우클릭 = 해당 셀 즉시 del/ 로 이동.
        그 외(1x1 등): 기존 컨텍스트 메뉴."""
        info = self._cell_to_file_index(evt)
        if self.grid_n > 1 and info is not None and self._grid_view_idx:
            _, _, target_i = info
            self._move_one_inplace(target_i, kind="del")
            return
        self._menu_target_idx = info[2] if info else self.idx
        self._build_canvas_menu_for_target(self._menu_target_idx)
        try: self._canvas_menu.tk_popup(evt.x_root, evt.y_root)
        finally: self._canvas_menu.grab_release()

    def _move_one_inplace(self, idx, kind="save"):
        """파일 1장을 save/ 또는 del/ 로 이동 후 그리드 view 같은 위치로 즉시 재충전."""
        if not (0 <= idx < len(self.files)) or self.folder is None: return
        p = self.files[idx]
        sub = SAVE_SUBDIR if kind == "save" else DEL_SUBDIR
        out_dir = self.folder / sub
        out_dir.mkdir(exist_ok=True)
        target = out_dir / p.name
        if target.exists():
            n = 0
            while True:
                n += 1
                cand = out_dir / f"{p.stem}_{n}{p.suffix}"
                if not cand.exists(): target = cand; break
        import shutil
        try: shutil.move(str(p), str(target))
        except OSError as e:
            messagebox.showerror("이동 실패", str(e)); return
        # 그리드 view 의 시작 인덱스 (path 기준 보존)
        if self._grid_view_idx:
            grid_paths = [str(self.files[i]) for i in self._grid_view_idx
                           if 0 <= i < len(self.files) and i != idx]
            start_path = grid_paths[0] if grid_paths else None
        else:
            start_path = None
        self.idx = -1
        self._reload_list()
        if self.files:
            if self.grid_n > 1:
                if start_path:
                    name_set = {p.name: i for i, p in enumerate(self.files)}
                    new_start = name_set.get(Path(start_path).name, 0)
                    self.idx = new_start
                else:
                    self.idx = 0
                self._unselected_marks = set()
                self.fill_grid_from_current()
            else:
                self._select_index(0)
        emoji = "💾" if kind == "save" else "🗑"
        self.status.configure(text=f"{emoji} {sub}/{target.name}")

    def _on_hover(self, evt):
        info = self._cell_to_file_index(evt)
        if info is None:
            self._clear_hover_highlight(); return
        row, col, target_i = info
        name = self.files[target_i].name
        self.status.configure(text=f"hover: {name}  (셀 {row+1},{col+1})")
        # 셀 호버 하이라이트 (그리드 모드만)
        if self._grid_cells and self.grid_n > 1:
            # 호버한 셀의 캔버스 경계
            ox, oy = self._render_off
            s = self.zoom / 100.0
            # 그리드 셀은 self._grid_cells 에 compose 좌표로 저장
            cell_idx = row * self.grid_n + col
            if cell_idx < len(self._grid_cells):
                gc = self._grid_cells[cell_idx]
                cx1 = ox + gc["x"] * s
                cy1 = oy + gc["y"] * s
                cx2 = ox + (gc["x"] + gc["cw"]) * s
                cy2 = oy + (gc["y"] + gc["ch"]) * s
                if self._hover_rect_id:
                    self.canvas.coords(self._hover_rect_id, cx1, cy1, cx2, cy2)
                else:
                    self._hover_rect_id = self.canvas.create_rectangle(
                        cx1, cy1, cx2, cy2,
                        outline="#FFFF00", width=4)
                self.canvas.tag_raise(self._hover_rect_id)
        else:
            self._clear_hover_highlight()

    def _clear_hover_highlight(self):
        if self._hover_rect_id is not None:
            try: self.canvas.delete(self._hover_rect_id)
            except Exception: pass
            self._hover_rect_id = None

    def _on_canvas_leave(self, _evt=None):
        self._clear_hover_highlight()

    def _on_canvas_dblclick(self, evt):
        """셀 더블클릭 → 1x1 모드로 그 파일만 (이전 grid_n 은 _view_stack 에 push)"""
        info = self._cell_to_file_index(evt)
        if info is None: return
        _, _, target_i = info
        if self.grid_n != 1:
            self._view_stack.append(self.grid_n)
        self.grid_n = 1
        self.grid_var.set("1x1")
        self.idx = target_i
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(target_i)
        self.listbox.see(target_i)
        self._load_current()

    def fill_grid_from_current(self):
        """현재 self.idx 부터 grid_n*grid_n 장을 listbox 에서 선택 (모두 빨강 = 처리 대상)"""
        if self.idx < 0 or not self.files: return
        n = self.grid_n
        end = min(self.idx + n * n, len(self.files))
        idxs = list(range(self.idx, end))
        self.listbox.selection_clear(0, "end")
        for i in idxs:
            self.listbox.selection_set(i)
        self.listbox.see(self.idx)
        self._unselected_marks = set()
        self._grid_view_idx = idxs           # 그리드 view 고정
        self._load_current()
        self.status.configure(text=f"🧱 그리드 채우기 {len(idxs)}장 (전부 빨강 — 클릭으로 해제)")

    def _toggle_right_panel(self):
        if self._right_panel_visible:
            self._body_paned.forget(self._right_panel)
            self._right_panel_visible = False
        else:
            self._body_paned.add(self._right_panel, weight=0)
            self._right_panel_visible = True

    def _on_grid_change(self, _evt=None):
        v = self.grid_var.get()
        try: n = int(v.split("x")[0])
        except Exception: n = 1
        self.grid_n = max(1, min(10, n))
        self._grid_view_idx = []
        self._unselected_marks = set()
        # 그리드 모드 자동 진입 (n>1) — 현재 위치부터 NxN 채움
        if self.grid_n > 1 and self.idx >= 0:
            self.fill_grid_from_current()
        elif self.idx >= 0:
            self._load_current()

    def _adjust_grid(self, delta):
        self.grid_n = max(1, min(10, self.grid_n + delta))
        self.grid_var.set(f"{self.grid_n}x{self.grid_n}")
        self._grid_view_idx = []
        self._unselected_marks = set()
        if self.grid_n > 1 and self.idx >= 0:
            self.fill_grid_from_current()
        elif self.idx >= 0:
            self._load_current()

    def _select_all(self):
        self.listbox.selection_set(0, "end")
        self._on_select(None)

    # ---------- 다중 선택 / 그룹 ----------
    def _selected_indices(self):
        """현재 listbox 다중 선택 인덱스. 비어있으면 [self.idx] 반환."""
        sel = list(self.listbox.curselection())
        if sel: return sel
        return [self.idx] if self.idx >= 0 else []

    def _group_indices_of(self, idx):
        """idx 파일과 같은 그룹(stem 또는 stem_N)인 self.files 인덱스 목록 (정렬)"""
        if idx < 0 or idx >= len(self.files): return [idx]
        stem = self.files[idx].stem
        m = GROUP_SUFFIX_PAT.match(stem)
        base = m.group("base") if m else stem
        pat = re.compile(rf"^{re.escape(base)}(?:_\d+)?$")
        out = [i for i, p in enumerate(self.files) if pat.match(p.stem)]
        return out if out else [idx]

    def _compose_grid(self, paths, indices, n=None):
        """N×N 그리드 + 셀 별 파일명 라벨. self._grid_cells 갱신 (셀별 layout)."""
        if n is None: n = self.grid_n
        n = max(1, min(10, int(n)))
        pils, names, idxs = [], [], []
        for p, i in zip(paths[:n * n], indices[:n * n]):
            try:
                im = Image.open(p).convert("RGB"); im.load()
                pils.append(im); names.append(p.stem); idxs.append(i)
            except Exception: continue
        if not pils:
            self._grid_cells = []; return None
        # 통일 셀 크기
        cell_h = max(im.size[1] for im in pils)
        cell_w = max(im.size[0] for im in pils)
        # 셀 라벨 폰트 — 셀 너비에 비례 (작은 그리드일수록 작게)
        font_size = max(12, min(28, cell_w // 12))
        font = _load_korean_font(font_size)
        cells = []
        cells_meta = []
        for im, nm in zip(pils, names):
            w, h = im.size
            scale = min(cell_w / w, cell_h / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            paste_x = (cell_w - nw) // 2
            paste_y = (cell_h - nh) // 2
            rim = im.resize((nw, nh), Image.LANCZOS)
            cell = Image.new("RGB", (cell_w, cell_h), (34, 34, 34))
            cell.paste(rim, (paste_x, paste_y))
            cells_meta.append({
                "orig_w": w, "orig_h": h,
                "paste_x": paste_x, "paste_y": paste_y,
                "paste_w": nw, "paste_h": nh,
            })
            d = ImageDraw.Draw(cell)
            # 라벨 텍스트 측정
            try:
                bbox = d.textbbox((0, 0), nm, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = font_size * len(nm), font_size
            # 좌측 위 — 얇은 외곽선
            tx, ty = 6, 4
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == 0 and dy == 0: continue
                    d.text((tx+dx, ty+dy), nm, font=font, fill="black")
            d.text((tx, ty), nm, font=font, fill="#FFFF00")
            cells.append(cell)
        blank = Image.new("RGB", (cell_w, cell_h), (45, 45, 45))
        while len(cells) < n * n:
            cells.append(blank.copy())
        gap = 4
        sep = (0, 200, 255)
        total_w = cell_w * n + gap * (n - 1)
        total_h = cell_h * n + gap * (n - 1)
        canvas = Image.new("RGB", (total_w, total_h), (20, 20, 20))
        for i, im in enumerate(cells):
            r, c = i // n, i % n
            x = c * (cell_w + gap); y = r * (cell_h + gap)
            canvas.paste(im, (x, y))
        if n > 1:
            d = ImageDraw.Draw(canvas)
            for k in range(1, n):
                gx = k * cell_w + (k - 1) * gap
                d.rectangle([gx, 0, gx + gap - 1, total_h - 1], fill=sep)
                gy = k * cell_h + (k - 1) * gap
                d.rectangle([0, gy, total_w - 1, gy + gap - 1], fill=sep)
        # cells_meta 에 셀의 compose-image 좌표 (x, y, cw, ch, file_idx) 추가
        self._grid_cells = []
        for i, meta in enumerate(cells_meta):
            r, c = i // n, i % n
            cell_x = c * (cell_w + gap); cell_y = r * (cell_h + gap)
            self._grid_cells.append({
                "file_idx": idxs[i],
                "x": cell_x, "y": cell_y, "cw": cell_w, "ch": cell_h,
                **meta,
            })
        return canvas

    def prev_image(self):
        if not self.files: return
        self._select_index(max(0, self.idx - 1))

    def next_image(self):
        if not self.files: return
        self._select_index(min(len(self.files) - 1, self.idx + 1))

    # ---------- 이미지 ----------
    def _load_current(self):
        if self.idx < 0 or self.idx >= len(self.files):
            self._clear_view(); return
        p = self.files[self.idx]
        # 표시 대상: 다중 선택이면 그 선택분, 아니면 자동 그룹
        # _grid_view_idx 가 설정돼있고 grid_n > 1 이면 그것을 고정 표시 (선택 상태와 무관)
        if self._grid_view_idx and self.grid_n > 1:
            target_idx = [i for i in self._grid_view_idx if 0 <= i < len(self.files)]
            mode = "fixed_grid"
        else:
            sel = list(self.listbox.curselection())
            if len(sel) > 1:
                target_idx = sel; mode = "multi"
            else:
                target_idx = self._group_indices_of(self.idx) if self.grid_n > 1 else [self.idx]
                mode = "group" if len(target_idx) > 1 else "single"
        target_paths = [self.files[i] for i in target_idx]

        try:
            if self.grid_n == 1 or (len(target_paths) == 1 and mode != "multi"):
                img = Image.open(target_paths[0]); img.load()
                self.pil_image = img.convert("RGB")
                self._grid_cells = []        # 단일 표시 — 그리드 메타 없음
            else:
                self.pil_image = self._compose_grid(target_paths, target_idx, n=self.grid_n)
                if self.pil_image is None: raise RuntimeError("compose failed")
        except Exception as e:
            messagebox.showerror("로드 실패", f"{p.name}\n{e}")
            self.pil_image = None; self._clear_view(); return

        self.crop_box = None
        self._drag_rect_id = None
        # 이름 입력란: 그룹 base (suffix 제거)
        m = GROUP_SUFFIX_PAT.match(p.stem)
        base_stem = m.group("base") if m else p.stem
        self.name_var.set(base_stem)
        self.ext_label.configure(text=f"확장자: {p.suffix}")
        self.crop_info.configure(text="(선택 없음)", foreground="#888")
        self.ocr_result.configure(text="(결과)")
        self._last_ocr_text = ""
        w, h = self.pil_image.size
        if mode == "single":
            info = f"파일: {p.name}\n크기: {w} × {h}\n경로: {p.parent}"
        else:
            names = "\n  ".join(pp.name for pp in target_paths)
            info = f"[{mode}] {len(target_paths)}장\n  {names}\n캔버스: {w} × {h}"
        self.info_label.configure(text=info)
        self.status.configure(text=f"{self.idx+1}/{len(self.files)} "
                                    f"{p.name}  ({mode}, {len(target_paths)}장)")
        # listbox 에서 그리드/그룹의 파일들을 자동 선택 표시 (fixed_grid 는 fill_grid_from_current 가 처리)
        if mode not in ("multi", "fixed_grid"):
            self.listbox.selection_clear(0, "end")
            for i in target_idx:
                self.listbox.selection_set(i)
            if target_idx:
                self.listbox.see(target_idx[0])
        self._render()
        # 캔버스 크기가 확정된 후 fit (중앙 꽉 채움)
        self.root.after(20, self.fit_to_window)
        # 자동 포커스 제거: 사용자가 직접 클릭해야만 입력란으로 이동

    def _clear_view(self):
        self.canvas.delete("all")
        self.pil_image = None
        self.tk_image = None
        self.name_var.set("")
        self.ext_label.configure(text="")
        self.crop_info.configure(text="")
        self.info_label.configure(text="")
        self.ocr_result.configure(text="")
        self.status.configure(text="")
        self.crop_box = None

    def _render(self):
        if self.pil_image is None: return
        w, h = self.pil_image.size
        s = self.zoom / 100.0
        nw, nh = max(1, int(w * s)), max(1, int(h * s))
        resample = Image.NEAREST if s >= 1.0 else Image.BILINEAR
        resized = self.pil_image.resize((nw, nh), resample)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        ox = max(0, (cw - nw) // 2)
        oy = max(0, (ch - nh) // 2)
        self._render_off = (ox, oy)
        self.canvas.create_image(ox, oy, anchor="nw", image=self.tk_image)
        # 스크롤바 X — scrollregion 미설정
        # 이미지 실제 경계 강조 (밝은 시안 테두리, 두께 굵게)
        self._image_rect = (ox, oy, ox + nw, oy + nh)
        self.canvas.create_rectangle(ox, oy, ox + nw, oy + nh,
                                     outline="#00E5FF", width=4)
        self._redraw_crop_overlay()
        # 그리드 모드: 선택=빨강 / 사용자 해제=노랑
        if self._grid_cells and self.grid_n > 1:
            sel_set = set(self.listbox.curselection())
            s_ratio = self.zoom / 100.0
            for gc in self._grid_cells:
                fi = gc["file_idx"]
                if fi in sel_set:
                    color = "#FF3030"      # 빨강 — 처리 대상
                elif fi in self._unselected_marks:
                    color = "#FFEE00"      # 노랑 — 해제된 셀
                else:
                    continue
                cx1 = ox + gc["x"] * s_ratio
                cy1 = oy + gc["y"] * s_ratio
                cx2 = ox + (gc["x"] + gc["cw"]) * s_ratio
                cy2 = oy + (gc["y"] + gc["ch"]) * s_ratio
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                              outline=color, width=4)
        # 1x1 (단일 표시) 모드면 이미지 하단 1/4 지점, 가운데, 이미지와 겹쳐서 파일명
        if not self._grid_cells and 0 <= self.idx < len(self.files):
            stem = self.files[self.idx].stem
            font = ("맑은 고딕", 22, "bold")
            ocr_t = self._last_ocr_text or ""
            cx = ox + nw // 2                              # 가로 가운데
            cy = oy + int(nh * 4 / 5)                      # 세로 하단 1/5 지점 (위에서 4/5)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == 0 and dy == 0: continue
                    self.canvas.create_text(cx + dx, cy + dy, text=stem,
                                            anchor="center", fill="black", font=font)
            self.canvas.create_text(cx, cy, text=stem,
                                    anchor="center", fill="#FFFF00", font=font)
            # OCR 결과 — 파일명 바로 위, "OCR:" 접두어 없이 결과만
            if ocr_t:
                cy_ocr = cy - 32
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if dx == 0 and dy == 0: continue
                        self.canvas.create_text(cx + dx, cy_ocr + dy, text=ocr_t,
                                                anchor="center", fill="black", font=font)
                self.canvas.create_text(cx, cy_ocr, text=ocr_t,
                                        anchor="center", fill="#00E5FF", font=font)

    def _stroke_text(self, x, y, text, font, fill="#FFEE00", stroke="black"):
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                       (-2, -2), (2, 2), (-2, 2), (2, -2)):
            self.canvas.create_text(x + dx, y + dy, text=text,
                                    fill=stroke, font=font, anchor="center")
        self.canvas.create_text(x, y, text=text,
                                fill=fill, font=font, anchor="center")

    def _draw_filename_overlay(self, cw, ch, nw, nh):
        """이미지 상/하단에 겹쳐서 파일명 오버레이"""
        if 0 <= self.idx < len(self.files):
            stem = self.files[self.idx].stem
        else:
            return
        ox, oy = self._render_off
        x_center = ox + nw // 2
        font = ("Arial", 28, "bold")
        # 상단: 이미지 윗쪽 안쪽 28px
        y_top = oy + 28
        self._stroke_text(x_center, y_top, stem, font)
        # 하단: 이미지 아래쪽 안쪽 28px
        y_bot = oy + nh - 28
        if y_bot - y_top > 50:                    # 너무 작은 이미지면 한 번만
            self._stroke_text(x_center, y_bot, stem, font)

    def _redraw_crop_overlay(self):
        if not self.crop_box or self.pil_image is None: return
        s = self.zoom / 100.0
        ox, oy = self._render_off
        x1, y1, x2, y2 = self.crop_box
        self._drag_rect_id = self.canvas.create_rectangle(
            x1 * s + ox, y1 * s + oy, x2 * s + ox, y2 * s + oy,
            outline="#0f0", width=2, dash=(4, 4),
        )

    # ---------- 크롭 드래그 ----------
    def _canvas_to_pil(self, evt):
        if self.pil_image is None: return None
        cx = self.canvas.canvasx(evt.x)
        cy = self.canvas.canvasy(evt.y)
        ox, oy = self._render_off
        s = self.zoom / 100.0
        return (cx - ox) / s, (cy - oy) / s

    def _hit_edge(self, evt, tol=12):
        """이미지 테두리 근처 클릭이면 ('L'|'R'|'T'|'B'|'TL'|'TR'|'BL'|'BR') 반환"""
        if not self._image_rect: return None
        x, y = evt.x, evt.y
        x1, y1, x2, y2 = self._image_rect
        on_l = abs(x - x1) <= tol and (y1 - tol) <= y <= (y2 + tol)
        on_r = abs(x - x2) <= tol and (y1 - tol) <= y <= (y2 + tol)
        on_t = abs(y - y1) <= tol and (x1 - tol) <= x <= (x2 + tol)
        on_b = abs(y - y2) <= tol and (x1 - tol) <= x <= (x2 + tol)
        if on_t and on_l: return "TL"
        if on_t and on_r: return "TR"
        if on_b and on_l: return "BL"
        if on_b and on_r: return "BR"
        if on_l: return "L"
        if on_r: return "R"
        if on_t: return "T"
        if on_b: return "B"
        return None

    def _drag_begin(self, evt):
        # 클릭 vs 드래그 구분용 시작점 (캔버스 좌표)
        self._press_xy = (evt.x, evt.y)
        self._drag_active = False
        # 테두리 클릭이면 edge-resize 모드, 아니면 기존 free-drag 크롭
        edge = self._hit_edge(evt)
        if edge is not None and self.pil_image is not None:
            self._edge_drag_mode = edge
            if self.crop_box is None:
                W, H = self.pil_image.size
                self.crop_box = (0, 0, W, H)
            self._drag_start = None
            return
        self._edge_drag_mode = None
        p = self._canvas_to_pil(evt)
        if p is None: return
        self._drag_start = p
        if self._drag_rect_id:
            self.canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

    def _drag_move(self, evt):
        # 이동 거리 5px 초과 시 드래그로 인식
        if hasattr(self, "_press_xy") and self._press_xy is not None:
            px, py = self._press_xy
            if abs(evt.x - px) + abs(evt.y - py) > 5:
                self._drag_active = True
        # edge-drag 모드면 crop_box 변경
        if self._edge_drag_mode is not None and self.pil_image is not None:
            p = self._canvas_to_pil(evt)
            if p is None: return
            W, H = self.pil_image.size
            x1, y1, x2, y2 = self.crop_box
            px = max(0, min(W, p[0])); py = max(0, min(H, p[1]))
            m = self._edge_drag_mode
            if "L" in m: x1 = min(px, x2 - 2)
            if "R" in m: x2 = max(px, x1 + 2)
            if "T" in m: y1 = min(py, y2 - 2)
            if "B" in m: y2 = max(py, y1 + 2)
            self.crop_box = (int(x1), int(y1), int(x2), int(y2))
            self._render()
            return
        if self._drag_start is None or self.pil_image is None: return
        p = self._canvas_to_pil(evt)
        if p is None: return
        s = self.zoom / 100.0
        ox, oy = self._render_off
        x1, y1 = self._drag_start
        x2, y2 = p
        cx1, cy1 = min(x1, x2) * s + ox, min(y1, y2) * s + oy
        cx2, cy2 = max(x1, x2) * s + ox, max(y1, y2) * s + oy
        if self._drag_rect_id:
            self.canvas.coords(self._drag_rect_id, cx1, cy1, cx2, cy2)
        else:
            self._drag_rect_id = self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline="#0f0", width=2, dash=(4, 4),
            )

    def _drag_end(self, evt):
        # edge-drag 종료
        if self._edge_drag_mode is not None and self.pil_image is not None:
            self._edge_drag_mode = None
            x1, y1, x2, y2 = self.crop_box
            cw, ch = int(x2 - x1), int(y2 - y1)
            self.crop_info.configure(
                text=f"선택: ({x1},{y1}) ~ ({x2},{y2})  {cw}×{ch}",
                foreground="#080",
            )
            return
        # 드래그 아닌 단순 좌클릭 → 그리드 모드면 해당 셀 즉시 save/ 로 이동
        if not self._drag_active and self._grid_cells and self.grid_n > 1:
            info = self._cell_to_file_index(evt)
            if info is not None:
                _, _, target_i = info
                self._drag_start = None; self._press_xy = None
                self._move_one_inplace(target_i, kind="save")
                return
            self._drag_start = None
            self._press_xy = None
            return
        if self._drag_start is None or self.pil_image is None:
            self._drag_start = None; return
        p = self._canvas_to_pil(evt)
        if p is None:
            self._drag_start = None; return
        x1, y1 = self._drag_start
        x2, y2 = p
        x1, x2 = sorted((x1, x2)); y1, y2 = sorted((y1, y2))
        # PIL 경계 클램프
        W, H = self.pil_image.size
        x1 = max(0, min(W, x1)); x2 = max(0, min(W, x2))
        y1 = max(0, min(H, y1)); y2 = max(0, min(H, y2))
        if x2 - x1 < 3 or y2 - y1 < 3:
            # 클릭만이면 선택 해제
            self.crop_box = None
            self.crop_info.configure(text="(선택 없음)", foreground="#888")
            if self._drag_rect_id:
                self.canvas.delete(self._drag_rect_id); self._drag_rect_id = None
        else:
            self.crop_box = (int(x1), int(y1), int(x2), int(y2))
            cw, ch = int(x2 - x1), int(y2 - y1)
            self.crop_info.configure(
                text=f"선택: ({int(x1)},{int(y1)}) ~ ({int(x2)},{int(y2)})  {cw}×{ch}",
                foreground="#080",
            )
        self._drag_start = None

    def clear_crop(self):
        self.crop_box = None
        if self._drag_rect_id:
            self.canvas.delete(self._drag_rect_id); self._drag_rect_id = None
        self.crop_info.configure(text="(선택 없음)", foreground="#888")

    # ---------- 줌 ----------
    def _on_zoom(self, _v):
        z = int(float(self.zoom_var.get()))
        z = max(25, min(500, z))
        if z != self.zoom:
            self.zoom = z
            self.zoom_label.configure(text=f"{z}%")
            self._render()

    def _set_zoom(self, z):
        z = max(25, min(500, int(z)))
        self.zoom_var.set(z); self._on_zoom(None)

    def _on_wheel_zoom(self, evt):
        if not self.pil_image: return
        self._set_zoom(self.zoom + (25 if evt.delta > 0 else -25))

    def fit_to_window(self):
        """현재 창 크기 그대로, 이미지/그리드를 캔버스 가득 채우는 줌으로만 조정."""
        if not self.pil_image: return
        iw, ih = self.pil_image.size
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        z = int(min(cw / iw, ch / ih) * 100)
        self._set_zoom(max(25, min(500, z)))

    # ---------- rename ----------
    def save_rename(self):
        """
        대상 파일들을 새 base 이름으로 folder/save/ 로 이동.
        대상 = 다중선택분 OR 자동 그룹 (단일선택일 때 stem 같은 _N 묶음).
        다수일 경우 base, base_2, base_3 ... 부여.
        """
        if self.idx < 0 or self.folder is None: return
        new_stem = self.name_var.get().strip()
        if not new_stem:
            messagebox.showwarning("이름 비어있음", "파일명을 입력해주세요."); return
        bad = set('<>:"/\\|?*')
        if any(c in bad for c in new_stem):
            messagebox.showwarning("잘못된 문자", '< > : " / \\ | ? *  사용 불가'); return

        sel = list(self.listbox.curselection())
        if len(sel) > 1:
            target_idx = sorted(sel)
        else:
            target_idx = self._group_indices_of(self.idx)
        target_paths = [self.files[i] for i in target_idx]
        prev_idx = min(target_idx)

        save_dir = self.folder / SAVE_SUBDIR
        save_dir.mkdir(exist_ok=True)
        moved = []
        n_seq = 1
        used = {p.name for p in save_dir.iterdir() if p.is_file()}
        for p in target_paths:
            # 첫번째 파일은 new_stem.jpg, 그 다음은 _2, _3 ...
            while True:
                cand_name = (f"{new_stem}{p.suffix}" if n_seq == 1
                             else f"{new_stem}_{n_seq}{p.suffix}")
                cand_path = save_dir / cand_name
                if cand_name not in used and not cand_path.exists(): break
                n_seq += 1
            target = cand_path
            used.add(cand_name)
            n_seq += 1
            try:
                import shutil
                shutil.move(str(p), str(target))
                moved.append(target.name)
            except OSError as e:
                print(f"[warn] save 실패 {p.name}: {e}")

        self.idx = -1
        # 더블클릭으로 1x1 들어왔던 경우엔 이전 그리드 모드로 복귀
        restored_grid = None
        if self._view_stack and self.grid_n == 1:
            restored_grid = self._view_stack.pop()
            self.grid_n = max(1, min(10, restored_grid))
            self.grid_var.set(f"{self.grid_n}x{self.grid_n}")
        self._reload_list()
        msg = f"✔ save/ 이동 {len(moved)}장: {', '.join(moved[:3])}"
        if len(moved) > 3: msg += f" ... (+{len(moved)-3})"
        if restored_grid:
            msg += f"  → 그리드 {restored_grid}x{restored_grid} 복귀"
        if not self.files:
            self.status.configure(text=msg + " (모든 파일 처리 완료)"); return
        next_i = min(prev_idx, len(self.files) - 1)
        # 그리드 모드면 같은 시작점에서 다시 NxN 채워서 보여줌 (그리드 창 유지)
        if self.grid_n > 1:
            self.idx = next_i
            self.fill_grid_from_current()
        else:
            self._select_index(next_i)
        if not restored_grid:
            msg += f"  → 다음: {self.files[self.idx].name}"
        self.status.configure(text=msg)

    def revert_name(self):
        if 0 <= self.idx < len(self.files):
            self.name_var.set(self.files[self.idx].stem)

    def rename_selected_via_dialog(self, initial_text: str = None):
        """선택된 파일들의 이름 변경 (in-place rename, save 폴더로 이동 X)."""
        sel = list(self.listbox.curselection())
        if not sel: sel = [self.idx] if self.idx >= 0 else []
        if not sel: return
        target_paths = [self.files[i] for i in sel]
        if initial_text:
            default_base = initial_text
        else:
            first_stem = target_paths[0].stem
            m = GROUP_SUFFIX_PAT.match(first_stem)
            default_base = m.group("base") if m else first_stem
        prompt = (f"{len(target_paths)}장의 새 base 이름 (확장자 제외)\n"
                  "- 1장: 그 이름으로 변경\n"
                  "- 다수: 동일 base + _2, _3 ... 자동 부여")
        new_stem = simpledialog.askstring("이름 변경 (F2)", prompt,
                                           initialvalue=default_base, parent=self.root)
        if not new_stem: return
        new_stem = new_stem.strip()
        bad = set('<>:"/\\|?*')
        if any(c in bad for c in new_stem):
            messagebox.showwarning("잘못된 문자", '< > : " / \\ | ? *  사용 불가'); return
        # 같은 폴더에서 in-place rename. 충돌 시 _N
        used = {p.name.lower() for p in target_paths[0].parent.iterdir() if p.is_file()}
        # 자기 자신은 used 에서 제외
        for p in target_paths: used.discard(p.name.lower())
        n_seq = 1
        renamed = []
        for p in target_paths:
            while True:
                cand = (f"{new_stem}{p.suffix}" if n_seq == 1
                        else f"{new_stem}_{n_seq}{p.suffix}")
                if cand.lower() not in used: break
                n_seq += 1
            try:
                new_path = p.with_name(cand)
                p.rename(new_path)
                used.add(cand.lower())
                renamed.append(cand)
            except OSError as e:
                print(f"[warn] rename {p.name}: {e}")
            n_seq += 1
        self._reload_list()
        self.status.configure(text=f"✏ rename {len(renamed)}장: {', '.join(renamed[:3])}"
                                    + (f" ... +{len(renamed)-3}" if len(renamed) > 3 else ""))

    # ---------- delete (folder/del/ 로 이동, 다중 선택 지원) ----------
    def delete_current(self):
        if self.idx < 0 or self.folder is None: return
        sel = list(self.listbox.curselection())
        if len(sel) > 1:
            target_idx = sorted(sel)
        else:
            target_idx = [self.idx]
        target_paths = [self.files[i] for i in target_idx]
        prev_idx = min(target_idx)

        del_dir = self.folder / DEL_SUBDIR
        del_dir.mkdir(exist_ok=True)
        moved = []
        used = {p.name for p in del_dir.iterdir() if p.is_file()}
        for p in target_paths:
            cand = p.name
            n = 1
            while cand in used:
                n += 1
                cand = f"{p.stem}_{n}{p.suffix}"
            used.add(cand)
            try:
                import shutil
                shutil.move(str(p), str(del_dir / cand))
                moved.append(cand)
            except OSError as e:
                print(f"[warn] del 실패 {p.name}: {e}")
        self.idx = -1
        restored_grid = None
        if self._view_stack and self.grid_n == 1:
            restored_grid = self._view_stack.pop()
            self.grid_n = max(1, min(10, restored_grid))
            self.grid_var.set(f"{self.grid_n}x{self.grid_n}")
        self._reload_list()
        msg = f"🗑 del/ 이동 {len(moved)}장"
        if restored_grid:
            msg += f"  → 그리드 {restored_grid}x{restored_grid} 복귀"
        if not self.files: self.status.configure(text=msg); return
        next_i = min(prev_idx, len(self.files) - 1)
        if self.grid_n > 1:
            self.idx = next_i
            self.fill_grid_from_current()
        else:
            self._select_index(next_i)
        self.status.configure(text=msg)

    # ---------- OCR ----------
    def _ensure_ocr(self):
        if self.ocr is not None: return True
        self.status.configure(text="v5 OCR 모델 로드 중... (최초 1회 ~수초)")
        self.root.update_idletasks()
        try:
            self.ocr = V3OCR()
        except Exception as e:
            messagebox.showerror("OCR 로드 실패", str(e))
            self.ocr = None; return False
        dev = self.ocr.device
        is_gpu = dev == "cuda"
        self.ocr_device_label.configure(
            text=(f"🟢 GPU 사용 중 (ORT-CUDA)" if is_gpu
                  else f"🟡 CPU 모드 작동 중 (ORT-CPU)"),
            foreground=("#080" if is_gpu else "#a60"),
        )
        self.status.configure(text=f"v5 OCR 로드됨 ({dev})")
        return True

    def _ocr_target_image(self):
        if self.pil_image is None: return None
        # 그리드 모드면 합성 캔버스 대신 현재 선택된 파일의 원본을 OCR
        if self._grid_cells and 0 <= self.idx < len(self.files):
            try:
                img = Image.open(self.files[self.idx]).convert("RGB")
                img.load()
                # 크롭 영역 옵션은 그리드의 셀 좌표 → 원본 좌표 매핑이 복잡 → 무시
                return img
            except Exception:
                pass
        if self.ocr_use_crop.get() and self.crop_box:
            return self.pil_image.crop(self.crop_box)
        return self.pil_image

    def run_ocr(self):
        if self.pil_image is None: return
        if not self._ensure_ocr(): return
        target = self._ocr_target_image()
        try:
            text = self.ocr.predict_pil(target)
        except Exception as e:
            messagebox.showerror("OCR 실패", str(e)); return
        self.ocr_result.configure(text=text or "(빈 결과)")
        # 결과는 라벨에만 표시 — 자동 rename 안 함. 사용자가 "결과로 이름 변경" 버튼 또는 F2 로 적용.
        self.status.configure(text=f"OCR: {text}")
        # 이미지 위 파일명 좌측에 OCR 결과 오버레이
        self._last_ocr_text = text or ""
        self._render()

    def use_ocr_as_name(self):
        t = self.ocr_result.cget("text")
        if not t or t in ("(결과)", "(빈 결과)"):
            self.status.configure(text="OCR 결과 없음 — 먼저 OCR 실행"); return
        # OCR 결과를 기본값으로 F2 rename 다이얼로그 호출
        self.rename_selected_via_dialog(initial_text=t)

    def rename_to_ocr(self):
        """3번: OCR 결과를 새 이름으로 사용하여 save/ 이동 (다이얼로그 없음)."""
        t = (self._last_ocr_text or "").strip()
        if not t:
            t = self.ocr_result.cget("text").strip()
        if not t or t in ("(결과)", "(빈 결과)"):
            self.status.configure(text="OCR 결과 없음 — 먼저 1번(OCR) 실행"); return
        self.name_var.set(t)
        self.save_rename()

    # ---------- 크롭 적용 ----------
    def _push_crop_undo(self, path: Path, pil_orig):
        self._crop_undo_stack.append((str(path), pil_orig.copy()))
        if len(self._crop_undo_stack) > 30:
            self._crop_undo_stack.pop(0)

    def undo_crop(self):
        if not self._crop_undo_stack:
            self.status.configure(text="⤺ undo: 기록 없음"); return
        path_str, pil = self._crop_undo_stack.pop()
        try:
            pil.save(path_str, quality=95)
        except Exception as e:
            messagebox.showerror("undo 실패", str(e)); return
        self._load_current()
        self.status.configure(text=f"⤺ undo: {Path(path_str).name}")

    def undo(self):
        """통합 undo: 더블클릭으로 들어간 1x1이면 이전 grid 복귀, 그 외엔 크롭 undo"""
        if self._view_stack:
            prev_n = self._view_stack.pop()
            self.grid_n = max(1, min(10, prev_n))
            self.grid_var.set(f"{self.grid_n}x{self.grid_n}")
            self._load_current()
            self.status.configure(text=f"⤺ 그리드 복귀: {self.grid_n}x{self.grid_n}")
            return
        self.undo_crop()

    def _apply_crop_grid_cell(self):
        """그리드 모드에서 crop_box 가 속한 셀 1개에만 크롭 적용."""
        if not self.crop_box or not self._grid_cells: return False
        cb = self.crop_box
        cx = (cb[0] + cb[2]) / 2
        cy = (cb[1] + cb[3]) / 2
        target = None
        for gc in self._grid_cells:
            if gc["x"] <= cx <= gc["x"] + gc["cw"] and \
               gc["y"] <= cy <= gc["y"] + gc["ch"]:
                target = gc; break
        if target is None: return False
        # 셀 안 박스
        lx1 = max(0, cb[0] - target["x"])
        ly1 = max(0, cb[1] - target["y"])
        lx2 = min(target["cw"], cb[2] - target["x"])
        ly2 = min(target["ch"], cb[3] - target["y"])
        # 붙여넣은 사진 안 좌표로
        px, py = target["paste_x"], target["paste_y"]
        pw, ph = target["paste_w"], target["paste_h"]
        ix1 = max(0, lx1 - px); iy1 = max(0, ly1 - py)
        ix2 = min(pw, lx2 - px); iy2 = min(ph, ly2 - py)
        if ix2 - ix1 < 2 or iy2 - iy1 < 2: return False
        # 원본 좌표로 역변환
        ow, oh = target["orig_w"], target["orig_h"]
        sx = ow / max(1, pw); sy = oh / max(1, ph)
        ox1 = int(ix1 * sx); oy1 = int(iy1 * sy)
        ox2 = int(ix2 * sx); oy2 = int(iy2 * sy)
        file_idx = target["file_idx"]
        if not (0 <= file_idx < len(self.files)): return False
        p = self.files[file_idx]
        try:
            orig = Image.open(p).convert("RGB"); orig.load()
            self._push_crop_undo(p, orig)
            cropped = orig.crop((ox1, oy1, ox2, oy2))
            cropped.save(p, quality=95)
        except Exception as e:
            messagebox.showerror("크롭 저장 실패", str(e)); return False
        self.crop_box = None
        if self._drag_rect_id:
            self.canvas.delete(self._drag_rect_id); self._drag_rect_id = None
        self._load_current()
        self.status.configure(text=f"✔ 셀 크롭: {p.name} → ({ox2-ox1}×{oy2-oy1})")
        return True

    def apply_crop_overwrite(self):
        if self.idx < 0 or self.pil_image is None: return
        if not self.crop_box:
            messagebox.showinfo("선택 없음", "크롭 영역을 먼저 드래그로 선택하세요."); return
        # 그리드 모드면 셀별로 단일 파일만 크롭
        if self._grid_cells:
            if self._apply_crop_grid_cell():
                return
            # 셀 매칭 실패 시 전체로 fallback
        # 단일 표시: 현재 파일 자체에 적용
        p = self.files[self.idx]
        cropped = self.pil_image.crop(self.crop_box)
        try:
            self._push_crop_undo(p, self.pil_image.copy())
            cropped.save(p, quality=95)
        except Exception as e:
            messagebox.showerror("저장 실패", str(e)); return
        self.pil_image = cropped
        self.crop_box = None
        self.crop_info.configure(text="(선택 없음)", foreground="#888")
        if self._drag_rect_id:
            self.canvas.delete(self._drag_rect_id); self._drag_rect_id = None
        self._render()
        w, h = cropped.size
        self.info_label.configure(text=f"파일: {p.name}\n크기: {w} × {h}\n경로: {p.parent}")
        self.status.configure(text=f"✔ 크롭 저장: {p.name} ({w}×{h})")

    def apply_crop_save_as(self):
        if self.idx < 0 or self.pil_image is None: return
        if not self.crop_box:
            messagebox.showinfo("선택 없음", "크롭 영역을 먼저 드래그로 선택하세요."); return
        p = self.files[self.idx]
        suggest = f"{p.stem}_crop{p.suffix}"
        new_path = filedialog.asksaveasfilename(
            initialdir=str(p.parent), initialfile=suggest,
            defaultextension=p.suffix,
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("모두", "*.*")],
        )
        if not new_path: return
        cropped = self.pil_image.crop(self.crop_box)
        try:
            cropped.save(new_path, quality=95)
        except Exception as e:
            messagebox.showerror("저장 실패", str(e)); return
        self.status.configure(text=f"✔ 크롭 새 파일: {Path(new_path).name}")
        # 같은 폴더면 리스트에 추가
        if Path(new_path).parent == p.parent:
            self._reload_list(select_name=Path(new_path).name)


def main():
    root = tk.Tk()
    try:
        s = ttk.Style()
        if "vista" in s.theme_names(): s.theme_use("vista")
    except Exception:
        pass
    app = App(root)
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        app.folder = Path(sys.argv[1])
        app.folder_label.configure(text=str(app.folder), foreground="black")
        app._reload_list()
    root.mainloop()


if __name__ == "__main__":
    main()
