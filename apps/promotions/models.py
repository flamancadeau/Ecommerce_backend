from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import random
import string
from django.db.models.signals import pre_save
from django.dispatch import receiver


class PriceBook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Campaign(models.Model):

    class StackingType(models.TextChoices):
        NONE = "none", "No Stacking"
        ALL = "all", "Stack All"
        EXCLUSIVE = "exclusive", "Exclusive"
        COMBINED = "combined", "Combined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    priority = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    stacking_type = models.CharField(
        max_length=20,
        choices=StackingType.choices,
        default=StackingType.NONE,
    )
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    usage_limit = models.IntegerField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    customer_groups = models.JSONField(default=list, blank=True)
    excluded_customer_groups = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def status(self):
        now = timezone.now()
        if now < self.start_at:
            return "scheduled"
        if self.start_at <= now <= self.end_at:
            return "active"
        return "expired"

    def __str__(self):
        return self.code


@receiver(pre_save, sender=Campaign)
def generate_campaign_code(sender, instance, **kwargs):
    if not instance.code:

        random_code = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )
        instance.code = f"CMP{random_code}{timezone.now().year}"


class CampaignRule(models.Model):

    class RuleType(models.TextChoices):
        PRODUCT = "product", "Product"
        VARIANT = "variant", "Variant"
        CATEGORY = "category", "Category"
        BRAND = "brand", "Brand"

    class Operator(models.TextChoices):
        EQUALS = "equals", "Equals"
        IN = "in", "In"
        BETWEEN = "between", "Between"

    class Scope(models.TextChoices):
        GLOBAL = "global", "Global"
        LINE_ITEM = "line_item", "Line Item"

    class Action(models.TextChoices):
        INCLUDE = "include", "Include"
        EXCLUDE = "exclude", "Exclude"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="rules"
    )
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    operator = models.CharField(max_length=20, choices=Operator.choices)
    value = models.TextField()
    order = models.IntegerField(default=0)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.GLOBAL)
    action = models.CharField(
        max_length=20, choices=Action.choices, default=Action.INCLUDE
    )

    class Meta:
        ordering = ["order"]


class CampaignDiscount(models.Model):

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED_AMOUNT = "fixed_amount", "Fixed Amount"
        PRICE_OVERRIDE = "price_override", "Price Override"

    class AppliesTo(models.TextChoices):
        LINE_ITEM = "line_item", "Line Item"
        ORDER = "order", "Order"
        SHIPPING = "shipping", "Shipping"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="discounts"
    )
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    max_quantity = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum price floor after discount",
    )
    applies_to = models.CharField(
        max_length=20, choices=AppliesTo.choices, default=AppliesTo.LINE_ITEM
    )

    def calculate_discount(self, price: Decimal) -> Decimal:
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = price * (self.value / Decimal("100"))
        elif self.discount_type == self.DiscountType.FIXED_AMOUNT:
            discount = self.value
        elif self.discount_type == self.DiscountType.PRICE_OVERRIDE:
            discount = max(price - self.value, Decimal("0"))
        else:
            discount = Decimal("0")

        if self.max_discount_amount is not None:
            discount = min(discount, self.max_discount_amount)

        return discount
