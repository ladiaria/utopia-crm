# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-05-18 15:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0014_auto_20220218_1325'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='envelope',
            field=models.BooleanField(default=False, verbose_name='Envelope', null=True),
        ),
    ]
