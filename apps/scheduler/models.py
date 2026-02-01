from django.db import models
import uuid
from django.utils import timezone


class IdempotencyKey(models.Model):
    """Idempotency key for safe retries."""

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

    def __str__(self):
        return f"IdempotencyKey: {self.key[:20]}..."

    @property
    def is_expired(self):
        return self.expires_at < timezone.now()


class ScheduledJob(models.Model):
    """Scheduled background jobs."""

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

    def __str__(self):
        return f"{self.job_type} scheduled for {self.scheduled_at}"

    @property
    def is_overdue(self):
        return self.status == "pending" and self.scheduled_at < timezone.now()

    def should_retry(self):
        return self.status == "failed" and self.retry_count < self.max_retries
