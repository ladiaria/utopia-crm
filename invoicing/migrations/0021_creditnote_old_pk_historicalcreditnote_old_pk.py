# Generated by Django 4.1.13 on 2025-02-26 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0020_alter_historicalinvoice_payment_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditnote',
            name='old_pk',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcreditnote',
            name='old_pk',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
