from __future__ import annotations

from rest_framework import serializers

from leads.models import Lead


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "leadgen_id",
            "full_name",
            "email",
            "phone",
            "consent_email",
            "consent_sms",
            "raw_answers",
            "captured_at",
            "created_at",
        ]
