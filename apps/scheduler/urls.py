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
    path(
        "idempotency/verify/",
        views.IdempotencyKeyViewSet.as_view({"post": "verify"}),
        name="idempotency-verify",
    ),
    path(
        "scheduled-jobs/<uuid:pk>/execute-now/",
        views.ScheduledJobViewSet.as_view({"post": "execute_now"}),
        name="execute-job-now",
    ),
    path(
        "scheduled-jobs/<uuid:pk>/cancel/",
        views.ScheduledJobViewSet.as_view({"post": "cancel"}),
        name="cancel-job",
    ),
    path(
        "scheduled-jobs/<uuid:pk>/retry/",
        views.ScheduledJobViewSet.as_view({"post": "retry"}),
        name="retry-job",
    ),
    path(
        "scheduled-jobs/overdue/",
        views.ScheduledJobViewSet.as_view({"get": "overdue"}),
        name="overdue-jobs",
    ),
    path(
        "scheduled-jobs/schedule-campaign-activation/",
        views.ScheduledJobViewSet.as_view({"post": "schedule_campaign_activation"}),
        name="schedule-campaign-activation",
    ),
]
