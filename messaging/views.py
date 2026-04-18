from __future__ import annotations

from rest_framework import permissions, viewsets

from messaging.models import MessageLog
from messaging.serializers import MessageLogSerializer


class MessageLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MessageLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MessageLog.objects.filter(lead__user=self.request.user).select_related("lead", "rule").prefetch_related("attempts")
