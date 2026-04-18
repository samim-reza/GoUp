from __future__ import annotations

from rest_framework import permissions, viewsets

from automations.models import AutomationRule, MessageTemplate
from automations.serializers import AutomationRuleSerializer, MessageTemplateSerializer


class IsOwnerMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class MessageTemplateViewSet(IsOwnerMixin, viewsets.ModelViewSet):
    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AutomationRuleViewSet(IsOwnerMixin, viewsets.ModelViewSet):
    serializer_class = AutomationRuleSerializer
    queryset = AutomationRule.objects.select_related("page", "email_template", "sms_template", "whatsapp_template").prefetch_related("lead_forms")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
