from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse
import csv
from io import StringIO

from .models import PriceAudit, InventoryAudit, CampaignAudit
from .serializers import (
    PriceAuditSerializer,
    InventoryAuditSerializer,
    CampaignAuditSerializer,
    AuditReportSerializer,
)


class PriceAuditViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = PriceAudit.objects.select_related("variant", "price_book", "changed_by")
    serializer_class = PriceAuditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["currency", "changed_at"]
    search_fields = ["variant__sku", "price_book__code", "reason"]
    ordering_fields = ["changed_at", "variant__sku", "price_book__code"]
    ordering = ["-changed_at"]

    @action(detail=False, methods=["post"])
    def generate_report(self, request):
        """Generate price audit report"""
        serializer = AuditReportSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            start_date = data.get(
                "start_date", timezone.now().date() - timedelta(days=7)
            )
            end_date = data.get("end_date", timezone.now().date())
            format_type = data.get("format", "json")

            queryset = self.filter_queryset(
                self.get_queryset().filter(
                    changed_at__date__gte=start_date, changed_at__date__lte=end_date
                )
            )

            if format_type == "csv":
                return self._export_csv(queryset, start_date, end_date)

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _export_csv(self, queryset, start_date, end_date):
        """Export price audits as CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="price_audits_{start_date}_{end_date}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "SKU",
                "Price Book",
                "Old Price",
                "New Price",
                "Currency",
                "Change Amount",
                "Change %",
                "Reason",
                "Changed At",
                "Changed By",
            ]
        )

        for audit in queryset:
            writer.writerow(
                [
                    audit.variant.sku if audit.variant else "N/A",
                    audit.price_book.code if audit.price_book else "N/A",
                    audit.old_price,
                    audit.new_price,
                    audit.currency,
                    (
                        audit.new_price - audit.old_price
                        if audit.old_price and audit.new_price
                        else ""
                    ),
                    (
                        f"{((audit.new_price - audit.old_price) / audit.old_price * 100):.2f}%"
                        if audit.old_price and audit.new_price and audit.old_price != 0
                        else ""
                    ),
                    audit.reason or "",
                    (
                        audit.changed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if audit.changed_at
                        else ""
                    ),
                    str(audit.changed_by)[:8] if audit.changed_by else "System",
                ]
            )

        return response


class InventoryAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing inventory audit logs.
    """

    queryset = InventoryAudit.objects.select_related("variant", "warehouse")
    serializer_class = InventoryAuditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["event_type", "created_at", "warehouse"]
    search_fields = ["variant__sku", "reference", "notes"]
    ordering_fields = ["created_at", "variant__sku", "warehouse__code"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["post"])
    def generate_report(self, request):
        """Generate inventory audit report"""
        serializer = AuditReportSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            start_date = data.get(
                "start_date", timezone.now().date() - timedelta(days=7)
            )
            end_date = data.get("end_date", timezone.now().date())
            format_type = data.get("format", "json")

            queryset = self.filter_queryset(
                self.get_queryset().filter(
                    created_at__date__gte=start_date, created_at__date__lte=end_date
                )
            )

            if format_type == "csv":
                return self._export_csv(queryset, start_date, end_date)

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _export_csv(self, queryset, start_date, end_date):
        """Export inventory audits as CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="inventory_audits_{start_date}_{end_date}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Event Type",
                "SKU",
                "Warehouse",
                "Quantity",
                "From Quantity",
                "To Quantity",
                "Reference",
                "Notes",
                "Created At",
            ]
        )

        for audit in queryset:
            writer.writerow(
                [
                    audit.event_type,
                    audit.variant.sku if audit.variant else "N/A",
                    audit.warehouse.code if audit.warehouse else "N/A",
                    audit.quantity,
                    audit.from_quantity or "",
                    audit.to_quantity or "",
                    audit.reference or "",
                    audit.notes or "",
                    (
                        audit.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if audit.created_at
                        else ""
                    ),
                ]
            )

        return response


class CampaignAuditViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CampaignAudit.objects.select_related("campaign", "changed_by")
    serializer_class = CampaignAuditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["changed_field", "changed_at"]
    search_fields = ["campaign__code", "campaign__name", "reason", "changed_field"]
    ordering_fields = ["changed_at", "campaign__code", "changed_field"]
    ordering = ["-changed_at"]

    @action(detail=False, methods=["post"])
    def generate_report(self, request):
        """Generate campaign audit report"""
        serializer = AuditReportSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            start_date = data.get(
                "start_date", timezone.now().date() - timedelta(days=7)
            )
            end_date = data.get("end_date", timezone.now().date())
            format_type = data.get("format", "json")

            queryset = self.filter_queryset(
                self.get_queryset().filter(
                    changed_at__date__gte=start_date, changed_at__date__lte=end_date
                )
            )

            if format_type == "csv":
                return self._export_csv(queryset, start_date, end_date)

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _export_csv(self, queryset, start_date, end_date):
        """Export campaign audits as CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="campaign_audits_{start_date}_{end_date}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Campaign Code",
                "Campaign Name",
                "Changed Field",
                "Old Value",
                "New Value",
                "Reason",
                "Changed At",
                "Changed By",
            ]
        )

        for audit in queryset:
            writer.writerow(
                [
                    audit.campaign.code if audit.campaign else "N/A",
                    (
                        audit.campaign.name
                        if audit.campaign and hasattr(audit.campaign, "name")
                        else "N/A"
                    ),
                    audit.changed_field or "",
                    (
                        (audit.old_value[:50] + "...")
                        if audit.old_value and len(audit.old_value) > 50
                        else (audit.old_value or "")
                    ),
                    (
                        (audit.new_value[:50] + "...")
                        if audit.new_value and len(audit.new_value) > 50
                        else (audit.new_value or "")
                    ),
                    audit.reason or "",
                    (
                        audit.changed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if audit.changed_at
                        else ""
                    ),
                    str(audit.changed_by)[:8] if audit.changed_by else "System",
                ]
            )

        return response
