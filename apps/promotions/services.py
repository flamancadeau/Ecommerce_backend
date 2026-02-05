from django.db import transaction
from django.utils import timezone
from apps.promotions.models import Campaign, CampaignRule, CampaignDiscount
from apps.audit.models import CampaignAudit


class PromotionsService:
    @staticmethod
    @transaction.atomic
    def create_campaign(campaign_data, rules_data=None, discounts_data=None):
        """
        Create a campaign with rules and discounts.
        """
        # Ensure we don't pass nested data to the main Campaign create
        main_data = campaign_data.copy()
        main_data.pop("rules", None)
        main_data.pop("discounts", None)

        # Parse dates if they are strings to avoid property comparison errors later
        from django.utils.dateparse import parse_datetime

        for field in ["start_at", "end_at"]:
            if isinstance(main_data.get(field), str):
                main_data[field] = parse_datetime(main_data[field])

        campaign = Campaign.objects.create(**main_data)

        if rules_data:
            for rule in rules_data:
                CampaignRule.objects.create(campaign=campaign, **rule)

        if discounts_data:
            for discount in discounts_data:
                CampaignDiscount.objects.create(campaign=campaign, **discount)

        CampaignAudit.objects.create(
            campaign=campaign,
            changed_field="all",
            new_value="Campaign created with initial configuration",
            reason="System creation",
        )
        return campaign

    @staticmethod
    def toggle_campaign_status(campaign_id, is_active):
        """
        Toggle campaign active status and audit it.
        """
        with transaction.atomic():
            campaign = Campaign.objects.select_for_update().get(id=campaign_id)
            old_status = campaign.is_active
            campaign.is_active = is_active
            campaign.save()

            CampaignAudit.objects.create(
                campaign=campaign,
                changed_field="is_active",
                new_value=str(is_active),
                reason="Manual status toggle",
                notes=f"Changed from {old_status} to {is_active}",
            )
            return campaign

    @staticmethod
    def add_rule_to_campaign(campaign_id, rule_data):
        """
        Add a rule to an existing campaign.
        """
        with transaction.atomic():
            campaign = Campaign.objects.get(id=campaign_id)
            rule = CampaignRule.objects.create(campaign=campaign, **rule_data)

            CampaignAudit.objects.create(
                campaign=campaign,
                changed_field="rules",
                new_value=f"Added rule {rule.id}",
                reason="Rule addition",
            )
            return rule
