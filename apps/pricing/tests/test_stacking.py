import pytest
from decimal import Decimal
from django.utils import timezone
from apps.catalog.models import Product, Variant
from apps.promotions.models import Campaign, CampaignDiscount
from apps.pricing.services import PricingService

pytestmark = pytest.mark.django_db


class TestPricingStacking:
    @pytest.fixture
    def product(self):
        return Product.objects.create(name="Test Phone", slug="test-phone")

    @pytest.fixture
    def variant(self, product):
        return Variant.objects.create(
            product=product, sku="TP-001", base_price=Decimal("100.00"), is_active=True
        )

    def test_scenario_2_stacking(self, variant):
        """
        Scenario 2:
        - A: 10% off (priority 10, stackable=all)
        - B: 20% off (priority 20, stackable=all)
        - C: 5 off (priority 15, stackable=none/exclusive)

        Logic:
        1. B (prio 20) applied first. Discount: 20. New price basis? usually base price unless overrides. Here percent off base.
        2. C (prio 15) is exclusive.
           If exclusive means "I cannot stack with others", then:
           Since B is already applied (higher priority), C cannot apply?
           OR: C invalidates B? "Highest priority wins". B is 20, C is 15.
           So B wins.
        3. A (prio 10). Stackable.
           So we have B + A.

        Let's adjust Scenario 2 to match the prompt exactly:
        "Scenario 2 — Overlapping Discounts with Priority & Stacking"
        - A: 10% off (priority 10)
        - B: 20% off (priority 20)
        - C: 5 off (priority 15, stackable=false/exclusive)

        Prompt says: "Highest priority wins unless stackable allows combination".
        Calculations:
        - B (20) checks out.
        - C (15, Exclusive). Can it apply? B is already applied.
          If C is exclusive, it generally means "I must be alone".
          Since a higher priority one exists, C is skipped.
        - A (10). Stackable. B is stackable (assumed 'all').
          So final: B + A.

        Total Discount: 20% of 100 + 10% of 100 = 20 + 10 = 30.
        (Assuming simple additive percentages from base price)
        """
        now = timezone.now()
        start = now - timezone.timedelta(days=1)
        end = now + timezone.timedelta(days=1)

        camp_b = Campaign.objects.create(
            name="Campaign B",
            start_at=start,
            end_at=end,
            priority=20,
            stacking_type="all",
        )
        CampaignDiscount.objects.create(
            campaign=camp_b, discount_type="percentage", value=Decimal("20.00")
        )

        camp_c = Campaign.objects.create(
            name="Campaign C",
            start_at=start,
            end_at=end,
            priority=15,
            stacking_type="exclusive",
        )
        CampaignDiscount.objects.create(
            campaign=camp_c, discount_type="fixed_amount", value=Decimal("5.00")
        )

        camp_a = Campaign.objects.create(
            name="Campaign A",
            start_at=start,
            end_at=end,
            priority=10,
            stacking_type="all",
        )
        CampaignDiscount.objects.create(
            campaign=camp_a, discount_type="percentage", value=Decimal("10.00")
        )

        result = PricingService.calculate_item_price(
            variant_id=variant.id, quantity=1, at_time=now, customer_context={}
        )

        assert result["base_price"] == 100.00
        assert result["discount_amount"] == 30.00

        applied_names = [c["name"] for c in result["applied_campaigns"]]
        assert "Campaign B" in applied_names
        assert "Campaign A" in applied_names
        assert "Campaign C" not in applied_names

    def test_exclusive_wins(self, variant):
        """
        Test where Exclusive is highest priority.
        - C: 50% off (priority 30, exclusive)
        - B: 20% off (priority 20, stackable)
        """
        now = timezone.now()
        start = now - timezone.timedelta(days=1)
        end = now + timezone.timedelta(days=1)

        camp_c = Campaign.objects.create(
            name="Exclusive High",
            start_at=start,
            end_at=end,
            priority=30,
            stacking_type="exclusive",
        )
        CampaignDiscount.objects.create(
            campaign=camp_c, discount_type="percentage", value=Decimal("50.00")
        )

        camp_b = Campaign.objects.create(
            name="Stackable Low",
            start_at=start,
            end_at=end,
            priority=20,
            stacking_type="all",
        )
        CampaignDiscount.objects.create(
            campaign=camp_b, discount_type="percentage", value=Decimal("20.00")
        )

        result = PricingService.calculate_item_price(
            variant_id=variant.id, quantity=1, at_time=now, customer_context={}
        )

        assert result["discount_amount"] == 50.00
        applied_names = [c["name"] for c in result["applied_campaigns"]]
        assert "Exclusive High" in applied_names
        assert "Stackable Low" not in applied_names

    def test_explain_price(self, variant):
        from rest_framework.test import APIClient

        client = APIClient()
        now = timezone.now()

        camp = Campaign.objects.create(
            name="Explain Test",
            start_at=now - timezone.timedelta(days=1),
            end_at=now + timezone.timedelta(days=1),
            priority=100,
        )
        CampaignDiscount.objects.create(
            campaign=camp, discount_type="percentage", value=Decimal("15.00")
        )

        url = f"/api/pricing/explain/?variant_id={variant.id}&at={now.isoformat()}"
        response = client.get(url)
        assert response.status_code == 200
        data = response.data["data"]
        assert data["base_price_used"] == 100.0
        assert len(data["campaigns_considered"]) >= 1
        assert data["final_calculation"]["discount_amount"] == 15.0
