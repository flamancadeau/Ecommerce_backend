import uuid
from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ScheduledJobManager(models.Manager):
    def create_job(self, job_type, scheduled_at, payload=None, max_retries=3):
        """Standard way to create and enqueue a job."""
        job = self.create(
            job_type=job_type,
            scheduled_at=scheduled_at,
            payload=payload or {},
            max_retries=max_retries,
            status=self.model.Status.PENDING,
        )

        from .tasks import execute_scheduled_job

        execute_scheduled_job.apply_async(args=[str(job.id)], eta=scheduled_at)

        logger.info(f"Scheduled job created: {job_type} for {scheduled_at}")
        return job

    def execute_now(self, job):
        """Immediately trigger a job execution."""
        if job.status not in [self.model.Status.PENDING, self.model.Status.FAILED]:
            raise ValueError(
                f"Job is in status '{job.status}' and cannot be executed now."
            )

        from .tasks import execute_scheduled_job

        execute_scheduled_job.delay(str(job.id))
        logger.info(f"Triggered immediate execution for job {job.id}")

    def cancel_job(self, job):
        """Cancel a pending or running job."""
        if job.status not in [self.model.Status.PENDING, self.model.Status.RUNNING]:
            raise ValueError(f"Cannot cancel job with status: {job.status}")

        job.status = self.model.Status.CANCELLED
        job.save()
        logger.info(f"Cancelled job {job.id}")

    def retry_job(self, job):
        """Retry a failed job if limits allow."""
        if job.status != self.model.Status.FAILED:
            raise ValueError(f"Only failed jobs can be retried.")

        if job.retry_count >= job.max_retries:
            raise ValueError(f"Maximum retries ({job.max_retries}) exceeded.")

        job.status = self.model.Status.PENDING
        job.scheduled_at = timezone.now()
        job.save()

        from .tasks import execute_scheduled_job

        execute_scheduled_job.delay(str(job.id))
        logger.info(f"Retrying job {job.id}")

    def schedule_campaign_activation(self, campaign_id, activate_at):
        """Specific helper for campaign activation."""
        from apps.promotions.models import Campaign

        campaign = Campaign.objects.get(id=campaign_id)

        # Parse time if string
        if isinstance(activate_at, str):
            activate_at = timezone.datetime.fromisoformat(
                activate_at.replace("Z", "+00:00")
            )

        if activate_at <= timezone.now():
            raise ValueError("Activation time must be in the future")

        return self.create_job(
            job_type=self.model.JobType.CAMPAIGN_ACTIVATION,
            scheduled_at=activate_at,
            payload={
                "campaign_id": str(campaign.id),
                "campaign_code": campaign.code,
                "action": "activate",
            },
        )


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

    objects = ScheduledJobManager()

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

    def execute(self):
        """Execute the actual job logic based on type."""
        from django.core.cache import cache
        from django.db.models import F
        from datetime import timedelta

        payload = self.payload or {}

        if self.job_type == self.JobType.CAMPAIGN_ACTIVATION:
            from apps.promotions.models import Campaign

            campaign_id = payload.get("campaign_id")
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.is_active = True
            campaign.save()
            cache.delete("active_campaigns")
            return {"action": "activated", "campaign": campaign.code}

        elif self.job_type == self.JobType.CAMPAIGN_EXPIRATION:
            from apps.promotions.models import Campaign

            campaign_id = payload.get("campaign_id")
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.is_active = False
            campaign.save()
            cache.delete("active_campaigns")
            return {"action": "deactivated", "campaign": campaign.code}

        elif self.job_type == self.JobType.RESERVATION_EXPIRY:
            from apps.orders.models import Reservation
            from apps.inventory.models import Stock
            from apps.audit.models import InventoryAudit

            now = timezone.now()
            expired_reservations = Reservation.objects.filter(
                status="pending", expires_at__lt=now
            )

            expired_count = 0
            for reservation in expired_reservations:
                try:
                    stock = Stock.objects.get(
                        variant=reservation.variant, warehouse=reservation.warehouse
                    )
                    stock.reserved -= reservation.quantity
                    stock.save()

                    reservation.status = "expired"
                    reservation.save()

                    InventoryAudit.objects.create(
                        event_type="release",
                        variant=reservation.variant,
                        warehouse=reservation.warehouse,
                        quantity=reservation.quantity,
                        reference=reservation.reservation_token,
                        notes="Auto-expired by scheduled job",
                    )
                    expired_count += 1
                except Stock.DoesNotExist:
                    reservation.status = "cancelled"
                    reservation.save()

            return {"action": "expired_reservations", "count": expired_count}

        elif self.job_type == self.JobType.INBOUND_RECEIPT:
            from apps.inventory.models import InboundShipment

            now = timezone.now()
            shipments = InboundShipment.objects.filter(
                status="pending", expected_at__lt=now
            )
            processed_count = 0
            for shipment in shipments:
                shipment.status = "arrived"
                shipment.save()
                processed_count += 1
            return {"action": "marked_arrived", "count": processed_count}

        elif self.job_type == self.JobType.PRICE_UPDATE:
            return {"action": "price_update", "updated": 0}

        elif self.job_type == self.JobType.INVENTORY_REORDER:
            from apps.inventory.models import Stock

            low_stock_items = Stock.objects.filter(
                available__lte=F("safety_stock")
            ).select_related("variant", "warehouse")
            reorder_count = 0
            for stock in low_stock_items:
                reorder_count += 1
            return {"action": "inventory_reorder", "reorders_created": reorder_count}

        elif self.job_type == self.JobType.DATA_CLEANUP:
            from apps.audit.models import IdempotencyKey

            now = timezone.now()
            expired_keys = IdempotencyKey.objects.filter(
                expires_at__lt=now - timedelta(days=7)
            )
            expired_keys_count = expired_keys.count()
            expired_keys.delete()

            old_jobs = ScheduledJob.objects.filter(
                status__in=["completed", "failed", "cancelled"],
                created_at__lt=now - timedelta(days=30),
            )
            old_jobs_count = old_jobs.count()
            old_jobs.delete()

            return {
                "action": "data_cleanup",
                "expired_keys_deleted": expired_keys_count,
                "old_jobs_deleted": old_jobs_count,
            }

        elif self.job_type == self.JobType.REPORT_GENERATION:
            report_data = {
                "timestamp": timezone.now().isoformat(),
                "type": payload.get("report_type", "general"),
                "data": {},
            }
            return {"action": "report_generated", "report": report_data}

        else:
            raise ValueError(f"Unknown job type: {self.job_type}")
