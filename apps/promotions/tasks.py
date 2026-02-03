from apps.promotions.models import Campaign
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging
from apps.scheduler.models import ScheduledJob

logger = logging.getLogger(__name__)


@shared_task
def check_campaign_activations():
    """
    Check and activate/deactivate campaigns based on time.
    Runs every minute via Celery Beat.
    """
    now = timezone.now()

    campaigns_to_activate = Campaign.objects.filter(
        start_at__lte=now, end_at__gte=now, is_active=False
    )

    activated_count = 0
    for campaign in campaigns_to_activate:
        campaign.is_active = True
        campaign.save()
        activated_count += 1

        logger.info(f"Activated campaign: {campaign.code}")

        ScheduledJob.objects.create(
            job_type="campaign_activation",
            scheduled_at=now,
            executed_at=now,
            status="completed",
            payload={"campaign_id": str(campaign.id), "action": "activated"},
        )

    campaigns_to_deactivate = Campaign.objects.filter(end_at__lt=now, is_active=True)

    deactivated_count = 0
    for campaign in campaigns_to_deactivate:
        campaign.is_active = False
        campaign.save()
        deactivated_count += 1

        logger.info(f"Deactivated campaign: {campaign.code}")

        ScheduledJob.objects.create(
            job_type="campaign_expiration",
            scheduled_at=now,
            executed_at=now,
            status="completed",
            payload={"campaign_id": str(campaign.id), "action": "deactivated"},
        )

    if activated_count > 0 or deactivated_count > 0:
        cache.delete("active_campaigns")
        cache.delete("campaign_rules")

    return {
        "activated": activated_count,
        "deactivated": deactivated_count,
        "total_active": Campaign.objects.filter(is_active=True).count(),
    }


@shared_task
def create_campaign_schedule(campaign_id, action, schedule_at):

    campaign = Campaign.objects.get(id=campaign_id)

    ScheduledJob.objects.create(
        job_type=f"campaign_{action}",
        scheduled_at=schedule_at,
        status="pending",
        payload={
            "campaign_id": str(campaign.id),
            "campaign_code": campaign.code,
            "action": action,
        },
    )

    logger.info(f"Scheduled {action} for campaign {campaign.code} at {schedule_at}")
