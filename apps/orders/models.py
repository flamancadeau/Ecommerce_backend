from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock
from apps.pricing.models import PriceBook
from apps.audit.models import InventoryAudit


def generate_reservation_token():
    """Generate a unique reservation token."""
    return str(uuid.uuid4())


class CartQuerySet(models.QuerySet):
    def active(self, cart_id=None, session_id=None, user_id=None):
        now = timezone.now()
        query = self.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if cart_id:
            return query.filter(id=cart_id).first()
        if session_id:
            return query.filter(session_id=session_id).first()
        if user_id:
            return query.filter(user_id=user_id).first()
        return None


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True, blank=True, null=True)
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = CartQuerySet.as_manager()

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


class OrderQuerySet(models.QuerySet):
    def for_customer(self, customer_id, status=None):
        query = self.filter(customer_id=customer_id)
        if status:
            query = query.filter(status=status)
        return query


class OrderManager(models.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)

    @transaction.atomic
    def create_from_reservation(
        self, reservation_token, email, shipping_address, customer_id=None
    ):
        reservations = Reservation.objects.select_related(
            "variant", "warehouse", "variant__product"
        ).filter(reservation_token=reservation_token, status="pending")

        if not reservations.exists():
            raise ValidationError("Invalid or expired reservation")

        first_res = reservations.first()
        if first_res.is_expired:
            raise ValidationError("Reservation expired")

        subtotal = Decimal("0")
        order_items_data = []

        current_time = timezone.now()
        context = {"channel": "web", "email": email}

        for res in reservations:
            stock = Stock.objects.select_for_update().get(
                variant=res.variant, warehouse=res.warehouse
            )

            stock.reserved -= res.quantity
            stock.on_hand -= res.quantity
            stock.save()

            res.status = Reservation.Status.CONFIRMED
            res.save()

            # Calculate Price
            price_data = PriceBook.objects.calculate_price(
                res.variant, context, res.quantity, current_time
            )

            unit_price = Decimal(str(price_data["final_unit_price"]))
            line_total = Decimal(str(price_data["extended_price"]))

            subtotal += line_total

            order_items_data.append(
                {
                    "variant": res.variant,
                    "warehouse": res.warehouse,
                    "quantity": res.quantity,
                    "unit_price": unit_price,
                    "sku": res.variant.sku,
                    "variant_name": res.variant.product.name,
                }
            )

            InventoryAudit.objects.create(
                event_type=InventoryAudit.EventType.FULFILLMENT,
                variant=res.variant,
                warehouse=stock.warehouse,
                quantity=res.quantity,
                from_quantity=stock.on_hand + res.quantity,
                to_quantity=stock.on_hand,
                reference=reservation_token,
                notes="Order confirmed from reservation",
            )

        tax_rate = Decimal("0.21")
        tax_amount = subtotal * tax_rate
        shipping_amount = Decimal("5.99")
        total = subtotal + tax_amount + shipping_amount

        order = self.create(
            customer_id=customer_id,
            customer_email=email,
            shipping_address=shipping_address,
            billing_address=shipping_address,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            total=total,
            status=self.model.Status.CONFIRMED,
        )

        for item_data in order_items_data:
            OrderItem.objects.create(
                order=order,
                variant=item_data["variant"],
                warehouse=item_data["warehouse"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                sku=item_data["sku"],
                variant_name=item_data["variant_name"],
            )

        reservations.update(order=order)

        return order

    def create_direct_order(self, cart_id, email, shipping_address, customer_id=None):
        res_data = Reservation.objects.create_from_cart(cart_id)
        token = res_data["reservation_token"]
        return self.create_from_reservation(token, email, shipping_address, customer_id)


class Order(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Payment"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

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

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderManager()

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

        # Ensure Decimal safety
        for field in ("subtotal", "tax_amount", "shipping_amount", "total"):
            value = getattr(self, field)
            if isinstance(value, (int, float)):
                setattr(self, field, Decimal(str(value)))

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


class ReservationQuerySet(models.QuerySet):
    def pending(self, variant_id=None, warehouse_id=None):
        now = timezone.now()
        query = self.filter(status="pending", expires_at__gt=now)
        if variant_id:
            query = query.filter(variant_id=variant_id)
        if warehouse_id:
            query = query.filter(warehouse_id=warehouse_id)
        return query

    def expired(self):
        now = timezone.now()
        return self.filter(status="pending", expires_at__lte=now)


class ReservationManager(models.Manager):
    def get_queryset(self):
        return ReservationQuerySet(self.model, using=self._db)

    @transaction.atomic
    def create_from_cart(self, cart_id):
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            raise ValidationError("Cart not found")

        if cart.is_expired:
            raise ValidationError("Cart has expired")

        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        reservations = []
        reservation_token = str(uuid.uuid4())
        expires_at = timezone.now() + timezone.timedelta(minutes=15)

        # Access Variant through items
        items = cart.items.select_related("variant").all()

        for item in items:
            variant = item.variant
            quantity = item.quantity

            # Find fulfillment options (from Stock model)
            stock_option = Stock.objects.find_fulfillment(variant.id, quantity)
            if not stock_option:
                raise ValidationError(
                    f"Insufficient stock for {variant.sku} (Global check)"
                )

            # Select for update to lock
            locked_stock = Stock.objects.select_for_update().get(id=stock_option.id)

            if not locked_stock.can_fulfill(quantity):
                raise ValidationError(
                    f"Insufficient stock for {variant.sku} at warehouse {locked_stock.warehouse.code}"
                )

            locked_stock.reserved += quantity
            locked_stock.save()

            res = self.create(
                reservation_token=reservation_token,
                variant=variant,
                warehouse=locked_stock.warehouse,
                quantity=quantity,
                status=self.model.Status.PENDING,
                expires_at=expires_at,
            )
            reservations.append(res)

            InventoryAudit.objects.create(
                event_type=InventoryAudit.EventType.RESERVATION,
                variant=variant,
                warehouse=locked_stock.warehouse,
                quantity=quantity,
                reference=reservation_token,
                notes="Cart reservation",
            )

        return {
            "reservation_token": reservation_token,
            "expires_at": expires_at,
            "items": len(reservations),
        }


class Reservation(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    reservation_token = models.CharField(
        max_length=100,
        db_index=True,
        default=generate_reservation_token,
        editable=False,
    )

    variant = models.ForeignKey("catalog.Variant", on_delete=models.CASCADE)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

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

    objects = ReservationManager()

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
        return bool(self.expires_at and self.expires_at < timezone.now())

    def save(self, *args, **kwargs):
        """Ensure token is always set."""
        if not self.reservation_token or not self.reservation_token.strip():
            self.reservation_token = generate_reservation_token()
        super().save(*args, **kwargs)
