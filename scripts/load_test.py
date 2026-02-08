import os
import sys
import logging
import threading
import uuid
import requests
import django
from decimal import Decimal

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings.development")
django.setup()

from apps.catalog.models import Product, Variant
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Cart, CartItem
from django.contrib.auth.models import User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
)
logger = logging.getLogger("load_test")


def checkout_worker(url, cart_id, user_idx):
    """Encapsulated worker with unique Trace IDs for observability."""
    trace_id = str(uuid.uuid4())[:8]
    payload = {
        "cart_id": str(cart_id),
        "email": f"user_{user_idx}@example.com",
        "shipping_address": {"line1": "Test St"},
    }

    try:

        response = requests.post(url, json=payload, timeout=10)

        logger.info(
            "RESULT | Trace: %s | User: %s | Status: %s | Body: %s",
            trace_id,
            user_idx,
            response.status_code,
            response.text[:50],
        )
    except requests.exceptions.RequestException as e:
        logger.error("FAILED | Trace: %s | User: %s | Error: %s", trace_id, user_idx, e)


def run_load_test():

    logger.info("Initializing Load Test: 'Oversell Scenario' (10 Stock vs 15 Requests)")

    product, _ = Product.objects.get_or_create(
        name="Load Test Prod", slug="load-test-prod"
    )
    variant, _ = Variant.objects.get_or_create(
        product=product, sku="LOAD-001", defaults={"base_price": Decimal("10.00")}
    )
    warehouse, _ = Warehouse.objects.get_or_create(code="WH-LOAD")

    stock, _ = Stock.objects.get_or_create(variant=variant, warehouse=warehouse)
    stock.on_hand = 10
    stock.reserved = 0
    stock.save()

    url = "http://localhost:8000/api/checkout/create-order/"
    threads = []

    for i in range(15):
        user, _ = User.objects.get_or_create(username=f"user_{i}")
        cart = Cart.objects.create(user_id=user.id)
        CartItem.objects.create(
            cart=cart, variant=variant, quantity=1, unit_price=Decimal("10.00")
        )

        t = threading.Thread(
            target=checkout_worker,
            args=(url, cart.id, i),
            name=f"Worker-{i}",
        )
        threads.append(t)

    logger.info("--- STARTING CONCURRENT BURST ---")
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    logger.info("--- BURST COMPLETE ---")

    stock.refresh_from_db()
    if stock.on_hand < 0:
        logger.critical(
            "RACE CONDITION DETECTED: Stock is negative (%s)!", stock.on_hand
        )
    else:
        logger.info("VALIDATION PASSED: Final Stock: %s", stock.on_hand)


if __name__ == "__main__":
    run_load_test()
