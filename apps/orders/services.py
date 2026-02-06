from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging

from apps.orders.models import Order, OrderItem, Reservation, Cart
from apps.inventory.models import Stock, Warehouse
from apps.inventory.services import InventoryService
from apps.audit.models import InventoryAudit
from apps.catalog.models import Variant

logger = logging.getLogger(__name__)


class OrderService:
    @staticmethod
    def create_reservation(cart_id):
        """
        Create inventory reservations for items in the cart.
        """
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            raise ValidationError("Cart not found")

        if cart.is_expired:
            raise ValidationError("Cart has expired")

        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        reservations = []
        reservation_token = None
        expires_at = timezone.now() + timezone.timedelta(minutes=15)

        with transaction.atomic():

            from apps.orders.models import generate_reservation_token

            shared_token = generate_reservation_token()

            for item in cart.items.select_related("variant").all():
                variant = item.variant
                quantity = item.quantity

                stock = InventoryService.get_stock_for_fulfillment(variant, quantity)
                if not stock:
                    raise ValidationError(
                        f"Insufficient stock for {variant.sku} (Global check)"
                    )

                locked_stock = Stock.objects.select_for_update().get(id=stock.id)

                if not locked_stock.can_fulfill(quantity):
                    raise ValidationError(
                        f"Insufficient stock for {variant.sku} at warehouse {locked_stock.warehouse.code}"
                    )

                locked_stock.reserved += quantity
                locked_stock.save()

                res = Reservation.objects.create(
                    reservation_token=shared_token,
                    variant=variant,
                    warehouse=locked_stock.warehouse,
                    quantity=quantity,
                    status=Reservation.Status.PENDING,
                    expires_at=expires_at,
                )
                reservations.append(res)

                InventoryAudit.objects.create(
                    event_type=InventoryAudit.EventType.RESERVATION,
                    variant=variant,
                    warehouse=locked_stock.warehouse,
                    quantity=quantity,
                    reference=shared_token,
                    notes="Cart reservation",
                )

        return {
            "reservation_token": shared_token,
            "expires_at": expires_at,
            "items": len(reservations),
        }

    @staticmethod
    def create_order_from_reservation(
        reservation_token, email, shipping_address, customer_id=None
    ):
        """
        Confirm an order using an existing reservation.
        """
        with transaction.atomic():
            reservations = Reservation.objects.select_related(
                "variant", "warehouse", "variant__product"
            ).filter(reservation_token=reservation_token, status="pending")

            if not reservations.exists():
                raise ValidationError("Invalid or expired reservation")

            first_res = reservations.first()
            if first_res.is_expired:

                raise ValidationError("Reservation expired")

            subtotal = Decimal("0")
            order_items_data = []

            from apps.pricing.services import PricingService

            current_time = timezone.now()

            context = {"channel": "web", "email": email}

            for res in reservations:

                stock = Stock.objects.select_for_update().get(
                    variant=res.variant, warehouse=res.warehouse
                )

                stock.reserved -= res.quantity
                stock.on_hand -= res.quantity
                stock.save()

                res.status = Reservation.Status.CONFIRMED
                res.save()

                price_data = PricingService.calculate_item_price(
                    res.variant.id, res.quantity, current_time, context
                )
                unit_price = Decimal(str(price_data["final_unit_price"]))
                line_total = Decimal(str(price_data["extended_price"]))

                subtotal += line_total

                order_items_data.append(
                    {
                        "variant": res.variant,
                        "warehouse": res.warehouse,
                        "quantity": res.quantity,
                        "unit_price": unit_price,
                        "sku": res.variant.sku,
                        "variant_name": res.variant.product.name,
                    }
                )

                InventoryAudit.objects.create(
                    event_type=InventoryAudit.EventType.FULFILLMENT,
                    variant=res.variant,
                    warehouse=stock.warehouse,
                    quantity=res.quantity,
                    from_quantity=stock.on_hand + res.quantity,
                    to_quantity=stock.on_hand,
                    reference=reservation_token,
                    notes="Order confirmed from reservation",
                )

            tax_rate = Decimal("0.21")
            tax_amount = subtotal * tax_rate
            shipping_amount = Decimal("5.99")
            total = subtotal + tax_amount + shipping_amount

            order = Order.objects.create(
                customer_id=customer_id,
                customer_email=email,
                shipping_address=shipping_address,
                billing_address=shipping_address,
                subtotal=subtotal,
                tax_amount=tax_amount,
                shipping_amount=shipping_amount,
                total=total,
                status=Order.Status.CONFIRMED,
            )

            for item_data in order_items_data:
                OrderItem.objects.create(
                    order=order,
                    variant=item_data["variant"],
                    warehouse=item_data["warehouse"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    sku=item_data["sku"],
                    variant_name=item_data["variant_name"],
                )

            reservations.update(order=order)

            return order

    @staticmethod
    def create_direct_order(cart_id, email, shipping_address, customer_id=None):
        """
        Create order directly from cart (implicit reservation).
        """

        res_data = OrderService.create_reservation(cart_id)
        token = res_data["reservation_token"]
        return OrderService.create_order_from_reservation(
            token, email, shipping_address, customer_id
        )
