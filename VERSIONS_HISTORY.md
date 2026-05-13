# Builder Versions History

## OCR Builder (`build_lp_ocr_dataset_vN.py`)

AI Hub plate crop → OCR 학습용 데이터셋 빌더.

| 버전 | 변경점 | 결과 |
|------|--------|------|
| **v1** | 초기: 한글 1자 이상이면 keep, q=90 | "x허" 같은 케이스 통과, 2줄 plate 포함 |
| **v2** | + 엄격 패턴 `^\d{2,3}[가-힣]$`, q=100, class_id 컬럼 | x 마스킹 거부, 1줄/2줄 구분 X |
| **v3** | + Layout filter (한글 x > 모든 숫자 x) | ⚠️ 버그: 모든 plate char 섞임 → 잘못된 거부 |
| **v4** ⭐ | **per-plate `index` 필드로 plate-local 비교** | 정확, 901K 완료 saved 661K |

### 사용 (v4 최종)
```bash
python build_lp_ocr_dataset_v4.py \
    --src "D:/185.CCTV 기반 차량정보 및 교통정보 계측 데이터" \
    --out D:/leb \
    --quality 100
```

### 결과 (v4)
```
출력: D:/leb/
  images/<frame>_p<N>.jpg   plate crops (q=100)
  labels.csv                 filename, text, class_id, source_jpg

소요: 35.7 시간 (901K frames)
saved: 661,295 plates
pattern_fail: 666,311 (x 마스킹 등)
layout_fail:  27,096 (진짜 2줄 plate)
```

---

## Combine Builder (`build_lp_yolo_combine_vN.py`)

901K FHD/UHD frames → lane-stack + jitter combined images (YOLO 학습 데이터).

| 버전 | 변경점 |
|------|--------|
| **v1** | JPG q=90 기본 |
| **v2** ⭐ | **JPG q=100 (최종)** |

### 사용 (v2 최종)
```bash
python build_lp_yolo_combine_v2.py \
    --src D:/lp_yolo_aihub \
    --out_c "C:/Users/3900X/Desktop/crop" \
    --out_d D:/crop \
    --c_min_free_gb 30 \
    --quality 100
```

### 결과 (v2)
```
출력: C:/Users/3900X/Desktop/crop + D:/crop (spillover)
  images/{train,val}/c_NNNNNNN.jpg   960×960 combined
  labels/{train,val}/c_NNNNNNN.txt   YOLO format
  lp.yaml

소요: 60.3 시간 (train 55.8h + val 4.5h)
train: 1,230,792 combined (2,461,585 strips)
val:     142,885 combined (285,770 strips)
합계:  1,373,677 combined images
```

---

## YOLO 학습 시도 (5번)

| # | 환경 | 결과 |
|---|------|------|
| 1 | USB + workers=8 | scanning 단계 중단 (USB 너무 느림) |
| 2 | resume from last.pt (잘못된 path 임베딩) | 즉시 실패 |
| 3 | Fresh start, USB + workers=4 | epoch 2, SSD 이동 결정 |
| 4 | SSD + workers=4 | ep 0 진행 중 workers=8 변경 결정 |
| **5** ⭐ | **SSD + workers=8 (최종)** | **ep22 완료, mAP50 0.983** |

### 최종 학습 명령 (시도 #5)
```bash
yolo detect train \
    model=yolo26s.pt \
    data=C:/Users/3900X/Desktop/lp_yolo_aihub_50k/lp.yaml \
    imgsz=960 epochs=30 batch=16 \
    device=0 workers=8 \
    patience=10 save_period=5 \
    close_mosaic=15 mixup=0.0 copy_paste=0.0 \
    perspective=0.0003 degrees=2 \
    name=lp26s_aihub_50k_pilot
```

### 최종 best (ep22)
```
mAP50:     0.983
mAP50-95:  0.806
Recall:    0.946
Precision: 0.971
```
