from django.core.cache import cache
from django.db.models import F
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import ScheduledJob
from apps.audit.models import IdempotencyKey

logger = logging.getLogger(__name__)


@shared_task
def execute_scheduled_job(job_id):
    try:
        job = ScheduledJob.objects.get(id=job_id)

        if job.status != ScheduledJob.Status.PENDING:
            logger.warning(f"Job {job_id} is not pending (status: {job.status})")
            return

        job.mark_as_running()

        result = job.execute()

        job.mark_as_completed(result)

        logger.info(f"Executed scheduled job {job_id}: {job.job_type}")
        return result

    except ScheduledJob.DoesNotExist:
        logger.error(f"Scheduled job {job_id} not found")
        raise

    except Exception as e:
        if "job" in locals():
            job.mark_as_failed(str(e))

            logger.error(f"Failed to execute job {job_id}: {str(e)}")

            if job.should_retry():
                retry_delay = 300
                execute_scheduled_job.apply_async(args=[job_id], countdown=retry_delay)
                logger.info(
                    f"Scheduled retry for job {job_id} in {retry_delay} seconds"
                )

        raise


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
