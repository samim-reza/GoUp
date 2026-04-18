from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage


class EmailProviderError(Exception):
    pass


def send_email(*, to_email: str, subject: str, body: str) -> str:
    if not settings.DEFAULT_FROM_EMAIL:
        raise EmailProviderError("DEFAULT_FROM_EMAIL is not configured")

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )

    try:
        sent = message.send(fail_silently=False)
    except Exception as exc:
        raise EmailProviderError(str(exc)) from exc

    if sent < 1:
        raise EmailProviderError("Email backend did not confirm delivery")

    return message.message().get("Message-ID", "")
