import pytest
from decimal import Decimal
from apps.orders.serializers import CartSerializer, OrderSerializer
from apps.orders.models import Cart, Order

pytestmark = pytest.mark.django_db


class TestCartSerializer:
    def test_cart_serializer_fields(self):
        cart = Cart.objects.create()
        serializer = CartSerializer(cart)
        data = serializer.data
        assert "id" in data
        assert "session_id" in data
        assert "item_count" in data
        assert "total_value" in data


class TestOrderSerializer:
    def test_order_serializer_fields(self):
        order = Order.objects.create(
            customer_email="test@example.com", shipping_address={}, billing_address={}
        )
        serializer = OrderSerializer(order)
        data = serializer.data
        assert "id" in data
        assert "order_number" in data
        assert "status" in data
        assert "items" in data
