"""v5.final 설정 — 고속도로 양산형. Phase 1 데이터 인프라."""
from pathlib import Path

# ===== 데이터 소스 =====
REAL_DIRS       = [
    Path(r"d:/aa/last/train"),
    Path(r"d:/aa/last/train-new"),
]
SYNTH_ROOT      = Path(r"d:/aa/data-new")
SYNTH_MANIFEST  = SYNTH_ROOT / "manifest.csv"          # accepted=1 만 사용

# ===== 산출물 (split freeze) =====
V5_DIR          = Path(r"d:/aa/training/v5")
ART_DIR         = V5_DIR / "artifacts"
SPLITS_DIR      = ART_DIR / "splits"
CKPT_DIR        = Path(r"d:/aa/training/checkpoints_v5")
LOG_DIR         = Path(r"d:/aa/training/logs_v5")
for d in (ART_DIR, SPLITS_DIR, CKPT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

VOCAB_PATH      = ART_DIR / "vocab.json"
RARE_PATH       = ART_DIR / "rare_chars.json"
AUDIT_REPORT    = ART_DIR / "audit_report.json"

TRAIN_INDICES   = SPLITS_DIR / "train_indices.json"
HARD_DEV_IDX    = SPLITS_DIR / "hard_dev_indices.json"
HARD_FINAL_IDX  = SPLITS_DIR / "hard_final_indices.json"
SPLIT_SUMMARY   = SPLITS_DIR / "split_summary.json"
REPORTS_DIR     = Path(r"d:/aa/training/reports_v5")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ===== v6 (fresh real training, 별도 디렉토리 — v5 자산 보호) =====
TT_AB_DIR        = Path(r"C:/Users/3900X/Desktop/tt/ab")
TT_TRAIN_GOOD    = Path(r"C:/Users/3900X/Desktop/tt/train_good")
MANIFEST_V6      = ART_DIR / "manifest_v6.csv"
SPLIT_V6         = ART_DIR / "split_v6.json"
CKPT_DIR_V6      = Path(r"d:/aa/training/checkpoints_v6")
LOG_DIR_V6       = Path(r"d:/aa/training/logs_v6")
REPORT_DIR_V6    = Path(r"d:/aa/training/reports_v6")
for _d in (CKPT_DIR_V6, LOG_DIR_V6, REPORT_DIR_V6):
    _d.mkdir(parents=True, exist_ok=True)


def seed_paths_v6(seed: int) -> dict:
    """v6 per-seed 디렉토리 (v5 와 분리)"""
    ck = CKPT_DIR_V6 / f"seed{seed}"
    lg = LOG_DIR_V6  / f"seed{seed}"
    rp = REPORT_DIR_V6 / f"seed{seed}"
    for d in (ck, lg, rp):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "ckpt_dir":     ck,
        "best_pt":      ck / "best.pt",
        "last_pt":      ck / "last.pt",
        "log_dir":      lg,
        "train_csv":    lg / "train.csv",
        "metrics_json": lg / "metrics.json",
        "eval_json":    lg / "eval_final.json",
        "report_dir":   rp,
        "errors_csv":   rp / "errors.csv",
        "errors_imgs":  rp / "errors",
    }


def seed_paths(seed: int) -> dict:
    """Per-seed 디렉토리 구조"""
    ck   = CKPT_DIR / f"seed{seed}"
    lg   = LOG_DIR  / f"seed{seed}"
    rp   = REPORTS_DIR / f"seed{seed}"
    ck.mkdir(parents=True, exist_ok=True)
    lg.mkdir(parents=True, exist_ok=True)
    rp.mkdir(parents=True, exist_ok=True)
    return {
        "ckpt_dir":     ck,
        "best_pt":      ck / "best.pt",
        "last_pt":      ck / "last.pt",
        "log_dir":      lg,
        "train_csv":    lg / "train.csv",
        "metrics_json": lg / "metrics.json",
        "eval_json":    lg / "eval_final.json",
        "report_dir":   rp,
        "errors_csv":   rp / "errors.csv",
        "errors_imgs":  rp / "errors",
    }

# ===== 입력 =====
IMG_H, IMG_W   = 48, 160
SEQ_LEN        = 40
NUM_CHANNELS   = 3

# ===== 학습 =====
BATCH_SIZE     = 96
LR             = 1e-3
WEIGHT_DECAY   = 1e-4
MAX_EPOCHS     = 100
WARMUP_EPOCHS  = 5
PATIENCE       = 10
NUM_WORKERS    = 4

# ===== Loss =====
FOCAL_GAMMA       = 1.2
RARE_REWEIGHT     = 1.2
LABEL_SMOOTH      = 0.0

# ===== EMA =====
EMA_DECAY      = 0.999
EMA_START_EP   = 10

# ===== AMP / Clip =====
AMP_ENABLED    = True
GRAD_CLIP      = 5.0

# ===== Synthetic Curriculum (epoch → synth ratio) =====
def synth_ratio(epoch: int) -> float:
    if epoch <= 20:    return 0.10
    if epoch <= 50:    return 0.20
    if epoch <= 70:    return 0.25
    return 0.20

# v6: synth max 15% 정책 (사용자 spec)
def synth_ratio_v6(epoch: int) -> float:
    if epoch <= 20:    return 0.10
    if epoch <= 50:    return 0.13
    return 0.15

# Synth 내부 비율
SYNTH_OHJJ_RATIO   = 0.75
SYNTH_YAKHYO_RATIO = 0.25

# ===== Augmentation Curriculum (epoch → phase, source 별 prob 따로) =====
def aug_phase(epoch: int) -> str:
    if epoch <= 20:    return "p1"     # ep 1~20
    if epoch <= 50:    return "p2"     # ep 21~50
    return "p3"                         # ep 51+

# Source 별 (phase, p) — augmentation.py 가 사용
AUG_PROB = {
    "real":   {"p1": 0.15, "p2": 0.30, "p3": 0.40},
    "ohjj":   {"p1": 0.08, "p2": 0.18, "p3": 0.25},
    "yakhyo": {"p1": 0.04, "p2": 0.10, "p3": 0.15},
}

# ===== Hard Validation =====
# 기본 조건
HARD_PLATE_H_MAX     = 40
HARD_LAPLACIAN_MAX   = 100.0
HARD_SKEW_MIN_DEG    = 15.0
HARD_VISIBLE_MAX     = 0.85
# 고속도로 추가
HW_PLATE_H_MAX       = 32          # 더 작은 번호판
HW_JPEG_BLOCK_MIN    = 8.0          # block artifact 의심 임계 (heuristic)
HW_LOW_CONTRAST_MAX  = 30.0         # std(luma) 임계
HW_CROP_EDGE_RATIO   = 0.30        # 가장자리 1px 픽셀 중 fg(글자) 비율 임계
HW_CROP_MIN_SIDES    = 1           # 위 임계를 만족해야 하는 변 개수
# 분리 운영
HARD_DEV_TOTAL       = 250
HARD_FINAL_TOTAL     = 250
# 카테고리 분포 (각 250장 기준)
HARD_CATEGORY_QUOTA = {
    "small_plate": 0.25,    # 62
    "motion_blur": 0.25,    # 62
    "night":       0.20,    # 50
    "crop_cut":    0.15,    # 38
    "skew":        0.10,    # 25
    "rare":        0.05,    # 13
}

# ===== Valid Hangul (고정 40자) =====
# vocab 빌드 시 데이터에서 발견된 문자라도 이 집합 밖이면 제외.
# 데이터에 신규 한글이 들어와도 vocab/num_classes 가 바뀌지 않도록 frozen.
VALID_HANGUL_40 = sorted(set([
    "가","거","고","구",
    "나","너","노","누",
    "다","더","도","두",
    "라","러","로","루",
    "마","머","모","무",
    "바","배","버","보","부",
    "사","서","소","수",
    "아","어","오","우",
    "자","저","조","주",
    "하","허","호",
]))
assert len(VALID_HANGUL_40) == 40, f"VALID_HANGUL_40 must be 40 chars, got {len(VALID_HANGUL_40)}"
VALID_HANGUL = set(VALID_HANGUL_40)
DIGITS = list("0123456789")
VALID_CHAR_SET = set(VALID_HANGUL_40) | set(DIGITS)
NUM_CLASSES_FIXED = len(VALID_CHAR_SET) + 1     # 40 + 10 + 1(blank) = 51

# ===== Rare Hangul =====
# Spec 변경 (사용자 지시):
#   1. low_freq_rare: 데이터 빈도 하위 quantile → sample weight 1.2 적용
#   2. confusable_hangul: 시각적으로 헷갈리는 한글 쌍 (sample weight X, metric/synth 보강용)
LOW_FREQ_RARE_QUANTILE = 0.15        # 하위 15% (40자 중 6자)
LOW_FREQ_RARE_EXPLICIT = []           # 데이터 기준만 사용

# 시각적 confusable 쌍 (한국 번호판 OCR 표준 오인 케이스)
# Group A: 자음 모양 유사 (전통적인 ㄱ/ㄴ, ㄷ/ㄹ, ㅁ/ㅂ, ㅅ/ㅈ, ㅎ/ㅇ 계열)
# Group B (2026-05 추가): yaw/perspective + blur 로 ㅗ/ㅜ, ㅏ/ㅓ, ㅇ/ㅎ/ㅁ 구분 약화 시 발생
#   - 실제 운영 crop에서 관찰된 12쌍
#   - sample weight 는 부여하지 않음 (metric/synth 보강용 only)
CONFUSABLE_PAIRS = [
    # Group A — 기존 (자음 유사)
    ("거","너"), ("더","러"), ("머","버"), ("서","저"),
    ("호","허"), ("자","사"),
    # Group B — 2026-05 관찰 추가 (yaw/perspective)
    ("조","소"), ("어","머"), ("우","두"), ("오","모"),
    ("오","호"), ("루","무"), ("로","루"), ("하","허"),
    ("두","루"), ("러","라"), ("우","무"), ("보","부"),
]
CONFUSABLE_HANGUL = sorted({c for pair in CONFUSABLE_PAIRS for c in pair})

# 하위 호환 alias
RARE_FREQ_QUANTILE = LOW_FREQ_RARE_QUANTILE
RARE_EXPLICIT      = LOW_FREQ_RARE_EXPLICIT

# ===== Composite Score (체크포인트 선택용) =====
W_HARD = 0.5
W_RARE = 0.3
W_OVERALL = 0.2
ECE_PENALTY_15X = -0.005
ECE_FORBID_2X   = True

# ===== Operational Hard Score 가중치 (운영 환경 반영) =====
# 운영(고속도로 CCTV)에서 small_plate 는 거의 발생하지 않는 보조 stress 카테고리.
# 따라서 pass/fail 판단은 이 가중평균을 주 지표로 사용.
OPERATIONAL_HARD_WEIGHTS = {
    "night":       0.25,
    "motion_blur": 0.25,
    "crop_cut":    0.20,
    "skew":        0.15,
    "rare":        0.10,
    "small_plate": 0.05,
}

# ===== 재현성 =====
SEEDS_3RUN = [42, 3407, 2026]

# ===== Parity =====
PARITY_MSE_MAX     = 1e-3
PARITY_ACC_DROP_MAX = 0.005     # 0.5%
PARITY_TOP1_MIN    = 0.99       # 99%

# ===== 라벨 검증 =====
import re
LABEL_PAT_7 = re.compile(r"^\d{2}[가-힣]\d{4}$")
LABEL_PAT_8 = re.compile(r"^\d{3}[가-힣]\d{4}$")
SUFFIX_PAT  = re.compile(r"_(\d+)$")     # 12가3456_2 → label 12가3456


def label_from_stem(stem: str) -> str | None:
    """train 파일 stem 에서 _N suffix 제거 → label. 패턴 미일치 시 None."""
    m = SUFFIX_PAT.search(stem)
    base = stem[:m.start()] if m else stem
    if LABEL_PAT_7.match(base) or LABEL_PAT_8.match(base):
        return base
    return None
