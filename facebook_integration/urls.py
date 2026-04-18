from django.urls import path

from facebook_integration.views import SyncFormsView, SyncPagesView, oauth_callback, oauth_start


urlpatterns = [
    path("oauth/start/", oauth_start, name="facebook-oauth-start"),
    path("oauth/callback/", oauth_callback, name="facebook-oauth-callback"),
    path("pages/", SyncPagesView.as_view(), name="facebook-pages-sync"),
    path("pages/<str:page_id>/forms/", SyncFormsView.as_view(), name="facebook-forms-sync"),
]
