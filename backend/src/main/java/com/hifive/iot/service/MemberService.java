package com.hifive.iot.service;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import com.hifive.iot.dto.SignUpRequest;
import com.hifive.iot.entity.Member;

import org.springframework.stereotype.Service;

@Service
public class MemberService {

	private final Map<String, Member> members = new ConcurrentHashMap<>();

	public boolean signUp(SignUpRequest signUpRequest) {
		Member member = new Member(
			signUpRequest.memberId(),
			signUpRequest.password(),
			signUpRequest.memberName(),
			signUpRequest.plateNumber()
		);
		return members.putIfAbsent(member.memberId(), member) == null;
	}

	public Optional<Member> login(String memberId, String password) {
		return Optional.ofNullable(members.get(memberId))
			.filter(member -> member.password().equals(password));
	}
}
