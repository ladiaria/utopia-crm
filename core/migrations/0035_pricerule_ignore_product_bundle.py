# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-02-18 14:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_productbundle'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricerule',
            name='ignore_product_bundle',
            field=models.ManyToManyField(to='core.ProductBundle'),
        ),
    ]