import os
import logging
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger("inventory.sync")


def sync_stock():
    """
    Syncs Stock levels with InboundItem records using atomic transactions
    and bulk-friendly patterns.
    """
    from apps.inventory.models import InboundItem, Stock
    from apps.audit.models import InventoryAudit

    items = InboundItem.objects.filter(received_quantity__gt=0).select_related(
        "variant", "warehouse"
    )

    logger.info("Starting stock synchronization for %d items", items.count())
    sync_count = 0

    try:
        with transaction.atomic():
            for item in items:
                stock, created = Stock.objects.get_or_create(
                    variant=item.variant, warehouse=item.warehouse
                )

                if stock.on_hand != item.received_quantity:
                    old_qty = stock.on_hand
                    new_qty = item.received_quantity
                    change = new_qty - old_qty

                    logger.info(
                        "SYNC_UPDATE | Variant: %s | Warehouse: %s | %d -> %d",
                        item.variant.sku,
                        item.warehouse.code,
                        old_qty,
                        new_qty,
                    )

                    stock.on_hand = new_qty
                    stock.save()

                    InventoryAudit.objects.create(
                        event_type=InventoryAudit.EventType.RECEIPT,
                        variant=item.variant,
                        warehouse=item.warehouse,
                        quantity=change,
                        from_quantity=old_qty,
                        to_quantity=new_qty,
                        notes="Automated sync from InboundItems",
                    )
                    sync_count += 1

        logger.info("Synchronization complete. Total records updated: %d", sync_count)

    except Exception as e:

        logger.error(
            "CRITICAL: Stock sync failed. Rollback triggered. Error: %s",
            e,
            exc_info=True,
        )


if __name__ == "__main__":
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")
    django.setup()
    sync_stock()
