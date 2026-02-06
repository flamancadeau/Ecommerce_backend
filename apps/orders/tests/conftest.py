import pytest
from decimal import Decimal
from apps.catalog.models import Product, Variant


@pytest.fixture
def sample_product(db):
    return Product.objects.create(
        name="Test Product", slug="test-product", is_active=True
    )


@pytest.fixture
def sample_variant(db, sample_product):
    return Variant.objects.create(
        product=sample_product,
        sku="TEST-SKU-001",
        base_price=Decimal("10.00"),
        is_active=True,
    )
