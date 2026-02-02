from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import datetime


def generate_reservation_token():
    """Generate a unique reservation token."""
    return str(uuid.uuid4())


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True, blank=True, null=True)
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Cart {self.id}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return self.expires_at < timezone.now()

    @property
    def item_count(self):
        return self.items.aggregate(total=models.Sum("quantity"))["total"] or 0

    @property
    def total_value(self):
        total = Decimal("0.00")
        for item in self.items.all():
            total += item.total_price
        return total


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.Variant", on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["cart", "variant"]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.variant.sku} x {self.quantity}"

    @property
    def total_price(self):
        return self.unit_price * Decimal(self.quantity)

    def save(self, *args, **kwargs):
        """Set unit_price from variant if not provided."""
        if self.unit_price == Decimal("0.00") and self.variant:
            self.unit_price = self.variant.base_price
        super().save(*args, **kwargs)


class Order(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Payment"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    customer_id = models.UUIDField(null=True, blank=True, db_index=True)
    customer_email = models.EmailField()
    shipping_address = models.JSONField()
    billing_address = models.JSONField()
    currency = models.CharField(max_length=3, default="EUR")

    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    shipping_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["customer_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_str = datetime.now().strftime("%Y%m%d")
            last_order = Order.objects.filter(
                order_number__startswith=f"ORD-{date_str}"
            ).count()
            self.order_number = f"ORD-{date_str}-{last_order + 1:04d}"

        if isinstance(self.subtotal, (int, float)):
            self.subtotal = Decimal(str(self.subtotal))
        if isinstance(self.tax_amount, (int, float)):
            self.tax_amount = Decimal(str(self.tax_amount))
        if isinstance(self.shipping_amount, (int, float)):
            self.shipping_amount = Decimal(str(self.shipping_amount))
        if isinstance(self.total, (int, float)):
            self.total = Decimal(str(self.total))

        super().save(*args, **kwargs)

    @property
    def item_count(self):
        return self.items.count()


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.Variant", on_delete=models.PROTECT)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.sku} x {self.quantity}"

    @property
    def total_price(self):
        return self.unit_price * Decimal(self.quantity)


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    reservation_token = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        default=generate_reservation_token,
        editable=False,
    )

    variant = models.ForeignKey("catalog.Variant", on_delete=models.CASCADE)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    expires_at = models.DateTimeField(null=True, blank=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reservation_token"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["variant", "warehouse"]),
        ]

    def __str__(self):
        return f"Reservation {self.reservation_token[:8]}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return self.expires_at < timezone.now()

    def save(self, *args, **kwargs):
        """Ensure token is always set."""
        if not self.reservation_token or self.reservation_token.strip() == "":
            self.reservation_token = generate_reservation_token()
        super().save(*args, **kwargs)
