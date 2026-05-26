"""Member dashboard chatbot backed by PostgreSQL and ingress status APIs."""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings


ALLOWED_LANES = (1, 2)
CURRENT_STATUS_RECENT_MINUTES = 5
CURRENT_STATUS_FAILURE_MINUTES = 30
GPS_ACCURACY_REVIEW_METERS = 50.0
KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class DateScope:
    start: datetime | None
    end: datetime | None
    label: str
    period_type: str
    explicit: bool


@dataclass(frozen=True)
class QueryPlan:
    domain: str
    metric: str
    view_type: str
    measure: str
    period_type: str
    start: datetime | None
    end: datetime | None
    group_by: list[str]
    lanes: list[int]
    execution_category: str
    date_label: str
    answer_format: str


@dataclass(frozen=True)
class StatusDecision:
    label: str
    reason: str
    action: str


@dataclass(frozen=True)
class LiveApiStatus:
    checked: bool
    available: bool
    healthy: bool
    status_code: int
    summary: str
    url: str

    @staticmethod
    def not_checked(url: str) -> "LiveApiStatus":
        return LiveApiStatus(False, False, False, 0, "확인 안 함", url)


class ChatbotService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.video_status_url = self._join_url(
            settings.ingress_video_base_url,
            settings.ingress_video_status_path,
        )
        self.ingress_status_url = self._join_url(settings.ingress_video_base_url, "/status")

    def answer(self, question: str) -> dict[str, Any]:
        if not question:
            return self._response(
                "질문이 비어 있습니다. 저는 회원 대시보드 메인 화면 기준으로만 답변할 수 있습니다. 하행 통행, GPS 정상, 검수 대기, 통행료, CCTV, 통신망, 현장 알림처럼 메인 화면에 보이는 항목을 질문해 주세요.",
                "empty_question",
                "error",
                "empty_question",
                "empty_question",
                {},
                [],
                [],
            )

        q = self._normalize(question)
        if self._is_time_question(q):
            return self._time_answer()
        try:
            return self._answer_from_live_sources(question, q)
        except (psycopg.Error, OSError, TimeoutError) as exc:
            return self._data_source_error(exc)

    def _answer_from_live_sources(self, question: str, q: str) -> dict[str, Any]:
        lanes = self._lanes_from_question(q)
        date_scope = self._parse_date_scope(question)
        current_status_kind = self._detect_current_status_kind(q)
        dashboard_answer = self._member_dashboard_answer(q, date_scope, lanes)
        if dashboard_answer is not None:
            return dashboard_answer

        if current_status_kind is None and self._has_no_dashboard_intent(q):
            return self._navigation_guide(question, date_scope, lanes, False)
        if current_status_kind is None and not date_scope.explicit and self._is_vague_domain_only_question(q):
            return self._navigation_guide(question, date_scope, lanes, True)
        if current_status_kind is None and self._is_out_of_scope(q):
            return self._navigation_guide(question, date_scope, lanes, False)

        plan = self._build_query_plan(question, q, date_scope, lanes, current_status_kind)
        if plan.execution_category == "settings":
            return self._settings_guide(plan)
        if current_status_kind is not None and not date_scope.explicit:
            return self._current_status_answer(plan, current_status_kind)
        if plan.execution_category == "settlement":
            return self._settlement_answer(q, plan)
        if plan.execution_category == "passage":
            return self._passage_answer(q, plan)
        if plan.execution_category == "gps":
            return self._gps_answer(q, plan)
        if plan.execution_category == "review":
            return self._review_answer(plan)
        if plan.execution_category in {"camera", "communication", "device"}:
            return self._current_status_answer(plan, {
                "camera": "camera",
                "communication": "network",
                "device": "device",
            }[plan.execution_category])
        return self._control_answer(plan)

    def _is_time_question(self, q: str) -> bool:
        return self._contains_any(q, "현재시간", "지금몇시", "오늘날짜", "날짜알려", "몇년", "몇월", "몇일", "며칠", "몇초")

    def _time_answer(self) -> dict[str, Any]:
        now = self._now_kst()
        answer = f"현재 시각은 {now:%Y년 %m월 %d일 %H시 %M분 %S초}입니다."
        policy = self._answer_policy("live_data_lookup")
        metadata = self._row(
            "start_at", None,
            "end_at", None,
            "queried_at", now.isoformat(timespec="seconds"),
            "timezone", "Asia/Seoul",
        )
        return self._response(answer, "postgresql", "ok", "time", "time", {}, [], [], policy, metadata)

    def _data_source_error(self, exc: Exception) -> dict[str, Any]:
        policy = self._answer_policy("live_data_lookup")
        metadata = self._row(
            "start_at", None,
            "end_at", None,
            "queried_at", self._now_kst().isoformat(timespec="seconds"),
            "timezone", "Asia/Seoul",
            "live", False,
            "error", exc.__class__.__name__,
        )
        return self._response(
            "현재 실제 데이터 저장소에 연결할 수 없어 답변을 만들 수 없습니다. 잠시 후 다시 조회해 주세요.",
            "fastapi_postgres_main_tables",
            "error",
            "data_source_error",
            "data_lookup",
            {},
            [],
            [],
            policy,
            metadata,
        )

    def video_status_snapshot(self) -> dict[str, Any]:
        latest = self._latest_passage_event([])
        received_at = self._as_datetime(latest.get("received_at"))
        event_time = self._as_datetime(latest.get("event_time"))
        latest_time = received_at or event_time
        camera_id = self._text(latest.get("camera_id"), "")
        needs_review = self._bool(latest.get("needs_review"))

        if not latest:
            status = "unknown"
            healthy = False
            reason = "DB에 카메라 이벤트가 없습니다."
        elif self._is_failure(latest_time):
            status = "failure"
            healthy = False
            reason = "최신 카메라 이벤트 수신이 장시간 멈춰 있습니다."
        elif needs_review or not camera_id:
            status = "review"
            healthy = False
            reason = "최신 카메라 이벤트에 검수 조건이 있습니다."
        elif not self._is_recent(latest_time):
            status = "review"
            healthy = False
            reason = "최신 카메라 이벤트 수신이 최근 기준을 넘었습니다."
        else:
            status = "ok"
            healthy = True
            reason = "최신 카메라 이벤트가 최근 기준 안에 수신됐습니다."

        return {
            "status": status,
            "available": True,
            "healthy": healthy,
            "reason": reason,
            "camera_id": camera_id or None,
            "latest_received_at": self._format_datetime(latest_time),
            "elapsed": self._elapsed_label(latest_time),
            "queried_at": self._now_kst().isoformat(timespec="seconds"),
        }

    def _connect(self):
        return psycopg.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            dbname=self.settings.db_name,
            user=self.settings.db_user,
            password=self.settings.db_password,
            connect_timeout=self.settings.db_connect_timeout_sec,
            options=f"-c statement_timeout={self.settings.db_statement_timeout_ms}",
            row_factory=dict_row,
        )

    def _build_query_plan(
        self,
        question: str,
        q: str,
        raw_date_scope: DateScope,
        lanes: list[int],
        current_status_kind: str | None,
    ) -> QueryPlan:
        domain = self._detect_domain(q)
        execution_category = self._execution_category(domain, q)
        date_scope = raw_date_scope
        if not raw_date_scope.explicit and current_status_kind is None and self._should_default_today(q):
            date_scope = self._today_scope(False)
        metric = self._metric_for(domain, execution_category, q, current_status_kind)
        view_type = "current_status" if current_status_kind and not raw_date_scope.explicit else (
            "status_breakdown" if execution_category in {"settlement", "gps", "review", "camera", "communication", "device"} else "overview"
        )
        answer_format = "table" if self._wants_table(q, metric) else "summary"
        return QueryPlan(
            domain=domain,
            metric=metric,
            view_type=view_type,
            measure="count_and_sum" if metric == "settlement_amount" else "count",
            period_type="realtime" if current_status_kind and not raw_date_scope.explicit else date_scope.period_type,
            start=date_scope.start,
            end=date_scope.end,
            group_by=self._default_group_by(execution_category, metric, current_status_kind),
            lanes=lanes,
            execution_category=execution_category,
            date_label=date_scope.label,
            answer_format=answer_format,
        )

    def _current_status_answer(self, plan: QueryPlan, kind: str) -> dict[str, Any]:
        latest = self._latest_passage_event(plan.lanes)
        latest_gps = self._latest_gps_telemetry()
        latest_toll = self._latest_toll_history()
        video_status = self._check_video_status() if kind in {"camera", "network", "device"} else LiveApiStatus.not_checked(self.video_status_url)
        ingress_status = self._check_ingress_status() if kind in {"camera", "network", "device", "event_receive", "data_sync"} else LiveApiStatus.not_checked(self.ingress_status_url)
        plan_map = self._query_plan_map(plan)
        policy = self._answer_policy("current_status")

        if not latest and not latest_gps and not latest_toll and not video_status.checked and not ingress_status.checked:
            return self._response(
                "현재 상태를 판단할 최신 데이터가 없습니다.",
                "fastapi_postgres_current_status",
                "ok",
                "current_status",
                "data_lookup",
                plan_map,
                [],
                [],
                policy,
                self._metadata(plan_map, policy, latest),
            )

        received_at = self._as_datetime(latest.get("received_at"))
        event_time = self._as_datetime(latest.get("event_time"))
        passage_time = received_at or event_time
        lane_text = f"{self._join_lanes(plan.lanes)} " if plan.lanes else ""
        details: list[str] = []
        dashboard_snapshot = self._dashboard_snapshot()
        network_label = self._snapshot_text(dashboard_snapshot, "network_status", "LAN 사용")

        if kind == "camera":
            camera_id = self._text(latest.get("camera_id"), "없음")
            decision = self._decide_camera_status(video_status, latest, passage_time)
            subject = "CCTV 영상"
            details.extend([
                f"카메라={camera_id}",
                f"최근 수신={self._format_datetime(passage_time)}({self._elapsed_label(passage_time)})",
            ])
        elif kind == "gps":
            decision = self._decide_gps_status(latest_gps, latest, passage_time)
            subject = "GPS 수신"
            details.append(self._gps_evidence(latest_gps, latest, passage_time))
        elif kind == "event_receive":
            decision = self._decide_event_receive_status(passage_time)
            subject = "이벤트 수신"
            details.extend([
                f"최근 수신={self._format_datetime(received_at)}({self._elapsed_label(passage_time)})",
            ])
        elif kind == "network":
            decision = self._decide_network_status(video_status, passage_time)
            subject = "통신망"
            details.extend([
                f"사용망={network_label}",
                f"최근 수신={self._format_datetime(passage_time)}({self._elapsed_label(passage_time)})",
            ])
        elif kind == "data_sync":
            latest_data_time = self._latest_data_time(latest, latest_gps, latest_toll)
            decision = self._decide_data_sync_status(latest, latest_data_time)
            subject = "데이터 반영"
            details.extend([
                f"최근 통행={self._format_datetime(passage_time)}",
                f"최신 GPS={self._format_datetime(self._as_datetime(latest_gps.get('received_at')))}",
                f"최신 정산={self._format_datetime(self._as_datetime(latest_toll.get('charged_at')))}",
            ])
        else:
            camera_decision = self._decide_camera_status(video_status, latest, passage_time)
            event_decision = self._decide_event_receive_status(passage_time)
            gps_decision = self._decide_gps_status(latest_gps, latest, passage_time)
            data_decision = self._decide_data_sync_status(latest, self._latest_data_time(latest, latest_gps, latest_toll))
            decision = self._decide_device_status(camera_decision, event_decision, gps_decision, data_decision)
            subject = "장비"
            details.extend([
                f"CCTV={camera_decision.label}",
                f"이벤트 수신={event_decision.label}",
                f"GPS={gps_decision.label}",
                f"데이터 반영={data_decision.label}",
            ])

        if kind == "network":
            answer = (
                f"현재 통신망은 {network_label}이고 상태는 {decision.label}입니다. "
                f"{decision.reason} 확인 내용: {'; '.join(details)}. {decision.action}"
            )
        else:
            answer = (
                f"현재 {lane_text}{subject} 상태는 {decision.label}입니다. "
                f"{decision.reason} 확인 내용: {'; '.join(details)}. {decision.action}"
            )
        response_query_type = "gps" if kind == "gps" else "equipment"
        return self._response(
            answer,
            "fastapi_postgres_current_status",
            "ok",
            response_query_type,
            "data_lookup",
            plan_map,
            [],
            [],
            policy,
            self._metadata(plan_map, policy, latest),
        )

    def _passage_answer(self, q: str, plan: QueryPlan) -> dict[str, Any]:
        where, params = self._passage_where_params(plan)
        total = self._count(f"SELECT COUNT(*) FROM passage_event {where}", params)
        lane1 = self._count(f"SELECT COUNT(*) FROM passage_event {self._append_condition(where, 'lane_no = 1')}", params)
        lane2 = self._count(f"SELECT COUNT(*) FROM passage_event {self._append_condition(where, 'lane_no = 2')}", params)
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        if "통행량" in q or "몇대" in q:
            table = [
                self._row("차선", "1차선", "차량 대수", lane1),
                self._row("차선", "2차선", "차량 대수", lane2),
            ] if self._should_include_table(plan) else []
            answer = f"현재 DB 기준 {plan.date_label} 통행량은 총 {self._format_number(total)}대입니다. 1차선 {self._format_number(lane1)}대, 2차선 {self._format_number(lane2)}대가 통과했습니다. 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
        else:
            table = [
                self._row("차선", "1차선", "건수", lane1),
                self._row("차선", "2차선", "건수", lane2),
            ] if self._should_include_table(plan) else []
            answer = f"현재 DB 기준 {plan.date_label} 통행 이벤트는 총 {self._format_number(total)}건입니다. 1차선 {self._format_number(lane1)}건, 2차선 {self._format_number(lane2)}건입니다. 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "passage", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _settlement_answer(self, q: str, plan: QueryPlan) -> dict[str, Any]:
        where, params = self._toll_where_params(plan)
        if plan.metric in {"settlement_hold", "settlement_waiting", "settlement_failed", "settlement_paid"}:
            filtered_where, filtered_params, label = self._settlement_status_filter(where, params, plan.metric)
            total = self._count(f"SELECT COUNT(*) FROM toll_history {filtered_where}", filtered_params)
            amount = self._count(f"SELECT COALESCE(SUM(amount), 0) FROM toll_history {filtered_where}", filtered_params)
            policy = self._answer_policy("live_data_lookup")
            plan_map = self._query_plan_map(plan)
            table = self._status_rows(
                f"SELECT COALESCE(payment_status, '없음') AS name, COUNT(*) AS count FROM toll_history {filtered_where} GROUP BY payment_status ORDER BY count DESC",
                filtered_params,
                "상태",
            ) if self._should_include_table(plan) else []
            note = " 사유가 따로 저장된 항목은 없어서 보류/대기 상태 기준으로 조회했습니다." if plan.metric == "settlement_hold" and self._contains_any(q, "통신", "지연", "네트워크") else ""
            answer = f"현재 DB 기준 {plan.date_label} {label}는 {self._format_number(total)}건, 금액은 {self._format_number(amount)}원입니다.{note} 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
            return self._response(answer, "fastapi_postgres_main_tables", "ok", "settlement", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

        total = self._count(f"SELECT COUNT(*) FROM toll_history {where}", params)
        amount = self._count(f"SELECT COALESCE(SUM(amount), 0) FROM toll_history {where}", params)
        if plan.metric == "settlement_daily_status":
            return self._settlement_daily_answer(plan, where, params, total, amount)
        table = self._status_rows(
            f"SELECT COALESCE(payment_status, '없음') AS name, COUNT(*) AS count FROM toll_history {where} GROUP BY payment_status ORDER BY count DESC",
            params,
            "상태",
        ) if self._should_include_table(plan) else []
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        answer = f"현재 DB 기준 {plan.date_label} 정산 현황입니다. 총 {self._format_number(total)}건, 총 정산 금액은 {self._format_number(amount)}원입니다. 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "settlement", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _settlement_daily_answer(self, plan: QueryPlan, where: str, params: list[Any], total: int, amount: int) -> dict[str, Any]:
        rows = self._query_all(
            "SELECT CAST(charged_at AS date) AS settlement_date, COALESCE(payment_status, '없음') AS payment_status, COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount "
            f"FROM toll_history {where} GROUP BY CAST(charged_at AS date), payment_status ORDER BY settlement_date DESC, count DESC LIMIT 30",
            params,
        )
        table = [
            self._row("날짜", str(row.get("settlement_date")), "정산 상태", self._text(row.get("payment_status"), "없음"), "건수", row.get("count", 0), "금액", f"{self._format_number(row.get('amount', 0))}원")
            for row in rows
        ]
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        answer = (
            f"현재 DB 기준 {plan.date_label} 날짜별 정산 현황입니다. 총 {self._format_number(total)}건, 총 정산 금액은 {self._format_number(amount)}원입니다. 표는 최근 날짜순 최대 30개 행입니다. 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
            if table else
            f"현재 DB 기준 {plan.date_label} 날짜별 정산 데이터가 없습니다. 이 답변은 요청 시점에 DB를 다시 조회한 결과입니다."
        )
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "settlement", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _gps_answer(self, q: str, plan: QueryPlan) -> dict[str, Any]:
        where, params = self._passage_where_params(plan)
        table = self._status_rows(
            f"SELECT COALESCE(gps_judgement_status, '없음') AS name, COUNT(*) AS count FROM passage_event {where} GROUP BY gps_judgement_status ORDER BY count DESC",
            params,
            "GPS 판정",
        ) if self._should_include_table(plan) else []
        total = self._count(f"SELECT COUNT(*) FROM passage_event {where}", params)
        normal_where = self._append_condition(where, "gps_judgement_status = '정상'")
        normal = self._count(f"SELECT COUNT(*) FROM passage_event {normal_where}", params)
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        lane_text = f" {self._join_lanes(plan.lanes)}" if plan.lanes else ""
        if "정상" in q:
            rate = (normal / total * 100) if total else 0
            answer = f"현재 DB 기준 {plan.date_label}{lane_text} GPS 정상 판정은 {self._format_number(normal)}건입니다. 전체 {self._format_number(total)}건 중 정상률은 {rate:.1f}%입니다."
        else:
            answer = f"현재 DB 기준 {plan.date_label}{lane_text} GPS 판정 현황입니다. 총 {self._format_number(total)}건을 DB에서 다시 조회했습니다."
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "gps", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _review_answer(self, plan: QueryPlan) -> dict[str, Any]:
        where, params = self._passage_where_params(plan)
        total = self._count(f"SELECT COUNT(*) FROM passage_event {where}", params)
        review = self._count(f"SELECT COUNT(*) FROM passage_event {self._append_condition(where, 'needs_review = true')}", params)
        table = self._status_rows(
            f"SELECT name, COUNT(*) AS count FROM (SELECT COALESCE(inspection_status, CASE WHEN needs_review THEN '검수필요' ELSE '검수불필요' END) AS name FROM passage_event {where}) review_status GROUP BY name ORDER BY count DESC",
            params,
            "검수 상태",
        ) if self._should_include_table(plan) else []
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        answer = f"현재 DB 기준 {plan.date_label} 검수 현황입니다. 전체 {self._format_number(total)}건 중 검수 필요는 {self._format_number(review)}건입니다."
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "review", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _control_answer(self, plan: QueryPlan) -> dict[str, Any]:
        where, params = self._passage_where_params(plan)
        total = self._count(f"SELECT COUNT(*) FROM passage_event {where}", params)
        review = self._count(f"SELECT COUNT(*) FROM passage_event {self._append_condition(where, 'needs_review = true')}", params)
        table = [
            self._row("구분", "전체 통행", "건수", total),
            self._row("구분", "검수 필요", "건수", review),
        ] if self._should_include_table(plan) else []
        policy = self._answer_policy("live_data_lookup")
        plan_map = self._query_plan_map(plan)
        answer = f"현재 DB 기준 {plan.date_label} 실시간 관제 현황입니다. 전체 통행은 {self._format_number(total)}건, 검수 필요는 {self._format_number(review)}건입니다."
        return self._response(answer, "fastapi_postgres_main_tables", "ok", "control", "data_lookup", plan_map, table, [], policy, self._metadata(plan_map, policy, self._latest_passage_event([])))

    def _settings_guide(self, plan: QueryPlan) -> dict[str, Any]:
        policy = self._answer_policy("category_guide")
        plan_map = self._query_plan_map(plan)
        return self._response("설정 메뉴는 데이터 집계 조회가 아니라 회원 대시보드 표시, 알림, 운영 옵션을 확인하는 영역입니다.", "dashboard_category_guide", "ok", "settings", "category_guide", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

    def _member_dashboard_answer(self, q: str, date_scope: DateScope, lanes: list[int]) -> dict[str, Any] | None:
        if not self._contains_any(
            q,
            "인식방향", "운행방향", "최근gps", "최근판정", "gps판정", "차량번호", "통과시각", "결제판정",
            "yolo", "fps", "해상도", "모델", "레일", "구역상태", "운영상태", "현장알림", "알림",
            "센터", "서울톨링", "선택방향", "현재화면", "통신망", "통신", "네트워크", "무슨망", "뭐사용", "뭘사용", "사용중", "lan", "lte",
            "상행", "하행", "통행", "통행량", "통행료", "gps정상", "정상률", "검수대기", "검수권장",
            "대시보드", "메인", "전체현황", "전체요약", "요약", "현재상태", "cctv", "카메라", "영상", "gps수신",
            "이벤트수신", "데이터반영", "회원", "운영자", "테스트회원", "사용자", "계정", "장비",
        ):
            return None

        if self._is_non_main_dashboard_question(q):
            return None

        if date_scope.explicit and not self._contains_any(q, "상행", "하행", "선택방향", "대시보드", "메인"):
            return None

        snapshot = self._dashboard_snapshot()
        if not snapshot:
            return None

        policy = self._answer_policy("live_data_lookup")
        plan_map = self._row(
            "domain", "member_dashboard",
            "metric", "dashboard_screen",
            "view_type", "screen_snapshot",
            "period_type", "realtime",
            "answer_format", "summary",
        )

        selected_lane = int(snapshot.get("selected_lane") or 2)
        target_lanes = lanes or [selected_lane]

        if self._is_dashboard_overview_question(q):
            return self._dashboard_overview_answer(snapshot, date_scope, target_lanes, policy, plan_map)

        if self._is_dashboard_identity_question(q):
            answer = "현재 회원 대시보드 상단 로그인 정보는 테스트 회원, 역할은 운영자입니다."
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        if self._is_dashboard_status_card_question(q):
            return self._dashboard_status_card_answer(q, snapshot, policy, plan_map)

        if self._is_dashboard_kpi_question(q):
            return self._dashboard_kpi_answer(q, snapshot, date_scope, target_lanes, policy, plan_map)

        if self._is_network_dashboard_question(q):
            answer = f"현재 통신망은 {self._snapshot_text(snapshot, 'network_status', 'LAN 사용')}입니다."
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        if self._contains_any(q, "현장알림", "알림"):
            alerts = self._dashboard_alerts(target_lanes)
            if not alerts:
                answer = f"{snapshot['center_name']} 회원 대시보드 기준 현재 현장 알림은 없습니다."
            else:
                parts = [
                    f"{self._format_datetime(self._as_datetime(row.get('occurred_at'))).split(' ')[-1]} {row.get('title')}({row.get('target')}, {row.get('badge')})"
                    for row in alerts[:3]
                ]
                answer = f"{snapshot['center_name']} 회원 대시보드 현장 알림 최근 {len(alerts[:3])}건은 " + "; ".join(parts) + "입니다."
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        if self._contains_any(q, "인식방향", "운행방향", "최근gps", "최근판정", "gps판정", "차량번호", "통과시각", "결제판정"):
            rows = self._recent_dashboard_passages(target_lanes)
            if not rows:
                answer = f"{snapshot['center_name']} 회원 대시보드 기준 최근 GPS 판정 데이터가 없습니다."
            else:
                row = rows[0]
                plate = self._plate_label(row.get("plate_text"))
                recognition = self._recognition_direction(row.get("direction"))
                driving = f"L{int(row.get('lane_no') or selected_lane)}"
                gps = self._text(row.get("gps_judgement_status"), "없음")
                payment = self._text(row.get("payment_decision"), self._text(row.get("inspection_status"), "없음"))
                passed_at = self._format_datetime(self._as_datetime(row.get("event_time"))).split(" ")[-1]
                if self._contains_any(q, "인식방향"):
                    answer = f"{snapshot['center_name']} 회원 대시보드의 최근 GPS 판정 기준 차량 {plate}의 인식 방향은 {recognition}입니다. 운행 방향은 {driving}, 통과 시각은 {passed_at}, GPS 판정은 {gps}, 결제 판정은 {payment}입니다."
                elif self._contains_any(q, "운행방향"):
                    answer = f"{snapshot['center_name']} 회원 대시보드의 최근 GPS 판정 기준 차량 {plate}의 운행 방향은 {driving}입니다. 인식 방향은 {recognition}입니다."
                elif self._contains_any(q, "차량번호"):
                    plates = ", ".join(self._plate_label(item.get("plate_text")) for item in rows[:2])
                    answer = f"{snapshot['center_name']} 회원 대시보드 최근 GPS 판정 차량번호는 {plates}입니다."
                elif self._contains_any(q, "통과시각"):
                    answer = f"{snapshot['center_name']} 회원 대시보드 최근 차량 {plate}의 통과 시각은 {passed_at}입니다."
                elif self._contains_any(q, "결제판정"):
                    answer = f"{snapshot['center_name']} 회원 대시보드 최근 차량 {plate}의 결제 판정은 {payment}입니다. GPS 판정은 {gps}, 통과 시각은 {passed_at}입니다."
                else:
                    summary = "; ".join(
                        f"{self._plate_label(item.get('plate_text'))} {self._recognition_direction(item.get('direction'))} L{int(item.get('lane_no') or 0)} {self._text(item.get('gps_judgement_status'), '없음')}"
                        for item in rows[:2]
                    )
                    answer = f"{snapshot['center_name']} 회원 대시보드 최근 GPS 판정은 {summary}입니다."
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        if self._contains_any(q, "yolo", "fps", "해상도", "모델", "레일", "구역상태", "운영상태"):
            answer = (
                f"{snapshot['center_name']} 회원 대시보드 기준 YOLO 상태는 {snapshot['yolo_status']}입니다. "
                f"원본 해상도는 {snapshot['original_resolution']}, 합성 해상도는 {snapshot['composite_resolution']}, "
                f"YOLO 모델은 {snapshot['yolo_model']}, FPS는 {self._text(snapshot.get('fps'), '--')}, "
                f"구역은 {snapshot['zone_name']}, 운영 상태는 {snapshot['operation_status']}입니다."
            )
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        if self._contains_any(q, "센터", "서울톨링", "선택방향", "현재화면"):
            answer = (
                f"현재 회원 대시보드는 {snapshot['center_name']} 기준이며 선택 방향은 {self._snapshot_text(snapshot, 'active_direction', '하행')}, "
                f"선택 레일은 {snapshot['selected_lane_text']}입니다. 상단 상태는 CCTV {self._snapshot_text(snapshot, 'cctv_status', '정상')}, "
                f"GPS {self._snapshot_text(snapshot, 'gps_status', '정상')}, 이벤트 수신 {self._snapshot_text(snapshot, 'event_status', '정상')}, "
                f"통신망 {self._snapshot_text(snapshot, 'network_status', 'LAN 사용')}, 데이터 반영 {self._snapshot_text(snapshot, 'data_status', '정상')}입니다."
            )
            return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

        return None

    def _is_non_main_dashboard_question(self, q: str) -> bool:
        if "결제판정" in q:
            return False
        if "검수" in q and self._contains_any(q, "카메라", "cctv", "통신", "지연"):
            return True
        return self._contains_any(
            q,
            "정산", "보류", "날짜별", "일자별", "월별", "연도별", "지난달", "작년", "통신지연",
        )

    def _is_dashboard_overview_question(self, q: str) -> bool:
        return (
            self._contains_any(q, "대시보드현황", "메인현황", "전체현황", "전체요약", "상태요약")
            or (self._contains_any(q, "대시보드", "메인", "현재화면") and self._contains_any(q, "현황", "상태", "요약", "알려"))
            or (self._contains_any(q, "상행", "하행", "선택방향") and self._contains_any(q, "현황", "요약", "전체"))
        )

    def _dashboard_overview_answer(
        self,
        snapshot: dict[str, Any],
        date_scope: DateScope,
        lanes: list[int],
        policy: dict[str, Any],
        plan_map: dict[str, Any],
    ) -> dict[str, Any]:
        lane = self._dashboard_lane("", snapshot, lanes)
        direction = "하행" if lane == 2 else "상행"
        scope = date_scope if date_scope.explicit else self._today_scope(False)
        passage = self._dashboard_passage_count(scope, lane)
        gps_normal = self._dashboard_gps_normal_count(scope, lane)
        gps_rate = (gps_normal / passage * 100) if passage else 0
        review = self._dashboard_review_count(scope, lane)
        toll = self._dashboard_toll_amount(scope, lane)
        statuses = self._dashboard_status_labels(snapshot)
        answer = (
            f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 선택 방향은 {direction}입니다. "
            f"{direction} 통행 {self._format_number(passage)}대, {direction} GPS 정상 {self._format_number(gps_normal)}건"
            f"(정상률 {gps_rate:.1f}%), {direction} 검수 대기 {self._format_number(review)}건, "
            f"{direction} 통행료 {self._format_number(toll)}원입니다. "
            f"현재 상태는 CCTV {statuses['cctv']}, GPS {statuses['gps']}, 이벤트 수신 {statuses['event']}, "
            f"통신망 {statuses['network']}, 데이터 반영 {statuses['data']}입니다."
        )
        metadata = self._metadata(plan_map, policy, self._latest_passage_event([lane]))
        metadata["start_at"] = self._iso_kst(scope.start)
        metadata["end_at"] = self._iso_kst(scope.end)
        metadata["dashboard_lane"] = lane
        return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, metadata)

    def _is_dashboard_identity_question(self, q: str) -> bool:
        return self._contains_any(q, "테스트회원", "운영자", "로그인", "사용자", "계정") or (
            "회원" in q and not self._contains_any(q, "대시보드", "메인")
        )

    def _is_dashboard_status_card_question(self, q: str) -> bool:
        if self._contains_any(q, "정산", "결제", "요금", "금액", "보류", "날짜별", "일자별", "지난달", "작년"):
            return False
        return self._contains_any(
            q,
            "cctv", "카메라", "영상", "gps수신", "이벤트수신", "통신망", "통신", "네트워크", "데이터반영",
            "현재상태", "장비상태", "장비",
        )

    def _dashboard_status_card_answer(
        self,
        q: str,
        snapshot: dict[str, Any],
        policy: dict[str, Any],
        plan_map: dict[str, Any],
    ) -> dict[str, Any]:
        statuses = self._dashboard_status_labels(snapshot)
        if "데이터" in q:
            answer = f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 데이터 반영은 {statuses['data']}입니다."
        elif "이벤트" in q:
            answer = f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 이벤트 수신은 {statuses['event']}입니다."
        elif "gps" in q:
            answer = f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 GPS 수신은 {statuses['gps']}입니다."
        elif self._contains_any(q, "통신망", "통신", "네트워크", "lan", "lte"):
            answer = f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 통신망은 {statuses['network']}입니다."
        elif self._contains_any(q, "cctv", "카메라", "영상"):
            answer = f"{snapshot['center_name']} 회원 대시보드 메인 화면 기준 CCTV 영상은 {statuses['cctv']}입니다."
        else:
            answer = (
                f"{snapshot['center_name']} 회원 대시보드 메인 화면의 현재 상태는 CCTV {statuses['cctv']}, "
                f"GPS {statuses['gps']}, 이벤트 수신 {statuses['event']}, 통신망 {statuses['network']}, "
                f"데이터 반영 {statuses['data']}입니다."
            )
        return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, self._metadata(plan_map, policy, {}))

    def _dashboard_status_labels(self, snapshot: dict[str, Any]) -> dict[str, str]:
        return {
            "cctv": self._snapshot_text(snapshot, "cctv_status", "정상"),
            "gps": self._snapshot_text(snapshot, "gps_status", "정상"),
            "event": self._snapshot_text(snapshot, "event_status", "정상"),
            "network": self._snapshot_text(snapshot, "network_status", "LAN 사용"),
            "data": self._snapshot_text(snapshot, "data_status", "정상"),
        }

    def _snapshot_text(self, snapshot: dict[str, Any], key: str, fallback: str) -> str:
        text = self._text(snapshot.get(key), "")
        return fallback if not text or "?" in text else text

    def _is_network_usage_question(self, q: str) -> bool:
        return self._contains_any(q, "통신망", "통신", "네트워크", "무슨망", "뭐사용", "뭘사용", "사용중", "lan", "lte") and self._contains_any(q, "뭐", "뭘", "무슨", "사용", "쓰", "연결")

    def _is_network_dashboard_question(self, q: str) -> bool:
        if not self._contains_any(q, "통신망", "통신", "네트워크", "lan", "lte"):
            return False
        if self._contains_any(q, "정산", "결제", "요금", "금액", "통행료", "보류", "검수", "통행", "차량", "몇건", "몇대"):
            return False
        return self._contains_any(q, "뭐", "뭘", "무슨", "사용", "쓰", "연결", "상태", "정상", "괜찮")

    def _is_dashboard_kpi_question(self, q: str) -> bool:
        return (
            self._contains_any(q, "통행료", "요금", "금액")
            or self._contains_any(q, "통행량", "통행", "차량", "몇대", "몇건")
            or ("gps" in q and self._contains_any(q, "정상", "정상률"))
            or ("검수" in q and self._contains_any(q, "대기", "권장", "필요", "건"))
        )

    def _dashboard_kpi_answer(
        self,
        q: str,
        snapshot: dict[str, Any],
        date_scope: DateScope,
        lanes: list[int],
        policy: dict[str, Any],
        plan_map: dict[str, Any],
    ) -> dict[str, Any]:
        lane = self._dashboard_lane(q, snapshot, lanes)
        direction = "하행" if lane == 2 else "상행"
        scope = date_scope if date_scope.explicit else self._today_scope(False)
        if self._contains_any(q, "통행료", "요금", "금액"):
            amount = self._dashboard_toll_amount(scope, lane)
            answer = f"{snapshot['center_name']} 회원 대시보드 기준 {direction} 통행료는 {self._format_number(amount)}원입니다."
        elif "gps" in q and self._contains_any(q, "정상", "정상률"):
            total = self._dashboard_passage_count(scope, lane)
            normal = self._dashboard_gps_normal_count(scope, lane)
            rate = (normal / total * 100) if total else 0
            answer = f"{snapshot['center_name']} 회원 대시보드 기준 {direction} GPS 정상은 {self._format_number(normal)}건입니다. 정상률은 {rate:.1f}%입니다."
        elif "검수" in q and self._contains_any(q, "대기", "권장", "필요", "건"):
            review = self._dashboard_review_count(scope, lane)
            answer = f"{snapshot['center_name']} 회원 대시보드 기준 {direction} 검수 대기는 {self._format_number(review)}건입니다."
        else:
            total = self._dashboard_passage_count(scope, lane)
            answer = f"{snapshot['center_name']} 회원 대시보드 기준 {direction} 통행은 {self._format_number(total)}대입니다."
        metadata = self._metadata(plan_map, policy, self._latest_passage_event([lane]))
        metadata["start_at"] = self._iso_kst(scope.start)
        metadata["end_at"] = self._iso_kst(scope.end)
        metadata["dashboard_lane"] = lane
        return self._response(answer, "fastapi_postgres_member_dashboard", "ok", "member_dashboard", "data_lookup", plan_map, [], [], policy, metadata)

    def _dashboard_lane(self, q: str, snapshot: dict[str, Any], lanes: list[int]) -> int:
        if "상행" in q:
            return 1
        if "하행" in q:
            return 2
        return lanes[0] if lanes else int(snapshot.get("selected_lane") or 2)

    def _dashboard_passage_count(self, scope: DateScope, lane: int) -> int:
        where, params = self._dashboard_passage_where(scope, lane)
        return self._count(f"SELECT COUNT(*) FROM passage_event {where}", params)

    def _dashboard_gps_normal_count(self, scope: DateScope, lane: int) -> int:
        where, params = self._dashboard_passage_where(scope, lane)
        normal_where = self._append_condition(where, "gps_judgement_status = '정상'")
        return self._count(f"SELECT COUNT(*) FROM passage_event {normal_where}", params)

    def _dashboard_review_count(self, scope: DateScope, lane: int) -> int:
        where, params = self._dashboard_passage_where(scope, lane)
        condition = "(needs_review = true OR inspection_status ILIKE %s OR inspection_status ILIKE %s OR payment_decision ILIKE %s)"
        return self._count(f"SELECT COUNT(*) FROM passage_event {self._append_condition(where, condition)}", [*params, "%대기%", "%필요%", "%검수%"])

    def _dashboard_toll_amount(self, scope: DateScope, lane: int) -> int:
        conditions: list[str] = ["LOWER(lane_id) = LOWER(%s)"]
        params: list[Any] = [f"lane-{lane}"]
        if scope.start:
            conditions.append("charged_at >= %s")
            params.append(scope.start)
        if scope.end:
            conditions.append("charged_at < %s")
            params.append(scope.end)
        where = "WHERE " + " AND ".join(conditions)
        return self._count(f"SELECT COALESCE(SUM(amount), 0) FROM toll_history {where}", params)

    def _dashboard_passage_where(self, scope: DateScope, lane: int) -> tuple[str, list[Any]]:
        conditions: list[str] = ["lane_no = %s"]
        params: list[Any] = [lane]
        if scope.start:
            conditions.append("COALESCE(event_time, received_at) >= %s")
            params.append(scope.start)
        if scope.end:
            conditions.append("COALESCE(event_time, received_at) < %s")
            params.append(scope.end)
        return "WHERE " + " AND ".join(conditions), params

    def _dashboard_snapshot(self) -> dict[str, Any]:
        rows = self._query_all(
            "SELECT * FROM member_dashboard_snapshot WHERE dashboard_id = %s",
            ["SEOUL-TOLL"],
            ignore_errors=True,
        )
        return rows[0] if rows else {}

    def _dashboard_alerts(self, lanes: list[int]) -> list[dict[str, Any]]:
        params: list[Any] = ["SEOUL-TOLL"]
        where = "WHERE dashboard_id = %s"
        if lanes:
            where += f" AND lane_no IN ({', '.join(['%s'] * len(lanes))})"
            params.extend(lanes)
        return self._query_all(
            f"SELECT * FROM member_dashboard_alert {where} ORDER BY occurred_at DESC LIMIT 3",
            params,
            ignore_errors=True,
        )

    def _recent_dashboard_passages(self, lanes: list[int]) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if lanes:
            where = f"WHERE lane_no IN ({', '.join(['%s'] * len(lanes))})"
            params.extend(lanes)
        return self._query_all(
            "SELECT COALESCE(plate_number, plate_text) AS plate_text, direction, lane_no, event_time, gps_judgement_status, payment_decision, inspection_status "
            f"FROM passage_event {where} ORDER BY COALESCE(event_time, received_at) DESC LIMIT 5",
            params,
            ignore_errors=True,
        )

    def _navigation_guide(self, question: str, date_scope: DateScope, lanes: list[int], vague: bool) -> dict[str, Any]:
        policy = self._answer_policy("navigation_guide")
        answer = (
            "저는 회원 대시보드 기준으로 답변합니다. "
            "질문 의도를 특정하기 어려워 아래 서브 카테고리 카드에서 이동할 화면을 선택해 주세요."
        )
        return self._response(answer, "fastapi_postgres_member_dashboard", "needs_clarification", "main_dashboard_only", "clarification", {}, [], self._guide_cards(question, date_scope, lanes), policy, self._metadata({}, policy, {}))

    def _guide_cards(self, question: str, date_scope: DateScope, lanes: list[int]) -> list[dict[str, Any]]:
        prefix = "" if date_scope.label == "전체 기간" else f"{date_scope.label} "
        normalized = self._normalize(question)
        cards = [
            self._guide("대시보드", "전체 요약 보기", "핵심 운영 지표와 최근 상태를 한 번에 확인합니다.", f"{prefix}대시보드 현황 알려줘"),
            self._guide("실시간 관제", "실시간 관제 현황", "현재 통행, 이상 통행, 검수 대기를 확인합니다.", f"{prefix}실시간 관제 현황 알려줘"),
            self._guide("통행 이벤트", "통행 이벤트 조회", "차량 통행 이벤트와 차선별 건수를 확인합니다.", f"{prefix}통행 이벤트 현황 알려줘"),
            self._guide("GPS 판정", "GPS 판정 조회", "GPS 판정 상태를 확인합니다.", f"{prefix}GPS 판정 현황 알려줘"),
            self._guide("정산", "정산 현황 조회", "정산 상태와 금액을 확인합니다.", f"{prefix}정산 현황 알려줘"),
            self._guide("장비 상태", "장비 상태 조회", "CCTV, 통신, 데이터 반영 상태를 확인합니다.", f"{prefix}장비 상태 현황 알려줘"),
            self._guide("설정", "설정 메뉴 안내", "알림, 표시, 운영 옵션을 확인합니다.", "설정 메뉴 안내해줘"),
        ]
        priority = {
            "통행 이벤트": self._contains_any(normalized, "통행", "차량", "이벤트", "진입", "통과"),
            "GPS 판정": "gps" in normalized or self._contains_any(normalized, "위치", "이탈", "구역"),
            "정산": self._contains_any(normalized, "정산", "결제", "요금", "금액", "통행료", "보류"),
            "장비 상태": self._contains_any(normalized, "장비", "cctv", "카메라", "영상", "통신", "네트워크", "데이터", "반영"),
            "실시간 관제": self._contains_any(normalized, "실시간", "관제", "검수", "이상", "현황"),
            "설정": self._contains_any(normalized, "설정", "옵션", "알림"),
            "대시보드": self._contains_any(normalized, "대시보드", "메인", "전체", "요약"),
        }
        cards.sort(key=lambda card: 0 if priority.get(card["target"], False) else 1)
        return cards

    def _guide(self, category: str, title: str, desc: str, question: str) -> dict[str, Any]:
        return self._row("category", category, "title", title, "desc", desc, "question", question, "action", "navigate", "target", category)

    def _detect_current_status_kind(self, q: str) -> str | None:
        if self._contains_any(q, "정산", "결제", "요금", "금액", "보류", "날짜별", "일자별", "지난달", "작년"):
            return None
        if not self._contains_any(q, "상태", "수신", "반영", "영상", "망", "이상", "고장", "장애"):
            return None
        if "데이터" in q and "반영" in q:
            return "data_sync"
        if "이벤트" in q and self._contains_any(q, "수신", "들어", "입력"):
            return "event_receive"
        if self._contains_any(q, "cctv", "카메라", "영상"):
            return "camera"
        if "gps" in q:
            return "gps"
        if self._contains_any(q, "통신망", "통신", "네트워크", "lte", "lan"):
            return "network"
        if self._contains_any(q, "장비", "엣지", "edge", "jetson", "젯슨", "alive", "fps"):
            return "device"
        return None

    def _detect_domain(self, q: str) -> str:
        if self._contains_any(q, "설정", "환경설정", "옵션"):
            return "settings"
        if self._contains_any(q, "정산", "결제", "요금", "금액", "통행료"):
            return "settlement"
        if self._contains_any(q, "gps", "이탈", "구역"):
            return "gps"
        if self._contains_any(q, "검수", "판독", "확인대상"):
            return "review"
        if self._contains_any(q, "cctv", "카메라", "통신", "통신망", "장비", "엣지", "edge"):
            return "equipment"
        if self._contains_any(q, "통행", "통행량", "이벤트", "차량", "진입", "통과"):
            return "passage"
        if self._contains_any(q, "실시간", "관제", "대시보드", "현황"):
            return "control"
        return "control"

    def _execution_category(self, domain: str, q: str) -> str:
        if domain != "equipment":
            return domain
        if self._contains_any(q, "cctv", "카메라", "영상"):
            return "camera"
        if self._contains_any(q, "통신", "통신망", "네트워크", "lte", "lan"):
            return "communication"
        return "device"

    def _metric_for(self, domain: str, category: str, q: str, current_status_kind: str | None) -> str:
        if current_status_kind:
            return {
                "camera": "camera_status",
                "gps": "gps_receive_status",
                "event_receive": "event_receive_status",
                "network": "communication_status",
                "data_sync": "data_reflect_status",
            }.get(current_status_kind, "device_status")
        if category == "settlement":
            if self._wants_date_breakdown(q):
                return "settlement_daily_status"
            if "보류" in q:
                return "settlement_hold"
            if "대기" in q:
                return "settlement_waiting"
            if "실패" in q:
                return "settlement_failed"
            if self._contains_any(q, "완료", "성공"):
                return "settlement_paid"
            return "settlement_amount" if self._contains_any(q, "금액", "요금", "통행료", "얼마") else "settlement_status"
        if category == "passage":
            return "passage_volume" if "통행량" in q else "passage_count"
        return {
            "gps": "gps_status",
            "review": "review_status",
            "camera": "camera_status",
            "communication": "communication_status",
            "device": "device_status",
            "settings": "settings",
        }.get(category, "traffic_status")

    def _default_group_by(self, category: str, metric: str, current_status_kind: str | None) -> list[str]:
        if current_status_kind:
            return []
        if category == "settlement":
            return ["charged_date", "payment_status"] if metric == "settlement_daily_status" else ["payment_status"]
        if category == "passage":
            return ["lane_no"]
        if category == "gps":
            return ["gps_judgement_status"]
        if category == "review":
            return ["inspection_status"]
        return []

    def _parse_date_scope(self, question: str) -> DateScope:
        q = self._normalize(question)
        today = self._now_naive().date()
        if self._contains_any(q, "전체기간", "전기간", "누적", "모든기간"):
            return DateScope(None, None, "전체 기간", "all", True)
        for pattern in (r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"):
            match = re.search(pattern, question)
            if match:
                year, month, day = map(int, match.groups())
                return self._with_time_scope(question, self._safe_day_scope(year, month, day, f"{year}년 {month}월 {day}일"))
        for pattern in (r"(\d{2})[-./](\d{1,2})[-./](\d{1,2})", r"(\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"):
            match = re.search(pattern, question)
            if match:
                year2, month, day = map(int, match.groups())
                year = self._expand_short_year(year2)
                return self._with_time_scope(question, self._safe_day_scope(year, month, day, f"{year}년 {month}월 {day}일"))
        match = re.search(r"작년\s*(\d{1,2})월\s*(\d{1,2})일", question)
        if match:
            year = today.year - 1
            month, day = map(int, match.groups())
            return self._with_time_scope(question, self._safe_day_scope(year, month, day, f"{year}년 {month}월 {day}일"))
        match = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", question)
        if match:
            month, day = map(int, match.groups())
            return self._with_time_scope(question, self._safe_day_scope(today.year, month, day, f"{today.year}년 {month}월 {day}일"))
        match = re.search(r"작년\s*(\d{1,2})월", question)
        if match:
            year = today.year - 1
            month = int(match.group(1))
            return self._safe_month_scope(year, month, f"{year}년 {month}월")
        match = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", question)
        if match:
            year, month = map(int, match.groups())
            return self._safe_month_scope(year, month, f"{year}년 {month}월")
        match = re.search(r"(\d{2})\s*년\s*(\d{1,2})\s*월", question)
        if match:
            year2, month = map(int, match.groups())
            year = self._expand_short_year(year2)
            return self._safe_month_scope(year, month, f"{year}년 {month}월")
        if "오늘" in q:
            return self._with_time_scope(question, self._day_scope(datetime.combine(today, datetime.min.time()), "오늘", True))
        if "어제" in q:
            return self._with_time_scope(question, self._day_scope(datetime.combine(today - timedelta(days=1), datetime.min.time()), "어제", True))
        if "그제" in q:
            return self._with_time_scope(question, self._day_scope(datetime.combine(today - timedelta(days=2), datetime.min.time()), "그제", True))
        if "이번달" in q or "이번월" in q:
            return self._month_scope(datetime(today.year, today.month, 1), "이번 달", True)
        if "지난달" in q or "전월" in q:
            month_start = datetime(today.year, today.month, 1)
            last_month = month_start - timedelta(days=1)
            return self._month_scope(datetime(last_month.year, last_month.month, 1), "지난달", True)
        if self._contains_any(q, "올해", "이번년도", "이번연도"):
            start = datetime(today.year, 1, 1)
            return DateScope(start, datetime(today.year + 1, 1, 1), f"{today.year}년", "year", True)
        if "작년" in q or "지난해" in q:
            start = datetime(today.year - 1, 1, 1)
            return DateScope(start, datetime(today.year, 1, 1), f"{today.year - 1}년", "year", True)
        match = re.search(r"(\d{4})\s*년", question)
        if match:
            year = int(match.group(1))
            return DateScope(datetime(year, 1, 1), datetime(year + 1, 1, 1), f"{year}년", "year", True)
        match = re.search(r"(\d{2})\s*년(?:도)?", question)
        if match:
            year = self._expand_short_year(int(match.group(1)))
            return DateScope(datetime(year, 1, 1), datetime(year + 1, 1, 1), f"{year}년", "year", True)
        match = re.search(r"(\d{1,2})\s*월", question)
        if match:
            month = int(match.group(1))
            return self._safe_month_scope(today.year, month, f"{today.year}년 {month}월")
        return DateScope(None, None, "전체 기간", "all", False)

    def _safe_day_scope(self, year: int, month: int, day: int, label: str) -> DateScope:
        try:
            return self._day_scope(datetime(year, month, day), label, True)
        except ValueError:
            return DateScope(None, None, "전체 기간", "all", False)

    def _expand_short_year(self, year: int) -> int:
        if year >= 100:
            return year
        return 2000 + year

    def _with_time_scope(self, question: str, scope: DateScope) -> DateScope:
        if scope.start is None or scope.period_type != "day":
            return scope
        match = re.search(r"(오전|오후)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?", question)
        if not match:
            match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", question)
            if not match:
                return scope
            hour = int(match.group(1))
            minute = int(match.group(2))
        else:
            ampm = match.group(1)
            hour = int(match.group(2))
            minute = int(match.group(3) or 0)
            if ampm == "오후" and hour < 12:
                hour += 12
            if ampm == "오전" and hour == 12:
                hour = 0
        if hour > 23 or minute > 59:
            return scope
        start = scope.start.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return DateScope(start, start + timedelta(hours=1), f"{scope.label} {hour:02d}시", "hour", True)

    def _safe_month_scope(self, year: int, month: int, label: str) -> DateScope:
        try:
            return self._month_scope(datetime(year, month, 1), label, True)
        except ValueError:
            return DateScope(None, None, "전체 기간", "all", False)

    def _today_scope(self, explicit: bool) -> DateScope:
        return self._day_scope(datetime.combine(self._now_naive().date(), datetime.min.time()), "오늘", explicit)

    def _day_scope(self, day: datetime, label: str, explicit: bool) -> DateScope:
        return DateScope(day, day + timedelta(days=1), label, "day", explicit)

    def _month_scope(self, first_day: datetime, label: str, explicit: bool) -> DateScope:
        year = first_day.year + (1 if first_day.month == 12 else 0)
        month = 1 if first_day.month == 12 else first_day.month + 1
        return DateScope(first_day, datetime(year, month, 1), label, "month", explicit)

    def _passage_where_params(self, plan: QueryPlan) -> tuple[str, list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if plan.start:
            conditions.append("COALESCE(event_time, received_at) >= %s")
            params.append(plan.start)
        if plan.end:
            conditions.append("COALESCE(event_time, received_at) < %s")
            params.append(plan.end)
        if plan.lanes:
            conditions.append(f"lane_no IN ({', '.join(['%s'] * len(plan.lanes))})")
            params.extend(plan.lanes)
        return ("WHERE " + " AND ".join(conditions) if conditions else ""), params

    def _toll_where_params(self, plan: QueryPlan) -> tuple[str, list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if plan.start:
            conditions.append("charged_at >= %s")
            params.append(plan.start)
        if plan.end:
            conditions.append("charged_at < %s")
            params.append(plan.end)
        if plan.lanes:
            conditions.append(f"lane_id IN ({', '.join(['%s'] * len(plan.lanes))})")
            params.extend([f"lane-{lane}" for lane in plan.lanes])
        return ("WHERE " + " AND ".join(conditions) if conditions else ""), params

    def _settlement_status_filter(self, where: str, params: list[Any], metric: str) -> tuple[str, list[Any], str]:
        patterns = {
            "settlement_hold": ("정산 보류/대기", ["%보류%", "%대기%", "%hold%", "%pending%"]),
            "settlement_waiting": ("정산 대기", ["%대기%", "%pending%"]),
            "settlement_failed": ("정산 실패", ["%실패%", "%failed%", "%fail%"]),
            "settlement_paid": ("정산 완료", ["%완료%", "%성공%", "%paid%", "%success%"]),
        }
        label, likes = patterns.get(metric, ("정산", []))
        condition = "(" + " OR ".join(["payment_status ILIKE %s"] * len(likes)) + ")"
        return self._append_condition(where, condition), [*params, *likes], label

    def _append_condition(self, where: str, condition: str) -> str:
        return f"{where} AND {condition}" if where else f"WHERE {condition}"

    def _latest_passage_event(self, lanes: list[int]) -> dict[str, Any]:
        where = f"WHERE lane_no IN ({', '.join(['%s'] * len(lanes))})" if lanes else ""
        rows = self._query_all(
            "SELECT passage_event_id, event_id, event_time, received_at, lane_no, camera_id, camera_role, gps_judgement_status, payment_decision, inspection_status, needs_review "
            f"FROM passage_event {where} ORDER BY passage_event_id DESC LIMIT 1",
            lanes,
        )
        return rows[0] if rows else {}

    def _latest_gps_telemetry(self) -> dict[str, Any]:
        rows = self._query_all(
            "SELECT gps_telemetry_id, gps_device_id, fix_status, status_message, accuracy_m, latitude, longitude, captured_at, received_at FROM gps_telemetry ORDER BY received_at DESC LIMIT 1",
            [],
            ignore_errors=True,
        )
        return rows[0] if rows else {}

    def _latest_toll_history(self) -> dict[str, Any]:
        rows = self._query_all(
            "SELECT toll_history_id, charged_at, payment_status, amount FROM toll_history ORDER BY charged_at DESC LIMIT 1",
            [],
            ignore_errors=True,
        )
        return rows[0] if rows else {}

    def _query_all(self, sql: str, params: list[Any], ignore_errors: bool = False) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return list(cur.fetchall())
        except psycopg.Error:
            if ignore_errors:
                return []
            raise

    def _count(self, sql: str, params: list[Any]) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return int(next(iter(row.values())) or 0) if row else 0

    def _status_rows(self, sql: str, params: list[Any], label_name: str) -> list[dict[str, Any]]:
        return [
            self._row(label_name, self._text(row.get("name"), "없음"), "건수", int(row.get("count") or 0))
            for row in self._query_all(sql, params)
        ]

    def _check_video_status(self) -> LiveApiStatus:
        return self._check_http_status(self.video_status_url, "영상 상태 API")

    def _check_ingress_status(self) -> LiveApiStatus:
        return self._check_http_status(self.ingress_status_url, "FastAPI")

    def _check_http_status(self, url: str, label: str) -> LiveApiStatus:
        try:
            with urllib.request.urlopen(url, timeout=self.settings.ingress_video_timeout_sec) as response:
                body = response.read(4096).decode("utf-8", errors="ignore")
                available = 200 <= response.status < 300
                healthy = available and self._video_body_looks_healthy(body)
                summary = f"{label} {'정상' if healthy else '비정상'}({response.status})"
                return LiveApiStatus(True, available, healthy, response.status, summary, url)
        except urllib.error.HTTPError as exc:
            summary = f"{label} 없음({exc.code})" if exc.code == 404 else f"{label} 오류({exc.code})"
            return LiveApiStatus(True, False, False, exc.code, summary, url)
        except (urllib.error.URLError, TimeoutError, ValueError):
            return LiveApiStatus(True, False, False, 0, f"{label} 연결 실패", url)

    def _video_body_looks_healthy(self, body: str) -> bool:
        value = self._normalize(body)
        if not value:
            return True
        return not self._contains_any(value, "error", "fail", "failed", "false", "offline", "stopped", "down", "nosignal", "no_signal", "disconnected")

    def _decide_camera_status(self, video_status: LiveApiStatus, latest: dict[str, Any], passage_time: datetime | None) -> StatusDecision:
        camera_missing = not self._text(latest.get("camera_id"), "")
        review_required = self._bool(latest.get("needs_review"))
        if video_status.checked and video_status.status_code == 404:
            return StatusDecision("검수 필요", "영상 상태 확인이 아직 연결되지 않아 CCTV 상태를 확정할 수 없습니다.", "영상 연결 상태를 확인하세요.")
        if video_status.checked and not video_status.available:
            if self._is_failure(passage_time):
                return StatusDecision("고장 의심", "영상 확인이 되지 않고 최근 통행 데이터도 오래 멈춰 있습니다.", "영상 장비와 CCTV 전원을 확인하세요.")
            return StatusDecision("검수 필요", "통행 데이터는 들어오지만 영상 확인이 되지 않습니다.", "카메라 영상 연결을 확인하세요.")
        if self._is_failure(passage_time):
            return StatusDecision("고장 의심", "최근 CCTV 수신 시간이 오래됐습니다.", "카메라와 장비 연결을 확인하세요.")
        if video_status.checked and not video_status.healthy:
            return StatusDecision("검수 필요", "영상 연결 상태가 정상으로 보이지 않습니다.", "카메라 영상 상태를 확인하세요.")
        if camera_missing or review_required:
            return StatusDecision("검수 필요", "최근 수신 데이터에 카메라 정보가 없거나 검수가 필요합니다.", "최근 CCTV 수신 내용을 확인하세요.")
        if not self._is_recent(passage_time):
            return StatusDecision("검수 필요", "CCTV 수신이 조금 늦어지고 있습니다.", "수신 지연이 계속되는지 확인하세요.")
        return StatusDecision("정상", "CCTV 영상과 최근 수신이 정상 범위입니다.", "추가 조치가 필요 없습니다.")

    def _decide_gps_status(self, latest_gps: dict[str, Any], latest_passage: dict[str, Any], passage_time: datetime | None) -> StatusDecision:
        if latest_gps:
            gps_time = self._as_datetime(latest_gps.get("received_at"))
            fix_status = self._normalize(self._text(latest_gps.get("fix_status"), ""))
            accuracy = self._as_float(latest_gps.get("accuracy_m"))
            if self._is_failure(gps_time):
                return StatusDecision("수신 지연", "GPS 정보가 기준 시간보다 오래되었습니다.", "GPS 수신 지연이 계속되는지 확인하세요.")
            if self._contains_any(fix_status, "nofix", "no_fix", "lost", "invalid") or (accuracy is not None and accuracy > GPS_ACCURACY_REVIEW_METERS):
                return StatusDecision("검수 필요", "GPS는 들어왔지만 위치가 불안정하거나 정확도가 낮습니다.", "GPS 수신 상태를 확인하세요.")
            if not self._is_recent(gps_time):
                return StatusDecision("검수 필요", "GPS 수신이 조금 늦어지고 있습니다.", "수신 지연이 계속되는지 확인하세요.")
            return StatusDecision("정상", "GPS가 최근에 정상 수신됐습니다.", "추가 조치가 필요 없습니다.")

        judgement = self._normalize(self._text(latest_passage.get("gps_judgement_status"), ""))
        if self._is_failure(passage_time):
            return StatusDecision("고장 의심", "GPS 정보와 통행 데이터가 장시간 갱신되지 않았습니다.", "GPS 수신과 장비 연결을 확인하세요.")
        if not judgement or self._contains_any(judgement, "없음", "no_fix", "out", "low", "fail", "abnormal", "이탈"):
            return StatusDecision("검수 필요", "통행 데이터의 GPS 판정이 없거나 이상 상태입니다.", "GPS 수신 내용을 확인하세요.")
        if not self._is_recent(passage_time):
            return StatusDecision("검수 필요", "GPS 판정 수신이 조금 늦어지고 있습니다.", "GPS 수신 지연이 계속되는지 확인하세요.")
        return StatusDecision("정상", "GPS 판정이 정상 범위입니다.", "추가 조치가 필요 없습니다.")

    def _decide_event_receive_status(self, passage_time: datetime | None) -> StatusDecision:
        if self._is_failure(passage_time):
            return StatusDecision("고장 의심", "통행 데이터 수신이 장시간 멈춰 있습니다.", "장비 연결 상태를 확인하세요.")
        if not self._is_recent(passage_time):
            return StatusDecision("검수 필요", "통행 데이터 수신이 조금 늦어지고 있습니다.", "수신 지연이 계속되는지 확인하세요.")
        return StatusDecision("정상", "통행 데이터가 최근 기준 안에 수신됐습니다.", "추가 조치가 필요 없습니다.")

    def _decide_network_status(self, video_status: LiveApiStatus, passage_time: datetime | None) -> StatusDecision:
        if video_status.checked and video_status.status_code == 404:
            if self._is_failure(passage_time):
                return StatusDecision("고장 의심", "최근 통행 데이터가 오래 갱신되지 않았습니다.", "장비 연결 상태를 확인하세요.")
            return StatusDecision("검수 필요", "영상 상태 확인이 아직 연결되지 않았습니다.", "영상 연결 상태를 확인하세요.")
        if video_status.checked and not video_status.available and self._is_failure(passage_time):
            return StatusDecision("고장 의심", "영상과 통행 데이터가 모두 정상적으로 들어오지 않습니다.", "네트워크와 장비 연결을 우선 확인하세요.")
        if video_status.checked and not video_status.available:
            return StatusDecision("검수 필요", "통행 데이터는 들어오지만 영상 확인이 되지 않습니다.", "영상 연결 상태를 확인하세요.")
        if self._is_failure(passage_time):
            return StatusDecision("고장 의심", "최근 통행 데이터가 오래 갱신되지 않았습니다.", "장비 연결 상태를 확인하세요.")
        if video_status.checked and not video_status.healthy:
            return StatusDecision("검수 필요", "영상 연결 상태가 정상으로 보이지 않습니다.", "영상 연결 상태를 확인하세요.")
        if not self._is_recent(passage_time):
            return StatusDecision("검수 필요", "통행 데이터 수신이 조금 늦어지고 있습니다.", "지연이 계속되는지 확인하세요.")
        return StatusDecision("정상", "영상과 통행 데이터가 정상 범위입니다.", "추가 조치가 필요 없습니다.")

    def _decide_data_sync_status(self, latest_passage: dict[str, Any], latest_data_time: datetime | None) -> StatusDecision:
        if self._is_failure(latest_data_time):
            return StatusDecision("고장 의심", "저장된 최신 데이터가 장시간 갱신되지 않았습니다.", "데이터 저장 상태를 확인하세요.")
        if self._bool(latest_passage.get("needs_review")):
            return StatusDecision("검수 필요", "최신 데이터는 저장됐지만 검수가 필요합니다.", "검수 대상 데이터를 확인하세요.")
        if not self._is_recent(latest_data_time):
            return StatusDecision("검수 필요", "데이터 저장은 됐지만 최근 기준보다 늦습니다.", "저장 지연이 계속되는지 확인하세요.")
        return StatusDecision("정상", "최신 데이터가 최근 기준 안에 저장됐습니다.", "추가 조치가 필요 없습니다.")

    def _decide_device_status(
        self,
        camera: StatusDecision,
        event_receive: StatusDecision,
        gps: StatusDecision,
        data_sync: StatusDecision,
    ) -> StatusDecision:
        components = {
            "CCTV": camera,
            "이벤트 수신": event_receive,
            "GPS": gps,
            "데이터 반영": data_sync,
        }
        failures = [name for name, decision in components.items() if decision.label == "고장 의심"]
        reviews = [name for name, decision in components.items() if decision.label == "검수 필요"]
        if len(failures) >= 2:
            return StatusDecision("고장 의심", f"{', '.join(failures)} 상태가 동시에 고장 의심입니다.", "장비 전원과 네트워크를 우선 확인하세요.")
        if failures:
            return StatusDecision("고장 의심", f"{failures[0]} 상태가 고장 의심입니다.", "해당 장비 연결을 우선 확인하세요.")
        if reviews:
            return StatusDecision("검수 필요", f"{', '.join(reviews)} 상태 확인이 필요합니다.", "검수 대상 이벤트와 장비별 상세 상태를 확인하세요.")
        return StatusDecision("정상", "주요 장비 수신 경로가 정상 범위입니다.", "추가 조치가 필요 없습니다.")

    def _gps_evidence(self, latest_gps: dict[str, Any], latest_passage: dict[str, Any], passage_time: datetime | None) -> str:
        if latest_gps:
            return f"수신 상태={self._gps_fix_label(latest_gps.get('fix_status'))}, 정확도={self._text(latest_gps.get('accuracy_m'), '없음')}m, 최근 GPS 수신={self._format_datetime(self._as_datetime(latest_gps.get('received_at')))}"
        return f"GPS 판정={self._text(latest_passage.get('gps_judgement_status'), '없음')}, 최근 통행 수신={self._format_datetime(passage_time)}"

    def _gps_fix_label(self, value: Any) -> str:
        normalized = self._normalize(self._text(value, ""))
        if not normalized:
            return "없음"
        if self._contains_any(normalized, "fixed", "fix", "normal", "정상"):
            return "위치 잡힘"
        if self._contains_any(normalized, "nofix", "no_fix", "lost", "invalid", "fail"):
            return "위치 못 잡음"
        return self._text(value, "없음")

    def _is_vague_domain_only_question(self, q: str) -> bool:
        value = q
        for term in ("오늘", "어제", "그제", "내일", "이번달", "지난달", "이번년도", "이번연도", "올해", "작년", "지난해", "전체기간"):
            value = value.replace(term, "")
        value = re.sub(r"\d{2,4}년", "", value)
        value = re.sub(r"\d{1,2}월", "", value)
        value = re.sub(r"\d{1,2}일", "", value)
        value = re.sub(r"[12]차[선로]", "", value)
        if self._contains_any(value, "현황", "상태", "건수", "몇건", "몇대", "조회", "확인", "알려", "보여", "이벤트", "수신", "반영"):
            return False
        return value in {"통행", "차량", "정산", "검수", "gps", "cctv", "카메라", "통신", "통신망", "장비", "데이터"}

    def _is_out_of_scope(self, q: str) -> bool:
        return self._contains_any(q, "날씨", "기온", "맛집", "주식", "뉴스", "환율", "코인", "영화", "음악", "게임", "요리", "번역", "python", "코드")

    def _has_no_dashboard_intent(self, q: str) -> bool:
        if self._contains_abusive_or_noise(q):
            return True
        return not self._has_dashboard_domain_term(q) and not self._has_dashboard_action_term(q)

    def _contains_abusive_or_noise(self, q: str) -> bool:
        return self._contains_any(q, "씨발", "시발", "ㅅㅂ", "개새", "개때", "개떼", "개같", "좆", "ㅈ같", "병신", "ㅂㅅ", "그지같", "거지같", "개판", "꺼져", "닥쳐", "멍청", "바보")

    def _has_dashboard_domain_term(self, q: str) -> bool:
        return self._contains_any(q, "대시보드", "실시간", "관제", "통행", "통행량", "차량", "이벤트", "진입", "통과", "gps", "정산", "결제", "요금", "금액", "통행료", "검수", "판독", "확인대상", "cctv", "카메라", "영상", "통신", "통신망", "네트워크", "장비", "엣지", "edge", "데이터", "반영", "설정", "환경설정", "옵션")

    def _has_dashboard_action_term(self, q: str) -> bool:
        return self._contains_any(q, "현황", "상태", "조회", "확인", "건수", "몇건", "몇대", "보류", "대기", "완료", "실패", "수신", "고장", "지연")

    def _should_default_today(self, q: str) -> bool:
        if self._contains_any(q, "전체기간", "전기간", "누적", "모든기간"):
            return False
        if self._wants_date_breakdown(q):
            return False
        return self._contains_any(q, "상태", "현황", "조회", "확인", "몇건", "몇대", "건수", "통행량", "정산", "결제", "요금", "금액", "통행료", "얼마")

    def _wants_date_breakdown(self, q: str) -> bool:
        return self._contains_any(q, "날짜별", "일자별", "일별", "날짜마다", "일자마다", "date별")

    def _wants_table(self, q: str, metric: str) -> bool:
        if metric == "settlement_daily_status":
            return True
        return self._contains_any(q, "표", "테이블", "목록", "리스트", "상세", "자세히", "날짜별", "일자별", "일별", "상태별", "차선별", "분류별")

    def _should_include_table(self, plan: QueryPlan) -> bool:
        return plan.answer_format == "table"

    def _lanes_from_question(self, q: str) -> list[int]:
        lanes: list[int] = []
        if "상행" in q:
            lanes.append(1)
        if "하행" in q:
            lanes.append(2)
        for match in re.finditer(r"([12])차[선로]", q):
            lane = int(match.group(1))
            if lane in ALLOWED_LANES and lane not in lanes:
                lanes.append(lane)
        return lanes

    def _is_recent(self, value: datetime | None) -> bool:
        return value is not None and self._now_naive() - value <= timedelta(minutes=CURRENT_STATUS_RECENT_MINUTES)

    def _is_failure(self, value: datetime | None) -> bool:
        return value is None or self._now_naive() - value > timedelta(minutes=CURRENT_STATUS_FAILURE_MINUTES)

    def _elapsed_label(self, value: datetime | None) -> str:
        if value is None:
            return "계산 불가"
        minutes = int((self._now_naive() - value).total_seconds() // 60)
        if minutes < 1:
            return "1분 미만"
        if minutes < 60:
            return f"{minutes}분 전"
        return f"{minutes / 60:.1f}시간 전"

    def _as_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        return None

    def _latest_data_time(self, latest_passage: dict[str, Any], latest_gps: dict[str, Any], latest_toll: dict[str, Any]) -> datetime | None:
        values = [
            self._as_datetime(latest_passage.get("received_at")) or self._as_datetime(latest_passage.get("event_time")),
            self._as_datetime(latest_gps.get("received_at")),
            self._as_datetime(latest_toll.get("charged_at")),
        ]
        valid = [value for value in values if value is not None]
        return max(valid) if valid else None

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"

    def _now_kst(self) -> datetime:
        return datetime.now(KST)

    def _now_naive(self) -> datetime:
        return self._now_kst().replace(tzinfo=None)

    def _iso_kst(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.replace(tzinfo=KST).isoformat(timespec="seconds")

    def _format_datetime(self, value: datetime | None) -> str:
        return "없음" if value is None else value.isoformat(sep=" ", timespec="seconds")

    def _format_number(self, value: Any) -> str:
        return f"{int(value or 0):,}"

    def _normalize(self, value: str) -> str:
        return (value or "").lower().replace(" ", "")

    def _contains_any(self, value: str, *terms: str) -> bool:
        return any(term in value for term in terms)

    def _text(self, value: Any, fallback: str) -> str:
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    def _join_lanes(self, lanes: list[int]) -> str:
        return ", ".join(f"{lane}차선" for lane in lanes)

    def _recognition_direction(self, direction: Any) -> str:
        value = self._normalize(self._text(direction, ""))
        if value == "in":
            return "Front"
        if value == "out":
            return "Rear"
        return self._text(direction, "-")

    def _plate_label(self, plate: Any) -> str:
        text = self._text(plate, "-")
        if len(text) >= 4 and " " not in text:
            return f"{text[:-4]} {text[-4:]}"
        return text

    def _join_url(self, base_url: str, path: str) -> str:
        base = (base_url or "http://127.0.0.1:8000").strip()
        suffix = (path or "/video/status").strip()
        if base.endswith("/") and suffix.startswith("/"):
            return base[:-1] + suffix
        if not base.endswith("/") and not suffix.startswith("/"):
            return base + "/" + suffix
        return base + suffix

    def _row(self, *values: Any) -> dict[str, Any]:
        return {str(values[i]): values[i + 1] for i in range(0, len(values) - 1, 2)}

    def _query_plan_map(self, plan: QueryPlan) -> dict[str, Any]:
        return self._row(
            "domain", plan.domain,
            "metric", plan.metric,
            "view_type", plan.view_type,
            "measure", plan.measure,
            "period_type", plan.period_type,
            "start_at", self._iso_kst(plan.start),
            "end_at", self._iso_kst(plan.end),
            "group_by", plan.group_by,
            "filters", [] if not plan.lanes else [self._row("field", "lane_no", "operator", "in", "value", plan.lanes)],
            "order_by", None,
            "limit", None,
            "answer_format", plan.answer_format,
        )

    def _answer_policy(self, key: str) -> dict[str, Any]:
        policies = {
            "current_status": self._row("key", key, "request_mode", "data_lookup", "answer_source", "fastapi_postgres_current_status", "query_type", "current_status"),
            "navigation_guide": self._row("key", key, "request_mode", "clarification", "answer_source", "missing_intent_guide", "query_type", "missing_intent"),
            "category_guide": self._row("key", key, "request_mode", "category_guide", "answer_source", "dashboard_category_guide", "query_type", "settings"),
        }
        return policies.get(key, self._row("key", key, "request_mode", "data_lookup", "answer_source", "fastapi_postgres_main_tables", "query_type", "data_lookup"))

    def _metadata(self, plan: dict[str, Any], policy: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
        query_plan = plan or {}
        return self._row(
            "start_at", query_plan.get("start_at"),
            "end_at", query_plan.get("end_at"),
            "queried_at", self._now_kst().isoformat(timespec="seconds"),
            "timezone", "Asia/Seoul",
            "live", True,
            "source_table", "passage_event,toll_history,gps_telemetry",
            "latest_event_id", latest.get("event_id"),
            "latest_received_at", self._format_datetime(self._as_datetime(latest.get("received_at"))),
            "runtime", "fastapi-edge",
            "query_plan", query_plan,
            "answer_policy", policy,
        )

    def _response(
        self,
        answer: str,
        source: str,
        status: str,
        query_type: str,
        request_mode: str,
        query_plan: dict[str, Any],
        table: list[dict[str, Any]],
        guide_cards: list[dict[str, Any]],
        answer_policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._row(
            "answer", answer,
            "source", "postgresql",
            "answer_source", source,
            "request_mode", request_mode,
            "status", status,
            "query_type", query_type,
            "filters", {} if not query_plan else self._row("query_plan", query_plan),
            "confidence", 1.0 if status == "ok" else 0.0,
            "cards", [],
            "table", table,
            "related_actions", [],
            "guide_cards", guide_cards,
            "sources", [],
            "metadata", metadata or {},
            "query_plan", query_plan,
            "answer_policy", answer_policy or {},
        )
