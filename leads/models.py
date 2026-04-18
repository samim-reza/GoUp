from __future__ import annotations

from django.conf import settings
from django.db import models


class Lead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leads")
    page = models.ForeignKey("facebook_integration.FacebookPage", on_delete=models.CASCADE, related_name="leads")
    lead_form = models.ForeignKey("facebook_integration.LeadForm", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    leadgen_id = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    consent_email = models.BooleanField(default=False)
    consent_sms = models.BooleanField(default=False)
    raw_answers = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.leadgen_id}"
