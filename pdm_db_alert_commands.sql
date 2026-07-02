-- PDM DB and alert commands for PostgreSQL
-- Run with psql. This script keeps device_id, camera_id, and lane_id separated.
-- passage_event is included as a compatibility fallback. If the project already
-- has passage_event, PostgreSQL will keep the existing table.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Existing Best-Fit passage events.
-- Important: device_id is the source traffic-event device. It is not camera_id.
CREATE TABLE IF NOT EXISTS passage_event (
  event_id BIGSERIAL PRIMARY KEY,
  event_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
  device_id BIGINT NOT NULL,
  lane_id BIGINT NOT NULL,
  plate_text VARCHAR(20),
  plate_confidence DOUBLE PRECISION,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  agreement_ratio DOUBLE PRECISION,
  needs_review BOOLEAN NOT NULL DEFAULT false,
  event_status VARCHAR(20) NOT NULL DEFAULT 'ACCEPT',
  event_time TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_passage_event_status
    CHECK (event_status IN ('ACCEPT', 'REVIEW', 'REJECT')),
  CONSTRAINT chk_passage_event_plate_confidence
    CHECK (plate_confidence IS NULL OR (plate_confidence >= 0 AND plate_confidence <= 1)),
  CONSTRAINT chk_passage_event_agreement_ratio
    CHECK (agreement_ratio IS NULL OR (agreement_ratio >= 0 AND agreement_ratio <= 1)),
  CONSTRAINT chk_passage_event_candidate_count
    CHECK (candidate_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_passage_event_event_uuid
  ON passage_event (event_uuid);
CREATE INDEX IF NOT EXISTS ix_passage_event_device_lane_time
  ON passage_event (device_id, lane_id, event_time DESC);
CREATE INDEX IF NOT EXISTS ix_passage_event_lane_time
  ON passage_event (lane_id, event_time DESC);

-- PDM camera master. source_device_id connects to passage_event.device_id.
-- Do not add lane_id here. Use camera_lane_mapping for camera-to-lane ownership.
CREATE TABLE IF NOT EXISTS camera_device (
  camera_id BIGSERIAL PRIMARY KEY,
  camera_code VARCHAR(50) NOT NULL,
  camera_name VARCHAR(100) NOT NULL,
  direction VARCHAR(20) NOT NULL,
  source_device_id BIGINT,
  location_name VARCHAR(100),
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT ux_camera_device_camera_code UNIQUE (camera_code),
  CONSTRAINT ux_camera_device_source_device_id UNIQUE (source_device_id),
  CONSTRAINT chk_camera_device_direction CHECK (direction IN ('FRONT', 'REAR'))
);

CREATE INDEX IF NOT EXISTS ix_camera_device_source_device_id
  ON camera_device (source_device_id);
CREATE INDEX IF NOT EXISTS ix_camera_device_direction_active
  ON camera_device (direction, is_active);

DROP TRIGGER IF EXISTS trg_camera_device_updated_at ON camera_device;
CREATE TRIGGER trg_camera_device_updated_at
BEFORE UPDATE ON camera_device
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One camera can cover lane 1 and lane 2 at the same time.
CREATE TABLE IF NOT EXISTS camera_lane_mapping (
  mapping_id BIGSERIAL PRIMARY KEY,
  camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id) ON DELETE CASCADE,
  lane_id BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT ux_camera_lane_mapping_camera_lane UNIQUE (camera_id, lane_id)
);

CREATE INDEX IF NOT EXISTS ix_camera_lane_mapping_lane_id
  ON camera_lane_mapping (lane_id);

CREATE TABLE IF NOT EXISTS camera_compare_result (
  compare_id BIGSERIAL PRIMARY KEY,
  event_group_key VARCHAR(100),
  front_event_id BIGINT REFERENCES passage_event(event_id) ON DELETE SET NULL,
  rear_event_id BIGINT REFERENCES passage_event(event_id) ON DELETE SET NULL,
  lane_id BIGINT NOT NULL,
  front_camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id),
  rear_camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id),
  front_plate_text VARCHAR(20),
  rear_plate_text VARCHAR(20),
  is_matched BOOLEAN NOT NULL DEFAULT false,
  mismatch_type VARCHAR(30),
  confidence_gap DOUBLE PRECISION,
  compared_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_camera_compare_mismatch_type
    CHECK (
      mismatch_type IS NULL OR
      mismatch_type IN ('TEXT_MISMATCH', 'FRONT_MISSING', 'REAR_MISSING', 'TIME_WINDOW_UNMATCHED')
    )
);

CREATE INDEX IF NOT EXISTS ix_camera_compare_event_group_key
  ON camera_compare_result (event_group_key);
CREATE INDEX IF NOT EXISTS ix_camera_compare_lane_compared_at
  ON camera_compare_result (lane_id, compared_at DESC);
CREATE INDEX IF NOT EXISTS ix_camera_compare_front_camera
  ON camera_compare_result (front_camera_id, compared_at DESC);
CREATE INDEX IF NOT EXISTS ix_camera_compare_rear_camera
  ON camera_compare_result (rear_camera_id, compared_at DESC);

CREATE TABLE IF NOT EXISTS camera_quality_metric (
  metric_id BIGSERIAL PRIMARY KEY,
  camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id) ON DELETE CASCADE,
  lane_id BIGINT,
  bucket_start TIMESTAMP NOT NULL,
  bucket_end TIMESTAMP NOT NULL,
  avg_ocr_confidence DOUBLE PRECISION,
  success_rate DOUBLE PRECISION,
  missing_rate DOUBLE PRECISION,
  match_rate DOUBLE PRECISION,
  mismatch_rate DOUBLE PRECISION,
  event_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_camera_quality_bucket CHECK (bucket_end > bucket_start),
  CONSTRAINT chk_camera_quality_event_count CHECK (event_count >= 0),
  CONSTRAINT chk_camera_quality_avg_ocr_confidence
    CHECK (avg_ocr_confidence IS NULL OR (avg_ocr_confidence >= 0 AND avg_ocr_confidence <= 1)),
  CONSTRAINT chk_camera_quality_success_rate
    CHECK (success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1)),
  CONSTRAINT chk_camera_quality_missing_rate
    CHECK (missing_rate IS NULL OR (missing_rate >= 0 AND missing_rate <= 1)),
  CONSTRAINT chk_camera_quality_match_rate
    CHECK (match_rate IS NULL OR (match_rate >= 0 AND match_rate <= 1)),
  CONSTRAINT chk_camera_quality_mismatch_rate
    CHECK (mismatch_rate IS NULL OR (mismatch_rate >= 0 AND mismatch_rate <= 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_camera_quality_metric_bucket
  ON camera_quality_metric (camera_id, COALESCE(lane_id, -1), bucket_start, bucket_end);
CREATE INDEX IF NOT EXISTS ix_camera_quality_metric_camera_bucket
  ON camera_quality_metric (camera_id, bucket_start DESC);

CREATE TABLE IF NOT EXISTS pdm_analysis_result (
  analysis_id BIGSERIAL PRIMARY KEY,
  camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id) ON DELETE CASCADE,
  lane_id BIGINT,
  analysis_start TIMESTAMP NOT NULL,
  analysis_end TIMESTAMP NOT NULL,
  health_score DOUBLE PRECISION NOT NULL,
  risk_level VARCHAR(20) NOT NULL,
  model_type VARCHAR(30) NOT NULL,
  model_version VARCHAR(50) NOT NULL,
  reason_code VARCHAR(50),
  reason_text TEXT,
  recommended_action TEXT,
  trend_summary TEXT,
  analyzed_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_pdm_analysis_period CHECK (analysis_end > analysis_start),
  CONSTRAINT chk_pdm_analysis_health_score CHECK (health_score >= 0 AND health_score <= 100),
  CONSTRAINT chk_pdm_analysis_risk_level CHECK (risk_level IN ('NORMAL', 'WARNING', 'CRITICAL')),
  CONSTRAINT chk_pdm_analysis_model_type
    CHECK (model_type IN ('RULE_BASED', 'ISOLATION_FOREST', 'XGBOOST', 'LSTM'))
);

CREATE INDEX IF NOT EXISTS ix_pdm_analysis_camera_analyzed_at
  ON pdm_analysis_result (camera_id, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS ix_pdm_analysis_risk_level
  ON pdm_analysis_result (risk_level, analyzed_at DESC);

CREATE TABLE IF NOT EXISTS maintenance_alert (
  alert_id BIGSERIAL PRIMARY KEY,
  analysis_id BIGINT NOT NULL REFERENCES pdm_analysis_result(analysis_id) ON DELETE CASCADE,
  camera_id BIGINT NOT NULL REFERENCES camera_device(camera_id) ON DELETE CASCADE,
  lane_id BIGINT,
  risk_level VARCHAR(20) NOT NULL,
  alert_title VARCHAR(200) NOT NULL,
  alert_message TEXT NOT NULL,
  reason_text TEXT,
  recommended_action TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT ux_maintenance_alert_analysis UNIQUE (analysis_id),
  CONSTRAINT chk_maintenance_alert_risk_level CHECK (risk_level IN ('WARNING', 'CRITICAL')),
  CONSTRAINT chk_maintenance_alert_status
    CHECK (status IN ('CREATED', 'CHECKING', 'RESOLVED', 'FALSE_ALARM'))
);

CREATE INDEX IF NOT EXISTS ix_maintenance_alert_status_created_at
  ON maintenance_alert (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_maintenance_alert_camera_created_at
  ON maintenance_alert (camera_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_maintenance_alert_updated_at ON maintenance_alert;
CREATE TRIGGER trg_maintenance_alert_updated_at
BEFORE UPDATE ON maintenance_alert
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS notification_log (
  notification_id BIGSERIAL PRIMARY KEY,
  alert_id BIGINT NOT NULL REFERENCES maintenance_alert(alert_id) ON DELETE CASCADE,
  receiver_email VARCHAR(200) NOT NULL,
  send_status VARCHAR(20) NOT NULL,
  failure_reason TEXT,
  sent_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_notification_log_send_status CHECK (send_status IN ('SUCCESS', 'FAIL', 'SKIPPED'))
);

CREATE INDEX IF NOT EXISTS ix_notification_log_alert_id
  ON notification_log (alert_id);
CREATE INDEX IF NOT EXISTS ix_notification_log_receiver_created_at
  ON notification_log (receiver_email, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_log_success_once_per_alert_receiver
  ON notification_log (alert_id, receiver_email)
  WHERE send_status = 'SUCCESS';

CREATE TABLE IF NOT EXISTS demo_scenario_log (
  scenario_id BIGSERIAL PRIMARY KEY,
  scenario_type VARCHAR(50) NOT NULL,
  description TEXT,
  executed_by VARCHAR(100),
  executed_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_demo_scenario_type
    CHECK (scenario_type IN ('NORMAL', 'REAR_DEGRADED', 'MISMATCH_INCREASED', 'MISSING_INCREASED'))
);

CREATE INDEX IF NOT EXISTS ix_demo_scenario_log_executed_at
  ON demo_scenario_log (executed_at DESC);

COMMIT;

-- Seed command example: one front camera and one rear camera, each mapped to lane 1 and lane 2.
-- Replace source_device_id values with the existing passage_event.device_id values.
/*
INSERT INTO camera_device
  (camera_code, camera_name, direction, source_device_id, location_name)
VALUES
  ('FRONT_CAM_001', 'Front camera 001', 'FRONT', 1001, 'Toll lane group A'),
  ('REAR_CAM_001', 'Rear camera 001', 'REAR', 1002, 'Toll lane group A')
ON CONFLICT (camera_code) DO UPDATE
SET camera_name = EXCLUDED.camera_name,
    direction = EXCLUDED.direction,
    source_device_id = EXCLUDED.source_device_id,
    location_name = EXCLUDED.location_name,
    is_active = true;

INSERT INTO camera_lane_mapping (camera_id, lane_id)
SELECT camera_id, lane_id
FROM camera_device
CROSS JOIN (VALUES (1::BIGINT), (2::BIGINT)) AS lanes(lane_id)
WHERE camera_code IN ('FRONT_CAM_001', 'REAR_CAM_001')
ON CONFLICT (camera_id, lane_id) DO NOTHING;
*/

-- Create alerts from FastAPI analysis results.
-- This creates exactly one alert per WARNING or CRITICAL analysis_id.
/*
INSERT INTO maintenance_alert (
  analysis_id,
  camera_id,
  lane_id,
  risk_level,
  alert_title,
  alert_message,
  reason_text,
  recommended_action,
  status
)
SELECT
  analysis_id,
  camera_id,
  lane_id,
  risk_level,
  '[' || risk_level || '] Camera predictive maintenance alert',
  COALESCE(trend_summary, 'Camera quality degradation detected.'),
  reason_text,
  recommended_action,
  'CREATED'
FROM pdm_analysis_result
WHERE risk_level IN ('WARNING', 'CRITICAL')
ON CONFLICT (analysis_id) DO NOTHING;
*/

-- Notification log command examples.
/*
INSERT INTO notification_log (alert_id, receiver_email, send_status, sent_at)
VALUES (:alert_id, 'operator@example.com', 'SUCCESS', now());

INSERT INTO notification_log (alert_id, receiver_email, send_status, failure_reason, sent_at)
VALUES (:alert_id, 'operator@example.com', 'FAIL', 'SMTP connection failed', now());

INSERT INTO notification_log (alert_id, receiver_email, send_status, failure_reason, sent_at)
VALUES (:alert_id, 'operator@example.com', 'SKIPPED', 'Demo mode or duplicate send limit', now());
*/
