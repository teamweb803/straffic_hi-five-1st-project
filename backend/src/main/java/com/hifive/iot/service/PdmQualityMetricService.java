package com.hifive.iot.service;

import java.time.LocalDateTime;
import java.util.List;

import com.hifive.iot.dto.PdmQualityMetricRequest;
import com.hifive.iot.dto.PdmQualityMetricResponse;
import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.CameraQualityMetric;
import com.hifive.iot.repository.CameraDeviceRepository;
import com.hifive.iot.repository.CameraLaneMappingRepository;
import com.hifive.iot.repository.CameraQualityMetricRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PdmQualityMetricService {

	private static final long DEFAULT_QUERY_HOURS = 6L;

	private final CameraDeviceRepository cameraDeviceRepository;
	private final CameraLaneMappingRepository cameraLaneMappingRepository;
	private final CameraQualityMetricRepository cameraQualityMetricRepository;
	private final PdmDemoModeService pdmDemoModeService;

	@Transactional
	public PdmQualityMetricResponse save(PdmQualityMetricRequest request) {
		validateRequest(request);
		CameraDevice camera = cameraDeviceRepository.findById(request.cameraId())
			.orElseThrow(() -> new IllegalArgumentException("camera not found"));
		if (!cameraLaneMappingRepository.existsByCameraAndLaneId(camera, request.laneId())) {
			throw new IllegalArgumentException("camera does not manage the requested lane");
		}

		return cameraQualityMetricRepository
			.findByCameraAndLaneIdAndBucketStart(camera, request.laneId(), request.bucketStart())
			.map(metric -> {
				metric.updateValues(
					request.bucketEnd(),
					request.avgOcrConfidence(),
					request.successRate(),
					request.missingRate(),
					request.matchRate(),
					request.mismatchRate(),
					request.eventCount()
				);
				return PdmQualityMetricResponse.from(metric);
			})
			.orElseGet(() -> PdmQualityMetricResponse.from(
				cameraQualityMetricRepository.save(CameraQualityMetric.builder()
					.camera(camera)
					.laneId(request.laneId())
					.bucketStart(request.bucketStart())
					.bucketEnd(request.bucketEnd())
					.avgOcrConfidence(request.avgOcrConfidence())
					.successRate(request.successRate())
					.missingRate(request.missingRate())
					.matchRate(request.matchRate())
					.mismatchRate(request.mismatchRate())
					.eventCount(request.eventCount())
					.build())
			));
	}

	public List<PdmQualityMetricResponse> getQualityMetrics(
		Long cameraId,
		Integer laneId,
		LocalDateTime from,
		LocalDateTime to
	) {
		if (cameraId != null && cameraDeviceRepository.findById(cameraId).isEmpty()) {
			throw new IllegalArgumentException("camera not found");
		}

		LocalDateTime effectiveTo = to != null ? to : LocalDateTime.now();
		LocalDateTime effectiveFrom = from != null ? from : effectiveTo.minusHours(DEFAULT_QUERY_HOURS);
		if (effectiveFrom.isAfter(effectiveTo)) {
			throw new IllegalArgumentException("from must be before to");
		}
		if (pdmDemoModeService.isEnabled()) {
			return pdmDemoModeService.getQualityMetrics(cameraId, laneId, effectiveTo);
		}

		return findQualityMetrics(cameraId, laneId, effectiveFrom, effectiveTo)
			.stream()
			.map(PdmQualityMetricResponse::from)
			.toList();
	}

	private List<CameraQualityMetric> findQualityMetrics(
		Long cameraId,
		Integer laneId,
		LocalDateTime from,
		LocalDateTime to
	) {
		Pageable limit = Pageable.ofSize(1000);
		if (cameraId != null && laneId != null) {
			return cameraQualityMetricRepository.findQualityMetrics(cameraId, laneId, from, to, limit);
		}
		if (cameraId != null) {
			return cameraQualityMetricRepository.findQualityMetricsByCamera(cameraId, from, to, limit);
		}
		if (laneId != null) {
			return cameraQualityMetricRepository.findQualityMetricsByLane(laneId, from, to, limit);
		}
		return cameraQualityMetricRepository.findAllQualityMetrics(from, to, limit);
	}

	private void validateRequest(PdmQualityMetricRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("request body is required");
		}
		if (request.cameraId() == null) {
			throw new IllegalArgumentException("cameraId is required");
		}
		if (request.laneId() == null) {
			throw new IllegalArgumentException("laneId is required");
		}
		if (request.bucketStart() == null || request.bucketEnd() == null) {
			throw new IllegalArgumentException("bucket period is required");
		}
		if (!request.bucketStart().isBefore(request.bucketEnd())) {
			throw new IllegalArgumentException("bucketStart must be before bucketEnd");
		}
		validateRate(request.avgOcrConfidence(), "avgOcrConfidence");
		validateRate(request.successRate(), "successRate");
		validateRate(request.missingRate(), "missingRate");
		validateRate(request.matchRate(), "matchRate");
		validateRate(request.mismatchRate(), "mismatchRate");
		if (request.eventCount() == null || request.eventCount() < 0) {
			throw new IllegalArgumentException("eventCount must be greater than or equal to 0");
		}
	}

	private void validateRate(Double value, String fieldName) {
		if (value == null || value < 0.0 || value > 1.0) {
			throw new IllegalArgumentException(fieldName + " must be between 0 and 1");
		}
	}
}
