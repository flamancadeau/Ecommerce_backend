from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from django.db.models import Q, F
from django.utils import timezone
from .models import Warehouse, Stock, InboundShipment, InboundItem
from .serializers import (
    WarehouseSerializer,
    StockSerializer,
    InboundShipmentSerializer,
    InboundItemSerializer,
)


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

    def create(self, request, *args, **kwargs):

        variant_id = request.data.get("variant")
        warehouse_id = request.data.get("warehouse")

        if variant_id and warehouse_id:
            try:

                existing_stock = Stock.objects.get(
                    variant_id=variant_id, warehouse_id=warehouse_id
                )

                serializer = self.get_serializer(
                    existing_stock, data=request.data, partial=False
                )
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                return Response(
                    {
                        "success": True,
                        "message": "Stock updated successfully!",
                        "data": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
            except Stock.DoesNotExist:

                pass

        return super().create(request, *args, **kwargs)


class InboundShipmentViewSet(_BaseViewSet):
    queryset = InboundShipment.objects.prefetch_related("items").all()
    serializer_class = InboundShipmentSerializer

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


class InboundItemViewSet(_BaseViewSet):
    queryset = InboundItem.objects.select_related(
        "inbound", "variant", "warehouse"
    ).all()
    serializer_class = InboundItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        inbound_id = self.request.query_params.get("inbound")
        variant_id = self.request.query_params.get("variant")

        if inbound_id:
            queryset = queryset.filter(inbound_id=inbound_id)
        if variant_id:
            queryset = queryset.filter(variant_id=variant_id)

        return queryset
