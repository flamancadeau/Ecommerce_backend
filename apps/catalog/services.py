from django.db import transaction
from django.core.exceptions import ValidationError
from apps.catalog.models import Product, Variant, Category


class CatalogService:
    @staticmethod
    @transaction.atomic
    def create_product_with_variants(product_data, variants_data=None):
        """
        Create a product and optionally its variants in one transaction.
        """

        product_data = product_data.copy()
        variants = variants_data or product_data.pop("variants", None)

        category_id = product_data.pop("category", None)
        if category_id:
            try:
                product_data["category"] = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                raise ValidationError(f"Category {category_id} not found")

        product = Product.objects.create(**product_data)

        if variants:
            for variant_data in variants:
                variant_data["product"] = product
                Variant.objects.create(**variant_data)

        return product

    @staticmethod
    @transaction.atomic
    def update_product(product_id, product_data):
        """
        Update product and handle relationships.
        """
        try:
            product = Product.objects.select_for_update().get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError("Product not found")

        category_id = product_data.pop("category", None)
        if category_id:
            try:
                product.category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                raise ValidationError(f"Category {category_id} not found")

        for attr, value in product_data.items():
            setattr(product, attr, value)

        product.save()
        return product

    @staticmethod
    def deactivate_product(product_id):
        """
        Deactivate product and all its variants.
        """
        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=product_id)
            product.is_active = False
            product.save()
            product.variants.all().update(is_active=False)
            return product
