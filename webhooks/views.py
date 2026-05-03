from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from webhooks.models import WebhookEvent
from webhooks.services.signatures import verify_meta_signature
from webhooks.tasks import process_meta_webhook_event  # noqa: F401


def _extract_meta_change(change: dict, entry: dict) -> tuple[str, str, str, datetime | None]:
    value = change.get("value", {})
    leadgen_id = value.get("leadgen_id", "")
    form_id = value.get("form_id", "")
    page_id = value.get("page_id") or entry.get("id", "")

    event_time = None
    raw_time = entry.get("time")
    if raw_time:
        event_time = datetime.fromtimestamp(raw_time, tz=dt_timezone.utc)

    return page_id, form_id, leadgen_id, event_time


def _build_event_key(page_id: str, form_id: str, leadgen_id: str, event_time: datetime | None) -> str:
    raw = f"meta|{page_id}|{form_id}|{leadgen_id}|{event_time.isoformat() if event_time else ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


@csrf_exempt
def meta_leadgen_webhook(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        if verify_token == settings.META_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Invalid verify token", status=403)

    if request.method != "POST":
        return HttpResponse(status=405)

    body = request.body
    signature_header = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature", "")
    signature_valid = verify_meta_signature(body=body, signature_header=signature_header, app_secret=settings.META_WEBHOOK_SECRET)
    if not signature_valid:
        return HttpResponse("Invalid signature", status=401)

    payload = json.loads(body.decode("utf-8"))
    entries = payload.get("entry", [])

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            if change.get("field") != "leadgen":
                continue

            page_id, form_id, leadgen_id, event_time = _extract_meta_change(change, entry)
            event_key = _build_event_key(page_id, form_id, leadgen_id, event_time)

            event, created = WebhookEvent.objects.get_or_create(
                event_key=event_key,
                defaults={
                    "provider": WebhookEvent.PROVIDER_META,
                    "page_id": page_id,
                    "form_id": form_id,
                    "leadgen_id": leadgen_id,
                    "event_time": event_time,
                    "signature_valid": True,
                    "payload": change,
                    "status": WebhookEvent.STATUS_PENDING,
                },
            )

            if not created:
                event.status = WebhookEvent.STATUS_DUPLICATE
                event.save(update_fields=["status"])
                continue

            process_meta_webhook_event.delay(event.id)

    return JsonResponse({"status": "ok"}, status=200)
