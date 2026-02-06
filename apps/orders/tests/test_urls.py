import pytest
from django.urls import reverse, resolve
from apps.orders.views import CartViewSet, OrderViewSet, CheckoutViewSet


def test_cart_list_url():
    url = reverse("cart-list")
    resolver = resolve(url)
    assert resolver.func.cls == CartViewSet


def test_order_list_url():
    url = reverse("order-list")
    resolver = resolve(url)
    assert resolver.func.cls == OrderViewSet


def test_checkout_create_order_url():
    url = reverse("create-order")
    resolver = resolve(url)

    assert (
        resolver.func.__name__
        == CheckoutViewSet.as_view({"post": "create_order"}).__name__
    )
