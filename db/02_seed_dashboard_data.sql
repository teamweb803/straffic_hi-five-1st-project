-- HiFive chatbot dashboard seed data.
-- This is intended for a development/test database.
-- Dates are generated relative to CURRENT_DATE so "오늘", "어제", and "지난달" questions work on a teammate's PC.

BEGIN;

DELETE FROM toll_history th
USING passage_event pe
WHERE th.passage_event_id = pe.passage_event_id
  AND pe.event_id LIKE 'CHATBOT-SEED-%';

DELETE FROM passage_event WHERE event_id LIKE 'CHATBOT-SEED-%';
DELETE FROM gps_telemetry WHERE gps_device_id = 'CHATBOT-GPS-SEOUL-TOLL-A';
DELETE FROM member_dashboard_alert WHERE dashboard_id = 'SEOUL-TOLL';

INSERT INTO member_dashboard_snapshot (
    dashboard_id,
    center_name,
    active_direction,
    selected_lane,
    selected_lane_text,
    yolo_status,
    original_resolution,
    composite_resolution,
    yolo_model,
    fps,
    zone_name,
    operation_status,
    cctv_status,
    gps_status,
    event_status,
    network_status,
    network_path,
    data_status,
    updated_at
) VALUES (
    'SEOUL-TOLL',
    '서울 톨링 A',
    '하행',
    2,
    'L2',
    'WAIT',
    '1920 x 1080',
    '960 x 960',
    'v8.1 (tuned)',
    NULL,
    '서울 톨링 A',
    '정상',
    '정상',
    '정상',
    '정상',
    'LAN 사용',
    'LAN',
    '정상',
    CURRENT_TIMESTAMP
)
ON CONFLICT (dashboard_id) DO UPDATE SET
    center_name = EXCLUDED.center_name,
    active_direction = EXCLUDED.active_direction,
    selected_lane = EXCLUDED.selected_lane,
    selected_lane_text = EXCLUDED.selected_lane_text,
    yolo_status = EXCLUDED.yolo_status,
    original_resolution = EXCLUDED.original_resolution,
    composite_resolution = EXCLUDED.composite_resolution,
    yolo_model = EXCLUDED.yolo_model,
    fps = EXCLUDED.fps,
    zone_name = EXCLUDED.zone_name,
    operation_status = EXCLUDED.operation_status,
    cctv_status = EXCLUDED.cctv_status,
    gps_status = EXCLUDED.gps_status,
    event_status = EXCLUDED.event_status,
    network_status = EXCLUDED.network_status,
    network_path = EXCLUDED.network_path,
    data_status = EXCLUDED.data_status,
    updated_at = EXCLUDED.updated_at;

WITH seeded_events AS (
    SELECT
        'TODAY' AS bucket,
        1 AS lane_no,
        n,
        'CHATBOT-SEED-TODAY-L1-' || LPAD(n::TEXT, 4, '0') AS event_id,
        CURRENT_DATE AS base_date
    FROM generate_series(1, 684) AS n

    UNION ALL

    SELECT
        'TODAY',
        2,
        n,
        'CHATBOT-SEED-TODAY-L2-' || LPAD(n::TEXT, 4, '0'),
        CURRENT_DATE
    FROM generate_series(1, 564) AS n

    UNION ALL

    SELECT
        'YDAY',
        1,
        n,
        'CHATBOT-SEED-YDAY-L1-' || LPAD(n::TEXT, 4, '0'),
        CURRENT_DATE - INTERVAL '1 day'
    FROM generate_series(1, 684) AS n

    UNION ALL

    SELECT
        'YDAY',
        2,
        n,
        'CHATBOT-SEED-YDAY-L2-' || LPAD(n::TEXT, 4, '0'),
        CURRENT_DATE - INTERVAL '1 day'
    FROM generate_series(1, 564) AS n

    UNION ALL

    SELECT
        'LAST_MONTH',
        CASE WHEN n % 2 = 0 THEN 1 ELSE 2 END,
        n,
        'CHATBOT-SEED-LASTMONTH-' || LPAD(n::TEXT, 4, '0'),
        (DATE_TRUNC('month', CURRENT_DATE)::DATE - INTERVAL '1 month')
    FROM generate_series(1, 903) AS n
),
mapped AS (
    SELECT
        *,
        CASE
            WHEN bucket = 'LAST_MONTH' THEN base_date + ((n % 25) || ' days')::INTERVAL + TIME '10:00:00' + ((n % 3600) || ' seconds')::INTERVAL
            WHEN lane_no = 1 AND n = 684 THEN base_date + TIME '17:36:47'
            WHEN lane_no = 1 AND n = 683 THEN base_date + TIME '17:35:41'
            WHEN lane_no = 2 AND n = 564 THEN base_date + TIME '17:35:18'
            WHEN lane_no = 2 AND n = 563 THEN base_date + TIME '17:36:12'
            ELSE base_date + TIME '08:00:00' + (n || ' seconds')::INTERVAL
        END AS event_at,
        CASE
            WHEN lane_no = 1 AND n = 684 THEN '31가9829'
            WHEN lane_no = 1 AND n = 683 THEN '12가3456'
            WHEN lane_no = 2 AND n = 564 THEN '85나1212'
            WHEN lane_no = 2 AND n = 563 THEN '46다7720'
            WHEN n % 5 = 0 THEN '98머3344'
            WHEN n % 5 = 1 THEN '12가3456'
            WHEN n % 5 = 2 THEN '45사6789'
            WHEN n % 5 = 3 THEN '90마1234'
            ELSE '56다7890'
        END AS plate_no,
        CASE
            WHEN bucket = 'LAST_MONTH' AND n <= 760 THEN '정상'
            WHEN bucket = 'LAST_MONTH' AND n <= 830 THEN '영역 이탈'
            WHEN bucket = 'LAST_MONTH' THEN 'NO_FIX'
            WHEN lane_no = 1 AND (n <= 666 OR n = 684) THEN '정상'
            WHEN lane_no = 1 AND n = 683 THEN '영역 이탈'
            WHEN lane_no = 2 AND (n <= 544 OR n = 564) THEN '정상'
            WHEN lane_no = 2 AND n = 563 THEN '경계 걸침'
            ELSE 'NO_FIX'
        END AS gps_status,
        CASE
            WHEN bucket = 'LAST_MONTH' THEN (n > 760)
            WHEN lane_no = 1 THEN (n BETWEEN 667 AND 683)
            WHEN lane_no = 2 THEN (n BETWEEN 545 AND 563)
            ELSE FALSE
        END AS review_needed
    FROM seeded_events
)
INSERT INTO passage_event (
    event_id,
    payload_bytes,
    payload_format,
    payload_size_bytes,
    received_at,
    camera_group_id,
    camera_id,
    camera_role,
    device_id,
    direction,
    event_time,
    global_lane_no,
    gps_judgement_status,
    inspection_status,
    lane_no,
    needs_review,
    payment_decision,
    plate_confidence,
    plate_text,
    review_reason,
    schema_version,
    vehicle_confidence,
    plate_number
)
SELECT
    event_id,
    0::OID,
    'SEED',
    0,
    event_at + INTERVAL '3 seconds',
    'gate-a-pair-01',
    CASE WHEN lane_no = 1 THEN 'cam-front-01' ELSE 'cam-rear-02' END,
    CASE WHEN lane_no = 1 THEN 'front' ELSE 'rear' END,
    'edge-jetson-01',
    CASE WHEN lane_no = 1 THEN 'IN' ELSE 'OUT' END,
    event_at,
    lane_no,
    gps_status,
    CASE WHEN review_needed THEN '검수대기' ELSE '검수완료' END,
    lane_no,
    review_needed,
    CASE WHEN review_needed THEN '검수 필요' ELSE '정상 통과' END,
    0.96,
    plate_no,
    CASE WHEN review_needed THEN gps_status ELSE NULL END,
    'v1',
    0.98,
    plate_no
FROM mapped
ON CONFLICT (event_id) DO NOTHING;

INSERT INTO toll_history (
    passage_event_id,
    amount,
    payment_status,
    charged_at,
    lane_id
)
SELECT
    pe.passage_event_id,
    CASE
        WHEN pe.lane_no = 1 AND RIGHT(pe.event_id, 4) = '0001' THEN 2554
        WHEN pe.lane_no = 1 THEN 1962
        WHEN pe.lane_no = 2 AND RIGHT(pe.event_id, 4) = '0001' THEN 2468
        ELSE 1964
    END AS amount,
    CASE WHEN pe.needs_review THEN '정산대기' ELSE '정산완료' END AS payment_status,
    COALESCE(pe.event_time, pe.received_at) + INTERVAL '10 seconds' AS charged_at,
    'lane-' || pe.lane_no AS lane_id
FROM passage_event pe
WHERE pe.event_id LIKE 'CHATBOT-SEED-TODAY-%'
   OR pe.event_id LIKE 'CHATBOT-SEED-YDAY-%';

INSERT INTO gps_telemetry (
    gps_device_id,
    fix_status,
    status_message,
    accuracy_m,
    latitude,
    longitude,
    captured_at,
    received_at
) VALUES (
    'CHATBOT-GPS-SEOUL-TOLL-A',
    'FIXED',
    '정상',
    2.4,
    37.5665,
    126.9780,
    CURRENT_TIMESTAMP - INTERVAL '10 seconds',
    CURRENT_TIMESTAMP
);

INSERT INTO member_dashboard_alert (
    dashboard_id,
    lane_no,
    level,
    title,
    target,
    badge,
    detail,
    occurred_at
) VALUES
    ('SEOUL-TOLL', 1, 'warn', '상행 GPS 경계 접근', '상행 · 31가 9829', '주의', '상행 차량 GPS 경계 접근', CURRENT_DATE + TIME '17:36:47'),
    ('SEOUL-TOLL', 1, 'info', '상행 이벤트 정상 수신', '상행 레일', '정보', '상행 레일 이벤트 정상 수신', CURRENT_DATE + TIME '17:35:22'),
    ('SEOUL-TOLL', 1, 'info', '상행 LAN 상태 정상', '상행 Edge', '정보', '상행 Edge LAN 상태 정상', CURRENT_DATE + TIME '17:31:08'),
    ('SEOUL-TOLL', 2, 'danger', '하행 정차 의심', '하행 · 98머 3344', '주의', '정차 의심 차량 확인 필요', CURRENT_DATE + TIME '17:28:55'),
    ('SEOUL-TOLL', 2, 'warn', '하행 CCTV 수신 지연', '하행 카메라', '주의', '카메라 프레임 지연 3초', CURRENT_DATE + TIME '17:26:28'),
    ('SEOUL-TOLL', 2, 'info', '하행 LTE 백업망 전환', 'LAN 연결 끊김 감지', '정보', 'LAN 장애 감지 후 LTE 백업망 전환', CURRENT_DATE + TIME '17:24:10');

COMMIT;
