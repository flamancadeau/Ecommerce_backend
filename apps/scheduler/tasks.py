from functools import cache
from django.db.models import F
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import ScheduledJob, IdempotencyKey

logger = logging.getLogger(__name__)


@shared_task
def execute_scheduled_job(job_id):
    try:
        job = ScheduledJob.objects.get(id=job_id)

        if job.status != "pending":
            logger.warning(f"Job {job_id} is not pending (status: {job.status})")
            return

        job.status = "running"
        job.save()

        result = execute_job_logic(job)

        job.executed_at = timezone.now()
        job.status = "completed"
        job.result = result
        job.save()

        logger.info(f"Executed scheduled job {job_id}: {job.job_type}")
        return result

    except ScheduledJob.DoesNotExist:
        logger.error(f"Scheduled job {job_id} not found")
        raise

    except Exception as e:
        if "job" in locals():
            job.status = "failed"
            job.error = str(e)
            job.retry_count += 1
            job.save()

            logger.error(f"Failed to execute job {job_id}: {str(e)}")

            if job.should_retry():
                retry_delay = 300
                execute_scheduled_job.apply_async(args=[job_id], countdown=retry_delay)
                logger.info(
                    f"Scheduled retry for job {job_id} in {retry_delay} seconds"
                )

        raise


def execute_job_logic(job):
    """Execute the actual job logic based on type."""
    payload = job.payload or {}

    if job.job_type == "campaign_activation":
        from apps.promotions.models import Campaign

        campaign_id = payload.get("campaign_id")
        campaign = Campaign.objects.get(id=campaign_id)
        campaign.is_active = True
        campaign.save()

        cache.delete("active_campaigns")

        return {"action": "activated", "campaign": campaign.code}

    elif job.job_type == "campaign_expiration":
        from apps.promotions.models import Campaign

        campaign_id = payload.get("campaign_id")
        campaign = Campaign.objects.get(id=campaign_id)
        campaign.is_active = False
        campaign.save()

        cache.delete("active_campaigns")

        return {"action": "deactivated", "campaign": campaign.code}

    elif job.job_type == "reservation_expiry":
        from apps.orders.models import Reservation
        from apps.inventory.models import Stock, InventoryAudit

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

    elif job.job_type == "inbound_receipt":
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

    elif job.job_type == "price_update":
        return {"action": "price_update", "updated": 0}

    elif job.job_type == "inventory_reorder":
        from apps.inventory.models import Stock

        low_stock_items = Stock.objects.filter(
            available__lte=F("safety_stock")
        ).select_related("variant", "warehouse")

        reorder_count = 0
        for stock in low_stock_items:
            reorder_count += 1

        return {"action": "inventory_reorder", "reorders_created": reorder_count}

    elif job.job_type == "data_cleanup":
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

    elif job.job_type == "report_generation":
        report_data = {
            "timestamp": timezone.now().isoformat(),
            "type": payload.get("report_type", "general"),
            "data": {},
        }
        return {"action": "report_generated", "report": report_data}

    else:
        raise ValueError(f"Unknown job type: {job.job_type}")


@shared_task
def cleanup_expired_idempotency_keys():
    """Clean up expired idempotency keys."""
    now = timezone.now()
    expired_keys = IdempotencyKey.objects.filter(expires_at__lt=now)

    deleted_count = expired_keys.count()
    expired_keys.delete()

    logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
    return {"deleted_count": deleted_count}


@shared_task
def check_overdue_jobs():
    """Check for and process overdue jobs."""
    now = timezone.now()
    overdue_jobs = ScheduledJob.objects.filter(status="pending", scheduled_at__lt=now)

    processed_count = 0
    for job in overdue_jobs:
        execute_scheduled_job.delay(str(job.id))
        processed_count += 1

    logger.info(f"Processed {processed_count} overdue jobs")
    return {"overdue_jobs_processed": processed_count}
