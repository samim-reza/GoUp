from django.contrib import admin

from automations.models import AutomationRule, MessageTemplate


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "channel", "is_active", "updated_at")
    search_fields = ("name", "user__email")


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "page", "enabled", "priority", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("name", "user__email", "page__name")
