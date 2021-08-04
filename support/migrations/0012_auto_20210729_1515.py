# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-07-29 15:15
from __future__ import unicode_literals

import autoslug.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0011_auto_20210616_1123'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssueSubcategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60)),
                ('slug', autoslug.fields.AutoSlugField(always_update=True, blank=True, editable=False, null=True, populate_from='name')),
                ('category', models.CharField(blank=True, choices=[(b'L', 'Logistics'), (b'I', 'Invoicing'), (b'C', 'Contents'), (b'W', 'Web'), (b'S', 'Service'), (b'O', 'Community')], max_length=2, null=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AlterModelOptions(
            name='issuestatus',
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='issue',
            name='sub_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='support.IssueSubcategory'),
        ),
    ]
