from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator
from safedelete.models import SafeDeleteModel
import uuid


class CategoryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Category(SafeDeleteModel):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def available(self):
        return self.filter(is_active=True, launch_date__lte=timezone.now())


class Product(SafeDeleteModel):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    brand = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    launch_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["launch_date"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.name

    def deactivate(self):
        with transaction.atomic():
            self.is_active = False
            self.save()
            self.variants.all().update(is_active=False)


class VariantQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, status="active")

    def by_sku(self, sku):
        return self.filter(sku=sku, is_active=True, status="active").first()

    def for_product(self, product_id):
        return self.filter(product_id=product_id, is_active=True, status="active")


class Variant(SafeDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISCONTINUED = "discontinued", "Discontinued"
        OUT_OF_SEASON = "out_of_season", "Out of Season"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    attributes = models.JSONField(default=dict, help_text="Color, size, material etc.")
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    compare_at_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    tax_class = models.CharField(max_length=50, default="standard")
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    dimensions = models.JSONField(
        default=dict, blank=True, help_text="Length, width, height in cm"
    )
    is_active = models.BooleanField(default=True)
    images = models.JSONField(
        default=list, blank=True, help_text="List of image URLs/metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VariantQuerySet.as_manager()

    class Meta:
        ordering = ["sku"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["base_price"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.sku}"

    @property
    def color(self):
        return self.attributes.get("color")

    @property
    def size(self):
        return self.attributes.get("size")
