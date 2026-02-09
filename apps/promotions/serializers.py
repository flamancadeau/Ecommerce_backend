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
        from apps.audit.models import CampaignAudit
        from django.db import transaction

        rules_data = validated_data.pop("rules", [])
        discounts_data = validated_data.pop("discounts", [])

        with transaction.atomic():
            campaign = Campaign.objects.create(**validated_data)

            for rule_data in rules_data:
                CampaignRule.objects.create(campaign=campaign, **rule_data)

            for discount_data in discounts_data:
                CampaignDiscount.objects.create(campaign=campaign, **discount_data)

            CampaignAudit.objects.create(
                campaign=campaign,
                changed_field="all",
                new_value="Campaign created",
                reason="API creation",
            )
            return campaign

    def update(self, instance, validated_data):
        from apps.audit.models import CampaignAudit
        from django.db import transaction

        rules_data = validated_data.pop("rules", None)
        discounts_data = validated_data.pop("discounts", None)

        old_is_active = instance.is_active

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if instance.is_active != old_is_active:
                CampaignAudit.objects.create(
                    campaign=instance,
                    changed_field="is_active",
                    old_value=str(old_is_active),
                    new_value=str(instance.is_active),
                    reason="API update",
                )

            if rules_data is not None:
                instance.rules.all().delete()
                for rule_data in rules_data:
                    CampaignRule.objects.create(campaign=instance, **rule_data)

                CampaignAudit.objects.create(
                    campaign=instance,
                    changed_field="rules",
                    new_value=f"Rules updated ({len(rules_data)} rules)",
                    reason="API update",
                )

            if discounts_data is not None:
                instance.discounts.all().delete()
                for discount_data in discounts_data:
                    CampaignDiscount.objects.create(campaign=instance, **discount_data)

            return instance
