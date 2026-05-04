package com.hifive.iot.dto;

import com.hifive.iot.entity.Member;

public record MemberResponse(
	String memberId,
	String memberName,
	String plateNumber
) {

	public static MemberResponse from(Member member) {
		return new MemberResponse(member.memberId(), member.memberName(), member.plateNumber());
	}
}
