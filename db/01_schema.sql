-- HiFive chatbot required PostgreSQL schema.
-- Run this on a development/test database before loading 02_seed_dashboard_data.sql.

CREATE TABLE IF NOT EXISTS passage_event (
    passage_event_id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL,
    payload_bytes OID NOT NULL DEFAULT 0,
    payload_format VARCHAR(255) NOT NULL DEFAULT 'SEED',
    payload_size_bytes INTEGER NOT NULL DEFAULT 0,
    received_at TIMESTAMP NOT NULL,
    agreement_ratio DOUBLE PRECISION,
    bbox_coord VARCHAR(255),
    bbox_h DOUBLE PRECISION,
    bbox_w DOUBLE PRECISION,
    bbox_x DOUBLE PRECISION,
    bbox_y DOUBLE PRECISION,
    camera_group_id VARCHAR(255),
    camera_id VARCHAR(255),
    camera_role VARCHAR(255),
    candidate_count INTEGER,
    device_id VARCHAR(255),
    direction VARCHAR(255),
    event_time TIMESTAMP,
    global_lane_no INTEGER,
    gps_judgement_status VARCHAR(255),
    inspection_status VARCHAR(255),
    lane_no INTEGER,
    local_track_id VARCHAR(255),
    needs_review BOOLEAN,
    payment_decision VARCHAR(255),
    plate_confidence DOUBLE PRECISION,
    plate_text VARCHAR(255),
    review_reason VARCHAR(255),
    schema_version VARCHAR(255),
    vehicle_confidence DOUBLE PRECISION,
    vehicle_pass_id VARCHAR(255),
    plate_number VARCHAR(255)
);

ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS event_id VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS payload_bytes OID NOT NULL DEFAULT 0;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS payload_format VARCHAR(255) NOT NULL DEFAULT 'SEED';
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS payload_size_bytes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS received_at TIMESTAMP;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS event_time TIMESTAMP;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS lane_no INTEGER;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS global_lane_no INTEGER;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS direction VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS camera_id VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS camera_role VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS camera_group_id VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS device_id VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS gps_judgement_status VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS inspection_status VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS needs_review BOOLEAN;
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS payment_decision VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS plate_text VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS plate_number VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS review_reason VARCHAR(255);
ALTER TABLE passage_event ADD COLUMN IF NOT EXISTS schema_version VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS ux_passage_event_event_id ON passage_event(event_id);
CREATE INDEX IF NOT EXISTS ix_passage_event_time ON passage_event(COALESCE(event_time, received_at));
CREATE INDEX IF NOT EXISTS ix_passage_event_lane ON passage_event(lane_no);

CREATE TABLE IF NOT EXISTS toll_history (
    toll_history_id BIGSERIAL PRIMARY KEY,
    passage_event_id BIGINT,
    amount BIGINT NOT NULL DEFAULT 0,
    payment_status VARCHAR(255),
    charged_at TIMESTAMP NOT NULL,
    lane_id VARCHAR(255)
);

ALTER TABLE toll_history ADD COLUMN IF NOT EXISTS passage_event_id BIGINT;
ALTER TABLE toll_history ADD COLUMN IF NOT EXISTS amount BIGINT NOT NULL DEFAULT 0;
ALTER TABLE toll_history ADD COLUMN IF NOT EXISTS payment_status VARCHAR(255);
ALTER TABLE toll_history ADD COLUMN IF NOT EXISTS charged_at TIMESTAMP;
ALTER TABLE toll_history ADD COLUMN IF NOT EXISTS lane_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_toll_history_charged_at ON toll_history(charged_at);
CREATE INDEX IF NOT EXISTS ix_toll_history_lane_id ON toll_history(lane_id);
CREATE INDEX IF NOT EXISTS ix_toll_history_passage_event_id ON toll_history(passage_event_id);

CREATE TABLE IF NOT EXISTS gps_telemetry (
    gps_telemetry_id BIGSERIAL PRIMARY KEY,
    gps_device_id VARCHAR(255),
    fix_status VARCHAR(255),
    status_message VARCHAR(255),
    accuracy_m DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    captured_at TIMESTAMP,
    received_at TIMESTAMP NOT NULL
);

ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS gps_device_id VARCHAR(255);
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS fix_status VARCHAR(255);
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS status_message VARCHAR(255);
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS accuracy_m DOUBLE PRECISION;
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP;
ALTER TABLE gps_telemetry ADD COLUMN IF NOT EXISTS received_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_gps_telemetry_received_at ON gps_telemetry(received_at);

CREATE TABLE IF NOT EXISTS member_dashboard_snapshot (
    dashboard_id TEXT PRIMARY KEY,
    center_name TEXT NOT NULL,
    active_direction TEXT NOT NULL,
    selected_lane INTEGER NOT NULL,
    selected_lane_text TEXT NOT NULL,
    yolo_status TEXT NOT NULL,
    original_resolution TEXT NOT NULL,
    composite_resolution TEXT NOT NULL,
    yolo_model TEXT NOT NULL,
    fps NUMERIC,
    zone_name TEXT NOT NULL,
    operation_status TEXT NOT NULL,
    cctv_status TEXT NOT NULL,
    gps_status TEXT NOT NULL,
    event_status TEXT NOT NULL,
    network_status TEXT NOT NULL,
    network_path TEXT NOT NULL,
    data_status TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS center_name TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS active_direction TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS selected_lane INTEGER;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS selected_lane_text TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS yolo_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS original_resolution TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS composite_resolution TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS yolo_model TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS fps NUMERIC;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS zone_name TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS operation_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS cctv_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS gps_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS event_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS network_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS network_path TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS data_status TEXT;
ALTER TABLE member_dashboard_snapshot ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS member_dashboard_alert (
    alert_id BIGSERIAL PRIMARY KEY,
    dashboard_id TEXT NOT NULL,
    lane_no INTEGER,
    level TEXT NOT NULL,
    title TEXT NOT NULL,
    target TEXT NOT NULL,
    badge TEXT NOT NULL,
    detail TEXT,
    occurred_at TIMESTAMP NOT NULL
);

ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS dashboard_id TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS lane_no INTEGER;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS level TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS target TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS badge TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS detail TEXT;
ALTER TABLE member_dashboard_alert ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_member_dashboard_alert_dashboard_lane_time
    ON member_dashboard_alert(dashboard_id, lane_no, occurred_at DESC);
