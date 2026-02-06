import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from apps.catalog.models import Product, Category

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@example.com", "password")


class TestProductViewSet:
    def test_list_products(self, api_client):
        Product.objects.create(name="Prod 1", slug="prod-1")
        url = reverse("product-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_create_product(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("product-list")
        data = {"name": "New Prod", "slug": "new-prod", "description": "Desc"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Product.objects.count() == 1


class TestCategoryViewSet:
    def test_list_categories(self, api_client):
        Category.objects.create(name="Cat 1", slug="cat-1")
        url = reverse("category-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
