from rest_framework import viewsets, status, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import PriceBook, PriceBookEntry, TaxRate
from .serializers import (
    PriceBookSerializer,
    PriceBookEntrySerializer,
    TaxRateSerializer,
    PriceQuoteRequestSerializer,  # added
    ExplainPriceQuerySerializer,  # added
)

# ==================== CRUD VIEWSETS ====================


class PriceBookViewSet(viewsets.ModelViewSet):
    """CRUD operations for Price Books."""

    queryset = PriceBook.objects.all()
    serializer_class = PriceBookSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            return Response(
                {
                    "status": True,
                    "message": f"{self.queryset.model.__name__} created successfully!",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        except IntegrityError as e:
            return Response(
                {
                    "status": False,
                    "message": "The combination of country, channel, and customer group must be unique.",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        return Response(
            {
                "status": True,
                "message": f"{self.queryset.model.__name__} updated successfully!",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        return Response(
            {
                "status": True,
                "message": f"{self.queryset.model.__name__} deleted successfully (soft delete).",
                "data": {},
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return self.perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return self.perform_destroy(instance)


class PriceBookEntryViewSet(viewsets.ModelViewSet):
    """CRUD operations for Price Book Entries."""

    queryset = PriceBookEntry.objects.select_related(
        "price_book", "variant", "product", "category"
    ).all()
    serializer_class = PriceBookEntrySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        instance = serializer.save()
        return Response(
            {
                "status": True,
                "message": "PriceBookEntry created successfully!",
                "data": PriceBookEntrySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        return Response(
            {
                "status": True,
                "message": "PriceBookEntry updated successfully!",
                "data": PriceBookEntrySerializer(instance).data,
            },
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        return Response(
            {
                "status": True,
                "message": "PriceBookEntry deleted successfully (soft delete).",
                "data": {},
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return self.perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return self.perform_destroy(instance)


class TaxRateViewSet(viewsets.ModelViewSet):
    """CRUD operations for Tax Rates."""

    queryset = TaxRate.objects.all()
    serializer_class = TaxRateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        instance = serializer.save()
        return Response(
            {
                "status": True,
                "message": f"{self.queryset.model.__name__} created successfully!",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        return Response(
            {
                "status": True,
                "message": f"{self.queryset.model.__name__} updated successfully!",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        return Response(
            {
                "status": True,
                "message": f"{self.queryset.model.__name__} deleted successfully (soft delete).",
                "data": {},
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return self.perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return self.perform_destroy(instance)


# ==================== PRICING ENGINE ====================


@api_view(["POST"])
@permission_classes([AllowAny])
def price_quote(request):

    try:
        data = request.data

        # 1. Parse the 'at' timestamp
        at_time = parse_timestamp(data.get("at"))

        # 2. Get customer context
        customer_context = data.get("customer_context", {})

        # 3. Process each item
        items_data = data.get("items", [])
        results = []

        for item in items_data:
            item_result = calculate_item_price(
                variant_id=item["variant_id"],
                quantity=item["quantity"],
                at_time=at_time,
                customer_context=customer_context,
            )
            results.append(item_result)

        # 4. Calculate summary
        summary = {
            "subtotal": float(sum(item["extended_price"] for item in results)),
            "tax_total": float(sum(item["tax_amount"] for item in results)),
            "discount_total": float(
                sum(item.get("discount_amount", 0) for item in results)
            ),
            "total": float(sum(item["total_price"] for item in results)),
            "item_count": len(results),
        }

        return Response(
            {
                "status": True,
                "message": "Price calculated successfully",
                "data": {
                    "calculated_at": data["at"],
                    "customer_context": customer_context,
                    "items": results,
                    "summary": summary,
                },
            }
        )

    except Exception as e:
        return Response(
            {
                "status": False,
                "message": f"Error calculating price: {str(e)}",
                "data": {},
            },
            status=400,
        )


@swagger_auto_schema(
    method="get",
    query_serializer=ExplainPriceQuerySerializer,
    responses={
        200: openapi.Response(
            description="Price explanation",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT),
        )
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def explain_price(request):

    try:
        variant_id = request.GET.get("variant_id")
        at_time = parse_timestamp(request.GET.get("at"))
        context_str = request.GET.get("context", "{}")
        quantity = int(request.GET.get("quantity", 1))

        customer_context = json.loads(context_str)

        from apps.catalog.models import Variant

        variant = get_object_or_404(Variant, id=variant_id)

        # Get all data that would affect price
        base_price = get_base_price(variant, customer_context, at_time)
        campaigns = get_applicable_campaigns(
            variant, customer_context, at_time, quantity
        )
        tax_rate = get_tax_rate(
            customer_context.get("country", "DE"), variant.tax_class, at_time
        )

        # Get final calculation
        final_calculation = calculate_item_price(
            variant_id, quantity, at_time, customer_context
        )

        # Build explanation
        explanation = {
            "variant": {
                "id": str(variant.id),
                "sku": variant.sku,
                "base_price": float(variant.base_price),
                "tax_class": variant.tax_class,
            },
            "calculated_at": at_time.isoformat(),
            "customer_context": customer_context,
            "base_price_used": float(base_price),
            "tax_rate_used": float(tax_rate),
            "campaigns_considered": [
                {
                    "id": str(campaign.id),
                    "code": campaign.code,
                    "name": campaign.name,
                    "priority": campaign.priority,
                    "stackable": campaign.stacking_type != "none",
                    "start_at": campaign.start_at.isoformat(),
                    "end_at": campaign.end_at.isoformat(),
                }
                for campaign in campaigns
            ],
            "price_books_checked": list(
                PriceBookEntry.objects.filter(
                    variant=variant,
                    effective_from__lte=at_time,
                    effective_to__gte=at_time,
                ).values("price_book__code", "price_book__name", "price")
            ),
            "final_calculation": final_calculation,
        }

        return Response(
            {
                "status": True,
                "message": "Price explanation generated",
                "data": explanation,
            }
        )

    except Exception as e:
        return Response(
            {
                "status": False,
                "message": f"Error generating explanation: {str(e)}",
                "data": {},
            },
            status=400,
        )


# ==================== HELPER FUNCTIONS ====================


def parse_timestamp(timestamp_str):
    """Parse timestamp string to datetime object."""
    try:
        # Handle ISO format with Z
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp_str)
    except:
        # Default to current time if parsing fails
        return timezone.now()


def calculate_item_price(variant_id, quantity, at_time, customer_context):
    """
    Calculate price for a single variant.
    """
    from apps.catalog.models import Variant
    from apps.promotions.models import Campaign, CampaignRule, CampaignDiscount

    # 1. Get the variant
    variant = get_object_or_404(Variant, id=variant_id)

    # 2. Get base price (from price book or variant)
    base_price = get_base_price(variant, customer_context, at_time)

    # 3. Find applicable campaigns
    applicable_campaigns = get_applicable_campaigns(
        variant=variant,
        customer_context=customer_context,
        at_time=at_time,
        quantity=quantity,
    )

    # 4. Apply discounts (by priority)
    discount_amount = Decimal("0")
    applied_campaigns = []

    # Sort campaigns by priority (highest first)
    applicable_campaigns.sort(key=lambda x: x.priority, reverse=True)

    for campaign in applicable_campaigns:
        campaign_discount = calculate_campaign_discount(
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

    # 5. Calculate final price
    final_price = base_price - discount_amount

    # Ensure price doesn't go below zero
    if final_price < Decimal("0"):
        final_price = Decimal("0")
        discount_amount = base_price

    # 6. Calculate tax
    tax_rate = get_tax_rate(
        country=customer_context.get("country", "DE"),
        tax_class=variant.tax_class,
        at_time=at_time,
    )

    tax_amount = final_price * tax_rate

    # 7. Round to 2 decimal places
    final_price = final_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax_amount = tax_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    extended_price = final_price * quantity
    total_tax = tax_amount * quantity
    total_price = (final_price + tax_amount) * quantity

    # 8. Check availability
    availability = check_availability(variant, quantity)

    # 9. Get price book info
    price_book_info = get_price_book_info(variant, customer_context, at_time)

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


def get_base_price(variant, customer_context, at_time):
    """
    Get base price from price book or variant.
    Priority: PriceBookEntry > Variant base_price
    """
    # Look for price book entry
    price_entry = (
        PriceBookEntry.objects.filter(
            Q(variant=variant)
            | Q(product=variant.product)
            | Q(category=variant.product.category),
            price_book__currency=customer_context.get("currency", "EUR"),
            price_book__country=customer_context.get("country", ""),
            price_book__channel=customer_context.get("channel", ""),
            price_book__customer_group=customer_context.get(
                "membership_tier", "retail"
            ),
            effective_from__lte=at_time,
            effective_to__gte=at_time,
            price_book__is_active=True,
        )
        .order_by(
            "variant",  # Exact variant match first
            "product",  # Then product match
            "category",  # Then category match
        )
        .first()
    )

    if price_entry:
        return price_entry.price

    # Fallback to variant base price
    return variant.base_price


def get_applicable_campaigns(variant, customer_context, at_time, quantity):
    """
    Get all campaigns that apply to this variant.
    """
    from apps.promotions.models import Campaign, CampaignRule

    # Get all active campaigns at the time
    campaigns = Campaign.objects.filter(
        start_at__lte=at_time, end_at__gte=at_time, is_active=True
    )

    applicable = []

    for campaign in campaigns:
        # Check customer eligibility
        if not is_customer_eligible(campaign, customer_context):
            continue

        # Check campaign rules
        if not does_campaign_apply(campaign, variant):
            continue

        # Check quantity requirements
        if not meets_quantity_requirements(campaign, quantity):
            continue

        applicable.append(campaign)

    return applicable


def is_customer_eligible(campaign, customer_context):
    """Check if customer is eligible for campaign."""
    # Check customer groups
    if campaign.customer_groups:
        customer_group = customer_context.get("membership_tier", "standard")
        if customer_group not in campaign.customer_groups:
            return False

    # Check exclusions
    if campaign.excluded_customer_groups:
        customer_group = customer_context.get("membership_tier", "standard")
        if customer_group in campaign.excluded_customer_groups:
            return False

    # Check minimum order amount (if applicable)
    if campaign.min_order_amount:
        # This would need the total order amount to check
        pass

    return True


def does_campaign_apply(campaign, variant):
    """Check if campaign applies to variant based on rules."""
    rules = campaign.rules.all()

    # If no rules, campaign applies to everything
    if not rules.exists():
        return True

    # Check each rule
    for rule in rules:
        if rule.rule_type == "product":
            if rule.value == str(variant.product.id) and rule.scope == "include":
                return True
            elif rule.value == str(variant.product.id) and rule.scope == "exclude":
                return False

        elif rule.rule_type == "variant":
            if rule.value == str(variant.id) and rule.scope == "include":
                return True
            elif rule.value == str(variant.id) and rule.scope == "exclude":
                return False

        elif rule.rule_type == "category":
            if variant.product.category and rule.value == str(
                variant.product.category.id
            ):
                return rule.scope == "include"

        elif rule.rule_type == "brand":
            if rule.value == variant.product.brand:
                return rule.scope == "include"

        elif rule.rule_type == "attribute":
            attr_key, attr_value = rule.value.split(":", 1)
            if variant.attributes.get(attr_key) == attr_value:
                return rule.scope == "include"

    return False


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

    # Apply maximum discount cap
    if discount.max_discount_amount:
        amount = min(amount, discount.max_discount_amount)

    # Apply minimum price floor
    if discount.min_price:
        final_price = max(base_price - amount, discount.min_price)
        amount = base_price - final_price

    return amount


def get_tax_rate(country, tax_class, at_time):
    """Get tax rate for country and tax class at specific time."""
    tax_rate = TaxRate.objects.filter(
        country=country,
        tax_class=tax_class,
        effective_from__lte=at_time.date(),
        effective_to__gte=at_time.date(),
        is_active=True,
    ).first()

    return tax_rate.rate if tax_rate else Decimal("0.19")  # Default 19%


def get_price_book_info(variant, customer_context, at_time):
    """Get which price book was used."""
    price_entry = PriceBookEntry.objects.filter(
        variant=variant,
        price_book__currency=customer_context.get("currency", "EUR"),
        effective_from__lte=at_time,
        effective_to__gte=at_time,
    ).first()

    if price_entry:
        return {
            "price_book": price_entry.price_book.code,
            "price_book_name": price_entry.price_book.name,
            "price": float(price_entry.price),
        }
    return None


def check_availability(variant, quantity):
    """Check if variant is available."""
    from apps.inventory.models import Stock

    total_available = sum(
        stock.available for stock in Stock.objects.filter(variant=variant)
    )

    if total_available >= quantity:
        return {
            "available": True,
            "message": "In stock",
            "available_quantity": total_available,
        }
    else:
        return {
            "available": False,
            "message": "Out of stock",
            "available_quantity": total_available,
            "backorderable": any(
                stock.backorderable for stock in Stock.objects.filter(variant=variant)
            ),
        }
