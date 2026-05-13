# LP Detector + OCR Deploy Pack

다른 PC (Windows / Linux + GPU) 에서 TensorRT engine 변환용 패키지.

## 파일 목록

### YOLO Detector (번호판 검출)
| 파일 | 용도 |
|------|------|
| `yolo.pt` | YOLOv26s, 50K AI Hub 학습, 1-class license_plate |

학습 스펙:
- 모델: yolo26s
- imgsz: 960 (deployment 도 960×960 입력)
- nc: 1 (license_plate)
- 최종 mAP50: ~0.98+

### v5 OCR (번호판 텍스트 인식)
| 파일 | 용도 |
|------|------|
| `ocr.pt` | PyTorch checkpoint (참고용, 변환에 모델 코드 필요) |
| `ocr.onnx` | **ONNX export, TRT 변환 시작점** ⭐ |
| `ocr_vocab.json` | 글자 vocab (51 classes, 후처리 필수) |
| `v5_model.py` | V5OCR architecture (STN+VGG+CBAM+BiLSTM+CTC) |
| `v5_loss.py` | ctc_decode 함수 (post-process) |
| `v5_grammar.py` | 한국 plate 형식 검증 (post-process) |
| `v5_config.py` | 설정 (입력 size 등) |

OCR 스펙:
- 입력: 48×160 (H×W), 3 channels
- 출력: (B, 40, 51) — sequence × num_classes
- 정규화: (RGB/255 - 0.5) / 0.5 (range [-1,1])
- color: BGR → RGB

## TensorRT Engine 변환

### YOLO Detector
```bash
# Ultralytics CLI 한 번에 변환
yolo export model=yolo.pt format=engine half=true imgsz=960
# → yolo.engine 생성
```

### v5 OCR
```bash
# trtexec 으로 ONNX → engine
trtexec --onnx=ocr.onnx --saveEngine=ocr.engine \
        --fp16 --workspace=4096
# → ocr.engine 생성
```

## 추론 파이프라인

```python
import cv2, numpy as np, json
from ultralytics import YOLO

# 1. YOLO detector
detector = YOLO("yolo.engine")    # or yolo.pt
results = detector.predict("input.jpg", imgsz=960, conf=0.25)

for box in results[0].boxes:
    x1, y1, x2, y2 = box.xyxy[0].tolist()
    plate_crop = results[0].orig_img[int(y1):int(y2), int(x1):int(x2)]
    
    # 2. v5 OCR 전처리
    pre = cv2.resize(plate_crop, (160, 48))
    pre = cv2.cvtColor(pre, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    pre = (pre - 0.5) / 0.5
    pre = pre.transpose(2, 0, 1)[None]   # (1, 3, 48, 160)
    
    # 3. v5 OCR 추론 (TRT/ONNX)
    # logits = ocr_engine.run(pre)  # (1, 40, 51)
    # text = ctc_decode(logits, idx2char)   # see v5_loss.py
```

## 환경 요구사항

| 라이브러리 | 권장 버전 |
|-----------|----------|
| PyTorch | 2.0+ |
| Ultralytics | 8.4+ |
| ONNX | 1.14+ (opset 20 지원) |
| TensorRT | 10.x |
| CUDA | 12.x |
| cuDNN | 9.x |

⚠️ TRT engine 은 **GPU 종속** (compute capability 매칭 필수). 변환은 반드시 **대상 GPU 에서** 수행.

## 추가 정보

- YOLO detector: 학습 데이터 = AI Hub 185 (도시 교차로 CCTV, 902K → 50K subset)
- v5 OCR: 한국 번호판 OCR, 51 chars (40 한글 + 10 digits + 1 blank)
- 둘 다 단일 GPU + AMP 학습됨
- 입력 해상도 매칭 필수 (deployment 960×960 / OCR 48×160)
