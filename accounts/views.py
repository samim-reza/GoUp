from __future__ import annotations

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "email": request.user.email,
                "username": request.user.get_username(),
            }
        )
