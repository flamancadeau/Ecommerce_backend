import pytest
from django.utils import timezone
from apps.promotions.models import Campaign, CampaignRule, CampaignDiscount
from apps.promotions.serializers import CampaignSerializer
from rest_framework.test import APIRequestFactory
import json


@pytest.mark.django_db
class TestCampaignSetup:
    def test_nested_campaign_creation_via_serializer(self):
        """Test that we can create a campaign with rules and discounts in one call."""
        data = {
            "name": "Big Summer Sale",
            "description": "Nested creation test",
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-12-31T23:59:59Z",
            "priority": 10,
            "is_active": True,
            "rules": [
                {
                    "rule_type": "brand",
                    "operator": "equals",
                    "value": "Samsung",
                    "action": "include",
                }
            ],
            "discounts": [
                {"discount_type": "percentage", "value": "15.00", "applies_to": "order"}
            ],
        }

        serializer = CampaignSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        campaign = serializer.save()

        assert Campaign.objects.count() == 1
        assert CampaignRule.objects.filter(campaign=campaign).count() == 1
        assert CampaignDiscount.objects.filter(campaign=campaign).count() == 1
        assert campaign.status == "active"

    def test_campaign_status_with_raw_date_strings(self):
        """
        Verify that our fix for date-string-vs-datetime comparison works.
        """
        from apps.promotions.services import PromotionsService

        # This data uses strings for dates, simulating direct service calls or API raw data
        campaign_data = {
            "name": "Date Fix Test",
            "start_at": "2026-02-01T00:00:00Z",
            "end_at": "2026-02-28T23:59:59Z",
        }

        # This used to crash due to internal status property comparison
        campaign = PromotionsService.create_campaign(campaign_data)

        # If we reach here, it didn't crash. Let's verify status.
        assert campaign.status in ["active", "scheduled", "expired"]
        assert isinstance(campaign.start_at, timezone.datetime)

    def test_nested_campaign_update(self):
        """Test that updating replaces old rules."""
        campaign = Campaign.objects.create(
            name="Initial Campaign",
            start_at=timezone.now(),
            end_at=timezone.now() + timezone.timedelta(days=1),
        )
        CampaignRule.objects.create(
            campaign=campaign, rule_type="brand", value="BrandA"
        )

        new_data = {
            "name": "Updated Campaign",
            "rules": [{"rule_type": "brand", "value": "BrandB"}],
        }

        serializer = CampaignSerializer(instance=campaign, data=new_data, partial=True)
        assert serializer.is_valid()
        serializer.save()

        assert campaign.rules.count() == 1
        assert campaign.rules.first().value == "BrandB"
