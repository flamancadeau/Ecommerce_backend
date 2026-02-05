from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from django.db.models import Q, F
from django.utils import timezone
from .models import Warehouse, Stock, InboundShipment, InboundItem
from django.db import transaction
from django.db.models import Sum
from apps.audit.models import InventoryAudit
from apps.audit.idempotency import idempotent_request
from apps.catalog.models import Variant
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    WarehouseSerializer,
    StockSerializer,
    InboundShipmentSerializer,
    InboundShipmentWriteSerializer,
    InboundItemSerializer,
)
from .services import InventoryService


class _BaseViewSet(viewsets.ModelViewSet):

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    "success": True,
                    "message": f"{self.queryset.model.__name__} created successfully!",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
                headers=headers,
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    "success": False,
                    "message": f"Failed to create {self.queryset.model.__name__}.",
                    "errors": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": str(e),
                    "errors": {"non_field_errors": [str(e)]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "message": f"{self.queryset.model.__name__}s retrieved successfully!",
                "data": serializer.data,
                "count": len(serializer.data),
            }
        )

    def retrieve(self, request, *args, **kwargs):
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(
                {
                    "success": True,
                    "message": f"{self.queryset.model.__name__} retrieved successfully!",
                    "data": serializer.data,
                }
            )
        except NotFound:
            return Response(
                {
                    "success": False,
                    "message": f"{self.queryset.model.__name__} not found.",
                },
                status=404,
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                {
                    "success": True,
                    "message": f"{self.queryset.model.__name__} updated successfully!",
                    "data": serializer.data,
                }
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    "success": False,
                    "message": f"Failed to update {self.queryset.model.__name__}.",
                    "errors": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {
                "success": True,
                "message": f"{self.queryset.model.__name__} deleted successfully!",
            },
            status=status.HTTP_200_OK,
        )


class WarehouseViewSet(_BaseViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        country = self.request.query_params.get("country")
        search = self.request.query_params.get("search")

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        if country:
            queryset = queryset.filter(country=country)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search)
                | Q(name__icontains=search)
                | Q(city__icontains=search)
            )

        return queryset


class StockViewSet(_BaseViewSet):
    queryset = Stock.objects.select_related(
        "variant", "variant__product", "warehouse"
    ).all()
    serializer_class = StockSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        variant_id = self.request.query_params.get("variant")
        warehouse_id = self.request.query_params.get("warehouse")
        sku = self.request.query_params.get("sku")

        if variant_id:
            queryset = queryset.filter(variant_id=variant_id)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if sku:
            queryset = queryset.filter(variant__sku__icontains=sku)

        return queryset

    @swagger_auto_schema(
        operation_description="Manual adjustment of stock levels.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["variant", "warehouse", "quantity"],
            properties={
                "variant": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="The UUID of the variant.",
                ),
                "warehouse": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="The UUID of the warehouse.",
                ),
                "quantity": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="The quantity to add (positive) or subtract (negative).",
                ),
                "reason": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The reason for the adjustment.",
                    default="Manual adjustment",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Stock adjusted successfully", schema=StockSerializer
            ),
            400: openapi.Response(description="Bad request"),
        },
    )
    @action(detail=False, methods=["post"], url_path="adjust")
    @idempotent_request()
    def adjust(self, request):
        """Manual adjustment of stock."""
        variant_id = request.data.get("variant")
        warehouse_id = request.data.get("warehouse")
        quantity = int(request.data.get("quantity", 0))
        reason = request.data.get("reason", "Manual adjustment")

        if not all([variant_id, warehouse_id]):
            return Response(
                {"success": False, "message": "variant and warehouse are required"},
                status=400,
            )

        try:
            stock = InventoryService.adjust_stock(
                variant_id, warehouse_id, quantity, reason
            )
            return Response({"success": True, "data": StockSerializer(stock).data})
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=400)

    @action(
        detail=False, methods=["get"], url_path="variant-status/(?P<variant_id>[^/.]+)"
    )
    def variant_status(self, request, variant_id=None):
        """Get stock status for a variant across all warehouses."""
        stocks = Stock.objects.filter(variant_id=variant_id)
        inbound_items = InboundItem.objects.filter(
            variant_id=variant_id, inbound__status__in=["pending", "in_transit"]
        )

        data = {
            "variant_id": variant_id,
            "total_on_hand": stocks.aggregate(Sum("on_hand"))["on_hand__sum"] or 0,
            "total_reserved": stocks.aggregate(Sum("reserved"))["reserved__sum"] or 0,
            "total_available": stocks.aggregate(Sum("available"))["available__sum"]
            or 0,
            "warehouses": StockSerializer(stocks, many=True).data,
            "inbound": InboundItemSerializer(inbound_items, many=True).data,
        }
        return Response({"success": True, "data": data})

    @swagger_auto_schema(
        operation_description="Create or update stock record. If quantity is provided, it will be adjusted.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["variant", "warehouse"],
            properties={
                "variant": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="Variant UUID",
                ),
                "warehouse": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="Warehouse UUID",
                ),
                "quantity": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Optional: Quantity to adjust (can be positive or negative)",
                ),
                "reason": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Optional: Reason for adjustment",
                    default="Manual adjustment",
                ),
                "backorderable": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "backorder_limit": openapi.Schema(type=openapi.TYPE_INTEGER),
                "safety_stock": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
        responses={
            201: openapi.Response("Stock created/updated", StockSerializer),
            400: "Bad Request",
        },
    )
    def create(self, request, *args, **kwargs):
        # Override to handle upsert-like behavior with adjustment
        variant_id = request.data.get("variant")
        warehouse_id = request.data.get("warehouse")
        quantity = request.data.get("quantity")
        reason = request.data.get("reason", "Manual adjustment")

        if not variant_id or not warehouse_id:
            return super().create(request, *args, **kwargs)

        try:
            with transaction.atomic():
                if quantity is not None:
                    # Use service for adjustment to maintain audit log
                    stock = InventoryService.adjust_stock(
                        variant_id, warehouse_id, int(quantity), reason
                    )
                else:
                    # Just get or create the stock record
                    stock, _ = Stock.objects.get_or_create(
                        variant_id=variant_id, warehouse_id=warehouse_id
                    )

                # Update other fields (settings)
                serializer = self.get_serializer(stock, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()

                return Response(
                    {
                        "success": True,
                        "message": "Stock record processed successfully!",
                        "data": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=400)


class InboundShipmentViewSet(_BaseViewSet):
    queryset = InboundShipment.objects.prefetch_related("items").all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return InboundShipmentWriteSerializer
        return InboundShipmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get("status")
        supplier = self.request.query_params.get("supplier")
        overdue = self.request.query_params.get("overdue")

        if status_param:
            queryset = queryset.filter(status=status_param)
        if supplier:
            queryset = queryset.filter(supplier__icontains=supplier)
        if overdue and overdue.lower() == "true":
            queryset = queryset.filter(
                Q(status="pending") | Q(status="in_transit"),
                expected_at__lt=timezone.now(),
            )

        return queryset

    @action(detail=True, methods=["post"], url_path="receive")
    @idempotent_request()
    def receive(self, request, pk=None):
        """Receive items from an inbound shipment."""
        receipts = request.data.get("items", [])

        if not receipts:
            return Response(
                {"success": False, "message": "No items provided"}, status=400
            )

        from .services import InventoryService

        try:
            shipment = InventoryService.receive_shipment(pk, receipts)
            return Response(
                {
                    "success": True,
                    "message": f"Items received successfully. Shipment status: {shipment.status}",
                }
            )
        except ValueError as e:
            return Response({"success": False, "message": str(e)}, status=400)
        except Exception as e:
            return Response({"success": False, "message": "Internal error"}, status=500)


class InboundItemViewSet(_BaseViewSet):
    queryset = InboundItem.objects.select_related(
        "inbound", "variant", "warehouse"
    ).all()
    serializer_class = InboundItemSerializer

    @swagger_auto_schema(
        operation_description="Create an inbound item linked to a shipment.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["inbound", "variant", "warehouse", "expected_quantity"],
            properties={
                "inbound": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="The ID of the Inbound Shipment (from create shipment response)",
                ),
                "variant": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="The Product Variant ID",
                ),
                "warehouse": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="The Warehouse ID",
                ),
                "expected_quantity": openapi.Schema(type=openapi.TYPE_INTEGER),
                "received_quantity": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="The quantity already received (defaults to 0)",
                    default=0,
                ),
                "unit_cost": openapi.Schema(type=openapi.TYPE_NUMBER, format="decimal"),
                "received_at": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATETIME,
                    description="Date and time when the item was received",
                    nullable=True,
                ),
                "notes": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        inbound_id = self.request.query_params.get("inbound")
        variant_id = self.request.query_params.get("variant")

        if inbound_id:
            queryset = queryset.filter(inbound_id=inbound_id)
        if variant_id:
            queryset = queryset.filter(variant_id=variant_id)

        return queryset
