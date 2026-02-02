from django.db import models
import uuid
from django.utils import timezone


class PriceAudit(models.Model):
    """Audit trail for price changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.CASCADE, null=True, blank=True
    )
    price_book = models.ForeignKey(
        "pricing.PriceBook", on_delete=models.CASCADE, null=True, blank=True
    )
    price_book_entry = models.ForeignKey(
        "pricing.PriceBookEntry", on_delete=models.SET_NULL, null=True, blank=True
    )
    old_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    changed_by = models.UUIDField(
        null=True, blank=True, help_text="User ID who made the change"
    )
    changed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["variant"]),
            models.Index(fields=["price_book"]),
            models.Index(fields=["changed_at"]),
        ]

    def __str__(self):
        target = self.variant.sku if self.variant else self.price_book.code
        return f"Price change for {target}: {self.old_price} → {self.new_price}"


class InventoryAudit(models.Model):
    """Audit trail for inventory changes."""

    EVENT_TYPE_CHOICES = [
        ("adjustment", "Manual Adjustment"),
        ("reservation", "Reservation"),
        ("release", "Reservation Release"),
        ("fulfillment", "Order Fulfillment"),
        ("receipt", "Inbound Receipt"),
        ("transfer", "Warehouse Transfer"),
        ("write_off", "Write Off"),
        ("correction", "Correction"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    variant = models.ForeignKey("catalog.Variant", on_delete=models.CASCADE)
    warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.CASCADE, null=True, blank=True
    )
    quantity = models.IntegerField()
    from_quantity = models.IntegerField(null=True, blank=True)
    to_quantity = models.IntegerField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["variant", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.variant.sku} ({self.quantity})"


class CampaignAudit(models.Model):
    """Audit trail for campaign changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey("promotions.Campaign", on_delete=models.CASCADE)
    changed_field = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    changed_by = models.UUIDField(null=True, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["campaign", "changed_at"]),
            models.Index(fields=["changed_field"]),
        ]

    def __str__(self):
        return f"{self.campaign.code}: {self.changed_field} changed"
