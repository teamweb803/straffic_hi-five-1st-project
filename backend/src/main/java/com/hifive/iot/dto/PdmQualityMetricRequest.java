package com.hifive.iot.dto;

import java.time.LocalDateTime;

public record PdmQualityMetricRequest(
	Long cameraId,
	Integer laneId,
	LocalDateTime bucketStart,
	LocalDateTime bucketEnd,
	Double avgOcrConfidence,
	Double successRate,
	Double missingRate,
	Double matchRate,
	Double mismatchRate,
	Integer eventCount
) {
}
