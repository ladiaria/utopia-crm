from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse


class Advertiser(models.Model):
    class AdvertiserType(models.TextChoices):
        PUBLIC = "PU", _("Public")
        PRIVATE = "PR", _("Private")
        AGENCY = "AG", _("Agency")

    name = models.CharField(_("Name"), max_length=100)
    main_contact = models.ForeignKey(
        "core.Contact", verbose_name=_("Main contact"), on_delete=models.CASCADE, null=True, blank=True
    )
    type = models.CharField(_("Type"), choices=AdvertiserType.choices, max_length=2)
    other_contacts = models.ManyToManyField("core.Contact", verbose_name=_("Other contacts"))
    email = models.EmailField(_("Email"), max_length=254, null=True, blank=True)
    phone = models.CharField(_("Phone"), max_length=50, null=True, blank=True)

    # Billing data
    billing_name = models.CharField(_("Billing name"), max_length=50, null=True, blank=True)
    billing_id_document = models.CharField(_("Billing ID document"), max_length=20, blank=True, null=True)
    utr = models.CharField(_("Unique taxpayer reference"), max_length=50, blank=True, null=True)
    billing_phone = models.CharField(_("Billing phone"), max_length=50, null=True, blank=True)
    billing_address = models.ForeignKey(
        "core.Address", verbose_name=_("Billing address"), on_delete=models.CASCADE, blank=True, null=True
    )
    billing_email = models.EmailField(_("Billing email field"), max_length=254, null=True, blank=True)
    main_seller = models.ForeignKey(
        "advertisement.advertisementseller", verbose_name=_("Seller"), on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        verbose_name = _("Advertiser")
        verbose_name_plural = _("Advertisers")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("Advertiser_detail", kwargs={"pk": self.pk})


class AdvertisementSeller(models.Model):
    name = models.CharField(_("Name"), max_length=50)

    class Meta:
        verbose_name = _("Advertisement seller")
        verbose_name_plural = _("Advertisement sellers")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("AdvertisementSeller_detail", kwargs={"pk": self.pk})


class AdType(models.Model):
    name = models.CharField(_("Name"), max_length=50)
    description = models.TextField(_("Description"))
    reference_price = models.PositiveIntegerField(_("Reference price"), null=True, blank=True)

    class Meta:
        verbose_name = _("Ad type")
        verbose_name_plural = _("Ad types")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("AdType_detail", kwargs={"pk": self.pk})


class Ad(models.Model):
    adtype = models.ForeignKey("advertisement.adtype", verbose_name=_("Advertisement type"), on_delete=models.CASCADE)
    description = models.CharField(_("Description"), max_length=200)
    price = models.PositiveIntegerField(_("Price"))
    start_date = models.DateField(_("Start date"), blank=True, null=True)
    end_date = models.DateField(_("End date"), blank=True, null=True)
    advertise_in_products = models.ManyToManyField("core.product", verbose_name=_("Advertise in these products"))

    class Meta:
        verbose_name = _("Ad")
        verbose_name_plural = _("Ad")

    def __str__(self):
        return self.description

    def get_absolute_url(self):
        return reverse("Ad_detail", kwargs={"pk": self.pk})


class AdPurchaseOrder(models.Model):
    date_created = models.DateField(_("Date created"), auto_now_add=True)
    seller = models.ForeignKey("advertisement.advertisementseller", verbose_name=_("Seller"), on_delete=models.CASCADE)
    adlines = models.ManyToManyField("advertisement.adline", verbose_name=_("Ad lines"))
    billed = models.BooleanField(_("billed"), default=False)
    advertiser = models.ForeignKey("advertisement.advertiser", verbose_name=_("Advertiser"), on_delete=models.CASCADE)
    taxes = models.PositiveIntegerField(_("Taxes"), blank=True, null=True)
    total_price = models.PositiveIntegerField(_("Total price"), blank=True, null=True)

    # Option 1: Bill to existing advertiser (IE: Agency)
    bill_to = models.ForeignKey(
        "advertisement.advertiser",
        verbose_name=_("Bill to advertiser"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="billing_advertiser",
    )

    # Option 2: Bill manually
    billing_name = models.CharField(_("Billing name"), max_length=50, null=True, blank=True)
    billing_id_document = models.CharField(_("Billing ID document"), max_length=20, blank=True, null=True)
    utr = models.CharField(_("Unique taxpayer reference"), max_length=50, blank=True, null=True)
    billing_phone = models.CharField(_("Billing phone"), max_length=50, null=True, blank=True)
    billing_address = models.ForeignKey(
        "core.Address", verbose_name=_("Billing address"), on_delete=models.CASCADE, blank=True, null=True
    )
    billing_email = models.EmailField(_("Billing email field"), max_length=254, null=True, blank=True)
    main_seller = models.ForeignKey(
        "advertisement.advertisementseller", verbose_name=_("Seller"), on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        verbose_name = _("Ad purchase order")
        verbose_name_plural = _("Ad purchase orders")

    def __str__(self):
        return f"Order at {self.date_created} for {self.advertiser}"

    def get_absolute_url(self):
        return reverse("AdPurchaseOrder_detail", kwargs={"pk": self.pk})
