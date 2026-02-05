from django.db.models import Q
from django.utils import timezone
from .models import PriceBook, PriceBookEntry, TaxRate


class PricingRepository:
    @staticmethod
    def get_price_entry(
        variant, currency, country, channel, customer_group, quantity=1
    ):
        """Finds the most specific price entry, falling back to 'Default' if needed."""
        now = timezone.now()

        # 1. Try to find an exact match for the customer context
        query_base = (
            PriceBookEntry.objects.filter(
                Q(variant=variant)
                | Q(product=variant.product)
                | Q(category=variant.product.category),
                price_book__currency=currency,
                price_book__is_active=True,
                min_quantity__lte=quantity,
            )
            .filter(Q(max_quantity__isnull=True) | Q(max_quantity__gte=quantity))
            .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
        )

        entry = (
            query_base.filter(
                price_book__country=country,
                price_book__channel=channel,
                price_book__customer_group=customer_group,
            )
            .order_by("variant", "product", "category", "-min_quantity")
            .first()
        )

        if entry:
            return entry

        # 2. Fallback to the 'Default' Price Book for this currency
        return (
            query_base.filter(price_book__is_default=True)
            .order_by("variant", "product", "category", "-min_quantity")
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
    def get_price_book_info(
        variant, currency, country, channel, customer_group, quantity=1
    ):
        """Finds metadata of the used price book, falling back to 'Default' if needed."""
        now = timezone.now()

        query_base = (
            PriceBookEntry.objects.filter(
                Q(variant=variant)
                | Q(product=variant.product)
                | Q(category=variant.product.category),
                price_book__currency=currency,
                price_book__is_active=True,
                min_quantity__lte=quantity,
            )
            .filter(Q(max_quantity__isnull=True) | Q(max_quantity__gte=quantity))
            .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
        )

        entry = (
            query_base.filter(
                price_book__country=country,
                price_book__channel=channel,
                price_book__customer_group=customer_group,
            )
            .order_by("variant", "product", "category", "-min_quantity")
            .first()
        )

        if entry:
            return entry

        # Fallback to the 'Default' Price Book for this currency
        return (
            query_base.filter(price_book__is_default=True)
            .order_by("variant", "product", "category", "-min_quantity")
            .first()
        )
