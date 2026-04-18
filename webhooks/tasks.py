from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from automations.models import AutomationRule
from facebook_integration.models import FacebookPage, LeadForm
from facebook_integration.services.meta_graph import MetaAPIError, MetaGraphClient
from leads.models import Lead
from messaging.tasks import send_messages_for_rule
from webhooks.models import WebhookEvent


TRUE_VALUES = {"true", "yes", "1", "opted_in", "y"}


def _to_bool(value: str) -> bool:
    return value.strip().lower() in TRUE_VALUES


def _extract_fields(field_data: list[dict]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in field_data:
        name = item.get("name", "")
        values = item.get("values") or []
        output[name] = values[0] if values else ""
    return output


@shared_task(bind=True, autoretry_for=(MetaAPIError,), retry_backoff=True, max_retries=5)
def process_meta_webhook_event(self, webhook_event_id: int) -> None:
    with transaction.atomic():
        event = WebhookEvent.objects.select_for_update().get(id=webhook_event_id)
        if event.status in {WebhookEvent.STATUS_PROCESSED, WebhookEvent.STATUS_DUPLICATE}:
            return

        page = FacebookPage.objects.filter(page_id=event.page_id, user__is_active=True).select_related("user").first()
        if not page:
            event.status = WebhookEvent.STATUS_FAILED
            event.error_message = "Page not connected"
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_message", "processed_at"])
            return

        client = MetaGraphClient(access_token=page.page_access_token)
        lead_payload = client.get_lead(event.leadgen_id)

        form = LeadForm.objects.filter(form_id=event.form_id).first()
        answers = _extract_fields(lead_payload.get("field_data", []))

        lead, _ = Lead.objects.update_or_create(
            leadgen_id=event.leadgen_id,
            defaults={
                "user": page.user,
                "page": page,
                "lead_form": form,
                "full_name": answers.get("full_name") or answers.get("name", ""),
                "email": answers.get("email", ""),
                "phone": answers.get("phone_number") or answers.get("phone", ""),
                "consent_email": _to_bool(answers.get("email_opt_in", "false")),
                "consent_sms": _to_bool(answers.get("sms_opt_in", "false")),
                "raw_answers": answers,
                "captured_at": timezone.now(),
            },
        )

        rules = AutomationRule.objects.filter(page=page, enabled=True).prefetch_related("lead_forms")
        if form:
            rules = [rule for rule in rules if (not rule.lead_forms.exists()) or rule.lead_forms.filter(id=form.id).exists()]
        else:
            rules = [rule for rule in rules if not rule.lead_forms.exists()]

        for rule in rules:
            send_messages_for_rule.delay(lead.id, rule.id)

        event.status = WebhookEvent.STATUS_PROCESSED
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])
