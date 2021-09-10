# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-09-10 14:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_auto_20210820_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='unsubscription_requested',
            field=models.BooleanField(default=False, verbose_name='Requested unsubscription'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='inactivity_reason',
            field=models.IntegerField(blank=True, choices=[(1, 'Normal end'), (2, 'Paused'), (3, 'Upgraded'), (13, 'Debtor'), (16, 'Debtor, automatic unsubscription'), (99, 'N/A')], null=True, verbose_name='Inactivity reason'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='unsubscription_channel',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, b'E-Mail'), (2, b'Phone')], null=True, verbose_name='Unsubscription channel'),
        ),
    ]