# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-04 12:29
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_pricerule_ignore_product_bundle'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvancedDiscount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('products_mode', models.PositiveSmallIntegerField(choices=[(1, 'Find at least one product'), (2, 'Find all products')])),
                ('value_mode', models.PositiveSmallIntegerField(choices=[(1, 'Integer'), (2, 'Percentage')])),
                ('value', models.PositiveSmallIntegerField(default=0)),
            ],
        ),
        migrations.AlterField(
            model_name='pricerule',
            name='ignore_product_bundle',
            field=models.ManyToManyField(blank=True, to='core.ProductBundle'),
        ),
        migrations.AlterField(
            model_name='product',
            name='type',
            field=models.CharField(choices=[(b'S', 'Subscription'), (b'N', 'Newsletter'), (b'D', 'Discount'), (b'P', 'Percentage discount'), (b'A', 'Advanced discount'), (b'O', 'Other')], db_index=True, default='O', max_length=1),
        ),
        migrations.AddField(
            model_name='advanceddiscount',
            name='discount_product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='discount', to='core.Product'),
        ),
        migrations.AddField(
            model_name='advanceddiscount',
            name='find_products',
            field=models.ManyToManyField(related_name='find_products_discount', to='core.Product'),
        ),
    ]
