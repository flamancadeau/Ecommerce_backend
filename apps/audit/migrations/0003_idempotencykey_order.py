import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_idempotencykey"),
        ("orders", "0006_alter_reservation_reservation_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="idempotencykey",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="idempotency_keys",
                to="orders.order",
            ),
        ),
    ]
