package com.hifive.iot.dto;

public record SignUpRequest(
	String memberId,
	String password,
	String memberName,
	String plateNumber
) {
}
