from django.contrib import admin
from django.utils.html import format_html
from .models import IdempotencyKey, ScheduledJob


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = (
        "key_short",
        "status",
        "created_at",
        "expires_at",
        "is_expired",
        "has_response",
    )
    list_filter = ("status", "created_at")
    search_fields = ("key", "request_hash")
    readonly_fields = ("created_at", "is_expired", "has_response")

    def key_short(self, obj):
        return obj.key[:20] + "..." if len(obj.key) > 20 else obj.key

    key_short.short_description = "Key"

    def is_expired(self, obj):
        return obj.is_expired

    is_expired.boolean = True

    def has_response(self, obj):
        return obj.response is not None

    has_response.boolean = True


@admin.register(ScheduledJob)
class ScheduledJobAdmin(admin.ModelAdmin):
    list_display = (
        "job_type",
        "scheduled_at",
        "executed_at",
        "status",
        "retry_count",
        "is_overdue",
        "has_error",
    )
    list_filter = ("job_type", "status", "scheduled_at")
    search_fields = ("job_type", "error")
    readonly_fields = ("created_at", "updated_at", "is_overdue", "has_error")

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True

    def has_error(self, obj):
        return bool(obj.error)

    has_error.boolean = True
