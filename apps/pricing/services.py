from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.catalog.models import Variant
from apps.pricing.models import PriceBookEntry, TaxRate
from apps.promotions.models import Campaign
from .repositories import PricingRepository


class PricingService:
    @staticmethod
    def calculate_item_price(variant_id, quantity, at_time, customer_context):
        """
        Calculate price for a single variant.
        """
        variant = get_object_or_404(Variant, id=variant_id)

        base_price = PricingService.get_base_price(
            variant, customer_context, at_time, quantity
        )

        applicable_campaigns = PricingService.get_applicable_campaigns(
            variant=variant,
            customer_context=customer_context,
            at_time=at_time,
            quantity=quantity,
        )

        discount_amount = Decimal("0")
        applied_campaigns = []

        applicable_campaigns.sort(key=lambda x: x.priority, reverse=True)

        # Track if we can continue stacking
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

            campaign_discount = PricingService.calculate_campaign_discount(
                campaign=campaign, base_price=base_price, quantity=quantity
            )

            if campaign_discount > 0:
                discount_amount += campaign_discount
                applied_campaigns.append(
                    {
                        "campaign_id": str(campaign.id),
                        "code": campaign.code,
                        "name": campaign.name,
                        "discount_amount": float(campaign_discount),
                        "discount_type": (
                            campaign.discounts.first().discount_type
                            if campaign.discounts.exists()
                            else "unknown"
                        ),
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

        tax_rate = PricingService.get_tax_rate(
            country=customer_context.get("country", "DE"),
            tax_class=variant.tax_class,
            at_time=at_time,
        )

        tax_amount = final_price * tax_rate

        final_price = final_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_amount = tax_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        extended_price = final_price * quantity
        total_tax = tax_amount * quantity
        total_price = (final_price + tax_amount) * quantity

        # Check availability
        from apps.inventory.services import InventoryService

        availability = InventoryService.check_availability(variant, quantity)
        price_book_info = PricingService.get_price_book_info(
            variant, customer_context, at_time, quantity
        )

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

    @staticmethod
    def get_base_price(variant, customer_context, at_time, quantity=1):
        """
        Get base price from price book or variant using Repository.
        """
        currency = customer_context.get("currency", "EUR")
        country = customer_context.get("country", "")
        channel = customer_context.get("channel", "web")
        customer_group = customer_context.get("membership_tier", "retail")

        price_entry = PricingRepository.get_price_entry(
            variant, currency, country, channel, customer_group, quantity
        )

        if price_entry:
            return price_entry.price

        return variant.base_price

    @staticmethod
    def get_applicable_campaigns(variant, customer_context, at_time, quantity):
        """
        Get all campaigns that apply to this variant.
        """
        campaigns = Campaign.objects.filter(
            start_at__lte=at_time, end_at__gte=at_time, is_active=True
        )

        applicable = []

        for campaign in campaigns:
            if not PricingService.is_customer_eligible(campaign, customer_context):
                continue

            if not PricingService.does_campaign_apply(campaign, variant):
                continue

            if not PricingService.meets_quantity_requirements(campaign, quantity):
                continue

            applicable.append(campaign)

        return applicable

    @staticmethod
    def is_customer_eligible(campaign, customer_context):
        """Check if customer is eligible for campaign."""
        if campaign.customer_groups:
            customer_group = customer_context.get("membership_tier", "standard")
            if customer_group not in campaign.customer_groups:
                return False

        if campaign.excluded_customer_groups:
            customer_group = customer_context.get("membership_tier", "standard")
            if customer_group in campaign.excluded_customer_groups:
                return False

        return True

    @staticmethod
    def does_campaign_apply(campaign, variant):
        """Check if campaign applies to variant based on rules."""
        rules = campaign.rules.all()

        if not rules.exists():
            return True

        include_rules = [r for r in rules if r.action == "include"]
        exclude_rules = [r for r in rules if r.action == "exclude"]

        # 1. Check exclusions first
        for rule in exclude_rules:
            if PricingService.evaluate_rule(rule, variant):
                return False

        # 2. Check inclusions
        if not include_rules:
            return True

        for rule in include_rules:
            if PricingService.evaluate_rule(rule, variant):
                return True

        return False

    @staticmethod
    def evaluate_rule(rule, variant):
        if rule.rule_type == "product":
            return rule.value == str(variant.product.id)

        elif rule.rule_type == "variant":
            return rule.value == str(variant.id)

        elif rule.rule_type == "category":
            if variant.product.category:
                return rule.value == str(variant.product.category.id)

        elif rule.rule_type == "brand":
            return rule.value == variant.product.brand

        elif rule.rule_type == "attribute":
            try:
                attr_key, attr_value = rule.value.split(":", 1)
                return variant.attributes.get(attr_key) == attr_value
            except ValueError:
                return False

        return False

    @staticmethod
    def meets_quantity_requirements(campaign, quantity):
        """Check if quantity meets campaign requirements."""
        discount = campaign.discounts.first()
        if not discount:
            return True

        if quantity < discount.min_quantity:
            return False

        if discount.max_quantity and quantity > discount.max_quantity:
            return False

        return True

    @staticmethod
    def calculate_campaign_discount(campaign, base_price, quantity):
        """Calculate discount amount from campaign."""
        discount = campaign.discounts.first()
        if not discount:
            return Decimal("0")

        if discount.discount_type == "percentage":
            amount = base_price * (discount.value / Decimal("100"))
        elif discount.discount_type == "fixed_amount":
            amount = discount.value
        elif discount.discount_type == "price_override":
            amount = max(base_price - discount.value, Decimal("0"))
        else:
            amount = Decimal("0")

        if discount.max_discount_amount:
            amount = min(amount, discount.max_discount_amount)

        if discount.min_price:
            final_price = max(base_price - amount, discount.min_price)
            amount = base_price - final_price

        return amount

    @staticmethod
    def get_tax_rate(country, tax_class, at_time):
        """Get tax rate using Repository."""
        tax_rate = PricingRepository.get_tax_rate_entry(country, tax_class)
        return tax_rate.rate if tax_rate else Decimal("0.19")

    @staticmethod
    def get_price_book_info(variant, customer_context, at_time, quantity=1):
        """Get price book info using Repository."""
        currency = customer_context.get("currency", "EUR")
        country = customer_context.get("country", "")
        channel = customer_context.get("channel", "web")
        customer_group = customer_context.get("membership_tier", "retail")

        price_entry = PricingRepository.get_price_book_info(
            variant, currency, country, channel, customer_group, quantity
        )

        if price_entry:
            return {
                "price_book": price_entry.price_book.code,
                "price_book_name": price_entry.price_book.name,
                "price": float(price_entry.price),
                "applied_at": (
                    "variant"
                    if price_entry.variant
                    else ("product" if price_entry.product else "category")
                ),
            }
        return None
