from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from automations.models import AutomationRule
from automations.services.template_renderer import render_template
from leads.models import Lead
from messaging.models import DeliveryAttempt, MessageLog
from messaging.services.email import EmailProviderError, send_email
from messaging.services.sms import SMSProviderError, WhatsAppProviderError, send_sms, send_whatsapp


@shared_task(
    bind=True,
    autoretry_for=(EmailProviderError, SMSProviderError, WhatsAppProviderError),
    retry_backoff=True,
    max_retries=5,
)
def send_messages_for_rule(self, lead_id: int, rule_id: int) -> None:
    lead = Lead.objects.select_related("page", "lead_form").get(id=lead_id)
    rule = AutomationRule.objects.select_related("email_template", "sms_template", "whatsapp_template").get(id=rule_id)

    if not rule.enabled:
        return

    context = {
        "name": lead.full_name,
        "email": lead.email,
        "phone": lead.phone,
        "page_name": lead.page.name,
        "form_name": lead.lead_form.name if lead.lead_form else "",
    }

    if rule.email_template and lead.email:
        status = MessageLog.STATUS_QUEUED
        error_message = ""
        provider_message_id = ""
        subject = render_template(rule.email_template.subject, context)
        rendered_body = render_template(rule.email_template.body, context)

        if rule.require_email_opt_in and not lead.consent_email:
            status = MessageLog.STATUS_SKIPPED
            error_message = "Email opt-in missing"
        else:
            try:
                provider_message_id = send_email(to_email=lead.email, subject=subject, body=rendered_body)
                status = MessageLog.STATUS_SENT
            except EmailProviderError as exc:
                status = MessageLog.STATUS_FAILED
                error_message = str(exc)

        log = MessageLog.objects.create(
            lead=lead,
            rule=rule,
            channel=MessageLog.CHANNEL_EMAIL,
            recipient=lead.email,
            subject=subject,
            rendered_body=rendered_body,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=timezone.now() if status == MessageLog.STATUS_SENT else None,
        )
        DeliveryAttempt.objects.create(
            message_log=log,
            attempt_number=1,
            status=DeliveryAttempt.STATUS_SUCCESS if status == MessageLog.STATUS_SENT else DeliveryAttempt.STATUS_FAILURE,
            error_message=error_message,
        )
        if status == MessageLog.STATUS_FAILED:
            raise EmailProviderError(error_message)

    if rule.sms_template and lead.phone:
        status = MessageLog.STATUS_QUEUED
        error_message = ""
        provider_message_id = ""
        rendered_body = render_template(rule.sms_template.body, context)

        if rule.require_sms_opt_in and not lead.consent_sms:
            status = MessageLog.STATUS_SKIPPED
            error_message = "SMS opt-in missing"
        else:
            try:
                provider_message_id = send_sms(to_phone=lead.phone, body=rendered_body)
                status = MessageLog.STATUS_SENT
            except SMSProviderError as exc:
                status = MessageLog.STATUS_FAILED
                error_message = str(exc)

        log = MessageLog.objects.create(
            lead=lead,
            rule=rule,
            channel=MessageLog.CHANNEL_SMS,
            recipient=lead.phone,
            rendered_body=rendered_body,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=timezone.now() if status == MessageLog.STATUS_SENT else None,
        )
        DeliveryAttempt.objects.create(
            message_log=log,
            attempt_number=1,
            status=DeliveryAttempt.STATUS_SUCCESS if status == MessageLog.STATUS_SENT else DeliveryAttempt.STATUS_FAILURE,
            error_message=error_message,
        )
        if status == MessageLog.STATUS_FAILED:
            raise SMSProviderError(error_message)

    if rule.whatsapp_template and lead.phone:
        status = MessageLog.STATUS_QUEUED
        error_message = ""
        provider_message_id = ""
        rendered_body = render_template(rule.whatsapp_template.body, context)
        content_sid = (rule.whatsapp_template.twilio_content_sid or "").strip()
        content_variables = {}
        for key, value in (rule.whatsapp_template.twilio_content_variables or {}).items():
            if isinstance(value, str):
                content_variables[key] = render_template(value, context)
            else:
                content_variables[key] = value

        if rule.require_sms_opt_in and not lead.consent_sms:
            status = MessageLog.STATUS_SKIPPED
            error_message = "WhatsApp opt-in missing"
        else:
            try:
                provider_message_id = send_whatsapp(
                    to_phone=lead.phone,
                    body=rendered_body,
                    content_sid=content_sid,
                    content_variables=content_variables,
                )
                status = MessageLog.STATUS_SENT
            except WhatsAppProviderError as exc:
                status = MessageLog.STATUS_FAILED
                error_message = str(exc)

        log = MessageLog.objects.create(
            lead=lead,
            rule=rule,
            channel=MessageLog.CHANNEL_WHATSAPP,
            recipient=lead.phone,
            rendered_body=rendered_body,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=timezone.now() if status == MessageLog.STATUS_SENT else None,
        )
        DeliveryAttempt.objects.create(
            message_log=log,
            attempt_number=1,
            status=DeliveryAttempt.STATUS_SUCCESS if status == MessageLog.STATUS_SENT else DeliveryAttempt.STATUS_FAILURE,
            error_message=error_message,
        )
        if status == MessageLog.STATUS_FAILED:
            raise WhatsAppProviderError(error_message)
