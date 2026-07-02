package com.hifive.iot.dto;

import java.time.LocalDateTime;
import java.util.List;

public record PdmCameraAnalysisResultsResponse(
	Long cameraId,
	String cameraCode,
	String cameraName,
	Integer laneId,
	LocalDateTime analysisStart,
	LocalDateTime analysisEnd,
	PdmIntegratedResultResponse integratedResult,
	List<PdmModelResultResponse> modelResults
) {
}
