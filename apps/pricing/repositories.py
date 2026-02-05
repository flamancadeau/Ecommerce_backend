from django.db.models import Q
from django.utils import timezone
from .models import PriceBook, PriceBookEntry, TaxRate


class PricingRepository:
    @staticmethod
    def get_price_entry(variant, currency, country, channel, customer_group):
        """Finds the most specific price entry valid right now."""
        now = timezone.now()
        return (
            PriceBookEntry.objects.filter(
                Q(variant=variant)
                | Q(product=variant.product)
                | Q(category=variant.product.category),
                price_book__currency=currency,
                price_book__country=country,
                price_book__channel=channel,
                price_book__customer_group=customer_group,
                price_book__is_active=True,
            )
            .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
            .order_by("variant", "product", "category")
            .first()
        )

    @staticmethod
    def get_tax_rate_entry(country, tax_class):
        """Finds an active tax rate for the given context."""
        today = timezone.now().date()
        return (
            TaxRate.objects.filter(
                country=country,
                tax_class=tax_class,
                is_active=True,
                effective_from__lte=today,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .first()
        )

    @staticmethod
    def get_price_book_info(variant_id, currency):
        """Simple lookup for price book metadata."""
        now = timezone.now()
        return (
            PriceBookEntry.objects.filter(
                variant_id=variant_id, price_book__currency=currency
            )
            .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
            .first()
        )
