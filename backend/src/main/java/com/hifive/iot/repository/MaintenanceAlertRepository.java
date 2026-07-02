package com.hifive.iot.repository;

import java.util.List;
import java.util.Optional;

import com.hifive.iot.entity.MaintenanceAlert;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface MaintenanceAlertRepository extends JpaRepository<MaintenanceAlert, Long> {

	List<MaintenanceAlert> findTop50ByOrderByCreatedAtDesc();

	List<MaintenanceAlert> findByStatusOrderByCreatedAtDesc(String status);

	List<MaintenanceAlert> findTop50ByStatusOrderByCreatedAtDesc(String status);

	Optional<MaintenanceAlert> findTopByAlertTitleAndStatusOrderByCreatedAtDesc(String alertTitle, String status);

	@Query("""
		select alert
		from MaintenanceAlert alert
		where alert.camera.cameraId = :cameraId
		  and (:laneId is null or alert.laneId = :laneId)
		  and alert.status = 'CREATED'
		order by alert.createdAt desc
		""")
	List<MaintenanceAlert> findCreatedByCameraAndLane(
		@Param("cameraId") Long cameraId,
		@Param("laneId") Integer laneId
	);
}
