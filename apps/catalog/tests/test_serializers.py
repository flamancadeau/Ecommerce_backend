import pytest
from apps.catalog.serializers import (
    ProductSerializer,
    CategorySerializer,
    VariantSerializer,
)
from apps.catalog.models import Product, Category, Variant

pytestmark = pytest.mark.django_db


class TestCategorySerializer:
    def test_valid_category_serializer(self):
        data = {"name": "Test Cat", "slug": "test-cat"}
        serializer = CategorySerializer(data=data)
        assert serializer.is_valid()
        category = serializer.save()
        assert category.name == "Test Cat"


class TestProductSerializer:
    def test_valid_product_serializer(self):
        data = {"name": "Test Prod", "slug": "test-prod", "description": "Desc"}
        serializer = ProductSerializer(data=data)
        assert serializer.is_valid()
        product = serializer.save()
        assert product.name == "Test Prod"

    def test_invalid_product_name(self):
        data = {"name": "", "slug": "test-prod"}
        serializer = ProductSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors


class TestVariantSerializer:
    def test_valid_variant_serializer(self):
        product = Product.objects.create(name="Test Prod", slug="test-prod")
        data = {"product": product.id, "sku": "SKU1", "base_price": "10.00"}
        serializer = VariantSerializer(data=data)
        assert serializer.is_valid()
        variant = serializer.save()
        assert variant.sku == "SKU1"

    def test_duplicate_sku(self):
        product = Product.objects.create(name="Test Prod", slug="test-prod")
        Variant.objects.create(product=product, sku="SKU1", base_price=10.00)
        data = {"product": product.id, "sku": "SKU1", "base_price": "20.00"}
        serializer = VariantSerializer(data=data)
        assert not serializer.is_valid()
        assert "sku" in serializer.errors or "non_field_errors" in serializer.errors
