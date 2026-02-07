import os
import django
import sys
import threading
import requests
import json
from decimal import Decimal

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings.development")
django.setup()

from apps.catalog.models import Product, Variant
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Cart
from django.contrib.auth.models import User


def load_test():
    print("Setting up load test data...")

    product, _ = Product.objects.get_or_create(
        name="Load Test Prod", slug="load-test-prod"
    )
    variant, _ = Variant.objects.get_or_create(
        product=product, sku="LOAD-001", defaults={"base_price": Decimal("10.00")}
    )
    warehouse, _ = Warehouse.objects.get_or_create(
        code="WH-LOAD", defaults={"name": "Load WH", "country": "US"}
    )

    stock, _ = Stock.objects.get_or_create(variant=variant, warehouse=warehouse)
    stock.on_hand = 10
    stock.reserved = 0
    stock.save()

    print(f"Stock before: {stock.available}")

    url = "http://localhost:8000/api/checkout/create-order/"

    cart_ids = []
    print("Creating 15 carts (demand > supply)...")
    for i in range(15):
        user, _ = User.objects.get_or_create(
            username=f"user_{i}", defaults={"email": f"user_{i}@example.com"}
        )
        cart = Cart.objects.create(user_id=user.id)

        from apps.orders.models import CartItem

        CartItem.objects.create(
            cart=cart, variant=variant, quantity=1, unit_price=Decimal("10.00")
        )
        cart_ids.append(cart.id)

    print("Starting concurrent checkout requests...")

    def checkout(cart_id, idx):
        try:
            payload = {
                "cart_id": str(cart_id),
                "email": f"user_{idx}@example.com",
                "shipping_address": {"line1": "Test St"},
            }

            res = requests.post(url, json=payload)
            print(f"User {idx} result: {res.status_code}")
        except Exception as e:
            print(f"User {idx} failed: {e}")

    threads = []
    for i, cid in enumerate(cart_ids):
        t = threading.Thread(target=checkout, args=(cid, i))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    stock.refresh_from_db()
    print(f"Stock after: {stock.available} (Should be 0)")
    print(f"On hand: {stock.on_hand}")
    if stock.on_hand < 0:
        print("FAIL: Stock went negative!")
    else:
        print("SUCCESS: Stock non-negative.")


if __name__ == "__main__":
    load_test()
