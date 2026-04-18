from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from automations.models import AutomationRule, MessageTemplate
from facebook_integration.models import ConnectedFacebookAccount, FacebookPage
from leads.models import Lead
from messaging.models import MessageLog
from messaging.tasks import send_messages_for_rule


User = get_user_model()


@override_settings(FIELD_ENCRYPTION_KEY="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
class MessagingConsentTests(TestCase):
    @patch("messaging.tasks.send_email")
    def test_email_not_sent_without_opt_in(self, mocked_send_email):
        user = User.objects.create_user(username="owner", email="owner@example.com", password="secret12345")
        fb_account = ConnectedFacebookAccount.objects.create(
            user=user,
            facebook_user_id="fb-1",
            display_name="Owner",
            email="owner@example.com",
            access_token="user-token",
        )
        page = FacebookPage.objects.create(
            user=user,
            connected_account=fb_account,
            page_id="page-1",
            name="Acme",
            page_access_token="page-token",
        )
        template = MessageTemplate.objects.create(
            user=user,
            name="welcome",
            channel=MessageTemplate.CHANNEL_EMAIL,
            subject="Welcome {{name}}",
            body="Hi {{name}}",
        )
        rule = AutomationRule.objects.create(
            user=user,
            name="rule-1",
            page=page,
            email_template=template,
            require_email_opt_in=True,
            enabled=True,
        )
        lead = Lead.objects.create(
            user=user,
            page=page,
            leadgen_id="lead-1",
            full_name="Alex",
            email="alex@example.com",
            consent_email=False,
        )

        send_messages_for_rule.run(lead.id, rule.id)

        log = MessageLog.objects.get(lead=lead, rule=rule, channel=MessageLog.CHANNEL_EMAIL)
        self.assertEqual(log.status, MessageLog.STATUS_SKIPPED)
        mocked_send_email.assert_not_called()
