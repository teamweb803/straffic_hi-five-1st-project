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
		CameraDevice frontCamera = findOrCreateCamera("CAM-F-01", "전방 카메라", "FRONT");
		CameraDevice rearCamera = findOrCreateCamera("CAM-R-01", "후방 카메라", "REAR");

		createLaneMappings(frontCamera);
		createLaneMappings(rearCamera);
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

	private void createLaneMappings(CameraDevice camera) {
		for (Integer laneId : List.of(1, 2)) {
			if (!cameraLaneMappingRepository.existsByCameraAndLaneId(camera, laneId)) {
				cameraLaneMappingRepository.save(
					CameraLaneMapping.builder()
						.camera(camera)
						.laneId(laneId)
						.build()
				);
			}
		}
	}
}
