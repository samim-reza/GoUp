from __future__ import annotations

import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from facebook_integration.models import ConnectedFacebookAccount, FacebookPage, LeadForm
from facebook_integration.serializers import FacebookPageSerializer, LeadFormSerializer
from facebook_integration.services.meta_graph import MetaAPIError, MetaGraphClient, exchange_code_for_token, get_user_profile
from accounts.services import get_active_membership, get_account_owner_user


def _owner_scope_user(request: HttpRequest):
    membership = get_active_membership(request.user)
    if not membership:
        return None, False
    owner_user = get_account_owner_user(membership.account)
    if not owner_user:
        return None, False
    return owner_user, owner_user.id == request.user.id


@login_required
def oauth_start(request: HttpRequest) -> HttpResponse:
    owner_user, is_owner = _owner_scope_user(request)
    if not owner_user:
        return HttpResponseBadRequest("No active account membership found.")
    if not is_owner:
        return HttpResponseBadRequest("Only the account owner can connect or reconnect Facebook.")

    state = secrets.token_urlsafe(32)
    request.session["meta_oauth_state"] = state
    request.session["meta_oauth_owner_user_id"] = owner_user.id
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }

    if settings.META_LOGIN_CONFIG_ID:
        params["config_id"] = settings.META_LOGIN_CONFIG_ID
    else:
        requested_scopes = ",".join(settings.META_OAUTH_SCOPES) if settings.META_OAUTH_SCOPES else "pages_show_list,pages_read_engagement"
        params["scope"] = requested_scopes

    return redirect(f"https://www.facebook.com/v20.0/dialog/oauth?{urlencode(params)}")


@login_required
def oauth_callback(request: HttpRequest) -> HttpResponse:
    owner_user, is_owner = _owner_scope_user(request)
    if not owner_user:
        return HttpResponseBadRequest("No active account membership found.")
    if not is_owner:
        return HttpResponseBadRequest("Only the account owner can complete Facebook connection.")

    expected_state = request.session.get("meta_oauth_state")
    state = request.GET.get("state")
    code = request.GET.get("code")
    expected_owner_id = request.session.get("meta_oauth_owner_user_id")

    if not expected_state or state != expected_state:
        return HttpResponseBadRequest("Invalid OAuth state")
    if expected_owner_id:
        try:
            expected_owner_id = int(expected_owner_id)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Invalid OAuth owner session.")
        if expected_owner_id != owner_user.id:
            return HttpResponseBadRequest("OAuth session does not match account owner.")
    if not code:
        return HttpResponseBadRequest("Missing OAuth code")

    try:
        token_data = exchange_code_for_token(code)
        user_access_token = token_data["access_token"]
        profile = get_user_profile(user_access_token)
    except MetaAPIError as exc:
        return HttpResponseBadRequest(f"Meta OAuth failed: {exc}")

    expires_in = token_data.get("expires_in")
    token_expires_at = None
    if isinstance(expires_in, int):
        token_expires_at = timezone.now() + timedelta(seconds=expires_in)

    account, _ = ConnectedFacebookAccount.objects.update_or_create(
        facebook_user_id=profile["id"],
        defaults={
            "user": owner_user,
            "display_name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "access_token": user_access_token,
            "token_expires_at": token_expires_at,
            "is_active": True,
        },
    )

    # Keep exactly one active connection per owner to avoid stale-token conflicts.
    ConnectedFacebookAccount.objects.filter(user=owner_user, is_active=True).exclude(id=account.id).update(is_active=False)

    return redirect("/")


class SyncPagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        owner_user, is_owner = _owner_scope_user(request)
        if not owner_user:
            return Response({"detail": "No active account membership found."}, status=status.HTTP_400_BAD_REQUEST)
        if not is_owner:
            return Response({"detail": "Only the account owner can sync pages."}, status=status.HTTP_403_FORBIDDEN)

        account = ConnectedFacebookAccount.objects.filter(user=owner_user, is_active=True).order_by("-updated_at").first()
        if not account:
            return Response({"detail": "Connect a Facebook account first."}, status=status.HTTP_400_BAD_REQUEST)

        client = MetaGraphClient(access_token=account.access_token)
        pages = client.list_pages()

        saved_pages: list[FacebookPage] = []
        for page in pages:
            obj, _ = FacebookPage.objects.update_or_create(
                page_id=page["id"],
                defaults={
                    "user": owner_user,
                    "connected_account": account,
                    "name": page.get("name", "Unknown page"),
                    "page_access_token": page.get("access_token", ""),
                },
            )
            saved_pages.append(obj)

        serializer = FacebookPageSerializer(saved_pages, many=True)
        return Response(serializer.data)


class SyncFormsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, page_id: str):
        owner_user, is_owner = _owner_scope_user(request)
        if not owner_user:
            return Response({"detail": "No active account membership found."}, status=status.HTTP_400_BAD_REQUEST)
        if not is_owner:
            return Response({"detail": "Only the account owner can sync forms."}, status=status.HTTP_403_FORBIDDEN)

        try:
            page = FacebookPage.objects.get(user=owner_user, page_id=page_id)
        except FacebookPage.DoesNotExist:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        client = MetaGraphClient(access_token=page.page_access_token)
        try:
            forms = client.list_forms(page_id)
        except MetaAPIError as exc:
            return Response({"detail": f"Facebook form sync failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        saved_forms: list[LeadForm] = []
        for form in forms:
            obj, _ = LeadForm.objects.update_or_create(
                form_id=form["id"],
                defaults={
                    "page": page,
                    "name": form.get("name", "Unnamed form"),
                    "status": form.get("status", "ACTIVE"),
                },
            )
            saved_forms.append(obj)

        serializer = LeadFormSerializer(saved_forms, many=True)
        return Response(serializer.data)
