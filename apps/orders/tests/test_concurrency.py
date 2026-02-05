import pytest
from django.db import transaction
from decimal import Decimal
from apps.catalog.models import Product, Variant
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Cart, CartItem
from apps.orders.services import OrderService
import threading
from django.db import connections


@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations():
    """
    Test that concurrent reservations do not oversell.
    """
    # 1. Setup
    warehouse = Warehouse.objects.create(
        code="WH-TEST", name="Test Warehouse", is_active=True
    )
    product = Product.objects.create(name="Limited Item", slug="limited")
    variant = Variant.objects.create(
        product=product, sku="LIM-001", base_price=Decimal("10.00")
    )

    # Only 5 items in stock
    stock = Stock.objects.create(variant=variant, warehouse=warehouse, on_hand=5)

    # 2. Prepare multiple carts
    carts = []
    for i in range(10):  # 10 people trying to buy
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        carts.append(cart)

    results = []

    def attempt_reserve(cart_id):
        connections.close_all()  # Ensure new connection for thread
        try:
            OrderService.create_reservation(cart_id)
            results.append(True)
        except Exception as e:
            results.append(False)

    # 3. Spawn threads
    threads = []
    for cart in carts:
        t = threading.Thread(target=attempt_reserve, args=(cart.id,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 4. Verify
    success_count = sum(1 for r in results if r is True)
    assert success_count == 5  # Only 5 should succeed

    stock.refresh_from_db()
    assert stock.reserved == 5
    assert stock.available == 0
