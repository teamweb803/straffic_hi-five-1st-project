package com.hifive.iot.service;

import java.time.LocalDateTime;

import com.hifive.iot.dto.IngestResultResponse;
import com.hifive.iot.entity.PassageEventRecord;
import com.hifive.iot.repository.PassageEventRepository;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Service
public class PassageEventIngestService {

	private final PassageEventRepository passageEventRepository;

	public PassageEventIngestService(PassageEventRepository passageEventRepository) {
		this.passageEventRepository = passageEventRepository;
	}

	@Transactional
	public IngestResultResponse ingest(String eventId, byte[] payload) {
		if (!StringUtils.hasText(eventId)) {
			throw new IllegalArgumentException("X-Event-Id header is required");
		}
		if (payload == null || payload.length == 0) {
			throw new IllegalArgumentException("protobuf payload is required");
		}

		String normalizedEventId = eventId.trim();
		if (passageEventRepository.existsByEventId(normalizedEventId)) {
			return new IngestResultResponse(normalizedEventId, "ack", true, payload.length, LocalDateTime.now());
		}

		PassageEventRecord saved = passageEventRepository.save(
			new PassageEventRecord(normalizedEventId, payload, LocalDateTime.now())
		);
		return new IngestResultResponse(
			saved.getEventId(),
			"ack",
			false,
			saved.getPayloadSizeBytes(),
			saved.getReceivedAt()
		);
	}
}
