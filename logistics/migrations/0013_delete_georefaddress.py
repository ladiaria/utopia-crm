# Generated by Django 4.1.4 on 2023-09-26 00:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_remove_address_geo_ref_address_and_more'),
        ('logistics', '0012_auto_20221017_1513'),
    ]

    operations = [
        migrations.DeleteModel(
            name='GeorefAddress',
        ),
    ]
