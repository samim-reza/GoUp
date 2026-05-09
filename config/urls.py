from django.urls import include, path


urlpatterns = [
    path("", include("dashboard.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/facebook/", include("facebook_integration.urls")),
    path("api/automations/", include("automations.urls")),
    path("api/leads/", include("leads.urls")),
    path("api/messaging/", include("messaging.urls")),
    path("webhooks/", include("webhooks.urls")),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
