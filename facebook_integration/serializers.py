from __future__ import annotations

from rest_framework import serializers

from facebook_integration.models import ConnectedFacebookAccount, FacebookPage, LeadForm


class ConnectedFacebookAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectedFacebookAccount
        fields = ["id", "facebook_user_id", "display_name", "email", "is_active", "created_at"]


class FacebookPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacebookPage
        fields = ["id", "page_id", "name", "is_selected", "created_at"]


class LeadFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadForm
        fields = ["id", "form_id", "name", "status", "is_selected", "created_at"]
