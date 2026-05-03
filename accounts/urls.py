from django.urls import path

from accounts.views import MeView, accept_invitation_view


urlpatterns = [
    path("me/", MeView.as_view(), name="account-me"),
    path("invitations/<str:token>/accept/", accept_invitation_view, name="account-invitation-accept"),
]
