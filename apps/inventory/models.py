from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, F
from apps.audit.models import InventoryAudit
import uuid


class WarehouseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WarehouseQuerySet.as_manager()

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["country"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:

            last_warehouse = (
                Warehouse.objects.filter(code__startswith="WH")
                .order_by("-code")
                .first()
            )
            if last_warehouse:
                try:
                    num_part = last_warehouse.code[2:]
                    last_number = int(num_part)
                    self.code = f"WH{last_number + 1:03d}"
                except (ValueError, TypeError):

                    import secrets

                    self.code = f"WH-{secrets.token_hex(4).upper()}"
            else:
                self.code = "WH001"
        super().save(*args, **kwargs)


class StockQuerySet(models.QuerySet):
    def for_variant(self, variant_id):
        return self.filter(variant_id=variant_id)

    def backorderable(self):
        return self.filter(backorderable=True)

    def find_fulfillment(self, variant_id, quantity):
        # Logic from Repository
        stock = (
            self.filter(
                variant_id=variant_id,
                warehouse__is_active=True,
                available__gte=quantity,
            )
            .order_by("-available")
            .first()
        )

        if stock:
            return stock

        return (
            self.filter(
                variant_id=variant_id, warehouse__is_active=True, backorderable=True
            )
            .order_by("-available")
            .first()
        )

    def check_availability(self, variant_id, quantity, warehouse=None):
        # Logic from Service/Repository
        query = self.filter(variant_id=variant_id, warehouse__is_active=True)
        if warehouse:
            query = query.filter(warehouse=warehouse)

        stats = query.aggregate(
            total_on_hand=Sum("on_hand"), total_available=Sum("available")
        )
        total_available = stats["total_available"] or 0

        is_backorderable = False
        if total_available < quantity:
            is_backorderable = self.filter(
                variant_id=variant_id, warehouse__is_active=True, backorderable=True
            ).exists()

        return {
            "available": total_available >= quantity,
            "message": "In stock" if total_available >= quantity else "Out of stock",
            "available_quantity": total_available,
            "backorderable": is_backorderable,
        }


class StockManager(models.Manager.from_queryset(StockQuerySet)):
    pass

    def adjust(self, variant_id, warehouse_id, quantity, reason="Manual adjustment"):
        with transaction.atomic():
            stock, created = self.select_for_update().get_or_create(
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


class Stock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.CASCADE, related_name="stocks"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stocks"
    )
    on_hand = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    reserved = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    available = models.GeneratedField(
        expression=models.F("on_hand") - models.F("reserved"),
        output_field=models.IntegerField(),
        db_persist=True,
    )
    backorderable = models.BooleanField(default=False)
    backorder_limit = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    safety_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StockManager()

    class Meta:
        unique_together = ["variant", "warehouse"]
        indexes = [
            models.Index(fields=["variant", "warehouse"]),
            models.Index(fields=["available"]),
            models.Index(fields=["backorderable"]),
        ]

    def __str__(self):
        return (
            f"{self.variant.sku} at {self.warehouse.code}: {self.available} available"
        )

    def can_fulfill(self, quantity):
        if self.available >= quantity:
            return True
        if self.backorderable and (
            self.backorder_limit == 0 or quantity <= self.backorder_limit
        ):
            return True
        return False


class InboundShipmentQuerySet(models.QuerySet):
    def overdue(self):
        return self.filter(
            expected_at__lt=timezone.now(), status__in=["pending", "in_transit"]
        )


class InboundShipmentManager(models.Manager):
    def get_queryset(self):
        return InboundShipmentQuerySet(self.model, using=self._db)

    @transaction.atomic
    def receive_shipment(self, shipment_id, items_data):
        try:
            shipment = self.select_for_update().get(id=shipment_id)
        except self.model.DoesNotExist:
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
            shipment.status = self.model.Status.RECEIVED
            shipment.received_at = timezone.now()
        else:
            shipment.status = self.model.Status.PARTIAL
        shipment.save()

        return shipment


class InboundShipment(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_TRANSIT = "in_transit", "In Transit"
        ARRIVED = "arrived", "Arrived at Warehouse"
        PARTIAL = "partial", "Partially Received"
        RECEIVED = "received", "Fully Received"
        CANCELLED = "cancelled", "Cancelled"
        DELAYED = "delayed", "Delayed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=50, unique=True, blank=True)
    supplier = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    expected_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InboundShipmentManager()

    class Meta:
        ordering = ["expected_at"]
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expected_at"]),
        ]

    def __str__(self):
        return f"Inbound {self.reference}"

    @property
    def is_overdue(self):
        return (
            self.expected_at
            and self.status in {self.Status.PENDING, self.Status.IN_TRANSIT}
            and self.expected_at < timezone.now()
        )

    def save(self, *args, **kwargs):
        if not self.reference:

            last_shipment = (
                InboundShipment.objects.filter(reference__startswith="INB")
                .order_by("-reference")
                .first()
            )
            if last_shipment:
                try:
                    num_part = last_shipment.reference[3:]
                    last_number = int(num_part)
                    self.reference = f"INB{last_number + 1:03d}"
                except (ValueError, TypeError):

                    import secrets

                    self.reference = f"INB-{timezone.now().strftime('%Y%p%d')}-{secrets.token_hex(3).upper()}"
            else:
                self.reference = "INB001"
        super().save(*args, **kwargs)


class InboundItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inbound = models.ForeignKey(
        InboundShipment, on_delete=models.CASCADE, related_name="items"
    )
    variant = models.ForeignKey("catalog.Variant", on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    expected_quantity = models.IntegerField(
        validators=[MinValueValidator(1)], null=True, blank=True
    )  # Made nullable
    received_quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["inbound", "variant", "warehouse"]
        indexes = [
            models.Index(fields=["inbound", "variant"]),
        ]

    def __str__(self):
        if self.variant and self.variant.sku:
            return f"{self.variant.sku} x {self.expected_quantity or 0} in {self.inbound.reference if self.inbound else 'No Shipment'}"
        return f"Inbound Item {self.id}"

    @property
    def remaining_quantity(self):

        if self.expected_quantity is None:
            return 0
        return self.expected_quantity - self.received_quantity

    @property
    def is_fully_received(self):

        if self.expected_quantity is None:
            return False
        return self.received_quantity >= self.expected_quantity
