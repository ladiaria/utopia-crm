# Generated by Django 4.1.13 on 2025-04-08 14:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0094_alter_city_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='city',
            name='code',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
