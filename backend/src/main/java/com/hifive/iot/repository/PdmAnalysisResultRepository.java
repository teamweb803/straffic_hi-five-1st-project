package com.hifive.iot.repository;

import java.util.List;
import java.util.Optional;
import java.time.LocalDateTime;

import com.hifive.iot.entity.CameraDevice;
import com.hifive.iot.entity.PdmAnalysisResult;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PdmAnalysisResultRepository extends JpaRepository<PdmAnalysisResult, Long> {

	Optional<PdmAnalysisResult> findTopByCamera_CameraIdOrderByAnalyzedAtDesc(Long cameraId);

	List<PdmAnalysisResult> findTop50ByOrderByAnalyzedAtDesc();

	Optional<PdmAnalysisResult> findByCameraAndLaneIdAndAnalysisStartAndAnalysisEndAndModelType(
		CameraDevice camera,
		Integer laneId,
		LocalDateTime analysisStart,
		LocalDateTime analysisEnd,
		String modelType
	);

	boolean existsByCameraAndLaneIdAndAnalysisStartAndAnalysisEndAndModelType(
		CameraDevice camera,
		Integer laneId,
		LocalDateTime analysisStart,
		LocalDateTime analysisEnd,
		String modelType
	);

	@Query("""
		select result
		from PdmAnalysisResult result
		where result.camera.cameraId = :cameraId
		  and result.analysisEnd = (
			select max(latest.analysisEnd)
			from PdmAnalysisResult latest
			where latest.camera.cameraId = :cameraId
		  )
		order by
		  case result.riskLevel
			when 'CRITICAL' then 3
			when 'HIGH' then 2
			when 'WARNING' then 1
			else 0
		  end desc,
		  result.healthScore asc,
		  result.analyzedAt desc
		""")
	List<PdmAnalysisResult> findLatestWindowResultsByCamera(@Param("cameraId") Long cameraId);

	@Query("""
		select result
		from PdmAnalysisResult result
		where result.camera.cameraId = :cameraId
		  and (:laneId is null or result.laneId = :laneId)
		  and result.analysisEnd = (
			select max(latest.analysisEnd)
			from PdmAnalysisResult latest
			where latest.camera.cameraId = :cameraId
			  and (:laneId is null or latest.laneId = :laneId)
		  )
		order by
		  case result.modelType
			when 'RULE_BASED' then 1
			when 'ISOLATION_FOREST' then 2
			when 'LSTM_AE' then 3
			else 4
		  end asc,
		  result.analyzedAt desc
		""")
	List<PdmAnalysisResult> findLatestWindowResults(
		@Param("cameraId") Long cameraId,
		@Param("laneId") Integer laneId
	);
}
