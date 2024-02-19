# Generated by Django 4.1.4 on 2024-01-15 17:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("advertisement", "0002_advertisementseller_user_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="advertisementactivity",
            options={
                "get_latest_by": "id",
                "verbose_name": "Advertisement activity",
                "verbose_name_plural": "Advertisement activities",
            },
        ),
        migrations.AddField(
            model_name="advertisementactivity",
            name="date",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Date"),
        ),
    ]