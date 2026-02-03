from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import hashlib
import json
import logging

from .models import IdempotencyKey, ScheduledJob
from .serializers import (
    IdempotencyKeySerializer,
    ScheduledJobSerializer,
    CreateScheduledJobSerializer,
    IdempotencyRequestSerializer,
)
from .tasks import execute_scheduled_job

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
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()

        if not self.request.user.is_staff:

            return queryset.none()

        return queryset

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark an idempotency key as completed with a response."""
        key = self.get_object()

        if key.status != "processing":
            return Response(
                {
                    "status": False,
                    "message": f"Key is already {key.status}",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = request.data.get("response")

        key.response = response_data
        key.status = "completed"
        key.save()

        logger.info(f"Idempotency key {key.key[:20]}... marked as completed")

        return Response(
            {
                "status": True,
                "message": "Idempotency key completed successfully",
                "data": IdempotencyKeySerializer(key).data,
            }
        )

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        """Mark an idempotency key as failed."""
        key = self.get_object()

        if key.status != "processing":
            return Response(
                {
                    "status": False,
                    "message": f"Key is already {key.status}",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        error_message = request.data.get("error", "Unknown error")

        key.status = "failed"
        key.save()

        logger.warning(
            f"Idempotency key {key.key[:20]}... marked as failed: {error_message}"
        )

        return Response(
            {
                "status": True,
                "message": "Idempotency key marked as failed",
                "data": IdempotencyKeySerializer(key).data,
            }
        )

    @action(detail=False, methods=["post"])
    def verify(self, request):
        """Verify if a request can be processed idempotently."""
        serializer = IdempotencyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_value = serializer.validated_data["key"]
        expires_in_hours = serializer.validated_data["expires_in_hours"]

        request_body = json.dumps(request.data, sort_keys=True)
        request_hash = hashlib.sha256(request_body.encode()).hexdigest()

        existing_key = IdempotencyKey.objects.filter(key=key_value).first()

        if existing_key:
            if existing_key.status == "completed":

                return Response(
                    {
                        "status": True,
                        "message": "Request already processed",
                        "data": {
                            "idempotent": True,
                            "status": "completed",
                            "response": existing_key.response,
                        },
                    }
                )
            elif existing_key.status == "processing":

                return Response(
                    {
                        "status": True,
                        "message": "Request is being processed",
                        "data": {"idempotent": True, "status": "processing"},
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            elif existing_key.status == "failed":

                existing_key.status = "processing"
                existing_key.save()

                return Response(
                    {
                        "status": True,
                        "message": "Retrying previously failed request",
                        "data": {
                            "idempotent": True,
                            "status": "retrying",
                            "key_id": str(existing_key.id),
                        },
                    }
                )

        new_key = IdempotencyKey.objects.create(
            key=key_value,
            request_hash=request_hash,
            status="processing",
            expires_at=timezone.now() + timedelta(hours=expires_in_hours),
        )

        logger.info(f"Created new idempotency key: {key_value[:20]}...")

        return Response(
            {
                "status": True,
                "message": "New idempotency key created",
                "data": {
                    "idempotent": True,
                    "status": "processing",
                    "key_id": str(new_key.id),
                    "expires_at": new_key.expires_at.isoformat(),
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
        """Use different serializer for creation vs retrieval."""
        if self.action == "create":
            return CreateScheduledJobSerializer
        return ScheduledJobSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()

        if not self.request.user.is_staff:

            queryset = queryset.filter(job_type="report_generation")

        return queryset

    def perform_create(self, serializer):

        job = serializer.save()

        logger.info(f"Scheduled job created: {job.job_type} at {job.scheduled_at}")

        execute_scheduled_job.apply_async(args=[str(job.id)], eta=job.scheduled_at)

    @action(detail=True, methods=["post"])
    def execute_now(self, request, pk=None):

        job = self.get_object()

        if job.status not in ["pending", "failed"]:
            return Response(
                {
                    "status": False,
                    "message": f"Job is already {job.status}",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        execute_scheduled_job.delay(str(job.id))

        return Response(
            {
                "status": True,
                "message": "Job execution started",
                "data": {
                    "job_id": str(job.id),
                    "job_type": job.job_type,
                    "scheduled_at": job.scheduled_at.isoformat(),
                },
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):

        job = self.get_object()

        if job.status not in ["pending", "running"]:
            return Response(
                {
                    "status": False,
                    "message": f"Cannot cancel job with status: {job.status}",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.status = "cancelled"
        job.save()

        logger.info(f"Cancelled scheduled job: {job.job_type}")

        return Response(
            {
                "status": True,
                "message": "Job cancelled successfully",
                "data": ScheduledJobSerializer(job).data,
            }
        )

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):

        job = self.get_object()

        if job.status != "failed":
            return Response(
                {
                    "status": False,
                    "message": f"Can only retry failed jobs (current: {job.status})",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not job.should_retry():
            return Response(
                {
                    "status": False,
                    "message": f"Maximum retries ({job.max_retries}) exceeded",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.status = "pending"
        job.scheduled_at = timezone.now()
        job.save()

        execute_scheduled_job.delay(str(job.id))

        return Response(
            {
                "status": True,
                "message": "Job retry scheduled",
                "data": ScheduledJobSerializer(job).data,
            }
        )

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get all overdue scheduled jobs."""
        overdue_jobs = ScheduledJob.objects.filter(
            status="pending", scheduled_at__lt=timezone.now()
        )

        serializer = ScheduledJobSerializer(overdue_jobs, many=True)

        return Response(
            {
                "status": True,
                "message": f"Found {overdue_jobs.count()} overdue jobs",
                "data": serializer.data,
            }
        )

    @action(detail=False, methods=["post"])
    def schedule_campaign_activation(self, request):
        """Schedule a campaign activation job."""
        from apps.promotions.models import Campaign

        campaign_id = request.data.get("campaign_id")
        activate_at = request.data.get("activate_at")

        if not campaign_id or not activate_at:
            return Response(
                {
                    "status": False,
                    "message": "campaign_id and activate_at are required",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign = Campaign.objects.get(id=campaign_id)
            activate_time = timezone.datetime.fromisoformat(
                activate_at.replace("Z", "+00:00")
            )

            if activate_time <= timezone.now():
                return Response(
                    {
                        "status": False,
                        "message": "Activation time must be in the future",
                        "data": {},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            job = ScheduledJob.objects.create(
                job_type="campaign_activation",
                scheduled_at=activate_time,
                status="pending",
                payload={
                    "campaign_id": str(campaign.id),
                    "campaign_code": campaign.code,
                    "action": "activate",
                },
            )

            execute_scheduled_job.apply_async(args=[str(job.id)], eta=activate_time)

            logger.info(
                f"Scheduled campaign activation: {campaign.code} at {activate_time}"
            )

            return Response(
                {
                    "status": True,
                    "message": "Campaign activation scheduled",
                    "data": ScheduledJobSerializer(job).data,
                }
            )

        except Campaign.DoesNotExist:
            return Response(
                {"status": False, "message": "Campaign not found", "data": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError:
            return Response(
                {
                    "status": False,
                    "message": "Invalid date format. Use ISO format (e.g., 2024-01-30T10:00:00Z)",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def system_status(request):
    """Get system status including background job statistics."""
    now = timezone.now()

    total_jobs = ScheduledJob.objects.count()
    pending_jobs = ScheduledJob.objects.filter(status="pending").count()
    overdue_jobs = ScheduledJob.objects.filter(
        status="pending", scheduled_at__lt=now
    ).count()
    failed_jobs = ScheduledJob.objects.filter(status="failed").count()

    total_keys = IdempotencyKey.objects.count()
    active_keys = IdempotencyKey.objects.filter(
        status="processing", expires_at__gt=now
    ).count()
    expired_keys = IdempotencyKey.objects.filter(expires_at__lte=now).count()

    return Response(
        {
            "status": True,
            "message": "System status retrieved",
            "data": {
                "jobs": {
                    "total": total_jobs,
                    "pending": pending_jobs,
                    "overdue": overdue_jobs,
                    "failed": failed_jobs,
                },
                "idempotency_keys": {
                    "total": total_keys,
                    "active": active_keys,
                    "expired": expired_keys,
                },
                "timestamp": now.isoformat(),
                "uptime": "System is running",
            },
        }
    )


class IdempotencyMiddlewareView(APIView):

    permission_classes = [IsAuthenticated]

    def process_request(self, request, business_logic_function):

        idempotency_key = request.headers.get("X-Idempotency-Key")

        if not idempotency_key:

            try:
                result = business_logic_function()
                return Response(result)
            except Exception as e:
                return Response(
                    {"status": False, "message": str(e), "data": {}},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        request_body = (
            json.dumps(request.data, sort_keys=True) if request.data else "{}"
        )
        request_hash = hashlib.sha256(request_body.encode()).hexdigest()

        with transaction.atomic():

            existing_key = (
                IdempotencyKey.objects.filter(key=idempotency_key)
                .select_for_update()
                .first()
            )

            if existing_key:
                if existing_key.status == "completed":

                    return Response(existing_key.response)
                elif existing_key.status == "processing":

                    return Response(
                        {
                            "status": False,
                            "message": "Request is still being processed",
                            "data": {},
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                elif existing_key.status == "failed":

                    existing_key.status = "processing"
                    existing_key.save()
                else:

                    return Response(
                        {
                            "status": False,
                            "message": f"Idempotency key in invalid state: {existing_key.status}",
                            "data": {},
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:

                existing_key = IdempotencyKey.objects.create(
                    key=idempotency_key,
                    request_hash=request_hash,
                    status="processing",
                    expires_at=timezone.now() + timedelta(hours=24),
                )

            try:

                result = business_logic_function()

                existing_key.response = result
                existing_key.status = "completed"
                existing_key.save()

                return Response(result)

            except Exception as e:

                existing_key.status = "failed"
                existing_key.save()

                logger.error(
                    f"Idempotent request failed: {idempotency_key[:20]}... - {str(e)}"
                )

                return Response(
                    {"status": False, "message": str(e), "data": {}},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
