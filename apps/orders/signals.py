from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Reservation


@receiver(pre_save, sender=Reservation)
def release_stock(sender, instance, **kwargs):
    if not instance.pk:
        return

    old_record = Reservation.objects.get(pk=instance.pk)

    if old_record.status == "pending" and instance.status == "expired":

        print(f"Stock released for {instance.variant}")
