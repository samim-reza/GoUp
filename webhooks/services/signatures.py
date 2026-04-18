from __future__ import annotations

import hashlib
import hmac


class InvalidWebhookSignature(Exception):
    pass


def _timing_safe_compare(expected: str, received: str) -> bool:
    return hmac.compare_digest(expected, received)


def verify_meta_signature(body: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header or not app_secret:
        return False

    if signature_header.startswith("sha256="):
        digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        return _timing_safe_compare(expected, signature_header)

    if signature_header.startswith("sha1="):
        digest = hmac.new(app_secret.encode(), body, hashlib.sha1).hexdigest()
        expected = f"sha1={digest}"
        return _timing_safe_compare(expected, signature_header)

    return False
