package com.hifive.iot.controller;

import java.util.List;

import com.hifive.iot.dto.BoardPostRequest;
import com.hifive.iot.entity.BoardPost;
import com.hifive.iot.entity.Member;
import com.hifive.iot.service.BoardService;

import jakarta.servlet.http.HttpSession;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/board")
public class BoardController {

	private static final String LOGIN_MEMBER = "loginMember";

	private final BoardService boardService;

	public BoardController(BoardService boardService) {
		this.boardService = boardService;
	}

	@GetMapping
	public List<BoardPost> findAll() {
		return boardService.findAll();
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public void create(@RequestBody BoardPostRequest boardPostRequest, HttpSession session) {
		Member loginMember = (Member) session.getAttribute(LOGIN_MEMBER);
		String writerName = loginMember == null ? "\ubc29\ubb38\uc790" : loginMember.memberName();
		boardService.create(boardPostRequest, writerName);
	}
}
