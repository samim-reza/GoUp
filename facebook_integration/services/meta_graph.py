from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


GRAPH_BASE_URL = "https://graph.facebook.com/v20.0"


class MetaAPIError(Exception):
    pass


@dataclass
class MetaGraphClient:
    access_token: str

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = params.copy() if params else {}
        payload["access_token"] = self.access_token
        response = requests.get(f"{GRAPH_BASE_URL}{path}", params=payload, timeout=20)
        data = response.json()
        if response.status_code >= 400:
            raise MetaAPIError(str(data))
        return data

    def list_pages(self) -> list[dict[str, Any]]:
        data = self._get("/me/accounts", {"fields": "id,name,access_token"})
        return data.get("data", [])

    def list_forms(self, page_id: str) -> list[dict[str, Any]]:
        data = self._get(f"/{page_id}/leadgen_forms", {"fields": "id,name,status"})
        return data.get("data", [])

    def get_lead(self, leadgen_id: str) -> dict[str, Any]:
        return self._get(f"/{leadgen_id}", {"fields": "id,created_time,field_data,ad_id,form_id"})


def exchange_code_for_token(code: str) -> dict[str, Any]:
    response = requests.get(
        f"{GRAPH_BASE_URL}/oauth/access_token",
        params={
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.META_REDIRECT_URI,
            "code": code,
        },
        timeout=20,
    )
    data = response.json()
    if response.status_code >= 400:
        raise MetaAPIError(str(data))
    return data


def get_user_profile(user_access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{GRAPH_BASE_URL}/me",
        params={"fields": "id,name,email", "access_token": user_access_token},
        timeout=20,
    )
    data = response.json()
    if response.status_code >= 400:
        raise MetaAPIError(str(data))
    return data
