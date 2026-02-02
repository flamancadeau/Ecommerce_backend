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
    STACKING_CHOICES = [
        ("none", "No Stacking"),
        ("all", "Stack All"),
        ("exclusive", "Exclusive"),
        ("combined", "Combined"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    priority = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    stacking_type = models.CharField(
        max_length=20, choices=STACKING_CHOICES, default="none"
    )
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    usage_limit = models.IntegerField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
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
    RULE_TYPE_CHOICES = [
        ("product", "Product"),
        ("variant", "Variant"),
        ("category", "Category"),
        ("brand", "Brand"),
    ]

    OPERATOR_CHOICES = [
        ("equals", "Equals"),
        ("in", "In"),
        ("between", "Between"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="rules"
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES)
    value = models.TextField()
    order = models.IntegerField(default=0)

    SCOPE_CHOICES = [
        ("global", "Global"),
        ("line_item", "Line Item"),
    ]
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="global")

    class Meta:
        ordering = ["order"]


class CampaignDiscount(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed_amount", "Fixed Amount"),
        ("price_override", "Price Override"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="discounts"
    )
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    max_quantity = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )

    APPLIES_TO_CHOICES = [
        ("line_item", "Line Item"),
        ("order", "Order"),
        ("shipping", "Shipping"),
    ]
    applies_to = models.CharField(
        max_length=20, choices=APPLIES_TO_CHOICES, default="line_item"
    )

    def calculate_discount(self, price):
        if self.discount_type == "percentage":
            discount = price * (self.value / Decimal("100"))
        elif self.discount_type == "fixed_amount":
            discount = self.value
        elif self.discount_type == "price_override":
            discount = max(price - self.value, Decimal("0"))
        else:
            discount = Decimal("0")

        if self.max_discount_amount:
            discount = min(discount, self.max_discount_amount)

        return discount
