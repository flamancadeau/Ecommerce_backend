import uuid
from django.db import models
from django.utils import timezone


class ScheduledJob(models.Model):

    class JobType(models.TextChoices):
        CAMPAIGN_ACTIVATION = "campaign_activation", "Campaign Activation"
        CAMPAIGN_EXPIRATION = "campaign_expiration", "Campaign Expiration"
        RESERVATION_EXPIRY = "reservation_expiry", "Reservation Expiry"
        INBOUND_RECEIPT = "inbound_receipt", "Inbound Receipt Processing"
        PRICE_UPDATE = "price_update", "Price Update"
        INVENTORY_REORDER = "inventory_reorder", "Inventory Reorder"
        DATA_CLEANUP = "data_cleanup", "Data Cleanup"
        REPORT_GENERATION = "report_generation", "Report Generation"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=50, choices=JobType.choices)
    scheduled_at = models.DateTimeField()
    executed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
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
    def is_overdue(self) -> bool:
        """Check if the job is overdue (past scheduled time and still pending)."""
        if self.scheduled_at is None:
            return False
        return self.status == self.Status.PENDING and self.scheduled_at < timezone.now()

    @property
    def can_retry(self) -> bool:
        return self.status == self.Status.FAILED and self.retry_count < self.max_retries

    def should_retry(self) -> bool:
        return self.can_retry

    def mark_as_running(self):
        self.status = self.Status.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def mark_as_completed(self, result=None):
        self.status = self.Status.COMPLETED
        self.executed_at = timezone.now()
        if result is not None:
            self.result = result
        self.save(update_fields=["status", "executed_at", "result", "updated_at"])

    def mark_as_failed(self, error_message=""):
        self.status = self.Status.FAILED
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
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])
