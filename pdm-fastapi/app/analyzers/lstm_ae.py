from __future__ import annotations

from statistics import mean, pstdev

from app.analyzers.risk import clamp_score, is_anomaly_level, risk_from_score
from app.schemas.pdm import ModelAnalysisResult, ProcessedMetric

SEQUENCE_FEATURES = [
    "avgOcrConfidence",
    "successRate",
    "missingRate",
    "mismatchRate",
    "eventCountValid",
    "missingBucket",
]

# 추세(지속 저하) 감지 임계: 최근 window 평균이 정상 window 평균 분포에서 이 배수(z) 이상
# '나쁜 방향'으로 벗어나면 느린 드리프트로 본다.
DRIFT_Z_THRESHOLD = 2.0

# 추세 판정에 쓰는 품질 피처와 '나빠지는 방향'(-1: 낮을수록 나쁨, +1: 높을수록 나쁨)
_DRIFT_FEATURE_DIRECTION = {0: -1.0, 1: -1.0, 2: 1.0, 3: 1.0}


class LstmAeAnalyzer:
    model_type = "LSTM_AE"
    model_version = "lstm-ae-v1"

    def analyze(
        self,
        metrics: list[ProcessedMetric],
        target: ProcessedMetric,
        window_size: int,
    ) -> ModelAnalysisResult:
        group = [
            metric
            for metric in metrics
            if metric.camera_id == target.camera_id and metric.lane_id == target.lane_id
        ]
        group = group[-72:]
        windows = _build_windows(group, window_size)
        if len(windows) < 3:
            return self._insufficient_sequence_result(target, group, window_size)

        # Rule/IF와 동일하게 대표(최악) 버킷을 끝으로 하는 window를 평가 대상으로 본다.
        # (이전엔 항상 맨 끝 window만 봐서, 저하 구간이 과거로 밀리면 LSTM만 정상으로 잡혔다.)
        current_idx = _target_window_index(group, target, window_size, len(windows))
        current_window = windows[current_idx]
        history = windows[:current_idx] or windows[: current_idx + 1]
        train_windows = _select_normal_training_windows(history) or history or windows
        error, threshold, backend = self._reconstruction_error(train_windows, current_window)
        # 점(버킷) 단위로는 정상 범위라도, 최근 window의 '평균 수준'이 정상 window 평균 분포에서
        # 지속적으로 벗어났는지(추세 z-score)를 함께 본다. 버킷 분산이 아니라 window 평균 분산을
        # 기준으로 하므로, IF/Rule이 놓치는 느리고 지속적인 드리프트를 LSTM이 고유하게 잡는다.
        drift_z = _sustained_drift_score(train_windows, current_window)
        persistent_quality_issue_ratio = _persistent_quality_issue_ratio(current_window)
        reconstruction_anomaly = error > threshold and persistent_quality_issue_ratio >= 0.6
        drift_anomaly = drift_z >= DRIFT_Z_THRESHOLD and persistent_quality_issue_ratio >= 0.6
        anomaly = reconstruction_anomaly or drift_anomaly
        raw_recon_health = 100 - max(0.0, error - threshold) * 120
        recon_health = raw_recon_health if reconstruction_anomaly else 100
        raw_drift_health = 100 - max(0.0, drift_z - DRIFT_Z_THRESHOLD) * 12
        drift_health = raw_drift_health if drift_anomaly else 100
        health_score = clamp_score(min(recon_health, drift_health))
        if anomaly and health_score >= 80:
            health_score = 79.9
        risk_level = risk_from_score(health_score)

        return ModelAnalysisResult(
            cameraId=target.camera_id,
            laneId=target.lane_id,
            analysisStart=current_window[0]["bucket"].bucket_start,
            analysisEnd=target.bucket_end,
            healthScore=health_score,
            riskLevel=risk_level,
            modelType=self.model_type,
            modelVersion=self.model_version,
            reasonCode="LONG_TERM_DEGRADATION" if anomaly else "NORMAL_SEQUENCE",
            reasonText=(
                "연속된 OCR 품질 시계열의 재구성 오차가 커져 장기 성능 저하 흐름이 의심됩니다."
                if anomaly
                else "연속된 OCR 품질 시계열이 정상적인 흐름에 가깝습니다."
            ),
            recommendedAction=(
                "렌즈 오염, 초점 상태, 설치 각도, 야간 조명 변화를 순서대로 점검하세요."
                if anomaly
                else "정기 점검 주기를 유지하세요."
            ),
            trendSummary=(
                f"최근 {window_size}개 구간을 하나의 시간 구간으로 보고 재구성 오차를 계산했습니다."
            ),
            isAnomaly=is_anomaly_level(risk_level),
            debug={
                "features": SEQUENCE_FEATURES,
                "windowSize": window_size,
                "reconstructionError": error,
                "threshold": threshold,
                "driftZ": drift_z,
                "driftZThreshold": DRIFT_Z_THRESHOLD,
                "persistentQualityIssueRatio": persistent_quality_issue_ratio,
                "reconstructionAnomaly": reconstruction_anomaly,
                "driftAnomaly": drift_anomaly,
                "backend": backend,
                "thresholdRule": "recon error > mean+3sigma, or drift z >= 2.0; both require persistent issue ratio >= 0.6",
            },
        )

    def _reconstruction_error(
        self,
        train_windows: list[list[dict]],
        current_window: list[dict],
    ) -> tuple[float, float, str]:
        try:
            return _torch_lstm_autoencoder_error(train_windows, current_window)
        except Exception:
            return _statistical_sequence_error(train_windows, current_window)

    def _insufficient_sequence_result(
        self,
        target: ProcessedMetric,
        group: list[ProcessedMetric],
        window_size: int,
    ) -> ModelAnalysisResult:
        return ModelAnalysisResult(
            cameraId=target.camera_id,
            laneId=target.lane_id,
            analysisStart=group[0].bucket_start if group else target.bucket_start,
            analysisEnd=target.bucket_end,
            healthScore=75.0,
            riskLevel="WARNING",
            modelType=self.model_type,
            modelVersion=self.model_version,
            reasonCode="INSUFFICIENT_SEQUENCE",
            reasonText="LSTM-AE 판단에 필요한 연속 time window가 부족합니다.",
            recommendedAction="eventCount가 낮은 구간은 삭제하지 말고 추가 시간 구간을 확보해 다시 분석하세요.",
            trendSummary=f"LSTM-AE는 최소 {window_size}개 이상의 연속 구간이 필요합니다.",
            isAnomaly=True,
            debug={"windowSize": window_size, "availableRows": len(group)},
        )


def _build_windows(metrics: list[ProcessedMetric], window_size: int) -> list[list[dict]]:
    rows = [{"bucket": metric, "features": _sequence_vector(metric)} for metric in metrics]
    return [rows[index : index + window_size] for index in range(0, len(rows) - window_size + 1)]


def _sustained_drift_score(
    train_windows: list[list[dict]],
    current_window: list[dict],
) -> float:
    """현재 window 평균이 '정상 window 평균 분포'에서 나쁜 방향으로 몇 σ 벗어났는지.

    버킷 단위 분산(IF가 보는 것)이 아니라 window 평균의 분산을 기준으로 하므로,
    개별 버킷은 정상 범위라도 최근 구간 전체가 지속적으로 치우치면 점수가 커진다.
    """
    if len(train_windows) < 2:
        return 0.0
    best = 0.0
    for feature_index, direction in _DRIFT_FEATURE_DIRECTION.items():
        window_means = [
            mean(row["features"][feature_index] for row in window) for window in train_windows
        ]
        base_mean = mean(window_means)
        base_std = pstdev(window_means) or 0.005
        current_values = [row["features"][feature_index] for row in current_window]
        current_mean = mean(current_values)
        # 지속성 게이트: window의 60% 이상 버킷이 같은(나쁜) 방향일 때만 추세로 인정한다.
        # (한두 버킷짜리 점 이상치는 IF가 잡고, LSTM은 '지속적' 드리프트만 잡도록)
        fraction_bad = mean(
            1.0 if direction * (value - base_mean) > 0 else 0.0 for value in current_values
        )
        if fraction_bad < 0.6:
            continue
        abs_deviation = direction * (current_mean - base_mean)
        # 절대 편차 게이트: 정상 주기 변동 수준(작은 std)으로 z가 폭주해 오탐하지 않도록,
        # 최소 3%p 이상 실제로 벗어난 경우만 본다.
        if abs_deviation < 0.03:
            continue
        z = min(abs_deviation / base_std, 8.0)  # z 상한으로 폭주 방지
        best = max(best, z)
    return best


def _persistent_quality_issue_ratio(current_window: list[dict]) -> float:
    if not current_window:
        return 0.0
    return mean(
        1.0 if _has_quality_issue(row["features"]) else 0.0 for row in current_window
    )


def _has_quality_issue(features: list[float]) -> bool:
    return (
        features[0] < 0.75
        or features[1] < 0.80
        or features[2] > 0.10
        or features[3] > 0.15
        or features[4] < 0.5
        or features[5] > 0.5
    )


def _target_window_index(
    group: list[ProcessedMetric],
    target: ProcessedMetric,
    window_size: int,
    window_count: int,
) -> int:
    """대표(target) 버킷을 끝으로 하는 window의 인덱스. 못 찾으면 마지막 window."""
    pos = next(
        (i for i, metric in enumerate(group) if metric.bucket_start == target.bucket_start),
        None,
    )
    if pos is None:
        return window_count - 1
    return max(0, min(pos - window_size + 1, window_count - 1))


def _select_normal_training_windows(windows: list[list[dict]]) -> list[list[dict]]:
    normal_windows = [window for window in windows if _is_normal_quality_window(window)]
    if len(normal_windows) >= 2:
        return normal_windows
    half = max(1, len(windows) // 2)
    return windows[:half]


def _is_normal_quality_window(window: list[dict]) -> bool:
    avg_confidence = mean(row["features"][0] for row in window)
    avg_success = mean(row["features"][1] for row in window)
    avg_missing = mean(row["features"][2] for row in window)
    avg_mismatch = mean(row["features"][3] for row in window)
    valid_ratio = mean(row["features"][4] for row in window)
    return (
        avg_confidence >= 0.75
        and avg_success >= 0.80
        and avg_missing <= 0.10
        and avg_mismatch <= 0.15
        and valid_ratio >= 0.80
    )


def _sequence_vector(metric: ProcessedMetric) -> list[float]:
    return [
        metric.avg_ocr_confidence / 100,
        metric.success_rate / 100,
        metric.missing_rate / 100,
        metric.mismatch_rate / 100,
        1.0 if metric.event_count_valid else 0.0,
        1.0 if metric.missing_bucket else 0.0,
    ]


def _statistical_sequence_error(
    train_windows: list[list[dict]],
    current_window: list[dict],
) -> tuple[float, float, str]:
    train_errors = []
    baseline = _mean_window(train_windows)
    for window in train_windows:
        train_errors.append(_window_mse(window, baseline))
    current_error = _window_mse(current_window, baseline)
    threshold = mean(train_errors) + 2.5 * (pstdev(train_errors) or 0.001)
    return current_error, threshold, "statistical-fallback"


def _mean_window(windows: list[list[dict]]) -> list[list[float]]:
    width = len(windows[0])
    feature_count = len(windows[0][0]["features"])
    means: list[list[float]] = []
    for step in range(width):
        step_values = []
        for feature_index in range(feature_count):
            step_values.append(mean(window[step]["features"][feature_index] for window in windows))
        means.append(step_values)
    return means


def _window_mse(window: list[dict], baseline: list[list[float]]) -> float:
    squared = []
    for step, row in enumerate(window):
        for feature_index, value in enumerate(row["features"]):
            squared.append((value - baseline[step][feature_index]) ** 2)
    return mean(squared)


def _torch_lstm_autoencoder_error(
    train_windows: list[list[dict]],
    current_window: list[dict],
) -> tuple[float, float, str]:
    import torch
    from torch import nn

    class TorchLstmAutoEncoder(nn.Module):
        def __init__(self, input_size: int, hidden_size: int) -> None:
            super().__init__()
            self.encoder = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
            self.decoder = nn.LSTM(input_size=hidden_size, hidden_size=hidden_size, batch_first=True)
            self.output = nn.Linear(hidden_size, input_size)

        def forward(self, inputs):
            _, (hidden, _) = self.encoder(inputs)
            repeated = hidden[-1].unsqueeze(1).repeat(1, inputs.shape[1], 1)
            decoded, _ = self.decoder(repeated)
            return self.output(decoded)

    torch.manual_seed(42)
    train_tensor = torch.tensor(
        [[row["features"] for row in window] for window in train_windows],
        dtype=torch.float32,
    )
    current_tensor = torch.tensor(
        [[row["features"] for row in current_window]],
        dtype=torch.float32,
    )
    model = TorchLstmAutoEncoder(input_size=train_tensor.shape[-1], hidden_size=8)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()

    model.train()
    for _ in range(30):
        optimizer.zero_grad()
        reconstructed = model(train_tensor)
        loss = criterion(reconstructed, train_tensor)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        train_reconstructed = model(train_tensor)
        train_errors = ((train_reconstructed - train_tensor) ** 2).mean(dim=(1, 2)).tolist()
        current_reconstructed = model(current_tensor)
        current_error = float(((current_reconstructed - current_tensor) ** 2).mean().item())
    threshold = mean(train_errors) + 2.5 * (pstdev(train_errors) or 0.001)
    return current_error, threshold, "torch"
