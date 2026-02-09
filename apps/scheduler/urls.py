from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(
    r"idempotency-keys", views.IdempotencyKeyViewSet, basename="idempotency-key"
)
router.register(r"scheduled-jobs", views.ScheduledJobViewSet, basename="scheduled-job")

urlpatterns = [
    path("", include(router.urls)),
    path("system-status/", views.system_status, name="system-status"),
]
