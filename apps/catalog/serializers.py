from rest_framework import serializers
from django.db import transaction
from .models import Product, Category, Variant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class VariantSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Variant
        fields = [
            "id",
            "product",
            "sku",
            "status",
            "attributes",
            "base_price",
            "compare_at_price",
            "cost_price",
            "tax_class",
            "weight",
            "dimensions",
            "is_active",
            "images",
            "created_at",
            "updated_at",
            "color",
            "size",
        ]

    def validate_sku(self, value):

        query = Variant.objects.filter(sku=value)

        if self.instance and self.instance.id:
            query = query.exclude(id=self.instance.id)

        if query.exists():
            raise serializers.ValidationError(f"SKU '{value}' is already taken.")

        return value

    def update(self, instance, validated_data):

        instance.sku = validated_data.get("sku", instance.sku)
        instance.status = validated_data.get("status", instance.status)
        instance.attributes = validated_data.get("attributes", instance.attributes)
        instance.base_price = validated_data.get("base_price", instance.base_price)
        instance.compare_at_price = validated_data.get(
            "compare_at_price", instance.compare_at_price
        )
        instance.cost_price = validated_data.get("cost_price", instance.cost_price)
        instance.tax_class = validated_data.get("tax_class", instance.tax_class)
        instance.weight = validated_data.get("weight", instance.weight)
        instance.dimensions = validated_data.get("dimensions", instance.dimensions)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.images = validated_data.get("images", instance.images)

        if "product" in validated_data:
            instance.product = validated_data["product"]

        instance.save()
        return instance


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "brand",
            "category",
            "category_name",
            "is_active",
            "launch_date",
            "variants",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Product name cannot be empty.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        variants_data = self.initial_data.get("variants")
        product = Product.objects.create(**validated_data)

        if variants_data:
            for variant_data in variants_data:
                variant_data["product"] = product
                Variant.objects.create(**variant_data)

        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
