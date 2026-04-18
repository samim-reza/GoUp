from __future__ import annotations

from django.conf import settings
from django.db import models

from common.fields import EncryptedTextField


class ConnectedFacebookAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="facebook_accounts")
    facebook_user_id = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    access_token = EncryptedTextField()
    token_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.display_name} ({self.facebook_user_id})"


class FacebookPage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="facebook_pages")
    connected_account = models.ForeignKey(ConnectedFacebookAccount, on_delete=models.CASCADE, related_name="pages")
    page_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    page_access_token = EncryptedTextField()
    is_selected = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class LeadForm(models.Model):
    page = models.ForeignKey(FacebookPage, on_delete=models.CASCADE, related_name="lead_forms")
    form_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=64, default="ACTIVE")
    is_selected = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.page.name}: {self.name}"
