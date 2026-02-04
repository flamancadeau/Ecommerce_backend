import pytest
from apps.catalog.models import Product, Category, Variant

pytestmark = pytest.mark.django_db


class TestCategoryModel:
    def test_create_category(self):
        category = Category.objects.create(name="Test Cat", slug="test-cat")
        assert category.id is not None
        assert str(category) == "Test Cat"


class TestProductModel:
    def test_create_product(self):
        product = Product.objects.create(name="Test Prod", slug="test-prod")
        assert product.id is not None
        assert str(product) == "Test Prod"


class TestVariantModel:
    def test_create_variant(self):
        product = Product.objects.create(name="Test Prod", slug="test-prod")
        variant = Variant.objects.create(product=product, sku="SKU1", base_price=10.00)
        assert variant.id is not None
        assert str(variant) == "Test Prod - SKU1"
