package com.hifive.iot.repository;

import com.hifive.iot.entity.PassageEventRecord;

import org.springframework.data.jpa.repository.JpaRepository;

public interface PassageEventRepository extends JpaRepository<PassageEventRecord, Long> {

	boolean existsByEventId(String eventId);

	java.util.Optional<PassageEventRecord> findByEventId(String eventId);

	java.util.List<PassageEventRecord> findTop50ByOrderByEventTimeDesc();
}
