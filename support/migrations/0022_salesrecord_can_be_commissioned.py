# Generated by Django 4.1.4 on 2024-03-19 17:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0021_salesrecord_commission_for_payment_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesrecord",
            name="can_be_commissioned",
            field=models.BooleanField(default=True, verbose_name="Can be commissioned"),
        ),
    ]
