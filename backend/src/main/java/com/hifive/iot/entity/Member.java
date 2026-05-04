package com.hifive.iot.entity;

public record Member(
	String memberId,
	String password,
	String memberName,
	String plateNumber
) {
}
