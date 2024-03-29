# Generated by Django 4.1.4 on 2023-06-20 13:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_address_verified_historicaladdress_verified_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='needs_georef',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name='historicaladdress',
            name='needs_georef',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='verified',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='historicaladdress',
            name='verified',
            field=models.BooleanField(default=False, null=True),
        ),
    ]
