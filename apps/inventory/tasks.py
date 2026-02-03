from apps.inventory import models
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging
from apps.inventory.models import InboundShipment, Stock
from apps.scheduler.models import ScheduledJob

logger = logging.getLogger(__name__)


@shared_task
def process_inbound_receipts():
    """
    Check and process inbound shipments that have arrived.
    Runs every hour via Celery Beat.
    """
    now = timezone.now()

    overdue_shipments = InboundShipment.objects.filter(
        status__in=["pending", "in_transit"], expected_at__lt=now
    )

    processed_count = 0
    for shipment in overdue_shipments:

        if shipment.status != "arrived":
            shipment.status = "arrived"
            shipment.save()

            ScheduledJob.objects.create(
                job_type="inbound_receipt",
                scheduled_at=now,
                executed_at=now,
                status="completed",
                payload={
                    "shipment_id": str(shipment.id),
                    "reference": shipment.reference,
                    "action": "marked_arrived",
                },
            )

            logger.info(f"Marked shipment {shipment.reference} as arrived")
            processed_count += 1

    cache.delete_pattern("stock:*")
    cache.delete("low_stock_alerts")

    return {"processed_shipments": processed_count}


@shared_task
def update_stock_levels_cache():
    """
    Update Redis cache with stock levels for fast access.
    """
    from django.db.models import Sum

    from apps.catalog.models import Variant

    variants = Variant.objects.filter(is_active=True)

    for variant in variants:
        total_available = (
            Stock.objects.filter(variant=variant).aggregate(Sum("available"))[
                "available__sum"
            ]
            or 0
        )

        cache_key = f"stock:variant:{variant.id}:available"
        cache.set(cache_key, total_available, timeout=300)

    low_stock_items = Stock.objects.filter(
        available__lte=models.F("safety_stock"), available__gt=0
    ).select_related("variant", "warehouse")

    low_stock_data = [
        {
            "variant_id": str(item.variant.id),
            "sku": item.variant.sku,
            "warehouse": item.warehouse.code,
            "available": item.available,
            "safety_stock": item.safety_stock,
        }
        for item in low_stock_items
    ]

    cache.set("low_stock_alerts", low_stock_data, timeout=600)

    return {"cached_variants": len(variants), "low_stock_items": len(low_stock_items)}
