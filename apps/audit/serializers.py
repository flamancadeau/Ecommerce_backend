from rest_framework import serializers
from .models import PriceAudit, InventoryAudit, CampaignAudit


class PriceAuditSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    price_book_code = serializers.CharField(source="price_book.code", read_only=True)
    changed_by_short = serializers.SerializerMethodField()
    change_amount = serializers.SerializerMethodField()
    change_percent = serializers.SerializerMethodField()

    class Meta:
        model = PriceAudit
        fields = [
            "id",
            "variant",
            "variant_sku",
            "price_book",
            "price_book_code",
            "old_price",
            "new_price",
            "change_amount",
            "change_percent",
            "currency",
            "reason",
            "changed_at",
            "changed_by",
            "changed_by_short",
        ]
        read_only_fields = ["changed_at", "changed_by"]

    def get_changed_by_short(self, obj):
        return str(obj.changed_by)[:8] if obj.changed_by else "System"

    def get_change_amount(self, obj):
        if obj.old_price and obj.new_price:
            return float(obj.new_price - obj.old_price)
        return None

    def get_change_percent(self, obj):
        if obj.old_price and obj.new_price and obj.old_price != 0:
            return float(((obj.new_price - obj.old_price) / obj.old_price) * 100)
        return None


class InventoryAuditSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    from_to = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAudit
        fields = [
            "id",
            "event_type",
            "variant",
            "variant_sku",
            "warehouse",
            "warehouse_code",
            "quantity",
            "from_quantity",
            "to_quantity",
            "from_to",
            "reference",
            "notes",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_from_to(self, obj):
        if obj.from_quantity is not None and obj.to_quantity is not None:
            return f"{obj.from_quantity} → {obj.to_quantity}"
        return "-"


class CampaignAuditSerializer(serializers.ModelSerializer):
    campaign_code = serializers.CharField(source="campaign.code", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)
    changed_by_short = serializers.SerializerMethodField()

    class Meta:
        model = CampaignAudit
        fields = [
            "id",
            "campaign",
            "campaign_code",
            "campaign_name",
            "changed_field",
            "old_value",
            "new_value",
            "reason",
            "changed_at",
            "changed_by",
            "changed_by_short",
        ]
        read_only_fields = ["changed_at", "changed_by"]

    def get_changed_by_short(self, obj):
        return str(obj.changed_by)[:8] if obj.changed_by else "System"


class AuditReportSerializer(serializers.Serializer):
    """Serializer for generating reports"""

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    format = serializers.ChoiceField(choices=["json", "csv"], default="json")
