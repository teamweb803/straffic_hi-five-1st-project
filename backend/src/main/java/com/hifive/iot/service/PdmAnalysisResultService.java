package com.hifive.iot.service;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

import com.hifive.iot.dto.PdmAlertResponse;
import com.hifive.iot.dto.PdmAnalysisResultBatchRequest;
import com.hifive.iot.dto.PdmAnalysisResultBatchResponse;
import com.hifive.iot.dto.PdmAnalysisResultRequest;
import com.hifive.iot.dto.PdmAnalysisResultResponse;
import com.hifive.iot.dto.PdmIntegratedResultResponse;
import com.hifive.iot.dto.PdmModelResultResponse;
import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.MaintenanceAlert;
import com.hifive.iot.entity.PdmAnalysisResult;
import com.hifive.iot.repository.CameraDeviceRepository;
import com.hifive.iot.repository.CameraLaneMappingRepository;
import com.hifive.iot.repository.MaintenanceAlertRepository;
import com.hifive.iot.repository.PdmAnalysisResultRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PdmAnalysisResultService {

	private static final Set<String> RISK_LEVELS = Set.of("NORMAL", "WARNING", "HIGH", "CRITICAL");
	private static final Set<String> MODEL_TYPES = Set.of(
		"RULE_BASED",
		"ISOLATION_FOREST",
		"LSTM_AE"
	);
	private static final Map<String, Double> MODEL_WEIGHTS = Map.of(
		"RULE_BASED", 0.4,
		"ISOLATION_FOREST", 0.3,
		"LSTM_AE", 0.3
	);

	private final CameraDeviceRepository cameraDeviceRepository;
	private final CameraLaneMappingRepository cameraLaneMappingRepository;
	private final PdmAnalysisResultRepository pdmAnalysisResultRepository;
	private final MaintenanceAlertRepository maintenanceAlertRepository;
	private final PdmAlertMailService pdmAlertMailService;

	@Transactional
	public PdmAnalysisResultResponse save(PdmAnalysisResultRequest request) {
		validateRequest(request);

		CameraDevice camera = cameraDeviceRepository.findById(request.cameraId())
			.orElseThrow(() -> new IllegalArgumentException("camera not found"));
		validateLane(camera, request.laneId());

		String modelType = request.modelType().trim().toUpperCase();
		if (findExisting(camera, request, modelType).isPresent()) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "analysis result already exists");
		}

		return PdmAnalysisResultResponse.from(saveNewResult(camera, request, modelType));
	}

	@Transactional
	public PdmAnalysisResultBatchResponse saveBatch(PdmAnalysisResultBatchRequest request) {
		if (request == null || request.results() == null || request.results().isEmpty()) {
			throw new IllegalArgumentException("results are required");
		}

		List<PdmAnalysisResultRequest> results = request.results();
		results.forEach(this::validateRequest);
		PdmAnalysisResultRequest first = results.get(0);
		validateSameWindow(results, first);

		CameraDevice camera = cameraDeviceRepository.findById(first.cameraId())
			.orElseThrow(() -> new IllegalArgumentException("camera not found"));
		validateLane(camera, first.laneId());

		List<PdmAnalysisResult> savedResults = results.stream()
			.map(result -> saveOrFindExisting(camera, result))
			.toList();
		PdmIntegratedResultResponse integrated = integrate(savedResults);
		MaintenanceAlert alert = createAlertIfNeeded(camera, first, savedResults, integrated);

		return new PdmAnalysisResultBatchResponse(
			camera.getCameraId(),
			first.laneId(),
			first.analysisStart(),
			first.analysisEnd(),
			integrated,
			savedResults.stream().map(PdmModelResultResponse::from).toList(),
			alert != null ? PdmAlertResponse.from(alert) : null
		);
	}

	private PdmAnalysisResult saveOrFindExisting(CameraDevice camera, PdmAnalysisResultRequest request) {
		String modelType = request.modelType().trim().toUpperCase();
		return findExisting(camera, request, modelType)
			.orElseGet(() -> saveNewResult(camera, request, modelType));
	}

	private PdmAnalysisResult saveNewResult(
		CameraDevice camera,
		PdmAnalysisResultRequest request,
		String modelType
	) {
		String riskLevel = normalizeRiskLevel(request.riskLevel());
		return pdmAnalysisResultRepository.save(PdmAnalysisResult.builder()
			.camera(camera)
			.laneId(request.laneId())
			.analysisStart(request.analysisStart())
			.analysisEnd(request.analysisEnd())
			.healthScore(request.healthScore())
			.riskLevel(riskLevel)
			.modelType(modelType)
			.modelVersion(trimToNull(request.modelVersion()))
			.reasonCode(trimToNull(request.reasonCode()))
			.reasonText(trimToNull(request.reasonText()))
			.recommendedAction(trimToNull(request.recommendedAction()))
			.trendSummary(trimToNull(request.trendSummary()))
			.analyzedAt(LocalDateTime.now())
			.build());
	}

	private Optional<PdmAnalysisResult> findExisting(
		CameraDevice camera,
		PdmAnalysisResultRequest request,
		String modelType
	) {
		return pdmAnalysisResultRepository.findByCameraAndLaneIdAndAnalysisStartAndAnalysisEndAndModelType(
			camera,
			request.laneId(),
			request.analysisStart(),
			request.analysisEnd(),
			modelType
		);
	}

	private void validateRequest(PdmAnalysisResultRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("request body is required");
		}
		if (!StringUtils.hasText(request.modelType())
			|| !MODEL_TYPES.contains(request.modelType().trim().toUpperCase())) {
			throw new IllegalArgumentException("unsupported modelType");
		}
		if (request.cameraId() == null) {
			throw new IllegalArgumentException("cameraId is required");
		}
		if (request.analysisStart() == null || request.analysisEnd() == null) {
			throw new IllegalArgumentException("analysis period is required");
		}
		if (request.analysisStart().isAfter(request.analysisEnd())) {
			throw new IllegalArgumentException("analysisStart must be before analysisEnd");
		}
		if (request.healthScore() == null
			|| request.healthScore() < 0
			|| request.healthScore() > 100) {
			throw new IllegalArgumentException("healthScore must be between 0 and 100");
		}
		if (!StringUtils.hasText(request.riskLevel())
			|| !RISK_LEVELS.contains(request.riskLevel().trim().toUpperCase())) {
			throw new IllegalArgumentException("riskLevel must be NORMAL, WARNING, HIGH, or CRITICAL");
		}
	}

	private void validateSameWindow(
		List<PdmAnalysisResultRequest> results,
		PdmAnalysisResultRequest first
	) {
		for (PdmAnalysisResultRequest result : results) {
			if (!Objects.equals(first.cameraId(), result.cameraId())
				|| !Objects.equals(first.laneId(), result.laneId())
				|| !Objects.equals(first.analysisStart(), result.analysisStart())
				|| !Objects.equals(first.analysisEnd(), result.analysisEnd())) {
				throw new IllegalArgumentException("batch results must have the same camera, lane, and analysis window");
			}
		}
	}

	private void validateLane(CameraDevice camera, Integer laneId) {
		if (laneId != null && !cameraLaneMappingRepository.existsByCameraAndLaneId(camera, laneId)) {
			throw new IllegalArgumentException("camera does not manage the requested lane");
		}
	}

	private PdmIntegratedResultResponse integrate(List<PdmAnalysisResult> results) {
		if (results.isEmpty()) {
			return new PdmIntegratedResultResponse(null, "UNKNOWN", null, null);
		}

		double weightedSum = 0.0;
		double weightSum = 0.0;
		for (PdmAnalysisResult result : results) {
			if (result.getHealthScore() == null) {
				continue;
			}
			double weight = MODEL_WEIGHTS.getOrDefault(result.getModelType(), 1.0);
			weightedSum += clampScore(result.getHealthScore()) * weight;
			weightSum += weight;
		}

		Double score = weightSum > 0 ? roundOne(weightedSum / weightSum) : null;
		PdmAnalysisResult representative = representativeResult(results).orElse(null);
		return new PdmIntegratedResultResponse(
			score,
			integratedRiskLevel(score, results),
			representative != null ? representative.getReasonText() : null,
			representative != null ? representative.getRecommendedAction() : null
		);
	}

	private String integratedRiskLevel(Double score, List<PdmAnalysisResult> results) {
		String scoreRisk = score != null ? riskLevel(score) : "UNKNOWN";
		String modelRisk = results.stream()
			.map(PdmAnalysisResult::getRiskLevel)
			.max(Comparator.comparingInt(this::riskRank))
			.orElse(scoreRisk);
		return riskRank(modelRisk) > riskRank(scoreRisk) ? modelRisk : scoreRisk;
	}

	private MaintenanceAlert createAlertIfNeeded(
		CameraDevice camera,
		PdmAnalysisResultRequest first,
		List<PdmAnalysisResult> results,
		PdmIntegratedResultResponse integrated
	) {
		List<MaintenanceAlert> activeAlerts = maintenanceAlertRepository.findCreatedByCameraAndLane(
			camera.getCameraId(),
			first.laneId()
		);

		if (!"WARNING".equals(integrated.riskLevel()) && !"CRITICAL".equals(integrated.riskLevel())) {
			activeAlerts.forEach(alert -> alert.changeStatus("RESOLVED"));
			return null;
		}

		PdmAnalysisResult representative = representativeResult(results)
			.orElseThrow(() -> new IllegalArgumentException("representative analysis result is required"));
		String message = StringUtils.hasText(integrated.reasonText())
			? integrated.reasonText()
			: camera.getCameraName() + " quality risk detected";
		String alertTitle = camera.getCameraName() + " " + integrated.riskLevel() + " alert";

		Optional<MaintenanceAlert> sameActiveAlert = activeAlerts.stream()
			.filter(alert -> isSameActiveAlert(alert, alertTitle, integrated.riskLevel()))
			.findFirst();
		if (sameActiveAlert.isPresent()) {
			MaintenanceAlert alert = sameActiveAlert.get();
			activeAlerts.stream()
				.filter(other -> !Objects.equals(other.getAlertId(), alert.getAlertId()))
				.forEach(other -> other.changeStatus("RESOLVED"));
			alert.refresh(
				representative,
				integrated.riskLevel(),
				alertTitle,
				message,
				integrated.reasonText(),
				integrated.recommendedAction()
			);
			return alert;
		}

		activeAlerts.forEach(alert -> alert.changeStatus("RESOLVED"));

		MaintenanceAlert alert = maintenanceAlertRepository.save(MaintenanceAlert.builder()
			.analysis(representative)
			.camera(camera)
			.laneId(first.laneId())
			.riskLevel(integrated.riskLevel())
			.alertTitle(alertTitle)
			.alertMessage(message)
			.reasonText(integrated.reasonText())
			.recommendedAction(integrated.recommendedAction())
			.status("CREATED")
			.build());
		pdmAlertMailService.sendAlert(alert);
		return alert;
	}

	private boolean isSameActiveAlert(MaintenanceAlert alert, String alertTitle, String riskLevel) {
		return Objects.equals(alert.getAlertTitle(), alertTitle)
			&& Objects.equals(alert.getRiskLevel(), riskLevel);
	}

	private Optional<PdmAnalysisResult> representativeResult(List<PdmAnalysisResult> results) {
		return results.stream()
			.max(Comparator
				.comparingInt((PdmAnalysisResult result) -> riskRank(result.getRiskLevel()))
				.thenComparing(result -> result.getHealthScore() != null ? -result.getHealthScore() : 0.0));
	}

	private double clampScore(double score) {
		return Math.min(100.0, Math.max(0.0, score));
	}

	private Double roundOne(double value) {
		return Math.round(value * 10.0) / 10.0;
	}

	private String riskLevel(double score) {
		if (score >= 80.0) {
			return "NORMAL";
		}
		if (score >= 60.0) {
			return "WARNING";
		}
		return "CRITICAL";
	}

	private int riskRank(String level) {
		return switch (level) {
			case "CRITICAL", "HIGH" -> 3;
			case "WARNING" -> 2;
			case "NORMAL" -> 1;
			default -> 0;
		};
	}

	private String normalizeRiskLevel(String riskLevel) {
		String normalized = riskLevel.trim().toUpperCase();
		return "HIGH".equals(normalized) ? "CRITICAL" : normalized;
	}

	private String trimToNull(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
