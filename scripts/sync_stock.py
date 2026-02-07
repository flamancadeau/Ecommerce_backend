from apps.inventory.models import InboundItem, Stock
from apps.audit.models import InventoryAudit
from django.db.models import Sum


def sync_stock():
    items = InboundItem.objects.filter(received_quantity__gt=0)
    for item in items:
        stock, created = Stock.objects.get_or_create(
            variant=item.variant, warehouse=item.warehouse
        )
        if stock.on_hand != item.received_quantity:
            print(f"Syncing {item.variant} at {item.warehouse}")
            old_qty = stock.on_hand
            stock.on_hand = item.received_quantity
            stock.save()
            InventoryAudit.objects.create(
                event_type=InventoryAudit.EventType.RECEIPT,
                variant=item.variant,
                warehouse=item.warehouse,
                quantity=stock.on_hand - old_qty,
                from_quantity=old_qty,
                to_quantity=stock.on_hand,
                notes="Manual sync from existing InboundItems",
            )
    print("Done")


if __name__ == "__main__":
    import django
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")
    django.setup()
    sync_stock()
