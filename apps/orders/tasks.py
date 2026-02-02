from celery import shared_task
from django.utils import timezone
from apps.orders.models import Reservation
import logging

logger = logging.getLogger(__name__)


@shared_task
def auto_expire_system():
    now = timezone.now()

    to_expire = Reservation.objects.filter(status__iexact="pending", expires_at__lt=now)

    count = 0
    for res in to_expire:
        res.status = "expired"
        res.save()
        count += 1

    msg = f"Task ran at {now.isoformat()}: Expired {count} reservations."
    logger.info(msg)
    return msg
