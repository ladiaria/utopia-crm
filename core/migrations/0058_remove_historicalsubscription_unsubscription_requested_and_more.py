# Generated by Django 4.1.4 on 2023-11-14 17:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_alter_emailreplacement_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalsubscription',
            name='unsubscription_requested',
        ),
        migrations.RemoveField(
            model_name='subscription',
            name='unsubscription_requested',
        ),
    ]
