import uuid
import random
import string
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.utils import timezone


class Channel(models.TextChoices):
    WEB = "web", "Web"
    APP = "app", "Mobile App"
    MOBILE = "mobile", "Mobile"
    MARKETPLACE = "marketplace", "Marketplace"
    RETAIL = "retail", "Retail Store"
    WHOLESALE = "wholesale", "Wholesale"


class CustomerGroup(models.TextChoices):
    RETAIL = "retail", "Retail"
    WHOLESALE = "wholesale", "Wholesale"
    VIP = "vip", "VIP"
    EMPLOYEE = "employee", "Employee"
    B2B = "b2b", "B2B"


class PriceBookManager(models.Manager):
    def calculate_price(self, variant, context, quantity=1, at_time=None):
        if at_time is None:
            at_time = timezone.now()

        from apps.promotions.models import Campaign
        from apps.inventory.models import Stock

        # 1. Base Price
        currency = context.get("currency", "EUR")
        country = context.get("country", "")
        channel = context.get("channel", "web")
        customer_group = context.get("membership_tier", "retail")

        price_entry = PriceBookEntry.objects.get_price(
            variant, currency, country, channel, customer_group, quantity
        )

        if price_entry:
            base_price = price_entry.price
            price_book_info = {
                "price_book": price_entry.price_book.code,
                "price_book_name": price_entry.price_book.name,
                "price": float(price_entry.price),
                "applied_at": (
                    "variant"
                    if price_entry.variant
                    else ("product" if price_entry.product else "category")
                ),
            }
        else:
            base_price = variant.base_price
            price_book_info = None

        # 2. Campaigns
        applicable_campaigns = Campaign.objects.get_applicable(
            variant, context, at_time, quantity
        )

        applicable_campaigns.sort(key=lambda x: x.priority, reverse=True)

        discount_amount = Decimal("0")
        applied_campaigns = []
        can_stack = True

        for campaign in applicable_campaigns:
            if not can_stack:
                break

            is_exclusive = (
                campaign.stacking_type == "none"
                or campaign.stacking_type == "exclusive"
            )

            if applied_campaigns and is_exclusive:
                continue

            campaign_discount = campaign.calculate_discount(base_price, quantity)

            if campaign_discount > 0:
                discount_amount += campaign_discount
                applied_campaigns.append(
                    {
                        "campaign_id": str(campaign.id),
                        "code": campaign.code,
                        "name": campaign.name,
                        "discount_amount": float(campaign_discount),
                        "priority": campaign.priority,
                    }
                )

                if is_exclusive:
                    can_stack = False
                    break

        final_price = base_price - discount_amount

        if final_price < Decimal("0"):
            final_price = Decimal("0")
            discount_amount = base_price

        # 3. Tax
        tax_rate_obj = TaxRate.objects.get_rate(
            country=context.get("country", "DE"), tax_class=variant.tax_class
        )
        tax_rate = tax_rate_obj.rate if tax_rate_obj else Decimal("0.19")

        tax_amount = final_price * tax_rate

        final_price = final_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_amount = tax_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        extended_price = final_price * quantity
        total_tax = tax_amount * quantity
        total_price = (final_price + tax_amount) * quantity

        # 4. Inventory
        availability = Stock.objects.check_availability(variant.id, quantity)

        return {
            "variant_id": str(variant.id),
            "sku": variant.sku,
            "product_name": variant.product.name,
            "attributes": variant.attributes,
            "quantity": quantity,
            "base_price": float(base_price),
            "final_unit_price": float(final_price),
            "discount_amount": float(discount_amount),
            "extended_price": float(extended_price),
            "tax_rate": float(tax_rate),
            "tax_amount": float(tax_amount),
            "total_tax": float(total_tax),
            "total_price": float(total_price),
            "applied_campaigns": applied_campaigns,
            "availability": availability,
            "price_book_used": price_book_info,
        }


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

    objects = PriceBookManager()

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


class PriceBookEntryQuerySet(models.QuerySet):
    def get_price(
        self, variant, currency, country, channel, customer_group, quantity=1
    ):
        now = timezone.now()
        query_base = (
            self.filter(
                Q(variant=variant)
                | Q(product=variant.product)
                | Q(category=variant.product.category),
                price_book__currency=currency,
                price_book__is_active=True,
                min_quantity__lte=quantity,
            )
            .filter(Q(max_quantity__isnull=True) | Q(max_quantity__gte=quantity))
            .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
        )

        entry = (
            query_base.filter(
                price_book__country=country,
                price_book__channel=channel,
                price_book__customer_group=customer_group,
            )
            .order_by("variant", "product", "category", "-min_quantity")
            .first()
        )

        if entry:
            return entry

        return (
            query_base.filter(price_book__is_default=True)
            .order_by("variant", "product", "category", "-min_quantity")
            .first()
        )


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

    objects = PriceBookEntryQuerySet.as_manager()

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


class TaxRateQuerySet(models.QuerySet):
    def get_rate(self, country, tax_class):
        today = timezone.now().date()
        return (
            self.filter(
                country=country,
                tax_class=tax_class,
                is_active=True,
                effective_from__lte=today,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .first()
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

    objects = TaxRateQuerySet.as_manager()

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
