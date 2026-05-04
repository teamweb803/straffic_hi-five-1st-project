package com.hifive.iot.service;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;

import com.hifive.iot.dto.BoardPostRequest;
import com.hifive.iot.entity.BoardPost;

import org.springframework.stereotype.Service;

@Service
public class BoardService {

	private final AtomicLong postSequence = new AtomicLong(3);
	private final List<BoardPost> boardPosts = new CopyOnWriteArrayList<>(List.of(
		new BoardPost(1, "\ud558\uc774\ud328\uc2a4 \ucc28\uc120 \uc778\uc2dd \uc810\uac80", "\u0031\ucc28\uc120 \ubc88\ud638\ud310 \uc778\uc2dd\ub960\uc774 \uc548\uc815\uc801\uc73c\ub85c \uc218\uc9d1\ub418\uace0 \uc788\uc2b5\ub2c8\ub2e4.", "\uc6b4\uc601\uc790", "\u0031\u0032\uac00\u0033\u0034\u0035\u0036", 128, 98.4, LocalDateTime.now().minusHours(3)),
		new BoardPost(2, "\uad50\ud1b5\ub7c9 \uc218\uc9d1 \ud14c\uc2a4\ud2b8", "\ud1f4\uadfc \uc2dc\uac04\ub300 \ucc28\ub7c9 \uc218 \uc9d1\uacc4 \ud14c\uc2a4\ud2b8 \uac8c\uc2dc\uae00\uc785\ub2c8\ub2e4.", "\uc6b4\uc601\uc790", "\u0033\u0034\ub098\u0035\u0036\u0037\u0038", 243, 96.7, LocalDateTime.now().minusHours(1))
	));

	public List<BoardPost> findAll() {
		return boardPosts.stream()
			.sorted(Comparator.comparing(BoardPost::postId).reversed())
			.toList();
	}

	public void create(BoardPostRequest boardPostRequest, String writerName) {
		boardPosts.add(new BoardPost(
			postSequence.getAndIncrement(),
			boardPostRequest.title(),
			boardPostRequest.content(),
			writerName,
			boardPostRequest.plateNumber(),
			boardPostRequest.vehicleCount(),
			boardPostRequest.recognitionConfidence(),
			LocalDateTime.now()
		));
	}
}
