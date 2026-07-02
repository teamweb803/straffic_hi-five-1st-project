package com.hifive.iot.dto;

public record PdmDemoMailAlertResponse(
	Long alertId,
	boolean sent,
	String message
) {
}
