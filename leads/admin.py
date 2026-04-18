from django.contrib import admin

from leads.models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "leadgen_id", "page", "email", "phone", "consent_email", "consent_sms", "created_at")
    search_fields = ("leadgen_id", "email", "phone")
    list_filter = ("consent_email", "consent_sms")
