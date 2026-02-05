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
    rules = CampaignRuleSerializer(many=True, required=False)
    discounts = CampaignDiscountSerializer(many=True, required=False)
    status = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ("id", "code")

    def create(self, validated_data):
        from django.db import transaction

        rules_data = validated_data.pop("rules", [])
        discounts_data = validated_data.pop("discounts", [])

        with transaction.atomic():
            campaign = Campaign.objects.create(**validated_data)
            for rule_data in rules_data:
                CampaignRule.objects.create(campaign=campaign, **rule_data)
            for discount_data in discounts_data:
                CampaignDiscount.objects.create(campaign=campaign, **discount_data)
            return campaign

    def update(self, instance, validated_data):
        from django.db import transaction

        rules_data = validated_data.pop("rules", None)
        discounts_data = validated_data.pop("discounts", None)

        with transaction.atomic():
            # Update main record
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Update nested rules if provided
            if rules_data is not None:
                instance.rules.all().delete()
                for rule_data in rules_data:
                    CampaignRule.objects.create(campaign=instance, **rule_data)

            # Update nested discounts if provided
            if discounts_data is not None:
                instance.discounts.all().delete()
                for discount_data in discounts_data:
                    CampaignDiscount.objects.create(campaign=instance, **discount_data)

            return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop("code", None)
        return representation
