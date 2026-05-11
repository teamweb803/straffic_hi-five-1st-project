from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def _load_cudart() -> Any:
    try:
        from cuda import cudart

        return cudart
    except ImportError:
        from cuda.bindings import runtime as cudart

        return cudart


def _cuda_check(err: Any, op: str) -> None:
    cudart = _load_cudart()
    if isinstance(err, tuple):
        err = err[0]
    if err != cudart.cudaError_t.cudaSuccess:
        raise RuntimeError(f"{op} failed: {err}")


class FixedShapeTensorRtEngine:
    def __init__(self, engine_path: str) -> None:
        import tensorrt as trt

        self.trt = trt
        self.cudart = _load_cudart()
        logger = trt.Logger(trt.Logger.WARNING)
        path = Path(engine_path)
        if not path.exists():
            raise FileNotFoundError(f"TensorRT engine not found: {path}")
        with path.open("rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())
        if self.engine is None:
            raise RuntimeError(f"cannot deserialize TensorRT engine: {path}")
        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("cannot create TensorRT execution context")

        self.input_name, self.output_name = self._resolve_io_names()
        self.input_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        self.output_shape = tuple(self.engine.get_tensor_shape(self.output_name))
        self.input_dtype = trt.nptype(self.engine.get_tensor_dtype(self.input_name))
        self.output_dtype = trt.nptype(self.engine.get_tensor_dtype(self.output_name))
        if any(dim <= 0 for dim in self.input_shape + self.output_shape):
            raise RuntimeError("dynamic TensorRT shapes are not supported")

        err, self.stream = self.cudart.cudaStreamCreate()
        _cuda_check(err, "cudaStreamCreate")
        self.d_input = self._malloc(int(np.prod(self.input_shape)) * np.dtype(self.input_dtype).itemsize)
        self.d_output = self._malloc(int(np.prod(self.output_shape)) * np.dtype(self.output_dtype).itemsize)
        self.context.set_tensor_address(self.input_name, int(self.d_input))
        self.context.set_tensor_address(self.output_name, int(self.d_output))

    def infer(self, tensor: np.ndarray) -> np.ndarray:
        host_input = np.ascontiguousarray(tensor.astype(self.input_dtype, copy=False))
        if tuple(host_input.shape) != self.input_shape:
            raise ValueError(f"bad input shape: {host_input.shape}, expected {self.input_shape}")
        host_output = np.empty(self.output_shape, dtype=self.output_dtype)

        cudart = self.cudart
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
        return host_output

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
