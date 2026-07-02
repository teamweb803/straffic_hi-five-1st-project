"""앱 라우트 등록 + APScheduler 기동/종료 검증."""
from __future__ import annotations

import os

os.environ["PDM_SCHEDULER_AUTOSTART"] = "false"  # import 시 자동 기동 방지

from app.config import Settings  # noqa: E402
from app.main import app  # noqa: E402
from app.pdm.scheduler import PdmScheduler  # noqa: E402


def main() -> int:
    print("=== ROUTES (OpenAPI 등록 경로) ===")
    # OpenAPI 스키마가 등록된 경로의 권위 있는 목록(_IncludedRouter 내부표현 무관).
    have = set(app.openapi().get("paths", {}).keys())
    for path in sorted(have):
        print(f"  {path}")

    required = {
        "/health",
        "/internal/pdm/run-once",
        "/internal/pdm/status",
        "/analysis/v1/pdm/quality-metrics/analyze",
        "/analysis/v1/pdm/spring/analyze-and-save",
    }
    missing = required - have
    print("\n=== SCHEDULER START/STOP ===")
    sched = PdmScheduler(settings=Settings(analysis_interval_seconds=3600, scheduler_autostart=False))
    sched.start()
    running = sched.scheduler.running
    jobs = [j.id for j in sched.scheduler.get_jobs()]
    sched.shutdown()
    stopped = not sched.scheduler.running
    print(f"  started running={running} jobs={jobs}")
    print(f"  stopped={stopped}")

    print("\n=== CHECKS ===")
    checks = {
        "필수 라우트 모두 등록": not missing,
        "스케줄러 기동": running,
        "pdm_analysis job 등록": "pdm_analysis" in jobs,
        "스케줄러 정상 종료": stopped,
    }
    ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    if missing:
        print(f"  missing routes: {missing}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
