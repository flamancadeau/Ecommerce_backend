from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid


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
            last_warehouse = Warehouse.objects.order_by("id").last()
            if last_warehouse and last_warehouse.code.startswith("WH"):
                last_number = int(last_warehouse.code.replace("WH", ""))
                self.code = f"WH{last_number + 1:03d}"
            else:
                self.code = "WH001"
        super().save(*args, **kwargs)


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


class InboundShipment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_transit", "In Transit"),
        ("arrived", "Arrived at Warehouse"),
        ("partial", "Partially Received"),
        ("received", "Fully Received"),
        ("cancelled", "Cancelled"),
        ("delayed", "Delayed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=50, unique=True, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    expected_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

        if self.expected_at and self.status in ["pending", "in_transit"]:
            return self.expected_at < timezone.now()
        return False

    def save(self, *args, **kwargs):
        if not self.reference:
            last_shipment = InboundShipment.objects.order_by("id").last()
            if last_shipment and last_shipment.reference.startswith("INB"):
                last_number = int(last_shipment.reference.replace("INB", ""))
                self.reference = f"INB{last_number + 1:03d}"
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
