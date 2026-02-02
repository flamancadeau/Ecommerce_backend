from rest_framework import serializers
from .models import (
    PriceBook,
    Campaign,
    CampaignRule,
    CampaignDiscount,
)


class PriceBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceBook
        fields = "__all__"

        ref_name = "PromotionsPriceBookSerializer"


class CampaignRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignRule
        fields = "__all__"
        read_only_fields = ("id", "campaign")


class CampaignDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignDiscount
        fields = "__all__"
        read_only_fields = ("id", "campaign")


class CampaignSerializer(serializers.ModelSerializer):
    rules = CampaignRuleSerializer(many=True, read_only=True)
    discounts = CampaignDiscountSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = "__all__"

        read_only_fields = ("id", "code")

    def to_representation(self, instance):

        representation = super().to_representation(instance)
        representation.pop("code", None)
        return representation
