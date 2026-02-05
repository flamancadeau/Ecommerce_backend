from rest_framework import serializers
from .models import ScheduledJob
from apps.audit.models import IdempotencyKey
from datetime import datetime
from django.utils import timezone


class IdempotencyKeySerializer(serializers.ModelSerializer):

    is_expired = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    order_number = serializers.CharField(source="order.order_number", read_only=True)
    key = serializers.CharField(required=False, allow_blank=True)
    request_hash = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = IdempotencyKey
        fields = [
            "id",
            "key",
            "order",
            "order_number",
            "request_hash",
            "response_code",
            "response_body",
            "status",
            "status_display",
            "created_at",
            "expires_at",
            "is_expired",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "created_at",
            "is_expired",
            "status_display",
        ]

    def validate(self, data):
        # Best Practice: Auto-calculate hash if not provided but body is
        if not data.get("request_hash") and data.get("response_body"):
            from apps.audit.services import IdempotencyService

            # We use the response body as a proxy for the request if nothing else is provided
            data["request_hash"] = IdempotencyService.get_request_hash(
                data.get("response_body")
            )

        # Automatic Order Linking
        if not data.get("order") and data.get("response_body"):
            body = data.get("response_body")
            order_num = body.get("order_id") or body.get("order_number")
            if order_num:
                from apps.orders.models import Order

                try:
                    order_obj = Order.objects.get(order_number=order_num)
                    data["order"] = order_obj
                except Order.DoesNotExist:
                    pass

        if "expires_at" in data and data["expires_at"] <= timezone.now():
            raise serializers.ValidationError(
                {"expires_at": "Expiration time must be in the future."}
            )

        if self.instance and "status" in data:
            if self.instance.status == "completed" and data["status"] != "completed":
                raise serializers.ValidationError(
                    {"status": "Completed keys cannot change status."}
                )

        return data

    def create(self, validated_data):
        """Standardize the creation of idempotency keys."""
        if "key" not in validated_data:
            from apps.audit.services import IdempotencyService

            validated_data["key"] = IdempotencyService.generate_key()

        if "expires_at" not in validated_data:
            # Default expiration: 24 hours from now
            validated_data["expires_at"] = timezone.now() + timezone.timedelta(hours=24)

        return super().create(validated_data)


class ScheduledJobSerializer(serializers.ModelSerializer):

    is_overdue = serializers.BooleanField(read_only=True)
    job_type_display = serializers.CharField(
        source="get_job_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    can_retry = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScheduledJob
        fields = [
            "id",
            "job_type",
            "job_type_display",
            "scheduled_at",
            "executed_at",
            "status",
            "status_display",
            "payload",
            "result",
            "error",
            "retry_count",
            "max_retries",
            "created_at",
            "updated_at",
            "is_overdue",
            "can_retry",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_overdue",
            "can_retry",
            "job_type_display",
            "status_display",
        ]

    def validate(self, data):
        """Validate scheduled job data."""
        # Ensure scheduled_at is in the future for new jobs
        if self.instance is None and "scheduled_at" in data:
            if data["scheduled_at"] <= timezone.now():
                raise serializers.ValidationError(
                    {"scheduled_at": "Scheduled time must be in the future."}
                )

        if "executed_at" in data and "scheduled_at" in data:
            if data["executed_at"] < data["scheduled_at"]:
                raise serializers.ValidationError(
                    {"executed_at": "Execution time cannot be before scheduled time."}
                )

        if "retry_count" in data and "max_retries" in data:
            if data["retry_count"] > data["max_retries"]:
                raise serializers.ValidationError(
                    {
                        "retry_count": f'Retry count cannot exceed max retries ({data["max_retries"]}).'
                    }
                )

        return data

    def validate_payload(self, value):

        if not isinstance(value, dict):
            raise serializers.ValidationError("Payload must be a JSON object.")
        return value


class CreateScheduledJobSerializer(serializers.ModelSerializer):

    class Meta:
        model = ScheduledJob
        fields = ["job_type", "scheduled_at", "payload"]

    def validate_scheduled_at(self, value):
        """Ensure scheduled time is in the future."""
        if value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value

    def create(self, validated_data):
        """Create scheduled job with default values."""
        validated_data["status"] = "pending"
        validated_data["max_retries"] = 3
        validated_data["retry_count"] = 0
        return super().create(validated_data)


class IdempotencyRequestSerializer(serializers.Serializer):

    key = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Unique idempotency key for this request",
    )
    expires_in_hours = serializers.IntegerField(
        min_value=1,
        max_value=168,
        default=24,
        help_text="Number of hours until the idempotency key expires",
    )
