# Generated by Django 4.1.13 on 2024-12-05 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0013_alter_invoice_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoiceitem',
            name='amount',
            field=models.DecimalField(decimal_places=2, help_text='Total amount', max_digits=10),
        ),
        migrations.AlterField(
            model_name='invoiceitem',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Price per copy', max_digits=10, null=True),
        ),
    ]