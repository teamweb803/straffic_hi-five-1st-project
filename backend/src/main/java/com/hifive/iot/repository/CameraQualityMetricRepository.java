package com.hifive.iot.repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.CameraQualityMetric;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CameraQualityMetricRepository extends JpaRepository<CameraQualityMetric, Long> {

	List<CameraQualityMetric> findByCamera_CameraIdOrderByBucketStartAsc(Long cameraId);

	Optional<CameraQualityMetric> findTopByCamera_CameraIdOrderByBucketStartDesc(Long cameraId);

	List<CameraQualityMetric> findTop6ByCamera_CameraIdOrderByBucketStartDesc(Long cameraId);

	Optional<CameraQualityMetric> findByCameraAndLaneIdAndBucketStart(
		CameraDevice camera,
		Integer laneId,
		LocalDateTime bucketStart
	);

	boolean existsByCameraAndLaneIdAndBucketStart(
		CameraDevice camera,
		Integer laneId,
		LocalDateTime bucketStart
	);

	@Query("""
		select metric
		from CameraQualityMetric metric
		where metric.camera.cameraId = :cameraId
		  and metric.laneId = :laneId
		  and metric.bucketEnd >= :fromTime
		  and metric.bucketStart <= :toTime
		order by metric.camera.cameraId asc, metric.laneId asc, metric.bucketStart asc
		""")
	List<CameraQualityMetric> findQualityMetrics(
		@Param("cameraId") Long cameraId,
		@Param("laneId") Integer laneId,
		@Param("fromTime") LocalDateTime from,
		@Param("toTime") LocalDateTime to,
		Pageable pageable
	);

	@Query("""
		select metric
		from CameraQualityMetric metric
		where metric.camera.cameraId = :cameraId
		  and metric.bucketEnd >= :fromTime
		  and metric.bucketStart <= :toTime
		order by metric.camera.cameraId asc, metric.laneId asc, metric.bucketStart asc
		""")
	List<CameraQualityMetric> findQualityMetricsByCamera(
		@Param("cameraId") Long cameraId,
		@Param("fromTime") LocalDateTime from,
		@Param("toTime") LocalDateTime to,
		Pageable pageable
	);

	@Query("""
		select metric
		from CameraQualityMetric metric
		where metric.laneId = :laneId
		  and metric.bucketEnd >= :fromTime
		  and metric.bucketStart <= :toTime
		order by metric.camera.cameraId asc, metric.laneId asc, metric.bucketStart asc
		""")
	List<CameraQualityMetric> findQualityMetricsByLane(
		@Param("laneId") Integer laneId,
		@Param("fromTime") LocalDateTime from,
		@Param("toTime") LocalDateTime to,
		Pageable pageable
	);

	@Query("""
		select metric
		from CameraQualityMetric metric
		where metric.bucketEnd >= :fromTime
		  and metric.bucketStart <= :toTime
		order by metric.camera.cameraId asc, metric.laneId asc, metric.bucketStart asc
		""")
	List<CameraQualityMetric> findAllQualityMetrics(
		@Param("fromTime") LocalDateTime from,
		@Param("toTime") LocalDateTime to,
		Pageable pageable
	);
}
