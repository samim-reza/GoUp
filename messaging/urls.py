from rest_framework.routers import DefaultRouter

from messaging.views import MessageLogViewSet


router = DefaultRouter()
router.register("logs", MessageLogViewSet, basename="message-log")

urlpatterns = router.urls
