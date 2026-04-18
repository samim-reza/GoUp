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


@login_required
def oauth_start(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(32)
    request.session["meta_oauth_state"] = state
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
    expected_state = request.session.get("meta_oauth_state")
    state = request.GET.get("state")
    code = request.GET.get("code")

    if not expected_state or state != expected_state:
        return HttpResponseBadRequest("Invalid OAuth state")
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
            "user": request.user,
            "display_name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "access_token": user_access_token,
            "token_expires_at": token_expires_at,
            "is_active": True,
        },
    )

    # Keep exactly one active connection per user to avoid stale-token conflicts.
    ConnectedFacebookAccount.objects.filter(user=request.user, is_active=True).exclude(id=account.id).update(is_active=False)

    return redirect("/")


class SyncPagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account = ConnectedFacebookAccount.objects.filter(user=request.user, is_active=True).order_by("-updated_at").first()
        if not account:
            return Response({"detail": "Connect a Facebook account first."}, status=status.HTTP_400_BAD_REQUEST)

        client = MetaGraphClient(access_token=account.access_token)
        pages = client.list_pages()

        saved_pages: list[FacebookPage] = []
        for page in pages:
            obj, _ = FacebookPage.objects.update_or_create(
                page_id=page["id"],
                defaults={
                    "user": request.user,
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
        try:
            page = FacebookPage.objects.get(user=request.user, page_id=page_id)
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
