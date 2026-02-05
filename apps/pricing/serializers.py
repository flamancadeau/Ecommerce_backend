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

    def validate(self, attrs):
        """Custom validation to provide a helpful error message for duplicate context."""
        country = attrs.get("country", "")
        channel = attrs.get("channel", "")
        customer_group = attrs.get("customer_group", "")

        # Check for unique_together constraint manually to provide a better error
        qs = PriceBook.objects.filter(
            country=country, channel=channel, customer_group=customer_group
        )

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        existing = qs.first()
        if existing:
            raise serializers.ValidationError(
                {
                    "non_field_errors": f"A Price Book with this context (Country: {country}, Channel: {channel}, Group: {customer_group}) already exists. Please update the existing Price Book (ID: {existing.id}) or use a different combination."
                }
            )
        return attrs


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

        # Best Practice Check: Max Quantity must be >= Min Quantity
        min_q = attrs.get("min_quantity", 1)
        max_q = attrs.get("max_quantity")

        if max_q is not None and max_q < min_q:
            raise serializers.ValidationError(
                {
                    "max_quantity": f"Max quantity ({max_q}) cannot be less than Min quantity ({min_q})."
                }
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
