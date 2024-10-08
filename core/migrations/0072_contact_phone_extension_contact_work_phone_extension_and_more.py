# Generated by Django 4.1.4 on 2024-10-04 02:15

from django.db import migrations, models
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0071_historicalsubscription_billing_contact_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="phone_extension",
            field=models.CharField(
                blank=True, default="", max_length=16, verbose_name="Phone extension"
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="work_phone_extension",
            field=models.CharField(
                blank=True,
                default="",
                max_length=16,
                verbose_name="Work phone extension",
            ),
        ),
        migrations.AddField(
            model_name="historicalcontact",
            name="phone_extension",
            field=models.CharField(
                blank=True, default="", max_length=16, verbose_name="Phone extension"
            ),
        ),
        migrations.AddField(
            model_name="historicalcontact",
            name="work_phone_extension",
            field=models.CharField(
                blank=True,
                default="",
                max_length=16,
                verbose_name="Work phone extension",
            ),
        ),
        migrations.AddField(
            model_name="historicalsubscription",
            name="billing_phone_extension",
            field=models.CharField(
                blank=True,
                default="",
                max_length=16,
                verbose_name="Billing phone extension",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="billing_phone_extension",
            field=models.CharField(
                blank=True,
                default="",
                max_length=16,
                verbose_name="Billing phone extension",
            ),
        ),
        migrations.AlterField(
            model_name="contact",
            name="mobile",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Mobile",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="contact",
            name="phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Phone",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="contact",
            name="work_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Work phone",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalcontact",
            name="mobile",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Mobile",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalcontact",
            name="phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Phone",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalcontact",
            name="work_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Work phone",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalsubscription",
            name="billing_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Billing phone",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="billing_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                default="",
                max_length=128,
                region=None,
                verbose_name="Billing phone",
                db_index=True,
            ),
        ),
    ]
