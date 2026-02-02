from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.orders.models import Reservation, Cart


class Command(BaseCommand):
    help = "Automatically expires old reservations and cleans up carts"

    def handle(self, *args, **options):
        now = timezone.now()

        expired_res = Reservation.objects.filter(status="pending", expires_at__lt=now)
        for res in expired_res:
            res.status = "expired"
            res.save()

        expired_carts = Cart.objects.filter(expires_at__lt=now).delete()

        self.stdout.write(self.style.SUCCESS(f"Processed expiry logic at {now}"))
