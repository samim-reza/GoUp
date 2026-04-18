from __future__ import annotations

from django.db import models


class MessageLog(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="message_logs")
    rule = models.ForeignKey("automations.AutomationRule", on_delete=models.CASCADE, related_name="message_logs")
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    rendered_body = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DeliveryAttempt(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILURE, "Failure"),
    ]

    message_log = models.ForeignKey(MessageLog, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["message_log", "attempt_number"]
