from django.db import models
import uuid
from django.utils import timezone
import csv
import hashlib
import json
from io import StringIO
from datetime import timedelta
from django.db import transaction


class PriceAuditQuerySet(models.QuerySet):
    def to_csv(self):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "SKU",
                "Price Book",
                "Old Price",
                "New Price",
                "Currency",
                "Reason",
                "Changed At",
            ]
        )
        for audit in self:
            writer.writerow(
                [
                    audit.variant.sku if audit.variant else "N/A",
                    audit.price_book.code if audit.price_book else "N/A",
                    audit.old_price,
                    audit.new_price,
                    audit.currency,
                    audit.reason,
                    audit.changed_at,
                ]
            )
        return output.getvalue()


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

    objects = PriceAuditQuerySet.as_manager()

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


class InventoryAuditQuerySet(models.QuerySet):
    def to_csv(self):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["Event", "SKU", "Warehouse", "Qty", "From", "To", "Ref", "Date"]
        )
        for audit in self:
            writer.writerow(
                [
                    audit.event_type,
                    audit.variant.sku if audit.variant else "N/A",
                    audit.warehouse.code if audit.warehouse else "N/A",
                    audit.quantity,
                    audit.from_quantity,
                    audit.to_quantity,
                    audit.reference,
                    audit.created_at,
                ]
            )
        return output.getvalue()


class InventoryAudit(models.Model):
    """Audit trail for inventory changes."""

    class EventType(models.TextChoices):
        ADJUSTMENT = "adjustment", "Manual Adjustment"
        RESERVATION = "reservation", "Reservation"
        RELEASE = "release", "Reservation Release"
        FULFILLMENT = "fulfillment", "Order Fulfillment"
        RECEIPT = "receipt", "Inbound Receipt"
        TRANSFER = "transfer", "Warehouse Transfer"
        WRITE_OFF = "write_off", "Write Off"
        CORRECTION = "correction", "Correction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
    )
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

    objects = InventoryAuditQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["variant", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()}: {self.variant.sku} ({self.quantity})"


class CampaignAuditQuerySet(models.QuerySet):
    def to_csv(self):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Campaign Code",
                "Campaign Name",
                "Changed Field",
                "Old Value",
                "New Value",
                "Reason",
                "Changed At",
                "Changed By",
            ]
        )
        for audit in self:
            writer.writerow(
                [
                    audit.campaign.code if audit.campaign else "N/A",
                    (
                        audit.campaign.name
                        if audit.campaign and hasattr(audit.campaign, "name")
                        else "N/A"
                    ),
                    audit.changed_field or "",
                    (
                        (audit.old_value[:50] + "...")
                        if audit.old_value and len(audit.old_value) > 50
                        else (audit.old_value or "")
                    ),
                    (
                        (audit.new_value[:50] + "...")
                        if audit.new_value and len(audit.new_value) > 50
                        else (audit.new_value or "")
                    ),
                    audit.reason or "",
                    (
                        audit.changed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if audit.changed_at
                        else ""
                    ),
                    str(audit.changed_by)[:8] if audit.changed_by else "System",
                ]
            )
        return output.getvalue()


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

    objects = CampaignAuditQuerySet.as_manager()

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["campaign", "changed_at"]),
            models.Index(fields=["changed_field"]),
        ]

    def __str__(self):
        return f"{self.campaign.code}: {self.changed_field} changed"


class IdempotencyKeyManager(models.Manager):
    def generate_key(self):
        return str(uuid.uuid4())

    def get_request_hash(self, data):
        if not data:
            return ""
        request_body = json.dumps(data, sort_keys=True)
        return hashlib.sha256(request_body.encode()).hexdigest()

    def verify_or_create(
        self, key, request_path, request_data=None, expires_in_hours=24
    ):
        """
        Main logic for idempotency check.
        Returns (idem_key, created)
        """
        request_hash = self.get_request_hash(request_data)

        with transaction.atomic():
            (
                idem_key,
                created,
            ) = self.select_for_update().get_or_create(
                key=key,
                defaults={
                    "request_path": request_path,
                    "request_hash": request_hash,
                    "status": self.model.Status.PROCESSING,
                    "expires_at": timezone.now() + timedelta(hours=expires_in_hours),
                },
            )
            return idem_key, created


class IdempotencyKey(models.Model):
    """Stores idempotency keys to prevent duplicate processing of the same request."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255, unique=True, db_index=True)
    request_hash = models.CharField(
        max_length=64, db_index=True, blank=True, help_text="SHA256 hash of request"
    )
    request_path = models.CharField(max_length=255, blank=True)
    response_code = models.IntegerField(null=True)
    response_body = models.JSONField(null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Relationship to Order (Optional)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="idempotency_keys",
    )

    objects = IdempotencyKeyManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return self.key

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now())

    def mark_completed(self, response_code, response_body):
        self.status = self.Status.COMPLETED
        self.response_code = response_code
        self.response_body = response_body
        self.save()

    def mark_failed(self):
        self.status = self.Status.FAILED
        self.save()
