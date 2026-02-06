from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0004_campaign_customer_groups_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaigndiscount",
            name="min_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Minimum price floor after discount",
                max_digits=10,
                null=True,
            ),
        ),
    ]
