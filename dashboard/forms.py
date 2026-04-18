from __future__ import annotations

import json

from django import forms

from automations.models import AutomationRule, MessageTemplate
from facebook_integration.models import FacebookPage, LeadForm


class MessageTemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = [
            "name",
            "channel",
            "subject",
            "body",
            "twilio_content_sid",
            "twilio_content_variables",
            "is_active",
        ]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
            "twilio_content_variables": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        channel = cleaned.get("channel")
        subject = cleaned.get("subject", "")
        if channel == MessageTemplate.CHANNEL_EMAIL and not subject.strip():
            self.add_error("subject", "Email templates require a subject.")
        if channel != MessageTemplate.CHANNEL_WHATSAPP and cleaned.get("twilio_content_sid"):
            self.add_error("twilio_content_sid", "Content SID is only used for WhatsApp templates.")

        variables = cleaned.get("twilio_content_variables") or {}
        if variables and not isinstance(variables, dict):
            self.add_error("twilio_content_variables", "Content variables must be a JSON object.")
        return cleaned


class AutomationRuleForm(forms.ModelForm):
    class Meta:
        model = AutomationRule
        fields = [
            "name",
            "page",
            "lead_forms",
            "email_template",
            "sms_template",
            "whatsapp_template",
            "require_email_opt_in",
            "require_sms_opt_in",
            "enabled",
            "priority",
        ]

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["page"].queryset = FacebookPage.objects.filter(user=user).order_by("name")
        self.fields["lead_forms"].queryset = LeadForm.objects.filter(page__user=user).select_related("page").order_by("page__name", "name")
        self.fields["email_template"].queryset = MessageTemplate.objects.filter(
            user=user,
            channel=MessageTemplate.CHANNEL_EMAIL,
            is_active=True,
        ).order_by("name")
        self.fields["sms_template"].queryset = MessageTemplate.objects.filter(
            user=user,
            channel=MessageTemplate.CHANNEL_SMS,
            is_active=True,
        ).order_by("name")
        self.fields["whatsapp_template"].queryset = MessageTemplate.objects.filter(
            user=user,
            channel=MessageTemplate.CHANNEL_WHATSAPP,
            is_active=True,
        ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        email_template = cleaned.get("email_template")
        sms_template = cleaned.get("sms_template")
        whatsapp_template = cleaned.get("whatsapp_template")
        page = cleaned.get("page")
        lead_forms = cleaned.get("lead_forms")

        if not email_template and not sms_template and not whatsapp_template:
            raise forms.ValidationError("Choose at least one template (email, SMS, or WhatsApp).")

        if page and lead_forms:
            invalid = [form for form in lead_forms if form.page_id != page.id]
            if invalid:
                raise forms.ValidationError("All selected forms must belong to the selected page.")

        return cleaned


class DummyLeadSubmissionForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=64, required=False)
    consent_email = forms.BooleanField(required=False, initial=True)
    consent_sms = forms.BooleanField(required=False, initial=True)

    send_sms = forms.BooleanField(required=False, initial=True)
    sms_body = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        initial="Hi {{name}}, thanks for your interest in {{page_name}}.",
    )

    send_email = forms.BooleanField(required=False)
    email_subject = forms.CharField(required=False, max_length=255, initial="Thanks {{name}} for contacting {{page_name}}")
    email_body = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        initial="Hello {{name}}, we received your request from {{form_name}}.",
    )

    send_whatsapp = forms.BooleanField(required=False, initial=True)
    whatsapp_body = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        initial="Hi {{name}}, thanks for your message to {{page_name}}.",
    )
    whatsapp_content_sid = forms.CharField(required=False, max_length=64)
    whatsapp_content_variables = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), initial='{"1": "{{name}}"}')

    def clean_whatsapp_content_variables(self):
        raw = (self.cleaned_data.get("whatsapp_content_variables") or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("WhatsApp content variables must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("WhatsApp content variables must be a JSON object.")
        return parsed

    def clean(self):
        cleaned = super().clean()
        send_sms = cleaned.get("send_sms")
        send_email = cleaned.get("send_email")
        send_whatsapp = cleaned.get("send_whatsapp")

        if not send_sms and not send_email and not send_whatsapp:
            raise forms.ValidationError("Select at least one channel: SMS, Email, or WhatsApp.")

        if send_sms and not (cleaned.get("phone") or "").strip():
            self.add_error("phone", "Phone is required when SMS is enabled.")

        if send_sms and not (cleaned.get("sms_body") or "").strip():
            self.add_error("sms_body", "SMS body is required when SMS is enabled.")

        if send_email and not (cleaned.get("email") or "").strip():
            self.add_error("email", "Email is required when email is enabled.")

        if send_email and not (cleaned.get("email_subject") or "").strip():
            self.add_error("email_subject", "Email subject is required when email is enabled.")

        if send_email and not (cleaned.get("email_body") or "").strip():
            self.add_error("email_body", "Email body is required when email is enabled.")

        if send_whatsapp and not (cleaned.get("phone") or "").strip():
            self.add_error("phone", "Phone is required when WhatsApp is enabled.")

        whatsapp_content_sid = (cleaned.get("whatsapp_content_sid") or "").strip()
        whatsapp_body = (cleaned.get("whatsapp_body") or "").strip()
        if send_whatsapp and not whatsapp_content_sid and not whatsapp_body:
            self.add_error("whatsapp_body", "WhatsApp body is required when content SID is empty.")

        return cleaned
