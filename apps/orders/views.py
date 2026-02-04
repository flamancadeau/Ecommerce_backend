from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.db import transaction, models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import uuid

from .models import Cart, CartItem, Order, OrderItem, Reservation
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer
from apps.audit.idempotency import idempotent_request
from apps.catalog.models import Variant
from apps.inventory.models import Stock, Warehouse


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    lookup_field = "id"
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user
        session_key = self.request.session.session_key

        if user.is_authenticated:
            return Cart.objects.filter(user_id=user.id).prefetch_related(
                "items", "items__variant"
            )
        elif session_key:
            return Cart.objects.filter(session_id=session_key).prefetch_related(
                "items", "items__variant"
            )
        return Cart.objects.none()

    def get_object(self):
        cart_id = self.kwargs.get("id")
        if cart_id:
            try:
                return Cart.objects.get(id=cart_id)
            except Cart.DoesNotExist:
                raise NotFound("Cart not found")

        user = self.request.user
        session_key = self.request.session.session_key

        if not session_key:
            self.request.session.create()
            session_key = self.request.session.session_key

        if user.is_authenticated:

            cart = Cart.objects.filter(user_id=user.id).first()
            if cart:
                return cart

            session_cart = Cart.objects.filter(session_id=session_key).first()
            if session_cart:
                session_cart.user_id = user.id
                session_cart.save()
                return session_cart

            cart = Cart.objects.create(
                user_id=user.id,
                session_id=session_key,
                expires_at=timezone.now() + timedelta(days=7),
            )
        else:
            cart, _ = Cart.objects.get_or_create(
                session_id=session_key,
                defaults={"expires_at": timezone.now() + timedelta(days=7)},
            )

        return cart

    @action(detail=True, methods=["post"], url_path="add-item")
    @transaction.atomic
    def add_item(self, request, id=None):
        """Add item to cart with basic inventory check"""
        cart = self.get_object()

        variant_id = request.data.get("variant_id")
        quantity = int(request.data.get("quantity", 1))

        if not variant_id:
            raise ValidationError("variant_id is required")

        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        try:
            variant = Variant.objects.select_related("product").get(
                id=variant_id, is_active=True
            )
        except Variant.DoesNotExist:
            raise ValidationError("Product variant not found")

        if variant.product.launch_date and variant.product.launch_date > timezone.now():
            raise ValidationError(
                f"This product will be available on {variant.product.launch_date}"
            )

        available_stock = self._check_availability(variant, quantity)
        if available_stock < quantity:
            raise ValidationError(f"Only {available_stock} available")

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
            defaults={"quantity": quantity, "unit_price": variant.base_price},
        )

        if not created:
            new_quantity = cart_item.quantity + quantity

            available_stock = self._check_availability(variant, new_quantity)
            if available_stock < new_quantity:
                raise ValidationError(
                    f"Cannot add {quantity} more. Only {available_stock} available in total"
                )

            cart_item.quantity = new_quantity
            cart_item.save()

        cart.expires_at = timezone.now() + timedelta(days=7)
        cart.save()

        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="update-item")
    def update_item(self, request, id=None):
        """Update item quantity in cart"""
        cart = self.get_object()
        variant_id = request.data.get("variant_id")
        quantity = int(request.data.get("quantity", 1))

        if not variant_id:
            raise ValidationError("variant_id is required")

        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        try:
            cart_item = CartItem.objects.get(cart=cart, variant_id=variant_id)
        except CartItem.DoesNotExist:
            raise NotFound("Item not found in cart")

        variant = cart_item.variant
        available_stock = self._check_availability(variant, quantity)
        if available_stock < quantity:
            raise ValidationError(f"Only {available_stock} available")

        cart_item.quantity = quantity
        cart_item.save()

        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="remove-item")
    def remove_item(self, request, id=None):
        """Remove item from cart"""
        cart = self.get_object()
        variant_id = request.data.get("variant_id")

        if not variant_id:
            raise ValidationError("variant_id is required")

        deleted, _ = CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()

        if deleted:
            return Response({"detail": "Item removed"})
        raise NotFound("Item not found in cart")

    def _check_availability(self, variant, requested_quantity):
        """Check stock availability"""
        try:
            total_stock = (
                Stock.objects.filter(
                    variant=variant, warehouse__is_active=True
                ).aggregate(total=models.Sum("available"))["total"]
                or 0
            )

            reserved = (
                Reservation.objects.filter(
                    variant=variant, status="pending", expires_at__gt=timezone.now()
                ).aggregate(total=models.Sum("quantity"))["total"]
                or 0
            )

            return max(0, total_stock - reserved)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Stock check error: {e}")
            return 0


class CheckoutViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"], url_path="create-order")
    @idempotent_request()
    @transaction.atomic
    def create_order(self, request):
        """Create order from cart"""
        cart_id = request.data.get("cart_id")
        email = request.data.get("email")
        shipping_address = request.data.get("shipping_address")

        if not all([cart_id, email, shipping_address]):
            raise ValidationError(
                "Missing required fields: cart_id, email, shipping_address"
            )

        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            raise NotFound("Cart not found")

        if cart.is_expired:
            raise ValidationError("Cart has expired")

        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        # Get active warehouse first
        warehouse = Warehouse.objects.filter(is_active=True).first()
        if not warehouse:
            raise ValidationError("No active warehouse available")

        subtotal = Decimal("0")
        order_items_data = []

        # Lock and update stock for each item
        for cart_item in cart.items.all().select_related("variant", "variant__product"):
            variant = cart_item.variant
            quantity = cart_item.quantity

            if (
                variant.product.launch_date
                and variant.product.launch_date > timezone.now()
            ):
                raise ValidationError(
                    f"Product {variant.sku} is not available until {variant.product.launch_date}"
                )

            try:

                stock = Stock.objects.select_for_update().get(
                    variant=variant, warehouse=warehouse
                )
            except Stock.DoesNotExist:
                raise ValidationError(f"Stock not found for {variant.sku}")

            if stock.available < quantity:

                if not (
                    stock.backorderable
                    and (
                        stock.backorder_limit == 0 or quantity <= stock.backorder_limit
                    )
                ):
                    raise ValidationError(
                        f"Insufficient stock for {variant.sku}. Available: {stock.available}"
                    )

            old_qty = stock.on_hand
            stock.on_hand -= quantity
            stock.save()

            from apps.audit.models import InventoryAudit

            InventoryAudit.objects.create(
                event_type="fulfillment",
                variant=variant,
                warehouse=warehouse,
                quantity=quantity,
                from_quantity=old_qty,
                to_quantity=stock.on_hand,
                notes="Order fulfillment",
            )

            item_total = cart_item.unit_price * Decimal(quantity)
            subtotal += item_total

            order_items_data.append(
                {
                    "variant": variant,
                    "quantity": quantity,
                    "unit_price": cart_item.unit_price,
                    "sku": variant.sku,
                    "variant_name": (
                        variant.product.name if variant.product else variant.sku
                    ),
                    "warehouse": warehouse,
                }
            )

        tax_rate = Decimal("0.21")
        tax_amount = subtotal * tax_rate
        shipping_amount = Decimal("5.99")
        total = subtotal + tax_amount + shipping_amount

        order = Order.objects.create(
            customer_id=cart.user_id,
            customer_email=email,
            shipping_address=shipping_address,
            billing_address=shipping_address,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            total=total,
            status="confirmed",
        )

        for item_data in order_items_data:
            OrderItem.objects.create(
                order=order,
                warehouse=item_data["warehouse"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                sku=item_data["sku"],
                variant_name=item_data["variant_name"],
            )

        cart.items.all().delete()
        cart.expires_at = timezone.now()
        cart.save()

        serializer = OrderSerializer(order)
        return Response(
            {
                "order": serializer.data,
                "order_number": order.order_number,
                "total": str(total),
            },
            status=status.HTTP_201_CREATED,
        )

    def _check_variant_availability(self, variant, quantity):
        """Check stock availability for variant"""
        try:
            total_stock = (
                Stock.objects.filter(
                    variant=variant, warehouse__is_active=True
                ).aggregate(total=models.Sum("available"))["total"]
                or 0
            )

            reserved = (
                Reservation.objects.filter(
                    variant=variant, status="pending", expires_at__gt=timezone.now()
                ).aggregate(total=models.Sum("quantity"))["total"]
                or 0
            )

            return max(0, total_stock - reserved)
        except Exception:
            return 0


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated:
            return Order.objects.filter(customer_id=user.id).prefetch_related("items")

        email = self.request.query_params.get("email")
        order_number = self.request.query_params.get("order_number")

        if email and order_number:
            return Order.objects.filter(
                customer_email=email, order_number=order_number
            ).prefetch_related("items")

        return Order.objects.none()

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Cancel order"""
        order = self.get_object()

        if order.status in ["draft", "pending", "confirmed"]:
            order.status = "cancelled"
            order.save()
            return Response({"detail": "Order cancelled"})

        raise ValidationError("Cannot cancel order in current status")
