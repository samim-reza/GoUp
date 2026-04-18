from __future__ import annotations

from django.db import models


class WebhookEvent(models.Model):
    PROVIDER_META = "meta"
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_DUPLICATE = "duplicate"

    provider = models.CharField(max_length=32, default=PROVIDER_META)
    event_key = models.CharField(max_length=255, unique=True)
    page_id = models.CharField(max_length=64, blank=True)
    form_id = models.CharField(max_length=64, blank=True)
    leadgen_id = models.CharField(max_length=64, blank=True)
    event_time = models.DateTimeField(null=True, blank=True)
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "leadgen_id"]),
            models.Index(fields=["status", "received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_key}"
