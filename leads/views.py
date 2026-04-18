from __future__ import annotations

from rest_framework import permissions, viewsets

from leads.models import Lead
from leads.serializers import LeadSerializer


class LeadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Lead.objects.filter(user=self.request.user).select_related("page", "lead_form")
