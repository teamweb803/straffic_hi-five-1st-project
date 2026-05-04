package com.hifive.iot.dto;

import java.time.LocalDateTime;

import com.hifive.iot.entity.GpsTelemetryRecord;

public record GpsTelemetryResponse(
	Long id,
	String gpsDeviceId,
	String plateNumber,
	String edgeNodeId,
	String laneId,
	Integer trackId,
	Double latitude,
	Double longitude,
	Double speedKmh,
	Double heading,
	Double altitudeM,
	Double accuracyM,
	String provider,
	LocalDateTime capturedAt,
	LocalDateTime receivedAt
) {
	public static GpsTelemetryResponse from(GpsTelemetryRecord telemetry) {
		return new GpsTelemetryResponse(
			telemetry.getId(),
			telemetry.getGpsDeviceId(),
			telemetry.getPlateNumber(),
			telemetry.getEdgeNodeId(),
			telemetry.getLaneId(),
			telemetry.getTrackId(),
			telemetry.getLatitude(),
			telemetry.getLongitude(),
			telemetry.getSpeedKmh(),
			telemetry.getHeading(),
			telemetry.getAltitudeM(),
			telemetry.getAccuracyM(),
			telemetry.getProvider(),
			telemetry.getCapturedAt(),
			telemetry.getReceivedAt()
		);
	}
}
