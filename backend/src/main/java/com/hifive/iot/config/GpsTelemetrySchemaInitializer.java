package com.hifive.iot.config;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class GpsTelemetrySchemaInitializer implements ApplicationRunner {

	private final JdbcTemplate jdbcTemplate;

	public GpsTelemetrySchemaInitializer(JdbcTemplate jdbcTemplate) {
		this.jdbcTemplate = jdbcTemplate;
	}

	@Override
	public void run(ApplicationArguments args) {
		jdbcTemplate.execute("ALTER TABLE IF EXISTS gps_telemetry ALTER COLUMN latitude DROP NOT NULL");
		jdbcTemplate.execute("ALTER TABLE IF EXISTS gps_telemetry ALTER COLUMN longitude DROP NOT NULL");
		jdbcTemplate.execute(
			"ALTER TABLE IF EXISTS gps_telemetry "
				+ "ADD COLUMN IF NOT EXISTS fix_status varchar(20) NOT NULL DEFAULT 'FIXED'"
		);
		jdbcTemplate.execute(
			"ALTER TABLE IF EXISTS gps_telemetry "
				+ "ADD COLUMN IF NOT EXISTS status_message varchar(120)"
		);
		jdbcTemplate.execute(
			"ALTER TABLE IF EXISTS gps_telemetry "
				+ "ADD COLUMN IF NOT EXISTS raw_sentence varchar(180)"
		);
		jdbcTemplate.execute("UPDATE gps_telemetry SET fix_status = 'FIXED' WHERE fix_status IS NULL");
	}
}
