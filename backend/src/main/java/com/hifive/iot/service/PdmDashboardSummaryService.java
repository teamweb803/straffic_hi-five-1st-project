package com.hifive.iot.service;

import java.util.List;

import com.hifive.iot.dto.PdmCameraResponse;
import com.hifive.iot.dto.PdmDashboardSummaryResponse;

import lombok.RequiredArgsConstructor;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PdmDashboardSummaryService {

	private final PdmCameraService pdmCameraService;

	public PdmDashboardSummaryResponse getSummary() {
		List<PdmCameraResponse> cameras = pdmCameraService.getCameras();
		long normalCount = 0;
		long warningCount = 0;
		long criticalCount = 0;
		double healthScoreSum = 0.0;
		long healthScoreCount = 0;

		for (PdmCameraResponse camera : cameras) {
			if ("NORMAL".equals(camera.riskLevel())) {
				normalCount++;
			} else if ("WARNING".equals(camera.riskLevel())) {
				warningCount++;
			} else if ("CRITICAL".equals(camera.riskLevel()) || "HIGH".equals(camera.riskLevel())) {
				criticalCount++;
			}

			if (camera.healthScore() != null) {
				healthScoreSum += camera.healthScore();
				healthScoreCount++;
			}
		}

		return new PdmDashboardSummaryResponse(
			cameras.size(),
			normalCount,
			warningCount,
			criticalCount,
			average(healthScoreSum, healthScoreCount)
		);
	}

	private Double average(double sum, long count) {
		if (count == 0) {
			return 0.0;
		}
		return Math.round((sum / count) * 10.0) / 10.0;
	}
}
