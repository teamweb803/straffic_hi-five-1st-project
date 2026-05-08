package com.hifive.iot.dto;

public record BoardPostRequest(
	String title,
	String content,
	String plateNumber,
	int vehicleCount,
	double recognitionConfidence
) {
}
