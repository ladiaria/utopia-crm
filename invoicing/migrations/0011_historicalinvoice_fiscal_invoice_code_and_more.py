# Generated by Django 4.1.4 on 2024-08-27 18:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0010_alter_invoiceitem_type_dr'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='fiscal_invoice_code',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='internal_provider_text',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='fiscal_invoice_code',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='internal_provider_text',
            field=models.TextField(blank=True, null=True),
        ),
    ]