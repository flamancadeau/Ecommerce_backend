from django.db.models import Sum, F
from .models import Stock, Warehouse, InboundShipment, InboundItem
from django.utils import timezone


class InventoryRepository:
    @staticmethod
    def get_active_warehouses():
        return Warehouse.objects.filter(is_active=True)

    @staticmethod
    def get_stock_stats(variant_id, warehouse=None):
        """Returns total on_hand and available for a variant."""
        query = Stock.objects.filter(variant_id=variant_id, warehouse__is_active=True)
        if warehouse:
            query = query.filter(warehouse=warehouse)

        return query.aggregate(
            total_on_hand=Sum("on_hand"), total_available=Sum("available")
        )

    @staticmethod
    def get_backorderable_stock(variant_id):
        return Stock.objects.filter(
            variant_id=variant_id, warehouse__is_active=True, backorderable=True
        )

    @staticmethod
    def find_fulfillment_stock(variant_id, quantity):
        """
        Priority 1: Warehouse with enough available stock.
        Priority 2: Warehouse with backorder enabled.
        """
        # Priority 1
        stock = (
            Stock.objects.filter(
                variant_id=variant_id,
                warehouse__is_active=True,
                available__gte=quantity,
            )
            .order_by("-available")
            .first()
        )

        if stock:
            return stock

        # Priority 2
        return (
            Stock.objects.filter(
                variant_id=variant_id, warehouse__is_active=True, backorderable=True
            )
            .order_by("-available")
            .first()
        )

    @staticmethod
    def get_overdue_shipments():
        return InboundShipment.objects.filter(
            expected_at__lt=timezone.now(), status__in=["pending", "in_transit"]
        )
