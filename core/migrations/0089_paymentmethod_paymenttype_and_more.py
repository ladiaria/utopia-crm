# Generated by Django 4.2.11 on 2024-12-12 18:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0088_alter_address_country_alter_address_state_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='PaymentType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.AlterField(
            model_name='activity',
            name='activity_type',
            field=models.CharField(blank=True, choices=[('S', 'Campaign start'), ('C', 'Call'), ('M', 'E-mail'), ('L', 'Link hit'), ('W', 'WhatsApp message or other apps'), ('E', 'Event participation'), ('I', 'In-place visit'), ('N', 'Internal')], max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name='historicalactivity',
            name='activity_type',
            field=models.CharField(blank=True, choices=[('S', 'Campaign start'), ('C', 'Call'), ('M', 'E-mail'), ('L', 'Link hit'), ('W', 'WhatsApp message or other apps'), ('E', 'Event participation'), ('I', 'In-place visit'), ('N', 'Internal')], max_length=1, null=True),
        ),
        migrations.AddField(
            model_name='historicalsubscription',
            name='payment_method_fk',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text="Payment method used to pay for the subscription, for example: 'Cash', 'Credit Card', 'Debit Card', 'Bank Transfer', etc.", null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.paymentmethod', verbose_name='Payment method'),
        ),
        migrations.AddField(
            model_name='historicalsubscription',
            name='payment_type_fk',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text="Payment type used to pay for the subscription, for example: 'American Express', 'Visa', 'Mastercard', etc.", null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.paymenttype', verbose_name='Payment type'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='payment_method_fk',
            field=models.ForeignKey(blank=True, help_text="Payment method used to pay for the subscription, for example: 'Cash', 'Credit Card', 'Debit Card', 'Bank Transfer', etc.", null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.paymentmethod', verbose_name='Payment method'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='payment_type_fk',
            field=models.ForeignKey(blank=True, help_text="Payment type used to pay for the subscription, for example: 'American Express', 'Visa', 'Mastercard', etc.", null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.paymenttype', verbose_name='Payment type'),
        ),
    ]
