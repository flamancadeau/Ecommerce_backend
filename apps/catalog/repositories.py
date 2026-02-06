from django.utils import timezone
from .models import Category, Product, Variant


class CatalogRepository:
    @staticmethod
    def get_active_categories():
        return Category.objects.filter(is_active=True)

    @staticmethod
    def get_active_products():
        return Product.objects.filter(is_active=True, launch_date__lte=timezone.now())

    @staticmethod
    def get_variant_by_sku(sku):
        return Variant.objects.filter(sku=sku, is_active=True, status="active").first()

    @staticmethod
    def get_product_variants(product_id):
        return Variant.objects.filter(
            product_id=product_id, is_active=True, status="active"
        )
