from rest_framework.routers import DefaultRouter

from automations.views import AutomationRuleViewSet, MessageTemplateViewSet


router = DefaultRouter()
router.register("templates", MessageTemplateViewSet, basename="template")
router.register("rules", AutomationRuleViewSet, basename="rule")

urlpatterns = router.urls
