# Generated by Django 4.1.13 on 2025-03-03 16:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0022_transactiontype'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='transaction_type',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='invoicing.transactiontype'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='transaction_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='invoicing.transactiontype'),
        ),
    ]
