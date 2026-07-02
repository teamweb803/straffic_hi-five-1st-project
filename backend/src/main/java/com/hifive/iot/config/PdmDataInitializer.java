package com.hifive.iot.config;

import java.util.List;

import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.CameraLaneMapping;
import com.hifive.iot.repository.CameraDeviceRepository;
import com.hifive.iot.repository.CameraLaneMappingRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
public class PdmDataInitializer implements ApplicationRunner {

	private final CameraDeviceRepository cameraDeviceRepository;
	private final CameraLaneMappingRepository cameraLaneMappingRepository;

	@Override
	@Transactional
	public void run(ApplicationArguments args) {
		for (CameraSeed seed : cameraSeeds()) {
			CameraDevice camera = findOrCreateCamera(seed.code(), seed.name(), seed.direction());
			createLaneMapping(camera, seed.laneId());
		}
	}

	private List<CameraSeed> cameraSeeds() {
		return List.of(
			new CameraSeed("CAM-F-01", "Front Camera Normal", "FRONT", 1),
			new CameraSeed("CAM-R-01", "Rear Camera Spike", "REAR", 1),
			new CameraSeed("CAM-F-02", "Front Camera Pattern", "FRONT", 3),
			new CameraSeed("CAM-R-02", "Rear Camera Degrade", "REAR", 3),
			new CameraSeed("CAM-F-03", "Front Camera Low Count", "FRONT", 5)
		);
	}

	private CameraDevice findOrCreateCamera(String cameraCode, String cameraName, String direction) {
		return cameraDeviceRepository.findByCameraCode(cameraCode)
			.orElseGet(() -> cameraDeviceRepository.save(
				CameraDevice.builder()
					.cameraCode(cameraCode)
					.cameraName(cameraName)
					.direction(direction)
					.sourceDeviceId(null)
					.isActive(true)
					.build()
			));
	}

	private void createLaneMapping(CameraDevice camera, Integer laneId) {
		if (!cameraLaneMappingRepository.existsByCameraAndLaneId(camera, laneId)) {
			cameraLaneMappingRepository.save(
				CameraLaneMapping.builder()
					.camera(camera)
					.laneId(laneId)
					.build()
			);
		}
	}

	private record CameraSeed(String code, String name, String direction, Integer laneId) {
	}
}
