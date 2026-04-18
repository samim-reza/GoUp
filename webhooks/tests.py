import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from webhooks.models import WebhookEvent


@override_settings(META_WEBHOOK_SECRET="test-secret", META_VERIFY_TOKEN="verify-token")
class MetaWebhookTests(TestCase):
    def _signature(self, payload: bytes) -> str:
        digest = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_verify_challenge_success(self):
        response = self.client.get(
            "/webhooks/meta/leadgen/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-token",
                "hub.challenge": "12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "12345")

    @patch("webhooks.views.process_meta_webhook_event.delay")
    def test_webhook_is_idempotent(self, mocked_delay):
        payload_obj = {
            "object": "page",
            "entry": [
                {
                    "id": "111",
                    "time": 1713340000,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead-1", "form_id": "form-1", "page_id": "111"},
                        }
                    ],
                }
            ],
        }
        payload = json.dumps(payload_obj).encode()
        headers = {"HTTP_X_HUB_SIGNATURE_256": self._signature(payload)}

        first = self.client.post("/webhooks/meta/leadgen/", payload, content_type="application/json", **headers)
        second = self.client.post("/webhooks/meta/leadgen/", payload, content_type="application/json", **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)

        event = WebhookEvent.objects.first()
        assert event is not None
        self.assertEqual(event.status, WebhookEvent.STATUS_DUPLICATE)
        mocked_delay.assert_called_once()

    def test_webhook_rejects_invalid_signature(self):
        payload = json.dumps({"object": "page", "entry": []}).encode()
        response = self.client.post(
            "/webhooks/meta/leadgen/",
            payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
        )
        self.assertEqual(response.status_code, 401)
