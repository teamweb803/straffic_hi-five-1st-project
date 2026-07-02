package com.hifive.iot.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import com.hifive.iot.entity.MaintenanceAlert;
import com.hifive.iot.entity.NotificationLog;
import com.hifive.iot.repository.NotificationLogRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

@Slf4j
@Service
@RequiredArgsConstructor
public class PdmAlertMailService {

	private static final String RESEND_EMAILS_PATH = "/emails";

	private final NotificationLogRepository notificationLogRepository;
	private final RestClient resendClient = RestClient.builder()
		.baseUrl("https://api.resend.com")
		.build();

	@Value("${RESEND_API_KEY:}")
	private String resendApiKey;

	@Value("${PDM_ALERT_MAIL_FROM:}")
	private String mailFrom;

	@Value("${PDM_ALERT_RECEIVER_EMAIL:}")
	private String receiverEmail;

	public void sendAlert(MaintenanceAlert alert) {
		if (!isConfigured()) {
			log.info("PDM alert mail skipped: RESEND_API_KEY/PDM_ALERT_MAIL_FROM/PDM_ALERT_RECEIVER_EMAIL is not configured");
			return;
		}

		try {
			resendClient.post()
				.uri(RESEND_EMAILS_PATH)
				.header(HttpHeaders.AUTHORIZATION, "Bearer " + resendApiKey)
				.body(Map.of(
					"from", mailFrom,
					"to", List.of(receiverEmail),
					"subject", subject(alert),
					"text", textBody(alert),
					"html", htmlBody(alert)
				))
				.retrieve()
				.toBodilessEntity();

			notificationLogRepository.save(NotificationLog.builder()
				.alert(alert)
				.receiverEmail(receiverEmail)
				.sendStatus("SENT")
				.failureReason(null)
				.sentAt(LocalDateTime.now())
				.build());
		} catch (Exception exception) {
			log.warn("PDM alert mail failed alertId={}", alert.getAlertId(), exception);
			notificationLogRepository.save(NotificationLog.builder()
				.alert(alert)
				.receiverEmail(receiverEmail)
				.sendStatus("FAILED")
				.failureReason(exception.getMessage())
				.sentAt(null)
				.build());
		}
	}

	private boolean isConfigured() {
		return StringUtils.hasText(resendApiKey)
			&& StringUtils.hasText(mailFrom)
			&& StringUtils.hasText(receiverEmail);
	}

	private String subject(MaintenanceAlert alert) {
		return "[HiFive PDM] " + alert.getRiskLevel() + " alert - " + alert.getCamera().getCameraCode();
	}

	private String textBody(MaintenanceAlert alert) {
		return """
			PDM alert detected.

			Camera: %s
			Lane: %s
			Risk: %s
			Reason: %s
			Action: %s
			""".formatted(
			alert.getCamera().getCameraCode(),
			alert.getLaneId(),
			alert.getRiskLevel(),
			nullToDash(alert.getReasonText()),
			nullToDash(alert.getRecommendedAction())
		);
	}

	private String htmlBody(MaintenanceAlert alert) {
		return """
			<h2>HiFive PDM Alert</h2>
			<ul>
			  <li><b>Camera:</b> %s</li>
			  <li><b>Lane:</b> %s</li>
			  <li><b>Risk:</b> %s</li>
			  <li><b>Reason:</b> %s</li>
			  <li><b>Action:</b> %s</li>
			</ul>
			""".formatted(
			escape(alert.getCamera().getCameraCode()),
			alert.getLaneId(),
			escape(alert.getRiskLevel()),
			escape(nullToDash(alert.getReasonText())),
			escape(nullToDash(alert.getRecommendedAction()))
		);
	}

	private String nullToDash(String value) {
		return StringUtils.hasText(value) ? value : "-";
	}

	private String escape(String value) {
		return value
			.replace("&", "&amp;")
			.replace("<", "&lt;")
			.replace(">", "&gt;")
			.replace("\"", "&quot;");
	}
}
