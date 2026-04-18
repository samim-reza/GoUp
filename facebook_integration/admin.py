from django.contrib import admin

from facebook_integration.models import ConnectedFacebookAccount, FacebookPage, LeadForm


@admin.register(ConnectedFacebookAccount)
class ConnectedFacebookAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "facebook_user_id", "display_name", "is_active", "updated_at")
    search_fields = ("facebook_user_id", "display_name", "email")


@admin.register(FacebookPage)
class FacebookPageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "page_id", "name", "is_selected", "updated_at")
    search_fields = ("page_id", "name")


@admin.register(LeadForm)
class LeadFormAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "form_id", "name", "status", "is_selected", "updated_at")
    search_fields = ("form_id", "name")
