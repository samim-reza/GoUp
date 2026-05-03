from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import InvitationError, accept_invitation, ensure_personal_account, get_active_membership


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account = ensure_personal_account(request.user)
        membership = get_active_membership(request.user)
        return Response(
            {
                "id": request.user.id,
                "email": request.user.email,
                "username": request.user.get_username(),
                "account_id": account.id,
                "role": membership.role if membership else None,
            }
        )


@login_required
def accept_invitation_view(request: HttpRequest, token: str) -> HttpResponse:
    ensure_personal_account(request.user)
    try:
        accept_invitation(token, request.user)
    except InvitationError as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("dashboard-shell")
