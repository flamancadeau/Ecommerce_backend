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


class CampaignManager(models.Manager):
    def get_applicable(self, variant, customer_context, at_time, quantity):
        """
        Get all campaigns that apply to this variant.
        """
        campaigns = self.filter(
            start_at__lte=at_time, end_at__gte=at_time, is_active=True
        )

        applicable = []

        for campaign in campaigns:
            if not campaign.is_customer_eligible(customer_context):
                continue

            if not campaign.applies_to_variant(variant):
                continue

            if not campaign.meets_quantity_requirements(quantity):
                continue

            applicable.append(campaign)

        return applicable


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

    objects = CampaignManager()

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

    def is_customer_eligible(self, customer_context):
        """Check if customer is eligible for campaign."""
        customer_group = str(customer_context.get("membership_tier", "retail")).lower()

        def get_group_list(data):
            if not data:
                return []
            if isinstance(data, list):
                return [str(g).lower() for g in data]
            if isinstance(data, dict):
                return [str(k).lower() for k, v in data.items() if v]
            return []

        allowed_groups = get_group_list(self.customer_groups)
        if allowed_groups and customer_group not in allowed_groups:
            return False

        excluded_groups = get_group_list(self.excluded_customer_groups)
        if excluded_groups and customer_group in excluded_groups:
            return False

        return True

    def applies_to_variant(self, variant):
        """Check if campaign applies to variant based on rules."""
        rules = self.rules.all()

        if not rules.exists():
            return True

        include_rules = [r for r in rules if r.action == "include"]
        exclude_rules = [r for r in rules if r.action == "exclude"]

        for rule in exclude_rules:
            if self._evaluate_rule(rule, variant):
                return False

        if not include_rules:
            return True

        for rule in include_rules:
            if self._evaluate_rule(rule, variant):
                return True

        return False

    def _evaluate_rule(self, rule, variant):
        """Evaluate a single campaign rule against a variant."""
        if rule.rule_type == "product":
            return rule.value == str(variant.product.id)

        elif rule.rule_type == "variant":
            return rule.value == str(variant.id)

        elif rule.rule_type == "category":
            if variant.product.category:
                return rule.value == str(variant.product.category.id)

        elif rule.rule_type == "brand":
            return (rule.value or "").lower() == (variant.product.brand or "").lower()

        elif rule.rule_type == "attribute":
            try:
                attr_key, attr_value = rule.value.split(":", 1)
                variant_val = variant.attributes.get(attr_key)
                if variant_val is None:
                    return False
                return str(variant_val).lower() == str(attr_value).lower()
            except (ValueError, AttributeError):
                return False

        return False

    def meets_quantity_requirements(self, quantity):
        """Check if quantity meets campaign requirements."""
        discount = self.discounts.first()
        if not discount:
            return True

        if quantity < discount.min_quantity:
            return False

        if discount.max_quantity and quantity > discount.max_quantity:
            return False

        return True

    def calculate_discount(self, base_price, quantity):
        """Calculate discount amount."""
        discount = self.discounts.first()
        if not discount:
            return Decimal("0")

        return discount.calculate_discount(base_price)


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
        ATTRIBUTE = "attribute", "Attribute"

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
            amount = price * (self.value / Decimal("100"))
        elif self.discount_type == self.DiscountType.FIXED_AMOUNT:
            amount = self.value
        elif self.discount_type == self.DiscountType.PRICE_OVERRIDE:
            amount = max(price - self.value, Decimal("0"))
        else:
            amount = Decimal("0")

        if self.max_discount_amount is not None:
            amount = min(amount, self.max_discount_amount)

        if self.min_price is not None:
            final_price = max(price - amount, self.min_price)
            amount = price - final_price

        return amount
