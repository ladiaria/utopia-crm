# Generated by Django 4.1.4 on 2024-02-19 15:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    replaces = [
        ("advertisement", "0001_initial"),
        ("advertisement", "0002_advertisementseller_user_and_more"),
        ("advertisement", "0003_alter_advertisementactivity_options_and_more"),
        ("advertisement", "0004_adpurchaseorder_agency_and_more"),
        ("advertisement", "0005_remove_adpurchaseorder_main_seller_and_more"),
        ("advertisement", "0006_remove_adpurchaseorder_ads_ad_order"),
        ("advertisement", "0007_remove_adpurchaseorder_billing_address_and_more"),
        ("advertisement", "0008_alter_advertiser_billing_address_and_more"),
        (
            "advertisement",
            "0009_remove_agency_agency_contact_agency_main_contact_and_more",
        ),
        ("advertisement", "0010_agent_notes_alter_agent_contact"),
        ("advertisement", "0011_adpurchaseorder_date_billed"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0060_alter_campaign_options_alter_subscription_options_and_more"),
        (
            "core",
            "0058_remove_historicalsubscription_unsubscription_requested_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="Ad",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "description",
                    models.CharField(max_length=200, verbose_name="Description"),
                ),
                ("price", models.PositiveIntegerField(verbose_name="Price")),
                (
                    "start_date",
                    models.DateField(blank=True, null=True, verbose_name="Start date"),
                ),
                (
                    "end_date",
                    models.DateField(blank=True, null=True, verbose_name="End date"),
                ),
            ],
            options={
                "verbose_name": "Ad",
                "verbose_name_plural": "Ad",
            },
        ),
        migrations.CreateModel(
            name="AdvertisementSeller",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, verbose_name="Name")),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Advertisement seller",
                "verbose_name_plural": "Advertisement sellers",
            },
        ),
        migrations.CreateModel(
            name="Advertiser",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                (
                    "type",
                    models.CharField(
                        choices=[("PU", "Public"), ("PR", "Private")],
                        max_length=2,
                        verbose_name="Type",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, null=True, verbose_name="Email"
                    ),
                ),
                (
                    "phone",
                    models.CharField(
                        blank=True, max_length=50, null=True, verbose_name="Phone"
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[("1", "High"), ("2", "Mid"), ("3", "Low")],
                        default="2",
                        max_length=2,
                        verbose_name="Importance",
                    ),
                ),
                (
                    "billing_name",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing name",
                    ),
                ),
                (
                    "billing_id_document",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        verbose_name="Billing ID document",
                    ),
                ),
                (
                    "utr",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Unique taxpayer reference",
                    ),
                ),
                (
                    "billing_phone",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing phone",
                    ),
                ),
                (
                    "billing_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        null=True,
                        verbose_name="Billing email field",
                    ),
                ),
                (
                    "billing_address",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing address",
                    ),
                ),
                (
                    "main_contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.contact",
                        verbose_name="Main contact",
                    ),
                ),
                (
                    "main_seller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="advertiser_main_seller",
                        to="advertisement.advertisementseller",
                        verbose_name="Seller",
                    ),
                ),
                (
                    "other_contacts",
                    models.ManyToManyField(
                        blank=True,
                        related_name="other_advertisements",
                        to="core.contact",
                        verbose_name="Other contacts",
                    ),
                ),
            ],
            options={
                "verbose_name": "Advertiser",
                "verbose_name_plural": "Advertisers",
            },
        ),
        migrations.CreateModel(
            name="AdType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, verbose_name="Name")),
                ("description", models.TextField(verbose_name="Description")),
                (
                    "reference_price",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Reference price"
                    ),
                ),
                (
                    "advertise_in_products",
                    models.ManyToManyField(
                        to="core.product", verbose_name="Advertise in these products"
                    ),
                ),
            ],
            options={
                "verbose_name": "Ad type",
                "verbose_name_plural": "Ad types",
            },
        ),
        migrations.CreateModel(
            name="AdPurchaseOrder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date_created",
                    models.DateField(auto_now_add=True, verbose_name="Date created"),
                ),
                ("billed", models.BooleanField(default=False, verbose_name="billed")),
                (
                    "taxes",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Taxes"
                    ),
                ),
                (
                    "total_price",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Total price"
                    ),
                ),
                ("notes", models.TextField(verbose_name="Notes")),
                (
                    "billing_name",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing name",
                    ),
                ),
                (
                    "billing_id_document",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        verbose_name="Billing ID document",
                    ),
                ),
                (
                    "utr",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Unique taxpayer reference",
                    ),
                ),
                (
                    "billing_phone",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing phone",
                    ),
                ),
                (
                    "billing_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        null=True,
                        verbose_name="Billing email field",
                    ),
                ),
                (
                    "ads",
                    models.ManyToManyField(
                        to="advertisement.ad", verbose_name="Ad lines"
                    ),
                ),
                (
                    "advertiser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.advertiser",
                        verbose_name="Advertiser",
                    ),
                ),
                (
                    "bill_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_advertiser",
                        to="advertisement.advertiser",
                        verbose_name="Bill to advertiser",
                    ),
                ),
                (
                    "billing_address",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.address",
                        verbose_name="Billing address",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.advertisementseller",
                        verbose_name="Seller",
                    ),
                ),
                (
                    "agency",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ad_order_agency",
                        to="advertisement.advertiser",
                        verbose_name="Advertiser",
                    ),
                ),
                (
                    "agency_commission",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "seller_commission",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
            ],
            options={
                "verbose_name": "Ad purchase order",
                "verbose_name_plural": "Ad purchase orders",
            },
        ),
        migrations.AddField(
            model_name="ad",
            name="adtype",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="advertisement.adtype",
                verbose_name="Advertisement type",
            ),
        ),
        migrations.CreateModel(
            name="Agency",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, null=True, verbose_name="Email"
                    ),
                ),
                (
                    "phone",
                    models.CharField(
                        blank=True, max_length=50, null=True, verbose_name="Phone"
                    ),
                ),
                (
                    "billing_name",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing name",
                    ),
                ),
                (
                    "billing_id_document",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        verbose_name="Billing ID document",
                    ),
                ),
                (
                    "utr",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Unique taxpayer reference",
                    ),
                ),
                (
                    "billing_phone",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing phone",
                    ),
                ),
                (
                    "billing_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        null=True,
                        verbose_name="Billing email field",
                    ),
                ),
                (
                    "billing_address",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Billing address",
                    ),
                ),
                (
                    "main_seller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agency_main_seller",
                        to="advertisement.advertisementseller",
                        verbose_name="Seller",
                    ),
                ),
                (
                    "other_contacts",
                    models.ManyToManyField(
                        blank=True,
                        related_name="other_agencies",
                        to="core.contact",
                        verbose_name="Other contacts",
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[("1", "High"), ("2", "Mid"), ("3", "Low")],
                        default="2",
                        max_length=2,
                        verbose_name="Importance",
                    ),
                ),
                (
                    "main_contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agency_main_contact",
                        to="core.contact",
                        verbose_name="Main contact",
                    ),
                ),
            ],
            options={
                "verbose_name": "Agency",
                "verbose_name_plural": "Agencies",
            },
        ),
        migrations.CreateModel(
            name="AdvertisementActivity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("I", "In"), ("O", "Out")], default="O", max_length=1
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("V", "Visit"),
                            ("E", "Email"),
                            ("P", "Phone call"),
                            ("M", "Instant messaging"),
                        ],
                        max_length=1,
                        null=True,
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("P", "Pending"), ("C", "Completed")],
                        default="P",
                        max_length=1,
                    ),
                ),
                (
                    "advertiser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.advertiser",
                        verbose_name="Advertiser",
                    ),
                ),
                (
                    "purchase_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.adpurchaseorder",
                        verbose_name="Purchase order",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.advertisementseller",
                        verbose_name="Seller",
                    ),
                ),
                (
                    "date",
                    models.DateTimeField(blank=True, null=True, verbose_name="Date"),
                ),
                (
                    "agency",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.agency",
                        verbose_name="Agency",
                    ),
                ),
            ],
            options={
                "verbose_name": "Advertisement activity",
                "verbose_name_plural": "Advertisement activities",
                "get_latest_by": "id",
            },
        ),
        migrations.AlterField(
            model_name="adpurchaseorder",
            name="agency",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="advertisement.agency",
                verbose_name="Agency",
            ),
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="ads",
        ),
        migrations.AddField(
            model_name="ad",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="advertisement.adpurchaseorder",
            ),
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="billing_address",
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="billing_email",
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="billing_id_document",
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="billing_name",
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="billing_phone",
        ),
        migrations.RemoveField(
            model_name="adpurchaseorder",
            name="utr",
        ),
        migrations.AlterField(
            model_name="adpurchaseorder",
            name="bill_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="billing_agency",
                to="advertisement.agency",
                verbose_name="Bill to agency",
            ),
        ),
        migrations.CreateModel(
            name="Agent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, null=True, verbose_name="Email"
                    ),
                ),
                (
                    "advertiser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.advertiser",
                    ),
                ),
                (
                    "agency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="advertisement.agency",
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.contact",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, null=True, verbose_name="Notes"),
                ),
            ],
            options={
                "verbose_name": "Agent",
                "verbose_name_plural": "Agents",
            },
        ),
        migrations.AddField(
            model_name="adpurchaseorder",
            name="date_billed",
            field=models.DateField(blank=True, null=True, verbose_name="Date billed"),
        ),
    ]
