package com.hifive.iot.controller;

import java.lang.management.ManagementFactory;
import java.util.Map;

import com.hifive.iot.repository.EdgeStatusLatestRepository;
import com.hifive.iot.repository.IngressStatusLatestRepository;
import com.hifive.iot.repository.PassageEventRepository;
import com.hifive.iot.repository.SystemAlertRepository;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/system")
public class AdminSystemController {
	private final EdgeStatusLatestRepository edgeRepository;
	private final IngressStatusLatestRepository ingressRepository;
	private final PassageEventRepository passageEventRepository;
	private final SystemAlertRepository alertRepository;

	public AdminSystemController(EdgeStatusLatestRepository edgeRepository, IngressStatusLatestRepository ingressRepository,
		PassageEventRepository passageEventRepository, SystemAlertRepository alertRepository) {
		this.edgeRepository = edgeRepository;
		this.ingressRepository = ingressRepository;
		this.passageEventRepository = passageEventRepository;
		this.alertRepository = alertRepository;
	}

	@GetMapping("/summary")
	public Map<String, Object> summary() {
		return Map.of(
			"totalEdges", edgeRepository.count(),
			"normalEdges", edgeRepository.countByAliveTrue(),
			"staleEdges", edgeRepository.countByStaleTrue(),
			"sourceRunningEdges", edgeRepository.countBySourceRunningTrue(),
			"ingressStatus", ingressRepository.findAll(),
			"backendStatus", "OK",
			"backendUptimeMs", ManagementFactory.getRuntimeMXBean().getUptime(),
			"pipelineStatus", "Jetson -> Ingress -> Spring -> DB",
			"passageEventCount", passageEventRepository.count(),
			"recentAlerts", alertRepository.findTop50ByOrderByCreatedAtDesc()
		);
	}
}
