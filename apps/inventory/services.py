from django.db.models import Sum, F
from apps.inventory.models import Stock, Warehouse, InboundShipment, InboundItem
from apps.orders.models import Reservation
from django.utils import timezone
from django.db import transaction
from apps.audit.models import InventoryAudit
from .repositories import InventoryRepository


class InventoryService:
    @staticmethod
    @transaction.atomic
    def receive_shipment(shipment_id, items_data):
        """
        Receive items from an inbound shipment.
        """
        try:
            shipment = InboundShipment.objects.select_for_update().get(id=shipment_id)
        except InboundShipment.DoesNotExist:
            raise ValueError("Shipment not found")

        if shipment.status in ["received", "cancelled"]:
            raise ValueError(
                f"Cannot receive items for shipment in status {shipment.status}"
            )

        for receipt in items_data:
            variant_id = receipt.get("variant_id")
            qty = int(receipt.get("quantity", 0))

            if qty <= 0:
                continue

            try:
                item = InboundItem.objects.select_for_update().get(
                    inbound=shipment, variant_id=variant_id
                )
                item.received_quantity += qty
                item.save()

                # Update stock
                stock, _ = Stock.objects.select_for_update().get_or_create(
                    variant_id=variant_id, warehouse=item.warehouse
                )
                old_qty = stock.on_hand
                stock.on_hand += qty
                stock.save()

                InventoryAudit.objects.create(
                    event_type=InventoryAudit.EventType.RECEIPT,
                    variant_id=variant_id,
                    warehouse=item.warehouse,
                    quantity=qty,
                    from_quantity=old_qty,
                    to_quantity=stock.on_hand,
                    reference=shipment.reference,
                    notes=f"Received via shipment {shipment.reference}",
                )
            except InboundItem.DoesNotExist:
                raise ValueError(f"Variant {variant_id} not in this shipment")

        all_received = not shipment.items.filter(
            received_quantity__lt=F("expected_quantity")
        ).exists()

        if all_received:
            shipment.status = InboundShipment.Status.RECEIVED
            shipment.received_at = timezone.now()
        else:
            shipment.status = InboundShipment.Status.PARTIAL
        shipment.save()

        return shipment

    @staticmethod
    @transaction.atomic
    def adjust_stock(variant_id, warehouse_id, quantity, reason="Manual adjustment"):
        """
        Adjust stock levels manually.
        """
        stock, created = Stock.objects.select_for_update().get_or_create(
            variant_id=variant_id, warehouse_id=warehouse_id
        )

        old_qty = stock.on_hand
        stock.on_hand += quantity
        stock.save()

        InventoryAudit.objects.create(
            event_type=InventoryAudit.EventType.ADJUSTMENT,
            variant_id=variant_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            from_quantity=old_qty,
            to_quantity=stock.on_hand,
            notes=reason,
        )
        return stock

    @staticmethod
    def check_availability(variant, quantity, warehouse=None):
        """
        Check if variant is available via Repository.
        """
        stats = InventoryRepository.get_stock_stats(variant.id, warehouse=warehouse)
        total_available = stats["total_available"] or 0

        if total_available >= quantity:
            return {
                "available": True,
                "message": "In stock",
                "available_quantity": total_available,
            }

        is_backorderable = InventoryRepository.get_backorderable_stock(
            variant.id
        ).exists()

        return {
            "available": False,
            "message": "Out of stock",
            "available_quantity": total_available,
            "backorderable": is_backorderable,
        }

    @staticmethod
    def get_stock_for_fulfillment(variant, quantity):
        """
        Find a warehouse that can fulfill the request via Repository.
        """
        return InventoryRepository.find_fulfillment_stock(variant.id, quantity)
