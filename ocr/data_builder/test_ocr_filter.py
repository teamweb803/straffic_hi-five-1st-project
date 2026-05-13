"""
OCR 빌더 필터 검증 — 알려진 케이스 4개로 결과 확인.

기대:
  C-220809_05_CR01_01_N3516: "71바" 2줄 plate → layout_fail
  C-220809_06_CR01_02_N0414: "87바" 2줄 plate → layout_fail
  C-220809_08_CR01_01_N0342: "47아" 1줄 plate (Plate2 277x 와 같이 있음) → SAVED
  (multi-plate frame 에서 1줄 plate 가 정상 통과되는지 확인)
"""
import sys, json, re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HANGUL_RE = re.compile(r"[가-힣]")
OCR_PAT = re.compile(r"^\d{2,3}[가-힣]$")

cases = [
    ("D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터/01-1.정식개방데이터/Training/02.라벨링데이터/TL_차량번호판인식_교차로_[cr01]비산사거리_01번/C-220809_05_CR01_01_N3516.json", "71바 2줄"),
    ("D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터/01-1.정식개방데이터/Training/02.라벨링데이터/TL_차량번호판인식_교차로_[cr01]비산사거리_02번/C-220809_06_CR01_02_N0414.json", "87바 2줄"),
    ("D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터/01-1.정식개방데이터/Training/02.라벨링데이터/TL_차량번호판인식_교차로_[cr01]비산사거리_01번/C-220809_08_CR01_01_N0342.json", "47아 1줄 + 277x 같이"),
]

for jp, desc in cases:
    print(f"\n=== {desc} ===")
    print(f"파일: {Path(jp).name}")
    with open(jp, encoding="utf-8") as f:
        meta = json.load(f)
    annots = meta["Learning_Data_Info"]["annotations"]

    for a in annots:
        char_list = a.get("license_plate_number", [])
        for lp in a.get("license_plate", []):
            text = lp.get("text", "")
            bbox = lp.get("bbox")
            cls_id = lp.get("class_ID", "?")
            plate_idx = lp.get("index")

            if not text:
                print(f"  [skip] no text  cls={cls_id} idx={plate_idx}")
                continue

            # 1. text pattern
            if not OCR_PAT.match(text):
                print(f"  [pattern_fail] text='{text}' cls={cls_id} idx={plate_idx}")
                continue

            # 2. plate-local layout check
            same_plate_chars = [c for c in char_list if c.get("index") == plate_idx]
            hg_chars = [c for c in same_plate_chars if HANGUL_RE.search(c.get("text", ""))]
            dg_chars = [c for c in same_plate_chars if c.get("text", "").isdigit()]

            if not hg_chars or not dg_chars:
                print(f"  [layout_fail no_chars] text='{text}' cls={cls_id} idx={plate_idx}  hg={len(hg_chars)} dg={len(dg_chars)}")
                continue

            hg_x_min = min(c["bbox"][0] for c in hg_chars)
            dg_x_max = max(c["bbox"][0] + c["bbox"][2] for c in dg_chars)

            if hg_x_min < dg_x_max:
                hg_x_list = [(c["text"], c["bbox"][0]) for c in hg_chars]
                dg_x_list = [(c["text"], c["bbox"][0]) for c in dg_chars]
                print(f"  [layout_fail] text='{text}' cls={cls_id} idx={plate_idx}  "
                       f"hg_x_min={hg_x_min}<dg_x_max={dg_x_max}")
                print(f"         hangul: {hg_x_list}")
                print(f"         digits: {dg_x_list}")
                continue

            # PASS
            print(f"  [SAVED ✓] text='{text}' cls={cls_id} idx={plate_idx}")
