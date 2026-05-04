package com.hifive.iot.dto;

public record LoginRequest(
	String memberId,
	String password
) {
}
