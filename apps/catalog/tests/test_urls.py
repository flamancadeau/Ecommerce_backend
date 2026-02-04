import pytest
from django.urls import reverse, resolve
from apps.catalog.views import ProductViewSet, CategoryViewSet, VariantViewSet


def test_product_list_url():
    url = reverse("product-list")
    resolver = resolve(url)
    assert resolver.func.cls == ProductViewSet


def test_category_list_url():
    url = reverse("category-list")
    resolver = resolve(url)
    assert resolver.func.cls == CategoryViewSet


def test_variant_list_url():
    url = reverse("variant-list")
    resolver = resolve(url)
    assert resolver.func.cls == VariantViewSet
