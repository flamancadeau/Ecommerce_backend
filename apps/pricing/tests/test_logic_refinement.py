import pytest
from decimal import Decimal
from django.utils import timezone
from apps.catalog.models import Product, Variant, Category
from apps.pricing.models import PriceBook, PriceBookEntry


@pytest.mark.django_db
class TestPricingRefinement:
    @pytest.fixture
    def setup_data(self):
        category = Category.objects.create(name="Electronics", slug="electronics")
        product = Product.objects.create(
            name="Laptop", slug="laptop", category=category
        )
        variant = Variant.objects.create(
            product=product, sku="LAP-001", base_price=Decimal("1000.00")
        )

        # Default Price Book
        default_pb = PriceBook.objects.create(
            name="Default EUR", currency="EUR", is_default=True, is_active=True
        )
        PriceBookEntry.objects.create(
            price_book=default_pb,
            variant=variant,
            price=Decimal("950.00"),
            min_quantity=1,
        )

        # Region Specific Price Book (Germany)
        germany_pb = PriceBook.objects.create(
            name="Germany Retail",
            currency="EUR",
            country="DE",
            channel="retail",
            is_active=True,
        )

        # Tier 1: 1-5 items
        PriceBookEntry.objects.create(
            price_book=germany_pb,
            variant=variant,
            price=Decimal("900.00"),
            min_quantity=1,
            max_quantity=5,
        )

        # Tier 2: 6+ items
        PriceBookEntry.objects.create(
            price_book=germany_pb,
            variant=variant,
            price=Decimal("850.00"),
            min_quantity=6,
        )

        return {"variant": variant, "default_pb": default_pb, "germany_pb": germany_pb}

    def test_tiered_pricing_logic(self, setup_data):
        variant = setup_data["variant"]
        ctx = {"country": "DE", "channel": "retail", "membership_tier": ""}

        # Test Tier 1 (qty=3)
        price_data = PriceBook.objects.calculate_price(
            variant=variant,
            quantity=3,
            at_time=timezone.now(),
            context=ctx,
        )
        assert price_data["final_unit_price"] == 900.00
        assert price_data["price_book_used"]["price_book_name"] == "Germany Retail"

        # Test Tier 2 (qty=10)
        price_data = PriceBook.objects.calculate_price(
            variant=variant,
            quantity=10,
            at_time=timezone.now(),
            context=ctx,
        )
        assert price_data["final_unit_price"] == 850.00

    def test_price_book_fallback_logic(self, setup_data):
        variant = setup_data["variant"]
        ctx = {"country": "FR", "channel": "retail", "membership_tier": ""}

        # Test Missing Context (e.g. France) -> Should fall back to Default
        price_data = PriceBook.objects.calculate_price(
            variant=variant,
            quantity=1,
            at_time=timezone.now(),
            context=ctx,
        )
        assert price_data["final_unit_price"] == 950.00
        assert price_data["price_book_used"]["price_book_name"] == "Default EUR"

    def test_price_book_entry_validation(self, setup_data):
        variant = setup_data["variant"]
        default_pb = setup_data["default_pb"]

        from apps.pricing.serializers import PriceBookEntrySerializer

        # Test Invalid Quantities (max < min)
        data = {
            "price_book": default_pb.id,
            "variant": variant.id,
            "price": "100.00",
            "min_quantity": 10,
            "max_quantity": 5,
        }
        serializer = PriceBookEntrySerializer(data=data)
        assert not serializer.is_valid()
        assert "max_quantity" in serializer.errors
