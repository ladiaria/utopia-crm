# Generated by Django 4.1.4 on 2023-12-26 14:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
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
            ],
            options={
                "verbose_name": "Ad purchase order",
                "verbose_name_plural": "Ad purchase orders",
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
                        choices=[("PU", "Public"), ("PR", "Private"), ("AG", "Agency")],
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
                        choices=[("HI", "High"), ("MD", "Mid"), ("LO", "Low")],
                        default="MD",
                        max_length=2,
                        verbose_name="Priority",
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
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.address",
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
                ("date_created", models.DateTimeField(verbose_name="Creation date")),
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
            ],
            options={
                "verbose_name": "Advertisement activity",
                "verbose_name_plural": "Advertisement activities",
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
        migrations.AddField(
            model_name="adpurchaseorder",
            name="advertiser",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="advertisement.advertiser",
                verbose_name="Advertiser",
            ),
        ),
        migrations.AddField(
            model_name="adpurchaseorder",
            name="bill_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="billing_advertiser",
                to="advertisement.advertiser",
                verbose_name="Bill to advertiser",
            ),
        ),
        migrations.AddField(
            model_name="adpurchaseorder",
            name="billing_address",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="core.address",
                verbose_name="Billing address",
            ),
        ),
        migrations.AddField(
            model_name="adpurchaseorder",
            name="main_seller",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="advertisement.advertisementseller",
                verbose_name="Seller",
            ),
        ),
        migrations.AddField(
            model_name="adpurchaseorder",
            name="seller",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="order_seller",
                to="advertisement.advertisementseller",
                verbose_name="Seller",
            ),
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
    ]
