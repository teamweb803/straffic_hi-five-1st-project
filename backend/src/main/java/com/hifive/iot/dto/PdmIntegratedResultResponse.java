package com.hifive.iot.dto;

public record PdmIntegratedResultResponse(
	Double healthScore,
	String riskLevel,
	String reasonText,
	String recommendedAction
) {
}
