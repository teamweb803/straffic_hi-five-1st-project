package com.hifive.iot.entity;

import java.time.LocalDateTime;

public record BoardPost(
	long postId,
	String title,
	String content,
	String writerName,
	String plateNumber,
	int vehicleCount,
	double recognitionConfidence,
	LocalDateTime createdAt
) {
}
