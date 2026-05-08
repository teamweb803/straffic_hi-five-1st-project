from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.crnn_ocr import CrnnCtcDecoder, preprocess_plate_bgr
from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.webtransport_transport import WebTransportIngressSender


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCR TensorRT crop-to-WebTransport ingress smoke test")
    parser.add_argument("--images-dir", default="/home/jetson/hifive/ocr_samples")
    parser.add_argument("--engine", default="/home/jetson/hifive/engines/ocr_plate_fp16.engine")
    parser.add_argument("--vocab", default="/home/jetson/hifive/models/ocr_vocab.json")
    parser.add_argument("--config", default="/home/jetson/hifive/app/example_runtime_config.py")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--path", default="/hifive/edge")
    parser.add_argument("--server-name", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    return parser.parse_args()


def _cuda_check(err, op: str) -> None:
    cudart = _load_cudart()
    if isinstance(err, tuple):
        err = err[0]

    if err != cudart.cudaError_t.cudaSuccess:
        raise RuntimeError(f"{op} failed: {err}")


def _load_cudart():
    try:
        from cuda import cudart

        return cudart
    except ImportError:
        from cuda.bindings import runtime as cudart

        return cudart


class TensorRtOcrRunner:
    def __init__(self, engine_path: str) -> None:
        import tensorrt as trt

        self.trt = trt
        self.cudart = _load_cudart()
        logger = trt.Logger(trt.Logger.WARNING)
        with Path(engine_path).open("rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())
        if self.engine is None:
            raise RuntimeError(f"cannot deserialize TensorRT engine: {engine_path}")
        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("cannot create TensorRT execution context")

        self.input_name, self.output_name = self._resolve_io_names()
        self.input_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        self.output_shape = tuple(self.engine.get_tensor_shape(self.output_name))
        self.input_dtype = trt.nptype(self.engine.get_tensor_dtype(self.input_name))
        self.output_dtype = trt.nptype(self.engine.get_tensor_dtype(self.output_name))
        if any(dim <= 0 for dim in self.input_shape + self.output_shape):
            raise RuntimeError("dynamic TensorRT shapes are not supported by this smoke test")

        err, self.stream = self.cudart.cudaStreamCreate()
        _cuda_check(err, "cudaStreamCreate")
        self.d_input = self._malloc(int(np.prod(self.input_shape)) * np.dtype(self.input_dtype).itemsize)
        self.d_output = self._malloc(int(np.prod(self.output_shape)) * np.dtype(self.output_dtype).itemsize)
        self.context.set_tensor_address(self.input_name, int(self.d_input))
        self.context.set_tensor_address(self.output_name, int(self.d_output))

    def _resolve_io_names(self) -> tuple[str, str]:
        input_names: list[str] = []
        output_names: list[str] = []
        for index in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(index)
            mode = self.engine.get_tensor_mode(name)
            if mode == self.trt.TensorIOMode.INPUT:
                input_names.append(name)
            else:
                output_names.append(name)
        if len(input_names) != 1 or len(output_names) != 1:
            raise RuntimeError(f"expected 1 input and 1 output, got {input_names=} {output_names=}")
        return input_names[0], output_names[0]

    def _malloc(self, nbytes: int) -> int:
        err, ptr = self.cudart.cudaMalloc(nbytes)
        _cuda_check(err, "cudaMalloc")
        return int(ptr)

    def infer_probs(self, tensor: np.ndarray) -> np.ndarray:
        cudart = self.cudart

        host_input = np.ascontiguousarray(tensor.astype(self.input_dtype, copy=False))
        if tuple(host_input.shape) != self.input_shape:
            raise ValueError(f"bad input shape: {host_input.shape}, expected {self.input_shape}")
        host_output = np.empty(self.output_shape, dtype=self.output_dtype)

        _cuda_check(
            cudart.cudaMemcpyAsync(
                self.d_input,
                host_input.ctypes.data,
                host_input.nbytes,
                cudart.cudaMemcpyKind.cudaMemcpyHostToDevice,
                self.stream,
            ),
            "cudaMemcpyAsync H2D",
        )
        if not self.context.execute_async_v3(self.stream):
            raise RuntimeError("TensorRT execute_async_v3 failed")
        _cuda_check(
            cudart.cudaMemcpyAsync(
                host_output.ctypes.data,
                self.d_output,
                host_output.nbytes,
                cudart.cudaMemcpyKind.cudaMemcpyDeviceToHost,
                self.stream,
            ),
            "cudaMemcpyAsync D2H",
        )
        _cuda_check(cudart.cudaStreamSynchronize(self.stream), "cudaStreamSynchronize")
        return host_output[0]


def label_from_filename(path: Path) -> str:
    return path.stem.split("_", 1)[0]


def load_vocab(path: str) -> str:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    vocab = body["vocab"]
    return "".join(vocab)


def build_event(config: RuntimeConfig, image_path: Path, text: str, confidence: float) -> tuple[str, dict]:
    camera = config.cameras[0]
    event_id = f"ocr-smoke-{time.time_ns()}-{image_path.stem}"
    event = {
        "event_id": event_id,
        "device_id": config.device_id,
        "camera_id": camera.camera_id,
        "camera_group_id": camera.camera_group_id,
        "camera_role": camera.camera_role,
        "lane_no": 1,
        "global_lane_no": 1,
        "local_track_id": f"ocr-{image_path.stem}",
        "vehicle_pass_id": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000+00:00", time.gmtime()),
        "direction": camera.direction,
        "vehicle_confidence": 1.0,
        "plate": {
            "text": text,
            "confidence": confidence,
            "candidate_count": 1,
            "agreement_ratio": 1.0,
        },
        "plate_bbox": {
            "x": 0,
            "y": 0,
            "w": 160,
            "h": 48,
            "unit": "pixel",
            "coord": "plate_crop",
        },
        "needs_review": False,
        "review_reason": "",
        "payload_format": "protobuf",
        "schema_version": config.schema_version,
    }
    return event_id, event


def main() -> None:
    args = parse_args()
    images_dir = Path(args.images_dir)
    image_paths = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    image_paths = image_paths[: args.limit]
    if not image_paths:
        raise RuntimeError(f"no crop images found: {images_dir}")

    config = RuntimeConfig.from_python_file(args.config)
    vocab = load_vocab(args.vocab)
    decoder = CrnnCtcDecoder(vocab)
    runner = TensorRtOcrRunner(args.engine)
    codec = PassageEventCodec(schema_version=config.schema_version)

    spool_root = Path.home() / "hifive" / "spool_ocr_ingress_smoke"
    shutil.rmtree(spool_root, ignore_errors=True)
    spool = FileSpool(spool_root)
    sender = WebTransportIngressSender(
        host=args.host,
        port=args.port,
        path=args.path,
        server_name=args.server_name or args.host,
        verify_tls=False,
        timeout_sec=args.timeout_sec,
        spool=spool,
        retry_enabled=False,
    )

    correct = 0
    total_start = time.perf_counter()
    for image_path in image_paths:
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"{image_path.name}\tread_fail")
            continue

        expected = label_from_filename(image_path)
        ocr_start = time.perf_counter()
        tensor = preprocess_plate_bgr(img)
        probs = runner.infer_probs(tensor)
        decoded = decoder.decode_probs(probs)
        ocr_ms = (time.perf_counter() - ocr_start) * 1000.0

        event_id, event = build_event(config, image_path, decoded.text, decoded.confidence)
        payload = codec.encode(event)
        send_start = time.perf_counter()
        accepted = sender.submit(payload, event_id)
        send_ms = (time.perf_counter() - send_start) * 1000.0

        if decoded.text == expected:
            correct += 1
        print(
            f"{image_path.name}\texpected={expected}\tpred={decoded.text}\t"
            f"conf={decoded.confidence:.4f}\tvalid={decoded.valid_pattern}\t"
            f"ocr_ms={ocr_ms:.2f}\tsend_ms={send_ms:.2f}\taccepted={accepted}"
        )

    total_ms = (time.perf_counter() - total_start) * 1000.0
    print(f"summary total={len(image_paths)} correct={correct} spool_count={spool.count()} total_ms={total_ms:.2f}")


if __name__ == "__main__":
    main()
