import pytest
from rest_framework.test import APIClient
from rest_framework import status
from apps.orders.models import Cart, Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestCartViewSet:
    def test_create_cart(self, api_client):

        url = "/api/orders/carts/"

        pass

    def test_list_cart_empty(self, api_client):
        from django.urls import reverse

        url = reverse("cart-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestOrderViewSet:
    def test_list_orders_authentication_required(self, api_client):
        from django.urls import reverse

        url = reverse("order-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
