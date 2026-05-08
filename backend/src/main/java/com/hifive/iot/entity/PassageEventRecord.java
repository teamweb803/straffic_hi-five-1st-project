package com.hifive.iot.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(
	name = "passage_event",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_passage_event_event_id", columnNames = "event_id")
	},
	indexes = {
		@Index(name = "idx_passage_event_received_at", columnList = "received_at")
	}
)
public class PassageEventRecord {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "passage_event_id")
	private Long passageEventId;

	@Column(name = "event_id", nullable = false, length = 120)
	private String eventId;

	@Column(name = "payload_format", nullable = false, length = 20)
	private String payloadFormat;

	@Lob
	@Column(name = "payload_bytes", nullable = false)
	private byte[] payloadBytes;

	@Column(name = "payload_size_bytes", nullable = false)
	private Integer payloadSizeBytes;

	@Column(name = "received_at", nullable = false)
	private LocalDateTime receivedAt;

	protected PassageEventRecord() {
	}

	public PassageEventRecord(String eventId, byte[] payloadBytes, LocalDateTime receivedAt) {
		this.eventId = eventId;
		this.payloadFormat = "protobuf";
		this.payloadBytes = payloadBytes;
		this.payloadSizeBytes = payloadBytes.length;
		this.receivedAt = receivedAt;
	}

	public Long getPassageEventId() {
		return passageEventId;
	}

	public String getEventId() {
		return eventId;
	}

	public Integer getPayloadSizeBytes() {
		return payloadSizeBytes;
	}

	public LocalDateTime getReceivedAt() {
		return receivedAt;
	}
}
