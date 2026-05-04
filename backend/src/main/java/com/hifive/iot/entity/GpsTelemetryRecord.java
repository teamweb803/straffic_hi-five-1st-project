package com.hifive.iot.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

@Entity
@Table(
	name = "gps_telemetry",
	indexes = {
		@Index(name = "idx_gps_telemetry_device_captured", columnList = "gpsDeviceId,capturedAt"),
		@Index(name = "idx_gps_telemetry_plate_captured", columnList = "plateNumber,capturedAt")
	}
)
public class GpsTelemetryRecord {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(nullable = false, length = 80)
	private String gpsDeviceId;

	@Column(length = 20)
	private String plateNumber;

	@Column(length = 40)
	private String edgeNodeId;

	@Column(length = 40)
	private String laneId;

	private Integer trackId;

	@Column(nullable = false)
	private Double latitude;

	@Column(nullable = false)
	private Double longitude;

	private Double speedKmh;

	private Double heading;

	private Double altitudeM;

	private Double accuracyM;

	@Column(length = 40)
	private String provider;

	@Column(nullable = false)
	private LocalDateTime capturedAt;

	@Column(nullable = false)
	private LocalDateTime receivedAt;

	protected GpsTelemetryRecord() {
	}

	public GpsTelemetryRecord(
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
		this.gpsDeviceId = gpsDeviceId;
		this.plateNumber = plateNumber;
		this.edgeNodeId = edgeNodeId;
		this.laneId = laneId;
		this.trackId = trackId;
		this.latitude = latitude;
		this.longitude = longitude;
		this.speedKmh = speedKmh;
		this.heading = heading;
		this.altitudeM = altitudeM;
		this.accuracyM = accuracyM;
		this.provider = provider;
		this.capturedAt = capturedAt;
		this.receivedAt = receivedAt;
	}

	public Long getId() {
		return id;
	}

	public String getGpsDeviceId() {
		return gpsDeviceId;
	}

	public String getPlateNumber() {
		return plateNumber;
	}

	public String getEdgeNodeId() {
		return edgeNodeId;
	}

	public String getLaneId() {
		return laneId;
	}

	public Integer getTrackId() {
		return trackId;
	}

	public Double getLatitude() {
		return latitude;
	}

	public Double getLongitude() {
		return longitude;
	}

	public Double getSpeedKmh() {
		return speedKmh;
	}

	public Double getHeading() {
		return heading;
	}

	public Double getAltitudeM() {
		return altitudeM;
	}

	public Double getAccuracyM() {
		return accuracyM;
	}

	public String getProvider() {
		return provider;
	}

	public LocalDateTime getCapturedAt() {
		return capturedAt;
	}

	public LocalDateTime getReceivedAt() {
		return receivedAt;
	}
}
