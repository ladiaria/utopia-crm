# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-08-20 15:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_auto_20210818_1639'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='unsubscription_channel',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, b'E-Mail'), (2, b'Phone')], null=True, verbose_name='Unsubscription channel'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='unsubscription_type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Asked for unsubscription'), (2, 'Did not ask for unsubscription')], null=True, verbose_name='Unsubscription type'),
        ),
    ]
