from django.urls import path

from webhooks.views import meta_leadgen_webhook


urlpatterns = [
    path("meta/leadgen/", meta_leadgen_webhook, name="meta-leadgen-webhook"),
]
