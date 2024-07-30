# Generated by Django 4.1.4 on 2024-01-15 15:11

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (
            "core",
            "0058_remove_historicalsubscription_unsubscription_requested_and_more",
        ),
        ("advertisement", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="advertisementseller",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="advertiser",
            name="other_contacts",
            field=models.ManyToManyField(
                blank=True,
                related_name="other_advertisements",
                to="core.contact",
                verbose_name="Other contacts",
            ),
        ),
        migrations.AlterField(
            model_name="advertiser",
            name="priority",
            field=models.CharField(
                choices=[("1", "High"), ("2", "Mid"), ("3", "Low")],
                default="2",
                max_length=2,
                verbose_name="Priority",
            ),
        ),
    ]
