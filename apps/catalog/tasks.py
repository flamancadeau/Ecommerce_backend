from celery import shared_task
from django.core.cache import cache
from django.db.models import Prefetch
import logging
from apps.catalog.models import Product, Variant, Category

logger = logging.getLogger(__name__)


@shared_task
def update_product_cache():
    """
    Update product catalog cache in Redis.
    Runs every 30 minutes via Celery Beat.
    """

    categories = Category.objects.filter(is_active=True).values("id", "name", "slug")
    cache.set("active_categories", list(categories), timeout=3600)

    popular_products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related(
            Prefetch("variants", queryset=Variant.objects.filter(is_active=True))
        )[:50]
    )

    product_data = []
    for product in popular_products:
        variants = list(
            product.variants.all().values("id", "sku", "base_price", "attributes")
        )
        product_data.append(
            {
                "id": str(product.id),
                "name": product.name,
                "slug": product.slug,
                "brand": product.brand,
                "category": product.category.name if product.category else None,
                "variant_count": len(variants),
                "min_price": (
                    min([v["base_price"] for v in variants]) if variants else 0
                ),
                "variants": variants[:5],
            }
        )

    cache.set("popular_products", product_data, timeout=1800)

    variants = Variant.objects.filter(is_active=True).values("attributes")
    colors = set()
    sizes = set()

    for variant in variants:
        attrs = variant["attributes"]
        if "color" in attrs:
            colors.add(attrs["color"])
        if "size" in attrs:
            sizes.add(attrs["size"])

    cache.set("available_colors", list(colors), timeout=3600)
    cache.set("available_sizes", list(sizes), timeout=3600)

    logger.info(
        f"Cached {len(product_data)} products, {len(colors)} colors, {len(sizes)} sizes"
    )

    return {
        "products_cached": len(product_data),
        "colors": len(colors),
        "sizes": len(sizes),
    }
