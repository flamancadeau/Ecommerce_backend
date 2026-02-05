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
from .serializers import (
    PriceBookSerializer,
    PriceBookEntrySerializer,
    TaxRateSerializer,
    PriceQuoteRequestSerializer,
    ExplainPriceQuerySerializer,
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


@api_view(["POST"])
@permission_classes([AllowAny])
def price_quote(request):

    try:
        data = request.data
        at_time = parse_timestamp(data.get("at"))
        customer_context = data.get("customer_context", {})
        items_data = data.get("items", [])
        results = []

        from apps.pricing.services import PricingService

        for item in items_data:
            item_result = PricingService.calculate_item_price(
                variant_id=item["variant_id"],
                quantity=item["quantity"],
                at_time=at_time,
                customer_context=customer_context,
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
                    "calculated_at": data.get("at", timezone.now().isoformat()),
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
        from apps.pricing.services import PricingService

        variant = get_object_or_404(Variant, id=variant_id)

        base_price = PricingService.get_base_price(variant, customer_context, at_time)
        campaigns = PricingService.get_applicable_campaigns(
            variant, customer_context, at_time, quantity
        )
        tax_rate = PricingService.get_tax_rate(
            customer_context.get("country", "DE"), variant.tax_class, at_time
        )

        final_calculation = PricingService.calculate_item_price(
            variant_id, quantity, at_time, customer_context
        )

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
            # Revisit this query if needed, but it's okay for now
            "price_books_checked": list(
                PriceBookEntry.objects.filter(
                    variant=variant,
                    effective_from__lte=at_time,
                )
                .filter(Q(effective_to__gte=at_time) | Q(effective_to__isnull=True))
                .values("price_book__code", "price_book__name", "price")
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
