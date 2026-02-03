from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from apps.orders.models import Reservation
from apps.inventory.models import Stock, InventoryAudit
from apps.scheduler.models import ScheduledJob

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def expire_old_reservations(self):
    """
    Central task to expire old reservations, release inventory,
    and create audit + scheduler records.
    Runs via Celery Beat.
    """
    now = timezone.now()

    reservations = Reservation.objects.select_related("variant", "warehouse").filter(
        status__iexact="pending", expires_at__lt=now
    )

    expired_count = 0

    for reservation in reservations:
        try:
            with transaction.atomic():
                # Lock stock row to prevent race conditions
                stock = Stock.objects.select_for_update().get(
                    variant=reservation.variant, warehouse=reservation.warehouse
                )

                # Release reserved quantity safely
                stock.reserved = max(0, stock.reserved - reservation.quantity)
                stock.save(update_fields=["reserved"])

                # Expire reservation
                reservation.status = "expired"
                reservation.save(update_fields=["status"])

                # Inventory audit trail
                InventoryAudit.objects.create(
                    event_type="release",
                    variant=reservation.variant,
                    warehouse=reservation.warehouse,
                    quantity=reservation.quantity,
                    reference=reservation.reservation_token,
                    notes="Reservation auto-expired",
                )

                expired_count += 1
                logger.info("Expired reservation %s", reservation.reservation_token)

        except Stock.DoesNotExist:
            logger.error(
                "Stock not found for reservation %s", reservation.reservation_token
            )
            reservation.status = "cancelled"
            reservation.save(update_fields=["status"])

    if expired_count > 0:
        ScheduledJob.objects.create(
            job_type="reservation_expiry",
            scheduled_at=now,
            executed_at=now,
            status="completed",
            payload={"expired_count": expired_count},
        )

    return {"expired_reservations": expired_count, "executed_at": now.isoformat()}
