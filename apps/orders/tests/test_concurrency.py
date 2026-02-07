import pytest
from django.db import transaction
from decimal import Decimal
from apps.catalog.models import Product, Variant
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Cart, CartItem, Reservation
import threading
from django.db import connections


@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations():
    """
    Test that concurrent reservations do not oversell.
    """

    warehouse = Warehouse.objects.create(
        code="WH-TEST", name="Test Warehouse", is_active=True
    )
    product = Product.objects.create(name="Limited Item", slug="limited")
    variant = Variant.objects.create(
        product=product, sku="LIM-001", base_price=Decimal("10.00")
    )

    stock = Stock.objects.create(variant=variant, warehouse=warehouse, on_hand=5)

    carts = []
    for i in range(10):
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        carts.append(cart)

    results = []

    def attempt_reserve(cart_id):
        import time
        from django.db import connections

        for attempt in range(10):
            connections.close_all()
            try:
                Reservation.objects.create_from_cart(cart_id)
                results.append(True)
                return
            except Exception as e:

                if "locked" in str(e).lower():
                    time.sleep(0.05)
                    continue
                results.append(False)
                return
        results.append(False)

    threads = []
    for cart in carts:
        t = threading.Thread(target=attempt_reserve, args=(cart.id,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    success_count = sum(1 for r in results if r is True)
    assert success_count == 5

    stock.refresh_from_db()
    assert stock.reserved == 5
    assert stock.available == 0
