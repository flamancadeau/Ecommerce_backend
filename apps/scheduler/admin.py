from django.contrib import admin
from django.utils.html import format_html
from .models import ScheduledJob


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
