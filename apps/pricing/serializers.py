from rest_framework import serializers
from .models import PriceBook, PriceBookEntry, TaxRate


class PriceBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceBook
        fields = [
            "id",
            "name",
            "code",
            "description",
            "currency",
            "country",
            "channel",
            "customer_group",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "code"]


class PriceBookEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceBookEntry
        fields = [
            "id",
            "price_book",
            "variant",
            "product",
            "category",
            "price",
            "compare_at_price",
            "effective_from",
            "effective_to",
            "min_quantity",
            "max_quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):

        variant = attrs.get("variant")
        product = attrs.get("product")
        category = attrs.get("category")

        provided = sum([bool(variant), bool(product), bool(category)])
        if provided == 0:
            raise serializers.ValidationError(
                "One of 'variant', 'product' or 'category' must be set."
            )
        if provided > 1:
            raise serializers.ValidationError(
                "Only one of 'variant', 'product' or 'category' may be set."
            )
        return attrs


class TaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = [
            "id",
            "country",
            "state",
            "rate",
            "tax_class",
            "description",
            "is_active",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
