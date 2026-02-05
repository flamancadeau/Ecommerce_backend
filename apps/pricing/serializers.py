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


class PriceQuoteItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CustomerContextSerializer(serializers.Serializer):
    country = serializers.CharField(
        max_length=2, required=False, help_text="ISO country code"
    )
    currency = serializers.CharField(max_length=3, required=False)
    channel = serializers.CharField(max_length=50, required=False)
    membership_tier = serializers.CharField(max_length=50, required=False)


class PriceQuoteRequestSerializer(serializers.Serializer):
    at = serializers.DateTimeField(
        required=False, help_text="ISO timestamp, e.g. 2024-01-30T10:00:00Z"
    )
    customer_context = CustomerContextSerializer(required=False)
    items = PriceQuoteItemSerializer(many=True)


class ExplainPriceQuerySerializer(serializers.Serializer):
    variant_id = serializers.UUIDField(help_text="UUID of the variant")
    quantity = serializers.IntegerField(
        required=False, default=1, help_text="Quantity to calculate for"
    )
    at = serializers.DateTimeField(
        required=False, help_text="ISO timestamp for price-as-of-time"
    )
    context = serializers.CharField(
        required=False,
        default="{}",
        help_text="JSON string of customer context (currency, country, etc.)",
    )
