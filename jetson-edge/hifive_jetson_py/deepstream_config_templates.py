from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YoloNvinferTemplate:
    engine_path: str
    label_path: str
    parser_library_path: str
    parser_function: str = "NvDsInferParseCustomYoloPlate"
    precision: str = "fp16"

    def render(self) -> str:
        network_mode = "1" if self.precision.lower() == "int8" else "2"
        return f"""[property]
gpu-id=0
model-engine-file={self.engine_path}
labelfile-path={self.label_path}
batch-size=1
network-mode={network_mode}
net-scale-factor=0.00392156862745098
model-color-format=0
num-detected-classes=1
gie-unique-id=1
process-mode=1
network-type=0
cluster-mode=2
maintain-aspect-ratio=1
parse-bbox-func-name={self.parser_function}
custom-lib-path={self.parser_library_path}

[class-attrs-all]
pre-cluster-threshold=0.25
nms-iou-threshold=0.45
topk=50
"""


@dataclass(frozen=True)
class CrnnOcrNvinferTemplate:
    engine_path: str
    vocab_path: str = ""
    parser_library_path: str = ""
    parser_function: str = "NvDsInferParseCustomCrnnPlate"
    precision: str = "fp16"

    def render(self) -> str:
        network_mode = "1" if self.precision.lower() == "int8" else "2"
        parser_lines = ""
        if self.parser_library_path:
            parser_lines = (
                f"parse-classifier-func-name={self.parser_function}\n"
                f"custom-lib-path={self.parser_library_path}\n"
            )
        return f"""[property]
gpu-id=0
model-engine-file={self.engine_path}
labelfile-path={self.vocab_path}
batch-size=1
network-mode={network_mode}
gie-unique-id=2
process-mode=2
network-type=1
operate-on-gie-id=1
operate-on-class-ids=0
classifier-async-mode=1
classifier-threshold=0.0
{parser_lines}"""


@dataclass(frozen=True)
class NvTrackerTemplate:
    tracker_width: int = 640
    tracker_height: int = 384
    ll_lib_file: str = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
    ll_config_file: str = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"

    def element(self) -> str:
        return (
            "nvtracker name=plate_tracker "
            f"tracker-width={self.tracker_width} tracker-height={self.tracker_height} "
            f"ll-lib-file={self.ll_lib_file} ll-config-file={self.ll_config_file} "
            "gpu-id=0"
        )
