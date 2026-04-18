from django.urls import path

from accounts.views import MeView


urlpatterns = [
    path("me/", MeView.as_view(), name="account-me"),
]
