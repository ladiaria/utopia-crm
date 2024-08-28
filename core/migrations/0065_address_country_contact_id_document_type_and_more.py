# Generated by Django 4.1.4 on 2024-08-19 15:31

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_historicalsubscription_renewal_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='country',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        # migrations.AddField(
        #     model_name='contact',
        #     name='id_document_type',
        #     field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Identification Document Type'),
        # ),
        migrations.AddField(
            model_name='contact',
            name='last_name',
            field=models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.RegexValidator("^[@A-Za-z0-9ñüáéíóúÑÜÁÉÍÓÚ _'.\\-]*$", 'This name only supports alphanumeric characters, at, apostrophes, spaces, hyphens, underscores, and periods.')], verbose_name='Last name'),
        ),
        migrations.AddField(
            model_name='contact',
            name='ranking',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ranking'),
        ),
        migrations.AddField(
            model_name='historicaladdress',
            name='country',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        # migrations.AddField(
        #     model_name='historicalcontact',
        #     name='id_document_type',
        #     field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Identification Document Type'),
        # ),
        migrations.AddField(
            model_name='historicalcontact',
            name='last_name',
            field=models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.RegexValidator("^[@A-Za-z0-9ñüáéíóúÑÜÁÉÍÓÚ _'.\\-]*$", 'This name only supports alphanumeric characters, at, apostrophes, spaces, hyphens, underscores, and periods.')], verbose_name='Last name'),
        ),
        migrations.AddField(
            model_name='historicalcontact',
            name='ranking',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ranking'),
        ),
    ]
