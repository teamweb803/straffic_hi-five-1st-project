package com.hifive.iot.dto;

import java.util.List;

public record PdmAnalysisResultBatchRequest(
	List<PdmAnalysisResultRequest> results
) {
}
