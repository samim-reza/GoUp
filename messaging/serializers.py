from __future__ import annotations

from rest_framework import serializers

from messaging.models import DeliveryAttempt, MessageLog


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = ["id", "attempt_number", "status", "provider_response", "error_message", "created_at"]


class MessageLogSerializer(serializers.ModelSerializer):
    attempts = DeliveryAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = MessageLog
        fields = [
            "id",
            "lead",
            "rule",
            "channel",
            "recipient",
            "subject",
            "rendered_body",
            "status",
            "provider_message_id",
            "error_message",
            "sent_at",
            "created_at",
            "attempts",
        ]
