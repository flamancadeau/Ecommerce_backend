from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from io import StringIO

from .models import PriceAudit, InventoryAudit, CampaignAudit
from .serializers import (
    PriceAuditSerializer,
    InventoryAuditSerializer,
    CampaignAuditSerializer,
    AuditReportSerializer,
)


class PriceAuditViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = PriceAudit.objects.select_related(
        "variant", "price_book", "price_book_entry"
    )
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

    @swagger_auto_schema(
        method="post",
        operation_description="Generate price audit report for a specified date range",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "start_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="Start date for the report (YYYY-MM-DD)",
                    example="2026-02-01",
                ),
                "end_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="End date for the report (YYYY-MM-DD)",
                    example="2026-02-07",
                ),
                "format": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Output format for the report",
                    enum=["json", "csv"],
                    default="json",
                    example="json",
                ),
            },
            example={
                "start_date": "2026-02-01",
                "end_date": "2026-02-07",
                "format": "json",
            },
        ),
        responses={
            200: openapi.Response(
                description="Report generated successfully",
                schema=PriceAuditSerializer(many=True),
            ),
            400: openapi.Response(description="Invalid request parameters"),
        },
    )
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
        """Export price audits using service"""
        csv_data = queryset.to_csv()
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="price_audits_{start_date}_{end_date}.csv"'
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

    @swagger_auto_schema(
        method="post",
        operation_description="Generate inventory audit report for a specified date range",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "start_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="Start date for the report (YYYY-MM-DD)",
                    example="2026-02-01",
                ),
                "end_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="End date for the report (YYYY-MM-DD)",
                    example="2026-02-07",
                ),
                "format": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Output format for the report",
                    enum=["json", "csv"],
                    default="json",
                    example="json",
                ),
            },
            example={
                "start_date": "2026-02-01",
                "end_date": "2026-02-07",
                "format": "json",
            },
        ),
        responses={
            200: openapi.Response(
                description="Report generated successfully",
                schema=InventoryAuditSerializer(many=True),
            ),
            400: openapi.Response(description="Invalid request parameters"),
        },
    )
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
        """Export inventory audits using service"""
        csv_data = queryset.to_csv()
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="inventory_audits_{start_date}_{end_date}.csv"'
        )
        return response


class CampaignAuditViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CampaignAudit.objects.select_related("campaign")
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

    @swagger_auto_schema(
        method="post",
        operation_description="Generate campaign audit report for a specified date range",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "start_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="Start date for the report (YYYY-MM-DD)",
                    example="2026-02-01",
                ),
                "end_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    description="End date for the report (YYYY-MM-DD)",
                    example="2026-02-07",
                ),
                "format": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Output format for the report",
                    enum=["json", "csv"],
                    default="json",
                    example="json",
                ),
            },
            example={
                "start_date": "2026-02-01",
                "end_date": "2026-02-07",
                "format": "json",
            },
        ),
        responses={
            200: openapi.Response(
                description="Report generated successfully",
                schema=CampaignAuditSerializer(many=True),
            ),
            400: openapi.Response(description="Invalid request parameters"),
        },
    )
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
        """Export campaign audits using QuerySet method"""
        csv_data = queryset.to_csv()
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="campaign_audits_{start_date}_{end_date}.csv"'
        )
        return response
