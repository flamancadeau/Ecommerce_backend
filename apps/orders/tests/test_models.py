import pytest
from decimal import Decimal
from django.utils import timezone
from apps.orders.models import Cart, CartItem, Order, OrderItem, Reservation
from apps.catalog.models import Variant
from apps.inventory.models import Warehouse

pytestmark = pytest.mark.django_db


class TestCartModel:
    def test_cart_creation(self):
        cart = Cart.objects.create()
        assert cart.id is not None
        assert cart.created_at is not None
        assert cart.updated_at is not None

    def test_cart_is_expired(self):
        cart = Cart.objects.create()
        assert cart.is_expired is False

        cart.expires_at = timezone.now() - timezone.timedelta(days=1)

        assert cart.is_expired is True

    def test_cart_total_value_and_item_count(self, sample_variant):
        cart = Cart.objects.create()
        item = CartItem.objects.create(
            cart=cart, variant=sample_variant, quantity=2, unit_price=Decimal("10.00")
        )

        assert cart.item_count == 2
        assert cart.total_value == Decimal("20.00")


class TestOrderModel:
    def test_order_number_generation(self):
        order = Order.objects.create(
            customer_email="test@example.com", shipping_address={}, billing_address={}
        )
        assert order.order_number is not None
        assert order.order_number.startswith("ORD-")

    def test_order_status_default(self):
        order = Order.objects.create(
            customer_email="test@example.com", shipping_address={}, billing_address={}
        )
        assert order.status == "draft"
