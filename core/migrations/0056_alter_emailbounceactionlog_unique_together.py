# Generated by Django 4.1.4 on 2023-09-30 22:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_remove_address_geo_ref_address_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='emailbounceactionlog',
            unique_together={('created', 'contact', 'email', 'action')},
        ),
    ]
