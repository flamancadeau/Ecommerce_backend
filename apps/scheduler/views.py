from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

from .models import ScheduledJob
from apps.audit.models import IdempotencyKey
from apps.audit.services import IdempotencyService
from .serializers import (
    IdempotencyKeySerializer,
    ScheduledJobSerializer,
    CreateScheduledJobSerializer,
    IdempotencyRequestSerializer,
)
from .services import SchedulerService

logger = logging.getLogger(__name__)


class IdempotencyKeyViewSet(viewsets.ModelViewSet):
    queryset = IdempotencyKey.objects.all()
    serializer_class = IdempotencyKeySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "key"]
    search_fields = ["key", "request_hash"]
    ordering_fields = ["created_at", "expires_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            return queryset.none()
        return queryset

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        key = self.get_object()
        if key.status != IdempotencyKey.Status.PROCESSING:
            return Response(
                {"status": False, "message": f"Key is already {key.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        IdempotencyService.complete_key(key, 200, request.data.get("response"))
        return Response(
            {
                "status": True,
                "message": "Key completed",
                "data": IdempotencyKeySerializer(key).data,
            }
        )

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        key = self.get_object()
        IdempotencyService.mark_failed(key)
        return Response({"status": True, "message": "Key marked as failed"})

    @action(detail=False, methods=["post"])
    def verify(self, request):
        serializer = IdempotencyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_val = serializer.validated_data["key"]
        expires_hrs = serializer.validated_data["expires_in_hours"]

        idem_key, created = IdempotencyService.verify_or_create(
            key=key_val,
            request_path=request.path,
            request_data=request.data,
            expires_in_hours=expires_hrs,
        )

        return Response(
            {
                "status": True,
                "data": {
                    "idempotent": True,
                    "status": idem_key.status,
                    "key_id": str(idem_key.id),
                    "created": created,
                },
            }
        )


class ScheduledJobViewSet(viewsets.ModelViewSet):
    queryset = ScheduledJob.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["job_type", "status", "scheduled_at"]
    search_fields = ["job_type", "error"]
    ordering_fields = ["scheduled_at", "created_at", "executed_at"]
    ordering = ["scheduled_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateScheduledJobSerializer
        return ScheduledJobSerializer

    def perform_create(self, serializer):
        SchedulerService.create_job(
            job_type=serializer.validated_data["job_type"],
            scheduled_at=serializer.validated_data["scheduled_at"],
            payload=serializer.validated_data.get("payload"),
        )

    @action(detail=True, methods=["post"])
    def execute_now(self, request, pk=None):
        job = self.get_object()
        try:
            SchedulerService.execute_now(job)
            return Response({"status": True, "message": "Job execution started"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        try:
            SchedulerService.cancel_job(job)
            return Response({"status": True, "message": "Job cancelled"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        job = self.get_object()
        try:
            SchedulerService.retry_job(job)
            return Response({"status": True, "message": "Job retry scheduled"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        now = timezone.now()
        queryset = self.get_queryset().filter(
            status=ScheduledJob.Status.PENDING, scheduled_at__lt=now
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def schedule_campaign_activation(self, request):
        campaign_id = request.data.get("campaign_id")
        activate_at = request.data.get("activate_at")
        try:
            job = SchedulerService.schedule_campaign_activation(
                campaign_id, activate_at
            )
            return Response({"status": True, "data": ScheduledJobSerializer(job).data})
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def system_status(request):
    now = timezone.now()
    return Response(
        {
            "status": True,
            "data": {
                "jobs": {
                    "total": ScheduledJob.objects.count(),
                    "pending": ScheduledJob.objects.filter(status="pending").count(),
                },
                "timestamp": now.isoformat(),
            },
        }
    )


class IdempotencyMiddlewareView(APIView):
    """Refactored to use central service."""

    permission_classes = [IsAuthenticated]

    def process_request(self, request, business_logic_function):
        key = request.headers.get("X-Idempotency-Key")
        if not key:
            return Response(business_logic_function())

        idem_key, created = IdempotencyService.verify_or_create(
            key=key, request_path=request.path, request_data=request.data
        )

        if not created:
            if idem_key.status == IdempotencyKey.Status.COMPLETED:
                return Response(idem_key.response_body)
            if idem_key.status == IdempotencyKey.Status.PROCESSING:
                return Response({"status": False, "message": "Processing"}, status=409)

        try:
            result = business_logic_function()
            IdempotencyService.complete_key(idem_key, 200, result)
            return Response(result)
        except Exception as e:
            IdempotencyService.mark_failed(idem_key)
            return Response({"status": False, "message": str(e)}, status=500)
