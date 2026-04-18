from __future__ import annotations

from rest_framework import serializers

from automations.models import AutomationRule, MessageTemplate
from facebook_integration.models import LeadForm


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "name",
            "channel",
            "subject",
            "body",
            "twilio_content_sid",
            "twilio_content_variables",
            "is_active",
            "created_at",
            "updated_at",
        ]


class AutomationRuleSerializer(serializers.ModelSerializer):
    lead_form_ids = serializers.PrimaryKeyRelatedField(
        source="lead_forms",
        many=True,
        required=False,
        queryset=LeadForm.objects.none(),
    )

    class Meta:
        model = AutomationRule
        fields = [
            "id",
            "name",
            "page",
            "lead_form_ids",
            "email_template",
            "sms_template",
            "whatsapp_template",
            "require_email_opt_in",
            "require_sms_opt_in",
            "enabled",
            "priority",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context["request"].user
        self.fields["lead_form_ids"].queryset = LeadForm.objects.filter(page__user=user)

    def create(self, validated_data):
        lead_forms = validated_data.pop("lead_forms", [])
        validated_data["user"] = self.context["request"].user
        rule = AutomationRule.objects.create(**validated_data)
        if lead_forms:
            rule.lead_forms.set(lead_forms)
        return rule

    def update(self, instance, validated_data):
        lead_forms = validated_data.pop("lead_forms", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if lead_forms is not None:
            instance.lead_forms.set(lead_forms)
        return instance
