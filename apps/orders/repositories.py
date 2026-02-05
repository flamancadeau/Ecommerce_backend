from django.utils import timezone
from django.db.models import Q
from .models import Cart, Order, Reservation


class OrderRepository:
    @staticmethod
    def get_active_cart(cart_id=None, session_id=None, user_id=None):
        now = timezone.now()
        query = Cart.objects.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if cart_id:
            return query.filter(id=cart_id).first()
        if session_id:
            return query.filter(session_id=session_id).first()
        if user_id:
            return query.filter(user_id=user_id).first()
        return None

    @staticmethod
    def get_customer_orders(customer_id, status=None):
        query = Order.objects.filter(customer_id=customer_id)
        if status:
            query = query.filter(status=status)
        return query

    @staticmethod
    def get_pending_reservations(variant_id=None, warehouse_id=None):
        now = timezone.now()
        query = Reservation.objects.filter(status="pending", expires_at__gt=now)
        if variant_id:
            query = query.filter(variant_id=variant_id)
        if warehouse_id:
            query = query.filter(warehouse_id=warehouse_id)
        return query

    @staticmethod
    def get_expired_reservations():
        now = timezone.now()
        return Reservation.objects.filter(status="pending", expires_at__lte=now)
