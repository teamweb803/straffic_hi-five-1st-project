# Plate Detection TensorRT Export

This workspace exports `yolo.pt` to ONNX and a TensorRT FP16 engine.

## Environment

```powershell
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

The local `.venv` is already created, and the YOLO ONNX/TensorRT dependencies have been installed.

## Export

```powershell
python src\export_models.py
```

Generated files:

- `yolo.onnx`
- `yolo.engine`

The export uses `960x960` input size by default.

## Current Status

`yolo.onnx` and `yolo.engine` have already been generated on this machine.
