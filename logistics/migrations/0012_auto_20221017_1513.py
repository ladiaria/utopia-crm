# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-10-17 15:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0011_route_the_geom'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='place',
            field=models.CharField(choices=[('P', 'Prints'), ('L', 'Labels')], max_length=20, unique=True, verbose_name='Place'),
        ),
        migrations.AlterField(
            model_name='resort',
            name='status',
            field=models.CharField(choices=[('AC', 'To be confirmed'), ('NL', "We don't deliver there"), ('P', 'Door to door'), ('R', 'Withdrawal')], max_length=2, verbose_name='Status'),
        ),
    ]
