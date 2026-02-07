from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import ScheduledJob
from apps.audit.models import IdempotencyKey

from .serializers import (
    IdempotencyKeySerializer,
    ScheduledJobSerializer,
    CreateScheduledJobSerializer,
    IdempotencyRequestSerializer,
    CampaignActivationSerializer,
    CreateIdempotencyKeySerializer,
)

logger = logging.getLogger(__name__)


class IdempotencyKeyViewSet(viewsets.ModelViewSet):
    """
    API for managing Idempotency Keys.
    Keys are primarily used to ensure request safety.
    """

    queryset = IdempotencyKey.objects.all()
    serializer_class = IdempotencyKeySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "key"]
    search_fields = ["key", "request_hash"]
    ordering_fields = ["created_at", "expires_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateIdempotencyKeySerializer
        return IdempotencyKeySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            return queryset.none()
        return queryset

    @swagger_auto_schema(
        operation_description="Create a new idempotency key manually or let the system auto-generate one.",
        request_body=CreateIdempotencyKeySerializer,
        responses={201: IdempotencyKeySerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = CreateIdempotencyKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_val = serializer.validated_data.get("key")
        if not key_val:
            key_val = IdempotencyKey.objects.generate_key()

        instance = IdempotencyKey.objects.create(
            key=key_val,
            status=serializer.validated_data.get(
                "status", IdempotencyKey.Status.PROCESSING
            ),
            response_body=serializer.validated_data.get("response_body"),
            expires_at=serializer.validated_data.get("expires_at")
            or (timezone.now() + timezone.timedelta(hours=24)),
        )

        full_serializer = IdempotencyKeySerializer(
            instance, data=request.data, partial=True
        )
        full_serializer.is_valid()
        full_serializer.save()

        return Response(
            {
                "status": True,
                "message": "Idempotency key created successfully",
                "data": IdempotencyKeySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        operation_description="Delete an idempotency key by its ID. Only staff users can perform this action.",
        responses={
            200: openapi.Response(
                description="Idempotency key deleted successfully",
                examples={
                    "application/json": {
                        "status": True,
                        "message": "Idempotency key deleted successfully",
                        "data": {
                            "deleted_key_id": "123e4567-e89b-12d3-a456-426614174000",
                            "deleted_key": "idem_key_abc123xyz",
                        },
                    }
                },
            ),
            403: openapi.Response(
                description="Permission denied - staff access required"
            ),
            404: openapi.Response(description="Idempotency key not found"),
        },
    )
    def destroy(self, request, *args, **kwargs):
        """Delete an idempotency key"""
        instance = self.get_object()
        key_id = instance.id
        key_value = instance.key

        self.perform_destroy(instance)

        return Response(
            {
                "status": True,
                "message": "Idempotency key deleted successfully",
                "data": {
                    "deleted_key_id": str(key_id),
                    "deleted_key": key_value,
                },
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="Mark an idempotency key as successfully completed",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "response": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Optional response body to cache",
                )
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        key = self.get_object()
        if key.status != IdempotencyKey.Status.PROCESSING:
            return Response(
                {"status": False, "message": f"Key is already {key.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key.mark_completed(200, request.data.get("response"))
        return Response(
            {
                "status": True,
                "message": "Key completed",
                "data": IdempotencyKeySerializer(key).data,
            }
        )

    @swagger_auto_schema(
        operation_description="Mark an idempotency key as failed and record the reason.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "reason": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Brief explanation of failure"
                ),
                "error_details": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Detailed error object for debugging",
                ),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        key = self.get_object()

        error_data = {
            "reason": request.data.get("reason", "Manual failure trigger"),
            "details": request.data.get("error_details", {}),
            "failed_at": timezone.now().isoformat(),
        }

        key.mark_failed()

        key.response_body = error_data
        key.response_code = 500
        key.save()

        return Response(
            {
                "status": True,
                "message": "Key marked as failed and error recorded",
                "error_stored": error_data,
            }
        )

    @swagger_auto_schema(
        operation_description="Claim, Verify, or Create a new idempotency key for a specific business flow.",
        request_body=IdempotencyRequestSerializer,
    )
    @action(detail=False, methods=["post"], url_path="verify")
    def verify(self, request):
        serializer = IdempotencyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_val = serializer.validated_data["key"]
        expires_hrs = serializer.validated_data["expires_in_hours"]

        idem_key, created = IdempotencyKey.objects.verify_or_create(
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

    """
    API for managing Idempotency Keys.
    Keys are primarily used to ensure request safety.
    """

    queryset = IdempotencyKey.objects.all()
    serializer_class = IdempotencyKeySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]  # Added "delete"
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "key"]
    search_fields = ["key", "request_hash"]
    ordering_fields = ["created_at", "expires_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateIdempotencyKeySerializer
        return IdempotencyKeySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            return queryset.none()
        return queryset

    @swagger_auto_schema(
        operation_description="Create a new idempotency key manually or let the system auto-generate one.",
        request_body=CreateIdempotencyKeySerializer,
        responses={201: IdempotencyKeySerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = CreateIdempotencyKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_val = serializer.validated_data.get("key")
        if not key_val:
            key_val = IdempotencyKey.objects.generate_key()

        instance = IdempotencyKey.objects.create(
            key=key_val,
            status=serializer.validated_data.get(
                "status", IdempotencyKey.Status.PROCESSING
            ),
            response_body=serializer.validated_data.get("response_body"),
            expires_at=serializer.validated_data.get("expires_at")
            or (timezone.now() + timezone.timedelta(hours=24)),
        )

        full_serializer = IdempotencyKeySerializer(
            instance, data=request.data, partial=True
        )
        full_serializer.is_valid()
        full_serializer.save()

        return Response(
            {
                "status": True,
                "message": "Idempotency key created successfully",
                "data": IdempotencyKeySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        operation_description="Delete an idempotency key by its ID. Only staff users can perform this action.",
        responses={
            204: openapi.Response(description="Idempotency key deleted successfully"),
            403: openapi.Response(
                description="Permission denied - staff access required"
            ),
            404: openapi.Response(description="Idempotency key not found"),
        },
    )
    def destroy(self, request, *args, **kwargs):
        """Delete an idempotency key"""
        instance = self.get_object()
        key_id = instance.id
        key_value = instance.key

        self.perform_destroy(instance)

        return Response(
            {
                "status": True,
                "message": "Idempotency key deleted successfully",
                "data": {
                    "deleted_key_id": str(key_id),
                    "deleted_key": key_value,
                },
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="Mark an idempotency key as successfully completed",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "response": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Optional response body to cache",
                )
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        key = self.get_object()
        if key.status != IdempotencyKey.Status.PROCESSING:
            return Response(
                {"status": False, "message": f"Key is already {key.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key.mark_completed(200, request.data.get("response"))
        return Response(
            {
                "status": True,
                "message": "Key completed",
                "data": IdempotencyKeySerializer(key).data,
            }
        )

    @swagger_auto_schema(
        operation_description="Mark an idempotency key as failed and record the reason.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "reason": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Brief explanation of failure"
                ),
                "error_details": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Detailed error object for debugging",
                ),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        key = self.get_object()

        error_data = {
            "reason": request.data.get("reason", "Manual failure trigger"),
            "details": request.data.get("error_details", {}),
            "failed_at": timezone.now().isoformat(),
        }

        key.mark_failed()

        key.response_body = error_data
        key.response_code = 500
        key.save()

        return Response(
            {
                "status": True,
                "message": "Key marked as failed and error recorded",
                "error_stored": error_data,
            }
        )

    @swagger_auto_schema(
        operation_description="Claim, Verify, or Create a new idempotency key for a specific business flow.",
        request_body=IdempotencyRequestSerializer,
    )
    @action(detail=False, methods=["post"], url_path="verify")
    def verify(self, request):
        serializer = IdempotencyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key_val = serializer.validated_data["key"]
        expires_hrs = serializer.validated_data["expires_in_hours"]

        idem_key, created = IdempotencyKey.objects.verify_or_create(
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
    """
    API for managing and monitoring scheduled background jobs.
    """

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

    @swagger_auto_schema(
        operation_description="Create a new scheduled background job",
        request_body=CreateScheduledJobSerializer,
        responses={201: ScheduledJobSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = CreateScheduledJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job = ScheduledJob.objects.create_job(
            job_type=serializer.validated_data["job_type"],
            scheduled_at=serializer.validated_data["scheduled_at"],
            payload=serializer.validated_data.get("payload"),
        )

        response_serializer = ScheduledJobSerializer(job)
        return Response(
            {
                "status": True,
                "message": "Job created and enqueued successfully",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):

        pass

    @swagger_auto_schema(
        operation_description="Force immediate execution of a pending job"
    )
    @action(detail=True, methods=["post"], url_path="execute-now")
    def execute_now(self, request, pk=None):
        job = self.get_object()
        try:
            ScheduledJob.objects.execute_now(job)
            return Response({"status": True, "message": "Job execution started"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @swagger_auto_schema(operation_description="Cancel a scheduled job")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        job = self.get_object()
        try:
            ScheduledJob.objects.cancel_job(job)
            return Response({"status": True, "message": "Job cancelled"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @swagger_auto_schema(operation_description="Retry a failed or cancelled job")
    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        job = self.get_object()
        try:
            ScheduledJob.objects.retry_job(job)
            return Response({"status": True, "message": "Job retry scheduled"})
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

    @swagger_auto_schema(
        operation_description="Retrieve all jobs that missed their scheduled time"
    )
    @action(detail=False, methods=["get"], url_path="overdue")
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

    @swagger_auto_schema(
        operation_description="Shortcut to schedule a promotion campaign activation",
        request_body=CampaignActivationSerializer,
        responses={201: ScheduledJobSerializer},
    )
    @action(detail=False, methods=["post"], url_path="schedule-campaign-activation")
    def schedule_campaign_activation(self, request):
        serializer = CampaignActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        campaign_id = serializer.validated_data["campaign_id"]
        activate_at = serializer.validated_data["activate_at"]
        try:
            job = ScheduledJob.objects.schedule_campaign_activation(
                campaign_id, activate_at
            )
            return Response(
                {
                    "status": True,
                    "message": f"Campaign activation job scheduled for {job.scheduled_at}",
                    "data": ScheduledJobSerializer(job).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {
                    "status": False,
                    "message": f"Failed to schedule activation: {str(e)}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


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

        idem_key, created = IdempotencyKey.objects.verify_or_create(
            key=key, request_path=request.path, request_data=request.data
        )

        if not created:
            if idem_key.status == IdempotencyKey.Status.COMPLETED:
                return Response(idem_key.response_body)
            if idem_key.status == IdempotencyKey.Status.PROCESSING:
                return Response({"status": False, "message": "Processing"}, status=409)

        try:
            result = business_logic_function()
            idem_key.mark_completed(200, result)
            return Response(result)
        except Exception as e:
            idem_key.mark_failed()
            return Response({"status": False, "message": str(e)}, status=500)
