from django.contrib import admin

from messaging.models import DeliveryAttempt, MessageLog


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "rule", "channel", "status", "recipient", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("recipient", "provider_message_id", "lead__leadgen_id")


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "message_log", "attempt_number", "status", "created_at")
    list_filter = ("status",)
