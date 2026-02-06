from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Cart, CartItem, Order, OrderItem, Reservation


class CartItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    variant_name = serializers.CharField(source="variant.product.name", read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "variant_sku",
            "variant_name",
            "quantity",
            "unit_price",
            "total_price",
        ]
        read_only_fields = ["id", "unit_price", "total_price"]


class CartItemAddSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartItemUpdateSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CartItemRemoveSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    total_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = [
            "id",
            "session_id",
            "user_id",
            "items",
            "item_count",
            "total_value",
            "created_at",
            "expires_at",
            "is_expired",
        ]
        read_only_fields = ["id", "created_at", "is_expired"]


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant",
            "sku",
            "variant_name",
            "quantity",
            "unit_price",
            "total_price",
            "warehouse",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_id",
            "customer_email",
            "status",
            "subtotal",
            "tax_amount",
            "shipping_amount",
            "total",
            "currency",
            "items",
            "item_count",
            "created_at",
            "shipping_address",
            "billing_address",
        ]
        read_only_fields = fields


class ReservationSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "reservation_token",
            "variant",
            "warehouse",
            "quantity",
            "status",
            "expires_at",
            "order",
            "is_expired",
            "created_at",
        ]
        read_only_fields = ["id", "reservation_token", "created_at", "is_expired"]
