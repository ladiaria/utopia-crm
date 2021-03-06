# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-12-14 15:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('community', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='supporter',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='supporter',
            name='support',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='community.Support'),
        ),
        migrations.AddField(
            model_name='productparticipation',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='productparticipation',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Product'),
        ),
    ]
