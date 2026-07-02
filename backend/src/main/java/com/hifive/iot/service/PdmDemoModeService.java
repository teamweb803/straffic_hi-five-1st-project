package com.hifive.iot.service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

import com.hifive.iot.dto.PdmAlertResponse;
import com.hifive.iot.dto.PdmCameraAnalysisResultsResponse;
import com.hifive.iot.dto.PdmCameraDetailResponse;
import com.hifive.iot.dto.PdmCameraResponse;
import com.hifive.iot.dto.PdmCompareResultResponse;
import com.hifive.iot.dto.PdmDemoMailAlertResponse;
import com.hifive.iot.dto.PdmDemoModeRequest;
import com.hifive.iot.dto.PdmDemoModeResponse;
import com.hifive.iot.dto.PdmIntegratedResultResponse;
import com.hifive.iot.dto.PdmModelResultResponse;
import com.hifive.iot.dto.PdmQualityMetricResponse;
import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.CameraLaneMapping;
import com.hifive.iot.entity.MaintenanceAlert;
import com.hifive.iot.entity.PdmAnalysisResult;
import com.hifive.iot.repository.CameraDeviceRepository;
import com.hifive.iot.repository.CameraLaneMappingRepository;
import com.hifive.iot.repository.MaintenanceAlertRepository;
import com.hifive.iot.repository.PdmAnalysisResultRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PdmDemoModeService {

	private static final int QUALITY_POINT_COUNT = 36;
	private static final String TEST_MAIL_ALERT_TITLE = "PDM Demo Mail Test WARNING alert";
	private static final Map<String, Scenario> SCENARIOS = Map.of(
		"CAM-F-01", new Scenario(
			100.0,
			"NORMAL",
			0.940,
			0.965,
			0.035,
			0.960,
			0.040,
			"Recognition quality is stable",
			"No immediate maintenance required",
			null,
			List.of(
				new ModelScenario("RULE_BASED", 100.0, "NORMAL", "NORMAL_RULE",
					"임계 지표가 모두 정상 범위입니다.", "정기 점검 주기를 유지하세요."),
				new ModelScenario("ISOLATION_FOREST", 100.0, "NORMAL", "NORMAL_IF",
					"지표 조합이 평소 정상 패턴과 일치합니다.", "정기 점검 주기를 유지하세요."),
				new ModelScenario("LSTM_AE", 100.0, "NORMAL", "NORMAL_LSTM",
					"최근 시계열 흐름이 안정적입니다.", "정기 점검 주기를 유지하세요.")
			)
		),
		"CAM-R-01", new Scenario(
			58.1,
			"CRITICAL",
			0.720,
			0.780,
			0.220,
			0.750,
			0.250,
			"Rear camera OCR sudden drop detected",
			"Check recent camera frame delay and lens contamination",
			"Rear Camera Spike CRITICAL alert",
			List.of(
				new ModelScenario("RULE_BASED", 10.4, "CRITICAL", "REAR_SPIKE_RULE",
					"OCR 신뢰도·성공률이 임계값 아래로 급락했습니다.", "렌즈 오염과 카메라 프레임 지연을 즉시 점검하세요."),
				new ModelScenario("ISOLATION_FOREST", 79.9, "WARNING", "REAR_SPIKE_IF",
					"급락 구간이 평소 분포에서 벗어난 이상치로 감지됩니다.", "해당 시간대 영상 품질을 함께 확인하세요."),
				new ModelScenario("LSTM_AE", 100.0, "NORMAL", "REAR_SPIKE_LSTM",
					"단기 급락이라 지속적 열화 추세는 아직 없습니다.", "추세 감시만 유지하세요.")
			)
		),
		"CAM-F-02", new Scenario(
			93.8,
			"WARNING",
			0.885,
			0.925,
			0.075,
			0.897,
			0.103,
			"Short repeated quality drop detected",
			"Inspect mounting vibration and focus state",
			"Front Camera Pattern WARNING alert",
			List.of(
				new ModelScenario("RULE_BASED", 99.5, "NORMAL", "FRONT_PATTERN_RULE",
					"개별 지표는 모두 임계값 안에 있습니다.", "정기 점검 주기를 유지하세요."),
				new ModelScenario("ISOLATION_FOREST", 79.9, "WARNING", "FRONT_PATTERN_IF",
					"임계는 넘지 않았지만 지표 조합이 평소 패턴에서 벗어났습니다.", "거치대 진동과 초점 상태를 점검하세요."),
				new ModelScenario("LSTM_AE", 100.0, "NORMAL", "FRONT_PATTERN_LSTM",
					"지속적 추세 저하 패턴은 관찰되지 않습니다.", "정기 점검 주기를 유지하세요.")
			)
		),
		"CAM-R-02", new Scenario(
			92.4,
			"WARNING",
			0.873,
			0.919,
			0.081,
			0.921,
			0.079,
			"Long-term degradation trend detected",
			"Schedule camera inspection and lens replacement check",
			"Rear Camera Degrade WARNING alert",
			List.of(
				new ModelScenario("RULE_BASED", 96.0, "NORMAL", "REAR_DEGRADE_RULE",
					"각 지표가 임계값을 넘지 않았습니다.", "정기 점검 주기를 유지하세요."),
				new ModelScenario("ISOLATION_FOREST", 100.0, "NORMAL", "REAR_DEGRADE_IF",
					"단일 구간 이상치로 보기는 어렵습니다.", "정기 점검 주기를 유지하세요."),
				new ModelScenario("LSTM_AE", 79.9, "WARNING", "REAR_DEGRADE_LSTM",
					"여러 구간에 걸친 완만한 품질 저하 추세가 학습되었습니다.", "카메라 점검 일정 등록 및 렌즈 교체를 검토하세요.")
			)
		),
		"CAM-F-03", new Scenario(
			81.1,
			"WARNING",
			0.903,
			0.923,
			0.077,
			0.914,
			0.086,
			"Event count is too low for reliable sequence analysis",
			"Check camera capture pipeline and event forwarding",
			"Front Camera Low Count WARNING alert",
			List.of(
				new ModelScenario("RULE_BASED", 67.9, "WARNING", "FRONT_LOW_COUNT_RULE",
					"유효 이벤트 수가 기준 미만이라 판단 신뢰도가 낮습니다.", "카메라 캡처·이벤트 전달 경로를 확인하세요."),
				new ModelScenario("ISOLATION_FOREST", 79.9, "WARNING", "FRONT_LOW_COUNT_IF",
					"저트래픽 구간의 지표 조합이 평소와 다릅니다.", "통행량이 적은 시간대인지 함께 확인하세요."),
				new ModelScenario("LSTM_AE", 100.0, "NORMAL", "FRONT_LOW_COUNT_LSTM",
					"데이터가 부족해 시계열 이상은 확정되지 않았습니다.", "추가 구간 확보 후 재분석하세요.")
			)
		)
	);

	private final CameraDeviceRepository cameraDeviceRepository;
	private final CameraLaneMappingRepository cameraLaneMappingRepository;
	private final PdmAnalysisResultRepository pdmAnalysisResultRepository;
	private final MaintenanceAlertRepository maintenanceAlertRepository;
	private final PdmAlertMailService pdmAlertMailService;

	private volatile boolean enabled;

	public boolean isEnabled() {
		return enabled;
	}

	public PdmDemoModeResponse getMode() {
		return new PdmDemoModeResponse(enabled);
	}

	public PdmDemoModeResponse updateMode(PdmDemoModeRequest request) {
		if (request == null || request.enabled() == null) {
			throw new IllegalArgumentException("enabled is required");
		}
		enabled = request.enabled();
		return getMode();
	}

	public List<PdmCameraResponse> getCameras() {
		return activeCameras().stream()
			.map(camera -> {
				Scenario scenario = scenario(camera);
				List<CameraLaneMapping> mappings = laneMappings(camera);
				return new PdmCameraResponse(
					camera.getCameraId(),
					camera.getCameraCode(),
					camera.getCameraName(),
					camera.getDirection(),
					laneIds(mappings),
					laneNames(mappings),
					scenario.healthScore(),
					scenario.riskLevel()
				);
			})
			.toList();
	}

	public PdmCameraDetailResponse getCameraDetail(Long cameraId) {
		CameraDevice camera = findCamera(cameraId);
		Scenario scenario = scenario(camera);
		List<CameraLaneMapping> mappings = laneMappings(camera);
		Integer laneId = primaryLaneId(mappings);
		List<PdmModelResultResponse> modelResults = modelResults(camera, scenario, laneId);
		ModelScenario representative = representativeModel(scenario);

		return new PdmCameraDetailResponse(
			camera.getCameraId(),
			camera.getCameraCode(),
			camera.getCameraName(),
			camera.getDirection(),
			laneIds(mappings),
			laneNames(mappings),
			scenario.healthScore(),
			scenario.riskLevel(),
			representative.modelType(),
			"demo-fixed-v1",
			scenario.avgOcrConfidence(),
			scenario.successRate(),
			scenario.missingRate(),
			scenario.matchRate(),
			scenario.mismatchRate(),
			scenario.reasonText(),
			scenario.recommendedAction(),
			integrated(scenario),
			modelResults
		);
	}

	public PdmCameraAnalysisResultsResponse getAnalysisResults(Long cameraId, Integer laneId) {
		CameraDevice camera = findCamera(cameraId);
		Scenario scenario = scenario(camera);
		Integer effectiveLaneId = laneId != null ? laneId : primaryLaneId(laneMappings(camera));
		LocalDateTime end = bucketEnd(LocalDateTime.now());
		return new PdmCameraAnalysisResultsResponse(
			camera.getCameraId(),
			camera.getCameraCode(),
			camera.getCameraName(),
			effectiveLaneId,
			end.minusMinutes(60),
			end,
			integrated(scenario),
			modelResults(camera, scenario, effectiveLaneId)
		);
	}

	public List<PdmQualityMetricResponse> getQualityMetrics(
		Long cameraId,
		Integer laneId,
		LocalDateTime to
	) {
		List<CameraDevice> cameras = cameraId != null ? List.of(findCamera(cameraId)) : activeCameras();
		List<PdmQualityMetricResponse> responses = new ArrayList<>();
		for (CameraDevice camera : cameras) {
			Scenario scenario = scenario(camera);
			Integer effectiveLaneId = laneId != null ? laneId : primaryLaneId(laneMappings(camera));
			responses.addAll(qualityMetrics(camera, scenario, effectiveLaneId, to));
		}
		return responses;
	}

	public List<PdmAlertResponse> getAlerts(String status) {
		String normalized = StringUtils.hasText(status) ? status.trim().toUpperCase() : null;
		if (normalized != null && !"CREATED".equals(normalized)) {
			return List.of();
		}

		LocalDateTime now = LocalDateTime.now().withNano(0);
		return activeCameras().stream()
			.map(camera -> alertResponse(camera, scenario(camera), now))
			.flatMap(Optional::stream)
			.sorted(Comparator.comparing(PdmAlertResponse::createdAt).reversed())
			.toList();
	}

	public Optional<PdmAlertResponse> findAlert(Long alertId) {
		return getAlerts("CREATED").stream()
			.filter(alert -> Objects.equals(alert.alertId(), alertId))
			.findFirst();
	}

	public List<PdmCompareResultResponse> getCompareResults(
		Integer laneId,
		Boolean matchedFilter,
		LocalDateTime from,
		LocalDateTime to,
		int limit
	) {
		return compareResults(LocalDateTime.now().withNano(0)).stream()
			.filter(result -> laneId == null || Objects.equals(result.laneId(), laneId))
			.filter(result -> matchedFilter == null || Objects.equals(result.isMatched(), matchedFilter))
			.filter(result -> from == null || !result.comparedAt().isBefore(from))
			.filter(result -> to == null || !result.comparedAt().isAfter(to))
			.limit(limit)
			.toList();
	}

	@Transactional
	public PdmDemoMailAlertResponse sendDemoMailAlert() {
		// 데모 한정: 반복 발송 허용 (멱등 가드 제거 — 누를 때마다 새 알림 생성 + 메일 발송)
		CameraDevice camera = cameraDeviceRepository.findByCameraCode("CAM-F-02")
			.orElseGet(() -> activeCameras().stream()
				.findFirst()
				.orElseThrow(() -> new IllegalStateException("active camera not found")));
		PdmAnalysisResult analysis = pdmAnalysisResultRepository
			.findTopByCamera_CameraIdOrderByAnalyzedAtDesc(camera.getCameraId())
			.orElse(null);
		if (analysis == null) {
			return new PdmDemoMailAlertResponse(
				null,
				false,
				"분석 결과가 없어 메일을 보낼 수 없습니다. FastAPI 분석을 1회 실행한 뒤 다시 시도하세요."
			);
		}

		MaintenanceAlert alert = maintenanceAlertRepository.save(MaintenanceAlert.builder()
			.analysis(analysis)
			.camera(camera)
			.laneId(analysis.getLaneId())
			.riskLevel("WARNING")
			.alertTitle(TEST_MAIL_ALERT_TITLE)
			.alertMessage("PDM demo mail alert")
			.reasonText("Short repeated quality drop detected")
			.recommendedAction("Inspect mounting vibration and focus state")
			.status("CREATED")
			.build());

		pdmAlertMailService.sendAlert(alert);
		return new PdmDemoMailAlertResponse(
			alert.getAlertId(),
			true,
			"메일 테스트 알림을 생성했습니다."
		);
	}

	private List<CameraDevice> activeCameras() {
		return cameraDeviceRepository.findByIsActiveTrueOrderByCameraIdAsc();
	}

	private CameraDevice findCamera(Long cameraId) {
		if (cameraId == null) {
			throw new IllegalArgumentException("cameraId is required");
		}
		return cameraDeviceRepository.findById(cameraId)
			.orElseThrow(() -> new IllegalArgumentException("camera not found"));
	}

	private List<CameraLaneMapping> laneMappings(CameraDevice camera) {
		return cameraLaneMappingRepository.findByCamera_CameraIdOrderByLaneIdAsc(camera.getCameraId());
	}

	private Scenario scenario(CameraDevice camera) {
		return SCENARIOS.getOrDefault(camera.getCameraCode(), SCENARIOS.get("CAM-F-01"));
	}

	private PdmIntegratedResultResponse integrated(Scenario scenario) {
		return new PdmIntegratedResultResponse(
			scenario.healthScore(),
			scenario.riskLevel(),
			scenario.reasonText(),
			scenario.recommendedAction()
		);
	}

	private ModelScenario representativeModel(Scenario scenario) {
		return scenario.models().stream()
			.max(Comparator
				.comparingInt((ModelScenario model) -> riskRank(model.riskLevel()))
				.thenComparing(model -> 100.0 - model.healthScore()))
			.orElse(scenario.models().get(0));
	}

	private List<PdmModelResultResponse> modelResults(
		CameraDevice camera,
		Scenario scenario,
		Integer laneId
	) {
		LocalDateTime end = bucketEnd(LocalDateTime.now());
		LocalDateTime start = end.minusMinutes(60);
		LocalDateTime analyzedAt = end.plusSeconds(5);
		List<PdmModelResultResponse> responses = new ArrayList<>();
		for (int i = 0; i < scenario.models().size(); i++) {
			ModelScenario model = scenario.models().get(i);
			responses.add(new PdmModelResultResponse(
				demoAnalysisId(camera.getCameraId(), i),
				camera.getCameraId(),
				laneId,
				start,
				end,
				model.healthScore(),
				model.riskLevel(),
				model.modelType(),
				"demo-fixed-v1",
				model.reasonCode(),
				model.reasonText(),
				model.recommendedAction(),
				model.reasonText(),
				analyzedAt
			));
		}
		return responses;
	}

	private List<PdmQualityMetricResponse> qualityMetrics(
		CameraDevice camera,
		Scenario scenario,
		Integer laneId,
		LocalDateTime to
	) {
		LocalDateTime end = bucketEnd(to != null ? to : LocalDateTime.now());
		List<PdmQualityMetricResponse> responses = new ArrayList<>();
		for (int i = 0; i < QUALITY_POINT_COUNT; i++) {
			LocalDateTime bucketStart = end.minusMinutes((long)(QUALITY_POINT_COUNT - i) * 10);
			MetricSample sample = metricSample(camera.getCameraCode(), scenario, i);
			responses.add(new PdmQualityMetricResponse(
				camera.getCameraId() * 10000 + i,
				camera.getCameraId(),
				laneId,
				bucketStart,
				bucketStart.plusMinutes(10),
				sample.avgOcrConfidence(),
				sample.successRate(),
				sample.missingRate(),
				sample.matchRate(),
				sample.mismatchRate(),
				sample.eventCount()
			));
		}
		return responses;
	}

	private MetricSample metricSample(String cameraCode, Scenario scenario, int index) {
		double wave = Math.sin(index * 0.72 + Math.abs(cameraCode.hashCode() % 13));
		double smallWave = Math.sin(index * 1.83 + Math.abs(cameraCode.hashCode() % 7));

		if ("CAM-F-01".equals(cameraCode)) {
			double ocr = 0.925 + wave * 0.018 + smallWave * 0.004;
			double success = 0.960 + Math.sin(index * 0.91) * 0.010;
			double match = 0.956 + Math.cos(index * 0.77) * 0.010;
			return metric(ocr, success, 1.0 - success, match, 38 + (index % 5));
		}
		if ("CAM-R-01".equals(cameraCode)) {
			double ocr;
			double success;
			double match;
			if (index < 12) {
				ocr = 0.900 + wave * 0.012;
				success = 0.930 + smallWave * 0.010;
				match = 0.925 + Math.cos(index * 0.63) * 0.012;
			} else if (index <= 13) {
				double severity = index == 12 ? 1.0 : 0.82;
				ocr = 0.900 - 0.390 * severity + wave * 0.004;
				success = 0.930 - 0.350 * severity + smallWave * 0.004;
				match = 0.925 - 0.320 * severity + Math.cos(index * 0.63) * 0.004;
			} else {
				double recovery = Math.min(1.0, (index - 14) / 5.0);
				double aftershock = pulse(index, 24, 24, 26, 0.030) + pulse(index, 31, 31, 32, 0.024);
				ocr = 0.640 + 0.235 * recovery + wave * 0.012 - aftershock;
				success = 0.690 + 0.210 * recovery + smallWave * 0.008 - aftershock * 0.75;
				match = 0.700 + 0.190 * recovery + Math.cos(index * 0.62) * 0.009 - aftershock * 0.80;
			}
			return metric(ocr, success, 1.0 - success, match, 17 + (index % 4));
		}
		if ("CAM-F-02".equals(cameraCode)) {
			double ocr = 0.890 + wave * 0.014;
			double success = 0.925 + smallWave * 0.011;
			double match = 0.910 + Math.cos(index * 0.70) * 0.012;
			double drop = pulse(index, 7, 9, 10, 0.105)
				+ pulse(index, 17, 18, 20, 0.075)
				+ pulse(index, 27, 29, 31, 0.090);
			ocr -= drop;
			success -= drop * 0.78;
			match -= drop * 0.84;
			return metric(ocr, success, 1.0 - success, match, 29 + (index % 5));
		}
		if ("CAM-R-02".equals(cameraCode)) {
			double drift = index / (double)(QUALITY_POINT_COUNT - 1);
			double ocr = 0.935 - drift * 0.170 + wave * 0.009;
			double success = 0.950 - drift * 0.145 + smallWave * 0.007;
			double match = 0.940 - drift * 0.135 + Math.cos(index * 0.55) * 0.008;
			return metric(ocr, success, 1.0 - success, match, 23 + (index % 4));
		}
		if ("CAM-F-03".equals(cameraCode)) {
			double ocr = 0.900 + wave * 0.015;
			double success = 0.925 + smallWave * 0.010;
			double match = 0.912 + Math.cos(index * 0.75) * 0.011;
			if (index >= 6 && index <= 10) {
				ocr -= 0.040;
				success -= 0.035;
				match -= 0.028;
			}
			return metric(ocr, success, 1.0 - success, match, 6 + (index % 3));
		}

		return metric(
			scenario.avgOcrConfidence() + wave * 0.010,
			scenario.successRate() + smallWave * 0.010,
			scenario.missingRate(),
			scenario.matchRate() + Math.cos(index * 0.7) * 0.010,
			20 + (index % 5)
		);
	}

	private MetricSample metric(
		double avgOcrConfidence,
		double successRate,
		double missingRate,
		double matchRate,
		int eventCount
	) {
		double success = clampRate(successRate);
		double match = clampRate(matchRate);
		double missing = clampRate(Math.max(missingRate, 1.0 - success));
		return new MetricSample(
			roundRate(avgOcrConfidence),
			roundRate(success),
			roundRate(missing),
			roundRate(match),
			roundRate(1.0 - match),
			Math.max(0, eventCount)
		);
	}

	private double pulse(int index, int start, int peak, int end, double depth) {
		if (index < start || index > end) {
			return 0.0;
		}
		if (index <= peak) {
			return depth * (index - start + 1) / (peak - start + 1);
		}
		return depth * (end - index + 1) / (end - peak + 1);
	}

	private Optional<PdmAlertResponse> alertResponse(
		CameraDevice camera,
		Scenario scenario,
		LocalDateTime now
	) {
		if (!StringUtils.hasText(scenario.alertTitle())) {
			return Optional.empty();
		}
		return Optional.of(new PdmAlertResponse(
			900000L + camera.getCameraId(),
			910000L + camera.getCameraId(),
			camera.getCameraId(),
			camera.getCameraCode(),
			primaryLaneId(laneMappings(camera)),
			scenario.healthScore(),
			scenario.riskLevel(),
			scenario.alertTitle(),
			scenario.reasonText(),
			scenario.reasonText(),
			scenario.recommendedAction(),
			"CREATED",
			now.minusMinutes(5 + camera.getCameraId()),
			now.minusMinutes(2)
		));
	}

	private List<PdmCompareResultResponse> compareResults(LocalDateTime now) {
		return List.of(
			compare(1L, "GRP-DEMO-001", 2, "34나7890", "34나7890", true, null, 0.018, now.minusSeconds(18)),
			compare(2L, "GRP-DEMO-002", 1, "12가3456", "12가3456", true, null, 0.021, now.minusSeconds(31)),
			compare(3L, "GRP-DEMO-003", 4, "78마9012", "78마9012", true, null, 0.016, now.minusSeconds(47)),
			compare(4L, "GRP-DEMO-004", 3, "56다1234", "56라1234", false, "PLATE_MISMATCH", 0.118, now.minusSeconds(66)),
			compare(5L, "GRP-DEMO-005", 2, "90바3456", null, false, "REAR_MISSING", 0.245, now.minusSeconds(84)),
			compare(6L, "GRP-DEMO-006", 1, "11사2222", "11사2222", true, null, 0.009, now.minusSeconds(105)),
			compare(7L, "GRP-DEMO-007", 4, "33자4444", "33차4444", false, "PLATE_MISMATCH", 0.132, now.minusSeconds(129)),
			compare(8L, "GRP-DEMO-008", 3, "22아3333", "22아3333", true, null, 0.028, now.minusSeconds(151)),
			compare(9L, "GRP-DEMO-009", 1, "44카5555", "44카5555", true, null, 0.014, now.minusSeconds(178)),
			compare(10L, "GRP-DEMO-010", 2, "55타6666", "55타6666", true, null, 0.019, now.minusSeconds(209)),
			compare(11L, "GRP-DEMO-011", 4, "77하8888", "77하8888", true, null, 0.011, now.minusSeconds(236)),
			compare(12L, "GRP-DEMO-012", 3, "66파7777", "66파7777", true, null, 0.023, now.minusSeconds(268))
		);
	}

	private PdmCompareResultResponse compare(
		Long id,
		String groupKey,
		Integer laneId,
		String frontPlate,
		String rearPlate,
		Boolean matched,
		String mismatchType,
		Double confidenceGap,
		LocalDateTime comparedAt
	) {
		return new PdmCompareResultResponse(
			900000L + id,
			groupKey,
			laneId,
			laneId + "차로",
			"CAM-F-01",
			"CAM-R-01",
			frontPlate,
			rearPlate,
			matched,
			mismatchType,
			confidenceGap,
			comparedAt
		);
	}

	private LocalDateTime bucketEnd(LocalDateTime value) {
		LocalDateTime time = value.withSecond(0).withNano(0);
		return time.withMinute((time.getMinute() / 10) * 10);
	}

	private Long demoAnalysisId(Long cameraId, int modelIndex) {
		return 910000L + cameraId * 10 + modelIndex;
	}

	private List<Integer> laneIds(List<CameraLaneMapping> mappings) {
		return mappings.stream()
			.map(CameraLaneMapping::getLaneId)
			.toList();
	}

	private List<String> laneNames(List<CameraLaneMapping> mappings) {
		return mappings.stream()
			.map(mapping -> mapping.getLaneId() + "차로")
			.toList();
	}

	private Integer primaryLaneId(List<CameraLaneMapping> mappings) {
		return mappings.stream()
			.map(CameraLaneMapping::getLaneId)
			.findFirst()
			.orElse(null);
	}

	private double clampRate(double value) {
		return Math.min(1.0, Math.max(0.0, value));
	}

	private Double roundRate(double value) {
		return Math.round(clampRate(value) * 1000.0) / 1000.0;
	}

	private int riskRank(String level) {
		return switch (level) {
			case "CRITICAL", "HIGH" -> 3;
			case "WARNING" -> 2;
			case "NORMAL" -> 1;
			default -> 0;
		};
	}

	private record Scenario(
		Double healthScore,
		String riskLevel,
		Double avgOcrConfidence,
		Double successRate,
		Double missingRate,
		Double matchRate,
		Double mismatchRate,
		String reasonText,
		String recommendedAction,
		String alertTitle,
		List<ModelScenario> models
	) {
	}

	private record ModelScenario(
		String modelType,
		Double healthScore,
		String riskLevel,
		String reasonCode,
		String reasonText,
		String recommendedAction
	) {
	}

	private record MetricSample(
		Double avgOcrConfidence,
		Double successRate,
		Double missingRate,
		Double matchRate,
		Double mismatchRate,
		Integer eventCount
	) {
	}
}
