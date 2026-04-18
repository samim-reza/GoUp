from __future__ import annotations

from django.conf import settings
from django.db import models


class MessageTemplate(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_templates")
    name = models.CharField(max_length=120)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    twilio_content_sid = models.CharField(max_length=64, blank=True)
    twilio_content_variables = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "name", "channel"]

    def __str__(self) -> str:
        return f"{self.name} ({self.channel})"


class AutomationRule(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="automation_rules")
    name = models.CharField(max_length=120)
    page = models.ForeignKey("facebook_integration.FacebookPage", on_delete=models.CASCADE, related_name="automation_rules")
    lead_forms = models.ManyToManyField("facebook_integration.LeadForm", related_name="automation_rules", blank=True)
    email_template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_rules",
        limit_choices_to={"channel": MessageTemplate.CHANNEL_EMAIL},
    )
    sms_template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_rules",
        limit_choices_to={"channel": MessageTemplate.CHANNEL_SMS},
    )
    whatsapp_template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_rules",
        limit_choices_to={"channel": MessageTemplate.CHANNEL_WHATSAPP},
    )
    require_email_opt_in = models.BooleanField(default=True)
    require_sms_opt_in = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return self.name
