from django.db import models
import uuid
from django.utils import timezone


class IdempotencyKey(models.Model):

    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True, db_index=True)
    request_hash = models.CharField(
        max_length=64, db_index=True, help_text="SHA256 hash of request"
    )
    response = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["request_hash"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "Idempotency Key"
        verbose_name_plural = "Idempotency Keys"

    def __str__(self):
        return f"IdempotencyKey: {self.key[:20]}..."

    @property
    def is_expired(self):

        if self.expires_at is None:
            return False
        return self.expires_at < timezone.now()


class ScheduledJob(models.Model):

    JOB_TYPE_CHOICES = [
        ("campaign_activation", "Campaign Activation"),
        ("campaign_expiration", "Campaign Expiration"),
        ("reservation_expiry", "Reservation Expiry"),
        ("inbound_receipt", "Inbound Receipt Processing"),
        ("price_update", "Price Update"),
        ("inventory_reorder", "Inventory Reorder"),
        ("data_cleanup", "Data Cleanup"),
        ("report_generation", "Report Generation"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES)
    scheduled_at = models.DateTimeField()
    executed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["job_type", "status"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Scheduled Job"
        verbose_name_plural = "Scheduled Jobs"

    def __str__(self):
        return f"{self.get_job_type_display()} scheduled for {self.scheduled_at}"

    @property
    def is_overdue(self):
        """
        Check if the job is overdue (past scheduled time and still pending).

        Returns:
            bool: True if job is pending and past scheduled time, False otherwise
        """
        # FIX: Add null check to prevent TypeError when scheduled_at is None
        # This happens when creating new objects in Django admin
        if self.scheduled_at is None:
            return False
        return self.status == "pending" and self.scheduled_at < timezone.now()

    @property
    def can_retry(self):

        return self.status == "failed" and self.retry_count < self.max_retries

    def should_retry(self):

        return self.can_retry

    def mark_as_running(self):
        """Mark the job as currently running."""
        self.status = "running"
        self.save(update_fields=["status", "updated_at"])

    def mark_as_completed(self, result=None):

        self.status = "completed"
        self.executed_at = timezone.now()
        if result is not None:
            self.result = result
        self.save(update_fields=["status", "executed_at", "result", "updated_at"])

    def mark_as_failed(self, error_message=""):

        self.status = "failed"
        self.executed_at = timezone.now()
        self.error = error_message
        self.retry_count += 1
        self.save(
            update_fields=[
                "status",
                "executed_at",
                "error",
                "retry_count",
                "updated_at",
            ]
        )

    def mark_as_cancelled(self):
        """Mark the job as cancelled."""
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])
