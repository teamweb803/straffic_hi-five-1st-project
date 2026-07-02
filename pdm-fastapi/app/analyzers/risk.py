from app.schemas.pdm import RiskLevel

RISK_ORDER: dict[RiskLevel, int] = {
    "NORMAL": 0,
    "WARNING": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


def clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)


def risk_from_score(score: float) -> RiskLevel:
    if score < 40:
        return "CRITICAL"
    if score < 60:
        return "HIGH"
    if score < 80:
        return "WARNING"
    return "NORMAL"


def max_risk(levels: list[RiskLevel]) -> RiskLevel:
    return max(levels, key=lambda level: RISK_ORDER[level])


def is_anomaly_level(level: RiskLevel) -> bool:
    return level in {"WARNING", "HIGH", "CRITICAL"}
