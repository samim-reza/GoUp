from __future__ import annotations

import json

from django.conf import settings
from twilio.rest import Client


class SMSProviderError(Exception):
    pass


class WhatsAppProviderError(Exception):
    pass


def send_sms(*, to_phone: str, body: str) -> str:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        raise SMSProviderError("Twilio credentials are not fully configured")

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    msg = client.messages.create(body=body, from_=settings.TWILIO_FROM_NUMBER, to=to_phone)
    return msg.sid


def _as_whatsapp_address(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("whatsapp:"):
        return value
    return f"whatsapp:{value}"


def send_whatsapp(
    *,
    to_phone: str,
    body: str,
    content_sid: str = "",
    content_variables: dict | None = None,
) -> str:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise WhatsAppProviderError("Twilio credentials are not fully configured")

    from_number = _as_whatsapp_address(getattr(settings, "TWILIO_WHATSAPP_FROM_NUMBER", ""))
    to_number = _as_whatsapp_address(to_phone)
    if not from_number or not to_number:
        raise WhatsAppProviderError("WhatsApp sender and recipient must be configured")

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    if content_sid:
        payload = {
            "from_": from_number,
            "to": to_number,
            "content_sid": content_sid,
            "content_variables": json.dumps(content_variables or {}),
        }
        msg = client.messages.create(**payload)
        return msg.sid

    if not body.strip():
        raise WhatsAppProviderError("WhatsApp body is required when content_sid is not provided")

    msg = client.messages.create(body=body, from_=from_number, to=to_number)
    return msg.sid
