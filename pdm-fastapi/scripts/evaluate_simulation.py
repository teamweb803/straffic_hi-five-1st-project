from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.scenarios.demo_scenarios import build_demo_metrics
from app.schemas.pdm import AnalyzeRequest, DemoScenarioRequest
from app.services.pdm_analysis_service import PdmAnalysisService

SCENARIO_LABELS = {
    "NORMAL": False,
    "REAR_DEGRADED": True,
    "MISMATCH_SPIKE": True,
    "LOW_TRAFFIC": True,
}


def main() -> None:
    service = PdmAnalysisService()
    rows = []
    start = datetime(2026, 6, 16, 10, 0, 0)

    for index, (scenario_type, expected_anomaly) in enumerate(SCENARIO_LABELS.items()):
        metrics = build_demo_metrics(
            DemoScenarioRequest(
                scenarioType=scenario_type,
                startTime=start + timedelta(hours=index),
                durationMinutes=60,
            )
        )
        result = service.analyze(AnalyzeRequest(metrics=metrics))[0]
        for model_result in result.model_results:
            rows.append(
                {
                    "modelType": model_result.model_type,
                    "expected": expected_anomaly,
                    "predicted": model_result.is_anomaly,
                }
            )

    print("# 시뮬레이션 데이터 기준 성능 평가")
    print()
    print("| 모델 | Precision | Recall | F1 | False Positive | False Negative |")
    print("|---|---:|---:|---:|---:|---:|")
    for model_type, metrics in _calculate_metrics(rows).items():
        print(
            f"| {model_type} | {metrics['precision']:.2f} | {metrics['recall']:.2f} | "
            f"{metrics['f1']:.2f} | {metrics['false_positive']} | {metrics['false_negative']} |"
        )


def _calculate_metrics(rows: list[dict]) -> dict[str, dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["modelType"]].append(row)

    result = {}
    for model_type, model_rows in grouped.items():
        true_positive = sum(1 for row in model_rows if row["expected"] and row["predicted"])
        false_positive = sum(1 for row in model_rows if not row["expected"] and row["predicted"])
        false_negative = sum(1 for row in model_rows if row["expected"] and not row["predicted"])
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result[model_type] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "false_positive": false_positive,
            "false_negative": false_negative,
        }
    return result


if __name__ == "__main__":
    main()
