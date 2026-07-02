package com.hifive.iot.controller;

import com.hifive.iot.dto.PdmDemoMailAlertResponse;
import com.hifive.iot.dto.PdmDemoModeRequest;
import com.hifive.iot.dto.PdmDemoModeResponse;
import com.hifive.iot.service.PdmDemoModeService;

import lombok.RequiredArgsConstructor;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/pdm")
public class PdmDemoController {

	private final PdmDemoModeService pdmDemoModeService;

	@GetMapping("/demo-mode")
	public ResponseEntity<PdmDemoModeResponse> getDemoMode() {
		return ResponseEntity.ok(pdmDemoModeService.getMode());
	}

	@PatchMapping("/demo-mode")
	public ResponseEntity<PdmDemoModeResponse> updateDemoMode(
		@RequestBody PdmDemoModeRequest request
	) {
		return ResponseEntity.ok(pdmDemoModeService.updateMode(request));
	}

	@PostMapping("/demo-mail-alert")
	public ResponseEntity<PdmDemoMailAlertResponse> sendDemoMailAlert() {
		return ResponseEntity.ok(pdmDemoModeService.sendDemoMailAlert());
	}
}
