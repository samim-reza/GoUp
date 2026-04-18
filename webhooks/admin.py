from django.contrib import admin

from webhooks.models import WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "page_id", "form_id", "leadgen_id", "status", "received_at")
    search_fields = ("event_key", "leadgen_id", "page_id", "form_id")
    list_filter = ("provider", "status", "signature_valid")
