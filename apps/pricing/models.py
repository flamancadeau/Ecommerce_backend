import uuid
import random
import string
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class Channel(models.TextChoices):
    WEB = "web", "Web"
    APP = "app", "Mobile App"
    MARKETPLACE = "marketplace", "Marketplace"
    RETAIL = "retail", "Retail Store"
    WHOLESALE = "wholesale", "Wholesale"


class CustomerGroup(models.TextChoices):
    RETAIL = "retail", "Retail"
    WHOLESALE = "wholesale", "Wholesale"
    VIP = "vip", "VIP"
    EMPLOYEE = "employee", "Employee"
    B2B = "b2b", "B2B"


class PriceBook(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    country = models.CharField(max_length=2, blank=True, help_text="ISO country code")

    channel = models.CharField(
        max_length=50,
        choices=Channel.choices,
        blank=True,
    )

    customer_group = models.CharField(
        max_length=50,
        choices=CustomerGroup.choices,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["country", "channel", "customer_group"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["country", "channel", "customer_group"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_default"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def generate_code(self):
        prefix = "PB"
        channel_code = self.channel.upper() if self.channel else "GEN"
        country_code = self.country.upper() if self.country else "XX"
        customer_group_code = (
            self.customer_group.upper() if self.customer_group else "GEN"
        )

        random_string = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=3)
        )

        code = f"{prefix}-{channel_code}-{country_code}-{customer_group_code}-{random_string}"

        while PriceBook.objects.filter(code=code).exists():
            random_string = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=3)
            )
            code = f"{prefix}-{channel_code}-{country_code}-{customer_group_code}-{random_string}"

        return code


class PriceBookEntry(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    price_book = models.ForeignKey(
        PriceBook, on_delete=models.CASCADE, related_name="entries"
    )
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.CASCADE, null=True, blank=True
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, null=True, blank=True
    )
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.CASCADE, null=True, blank=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    compare_at_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)

    min_quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    max_quantity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Price book entries"
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["price_book", "variant"]),
            models.Index(fields=["price_book", "product"]),
            models.Index(fields=["price_book", "category"]),
            models.Index(fields=["effective_from", "effective_to"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self):
        if self.variant:
            target = self.variant.sku
        elif self.product:
            target = self.product.name
        else:
            target = self.category.name
        return f"{self.price_book.code}: {target} @ {self.price}"

    @property
    def is_active(self):
        from django.utils import timezone

        now = timezone.now()
        if self.effective_from and self.effective_from > now:
            return False
        if self.effective_to and self.effective_to < now:
            return False
        return True

    def clean(self):
        provided = sum(bool(x) for x in (self.variant, self.product, self.category))

        if provided == 0:
            raise ValidationError(
                "One of 'variant', 'product' or 'category' must be set."
            )
        if provided > 1:
            raise ValidationError(
                "Only one of 'variant', 'product' or 'category' may be set."
            )


class TaxRate(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField(max_length=2)
    state = models.CharField(max_length=50, blank=True)

    rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )

    tax_class = models.CharField(max_length=50, default="standard")
    description = models.CharField(max_length=200, blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["country", "state", "-effective_from"]
        unique_together = ["country", "state", "tax_class", "effective_from"]
        indexes = [
            models.Index(fields=["country", "state", "tax_class"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["effective_from", "effective_to"]),
        ]

    def __str__(self):
        state_str = f" - {self.state}" if self.state else ""
        return f"{self.country}{state_str}: {self.rate * 100}% ({self.tax_class})"
