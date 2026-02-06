import logging
from django.utils import timezone
from .models import ScheduledJob
from .tasks import execute_scheduled_job

logger = logging.getLogger(__name__)


class SchedulerService:
    @staticmethod
    def create_job(job_type, scheduled_at, payload=None, max_retries=3):
        """Standard way to create and enqueue a job."""
        job = ScheduledJob.objects.create(
            job_type=job_type,
            scheduled_at=scheduled_at,
            payload=payload or {},
            max_retries=max_retries,
            status=ScheduledJob.Status.PENDING,
        )

        execute_scheduled_job.apply_async(args=[str(job.id)], eta=scheduled_at)

        logger.info(f"Scheduled job created: {job_type} for {scheduled_at}")
        return job

    @staticmethod
    def execute_now(job):
        """Immediately trigger a job execution."""
        if job.status not in [ScheduledJob.Status.PENDING, ScheduledJob.Status.FAILED]:
            raise ValueError(
                f"Job is in status '{job.status}' and cannot be executed now."
            )

        execute_scheduled_job.delay(str(job.id))
        logger.info(f"Triggered immediate execution for job {job.id}")

    @staticmethod
    def cancel_job(job):
        """Cancel a pending or running job."""
        if job.status not in [ScheduledJob.Status.PENDING, ScheduledJob.Status.RUNNING]:
            raise ValueError(f"Cannot cancel job with status: {job.status}")

        job.status = ScheduledJob.Status.CANCELLED
        job.save()
        logger.info(f"Cancelled job {job.id}")

    @staticmethod
    def retry_job(job):
        """Retry a failed job if limits allow."""
        if job.status != ScheduledJob.Status.FAILED:
            raise ValueError(f"Only failed jobs can be retried.")

        if job.retry_count >= job.max_retries:
            raise ValueError(f"Maximum retries ({job.max_retries}) exceeded.")

        job.status = ScheduledJob.Status.PENDING
        job.scheduled_at = timezone.now()
        job.save()

        execute_scheduled_job.delay(str(job.id))
        logger.info(f"Retrying job {job.id}")

    @staticmethod
    def schedule_campaign_activation(campaign_id, activate_at):
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

        return SchedulerService.create_job(
            job_type=ScheduledJob.JobType.CAMPAIGN_ACTIVATION,
            scheduled_at=activate_at,
            payload={
                "campaign_id": str(campaign.id),
                "campaign_code": campaign.code,
                "action": "activate",
            },
        )
