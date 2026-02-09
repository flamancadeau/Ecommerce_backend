from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.db import transaction, models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Cart, CartItem, Order, OrderItem, Reservation
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    OrderSerializer,
    CartItemAddSerializer,
    CartItemUpdateSerializer,
    CartItemRemoveSerializer,
)
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
        if cart_id and cart_id != "current":
            try:
                return Cart.objects.get(id=cart_id)
            except (Cart.DoesNotExist, ValidationError):
                raise NotFound("Cart not found")

        user = self.request.user
        request_data = self.request.data if isinstance(self.request.data, dict) else {}

        session_key = request_data.get("session_id") or self.request.session.session_key

        if not session_key:
            if not self.request.session.session_key:
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

    @swagger_auto_schema(
        request_body=CartItemAddSerializer,
        responses={200: CartItemSerializer(), 400: "Validation Error"},
    )
    @action(detail=False, methods=["post"], url_path="add-item")
    @transaction.atomic
    def add_item_collection(self, request):
        """Add item to current session/user cart"""
        return self.add_item(request)

    @swagger_auto_schema(
        request_body=CartItemAddSerializer,
        responses={200: CartItemSerializer(), 400: "Validation Error"},
    )
    @action(detail=True, methods=["post"], url_path="add-item")
    @transaction.atomic
    def add_item(self, request, id=None):
        """Add item to cart with basic inventory check"""
        cart = self.get_object()

        serializer = CartItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant_id = serializer.validated_data["variant_id"]
        quantity = serializer.validated_data["quantity"]

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

        return Response(CartItemSerializer(cart_item).data)

    @swagger_auto_schema(
        request_body=CartItemUpdateSerializer,
        responses={
            200: CartItemSerializer(),
            404: "Not Found",
            400: "Validation Error",
        },
    )
    @action(detail=False, methods=["post"], url_path="update-item")
    def update_item_collection(self, request):
        """Update item quantity in current cart"""
        return self.update_item(request)

    @swagger_auto_schema(
        request_body=CartItemUpdateSerializer,
        responses={
            200: CartItemSerializer(),
            404: "Not Found",
            400: "Validation Error",
        },
    )
    @action(detail=True, methods=["post"], url_path="update-item")
    def update_item(self, request, id=None):
        """Update item quantity in cart"""
        cart = self.get_object()

        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant_id = serializer.validated_data["variant_id"]
        quantity = serializer.validated_data["quantity"]

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

        return Response(CartItemSerializer(cart_item).data)

    @swagger_auto_schema(
        request_body=CartItemRemoveSerializer,
        responses={200: "Item removed", 404: "Not Found"},
    )
    @action(detail=False, methods=["post"], url_path="remove-item")
    def remove_item_collection(self, request):
        """Remove item from current cart"""
        return self.remove_item(request)

    @swagger_auto_schema(
        request_body=CartItemRemoveSerializer,
        responses={200: "Item removed", 404: "Not Found"},
    )
    @action(detail=True, methods=["post"], url_path="remove-item")
    def remove_item(self, request, id=None):
        """Remove item from cart"""
        cart = self.get_object()

        serializer = CartItemRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant_id = serializer.validated_data["variant_id"]

        deleted, _ = CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()

        if deleted:
            return Response({"detail": "Item removed"})
        raise NotFound("Item not found in cart")

    def _check_availability(self, variant, requested_quantity):
        """Check stock availability using central service"""
        availability = Stock.objects.check_availability(variant.id, requested_quantity)
        return availability["available_quantity"]


class CheckoutViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Reserve inventory for items in a cart before placing an order.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["cart_id"],
            properties={
                "cart_id": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
                ),
            },
        ),
        responses={201: "Inventory Reserved", 400: "Validation Error"},
    )
    @action(detail=False, methods=["post"], url_path="reserve")
    @transaction.atomic
    def reserve(self, request):
        """
        Reserve inventory for a cart.
        Returns a reservation token.
        """
        cart_id = request.data.get("cart_id")
        if not cart_id:
            raise ValidationError("cart_id is required")

        try:
            result = Reservation.objects.create_from_cart(cart_id)
            return Response(
                {
                    "status": True,
                    "message": "Inventory reserved",
                    "data": result,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Reservation error: {e}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_description="Finalize checkout and place an order. Use either reservation_token or cart_id.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "shipping_address"],
            properties={
                "reservation_token": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Token from /reserve/"
                ),
                "cart_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="Direct order from cart",
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                ),
                "shipping_address": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "street": openapi.Schema(type=openapi.TYPE_STRING),
                        "city": openapi.Schema(type=openapi.TYPE_STRING),
                        "country": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            },
        ),
        responses={201: OrderSerializer()},
    )
    @action(detail=False, methods=["post"], url_path="place-order")
    @idempotent_request()
    def place_order(self, request):
        """
        Place an order.
        Can be called with 'reservation_token' (preferred) or 'cart_id' (direct).
        """
        reservation_token = request.data.get("reservation_token")
        cart_id = request.data.get("cart_id")
        email = request.data.get("email")
        shipping_address = request.data.get("shipping_address")

        if not email or not shipping_address:
            raise ValidationError("email and shipping_address are required")

        try:
            if reservation_token:
                order = Order.objects.create_from_reservation(
                    reservation_token,
                    email,
                    shipping_address,
                    customer_id=(
                        request.user.id if request.user.is_authenticated else None
                    ),
                )
            elif cart_id:
                order = Order.objects.create_direct_order(
                    cart_id,
                    email,
                    shipping_address,
                    customer_id=(
                        request.user.id if request.user.is_authenticated else None
                    ),
                )
            else:
                raise ValidationError("Either reservation_token or cart_id is required")

            serializer = OrderSerializer(order)
            return Response(
                {
                    "status": True,
                    "message": "Order placed successfully",
                    "data": {
                        "order": serializer.data,
                        "order_number": order.order_number,
                        "total": str(order.total),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Order placement error: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description="Finalize checkout and place an order. Use either reservation_token or cart_id.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "shipping_address"],
            properties={
                "reservation_token": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Token from /reserve/"
                ),
                "cart_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_UUID,
                    description="Direct order from cart",
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                ),
                "shipping_address": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "street": openapi.Schema(type=openapi.TYPE_STRING),
                        "city": openapi.Schema(type=openapi.TYPE_STRING),
                        "country": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            },
        ),
        responses={201: OrderSerializer()},
    )
    @action(detail=False, methods=["post"], url_path="create-order")
    def create_order(self, request):
        return self.place_order(request)

    def _check_variant_availability(self, variant, quantity):
        """Check stock availability for variant using central service"""
        availability = Stock.objects.check_availability(variant.id, quantity)
        return availability["available_quantity"]


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
