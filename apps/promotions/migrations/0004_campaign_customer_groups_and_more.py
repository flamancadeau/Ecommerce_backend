from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0003_alter_campaign_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="customer_groups",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="campaign",
            name="excluded_customer_groups",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
