package com.hifive.iot.dto;

import java.time.LocalDateTime;
import java.util.List;

public record PdmAnalysisResultBatchResponse(
	Long cameraId,
	Integer laneId,
	LocalDateTime analysisStart,
	LocalDateTime analysisEnd,
	PdmIntegratedResultResponse integratedResult,
	List<PdmModelResultResponse> modelResults,
	PdmAlertResponse alert
) {
}
