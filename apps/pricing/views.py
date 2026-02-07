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
from apps.audit.models import PriceAudit
from apps.catalog.models import Variant
from .serializers import (
    PriceBookSerializer,
    PriceBookEntrySerializer,
    TaxRateSerializer,
    PriceQuoteRequestSerializer,
    PriceExplainRequestSerializer,
)


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

        PriceAudit.objects.create(
            variant=instance.variant,
            price_book=instance.price_book,
            price_book_entry=instance,
            new_price=instance.price,
            currency=instance.price_book.currency,
            reason="Price entry created",
        )

        return Response(
            {
                "status": True,
                "message": "PriceBookEntry created successfully!",
                "data": PriceBookEntrySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        entry = self.get_object()
        old_price = entry.price
        instance = serializer.save()

        if old_price != instance.price:
            PriceAudit.objects.create(
                variant=instance.variant,
                price_book=instance.price_book,
                price_book_entry=instance,
                old_price=old_price,
                new_price=instance.price,
                currency=instance.price_book.currency,
                reason="Price entry updated",
            )

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


@swagger_auto_schema(
    method="post",
    request_body=PriceQuoteRequestSerializer,
    responses={
        200: openapi.Response(
            description="Price calculation successful",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT),
        ),
        400: "Invalid request data",
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def price_quote(request):
    """
    Calculate price for a list of items based on customer context and time.
    """
    serializer = PriceQuoteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": "Invalid request data",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_data = serializer.validated_data
        at_time = validated_data.get("at") or timezone.now()
        customer_context = validated_data.get("customer_context", {})
        items_data = validated_data.get("items", [])
        results = []

        for item in items_data:
            item_result = PriceBook.objects.calculate_price(
                variant=get_object_or_404(Variant, id=item["variant_id"]),
                quantity=item["quantity"],
                at_time=at_time,
                context=customer_context,
            )
            results.append(item_result)

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
                    "calculated_at": at_time.isoformat(),
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
    method="post",
    request_body=PriceExplainRequestSerializer,
    responses={
        200: openapi.Response(
            description="Price explanation generated",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT),
        ),
        400: "Invalid request data",
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def explain_price(request):
    """
    Generate a detailed explanation of how a price was calculated for a variant.
    """
    serializer = PriceExplainRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": "Invalid request data",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_data = serializer.validated_data
        variant_id = validated_data["variant_id"]
        at_time = validated_data.get("at") or timezone.now()
        quantity = validated_data.get("quantity", 1)
        customer_context = validated_data.get("customer_context", {})

        from apps.promotions.models import Campaign

        variant = get_object_or_404(Variant, id=variant_id)

        # Use the central calculation logic
        final_calculation = PriceBook.objects.calculate_price(
            variant, customer_context, quantity, at_time
        )

        checks = []
        possible_entries = PriceBookEntry.objects.filter(
            Q(variant=variant)
            | Q(product=variant.product)
            | Q(category=variant.product.category)
        ).select_related("price_book")

        customer_currency = customer_context.get("currency", "EUR")
        customer_country = customer_context.get("country", "")
        customer_channel = customer_context.get("channel", "web")
        customer_membership = customer_context.get("membership_tier", "retail")

        for entry in possible_entries:
            pb = entry.price_book
            mismatches = []

            if not pb.is_active:
                mismatches.append("Price Book is inactive")
            if pb.currency != customer_currency:
                mismatches.append(f"Currency ({pb.currency} != {customer_currency})")
            if pb.country and pb.country != customer_country:
                mismatches.append(f"Country ({pb.country} != {customer_country})")
            if pb.channel and pb.channel != customer_channel:
                mismatches.append(f"Channel ({pb.channel} != {customer_channel})")
            if pb.customer_group and pb.customer_group != customer_membership:
                mismatches.append(
                    f"Group ({pb.customer_group} != {customer_membership})"
                )

            if entry.effective_from and entry.effective_from > at_time:
                mismatches.append(f"Not effective yet (Starts {entry.effective_from})")
            if entry.effective_to and entry.effective_to < at_time:
                mismatches.append(f"Expired (Ended {entry.effective_to})")

            if entry.min_quantity > quantity:
                mismatches.append(
                    f"Quantity too low (Need {entry.min_quantity}, have {quantity})"
                )
            if entry.max_quantity and entry.max_quantity < quantity:
                mismatches.append(
                    f"Quantity too high (Max {entry.max_quantity}, have {quantity})"
                )

            checks.append(
                {
                    "code": pb.code,
                    "name": pb.name,
                    "price": float(entry.price),
                    "is_eligible": len(mismatches) == 0,
                    "mismatches": mismatches,
                    "level": (
                        "variant"
                        if entry.variant
                        else ("product" if entry.product else "category")
                    ),
                }
            )

        campaign_checks = []
        potential_campaigns = Campaign.objects.filter(
            end_at__gte=at_time - timezone.timedelta(days=1)
        )

        for campaign in potential_campaigns:
            c_mismatches = []
            if not campaign.is_active:
                c_mismatches.append("Campaign is disabled (is_active=False)")
            if campaign.start_at > at_time:
                c_mismatches.append(f"Scheduled for future ({campaign.start_at})")
            if campaign.end_at < at_time:
                c_mismatches.append(f"Already expired ({campaign.end_at})")

            # Check eligibility using campaign model methods
            if not campaign.is_customer_eligible(customer_context):
                c_mismatches.append(
                    f"Customer group not eligible. Allowed: {campaign.customer_groups}"
                )

            if not campaign.applies_to_variant(variant):
                c_mismatches.append("Product/Brand rules do not match this variant")

            if not campaign.meets_quantity_requirements(quantity):
                c_mismatches.append("Quantity requirements not met")

            campaign_checks.append(
                {
                    "code": campaign.code,
                    "name": campaign.name,
                    "is_eligible": len(c_mismatches) == 0,
                    "mismatches": c_mismatches,
                    "priority": campaign.priority,
                }
            )

        explanation = {
            "variant": {
                "id": str(variant.id),
                "sku": variant.sku,
                "base_price": float(variant.base_price),
                "tax_class": variant.tax_class,
            },
            "calculated_at": at_time.isoformat(),
            "customer_context": {
                "currency": customer_currency,
                "country": customer_country,
                "channel": customer_channel,
                "membership_tier": customer_membership,
            },
            "base_price_used": final_calculation.get("base_price"),
            "tax_rate_used": final_calculation.get("tax_rate"),
            "price_books_analysis": checks,
            "campaigns_analysis": campaign_checks,
            "final_calculation": final_calculation,
        }

        return Response(
            {
                "status": True,
                "message": "Price explanation generated with troubleshooting diagnostics",
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


def parse_timestamp(timestamp_str):
    """Parse timestamp string to datetime object."""
    try:
        if not timestamp_str:
            return timezone.now()
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp_str)
    except:
        return timezone.now()
