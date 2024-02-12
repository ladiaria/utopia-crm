from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.urls import reverse


class Advertiser(models.Model):
    # This model is used to store the advertisers
    class AdvertiserType(models.TextChoices):
        PUBLIC = "PU", _("Public")
        PRIVATE = "PR", _("Private")

    class Priority(models.TextChoices):
        HIGH = "1", _("High")
        MID = "2", _("Mid")
        LOW = "3", _("Low")

    name = models.CharField(_("Name"), max_length=100)
    main_contact = models.ForeignKey(
        "core.Contact", verbose_name=_("Main contact"), on_delete=models.CASCADE, null=True, blank=True
    )
    type = models.CharField(_("Type"), choices=AdvertiserType.choices, max_length=2)
    other_contacts = models.ManyToManyField(
        "core.Contact", verbose_name=_("Other contacts"), related_name="other_advertisements", blank=True
    )
    email = models.EmailField(_("Email"), max_length=254, null=True, blank=True)
    phone = models.CharField(_("Phone"), max_length=50, null=True, blank=True)
    priority = models.CharField(_("Importance"), max_length=2, choices=Priority.choices, default=Priority.MID)

    # Billing data
    billing_name = models.CharField(_("Billing name"), max_length=50, null=True, blank=True)
    billing_id_document = models.CharField(_("Billing ID document"), max_length=20, blank=True, null=True)
    utr = models.CharField(_("Unique taxpayer reference"), max_length=50, blank=True, null=True)
    billing_phone = models.CharField(_("Billing phone"), max_length=50, null=True, blank=True)
    billing_address = models.CharField(_("Billing address"), max_length=50, null=True, blank=True)
    billing_email = models.EmailField(_("Billing email field"), max_length=254, null=True, blank=True)
    main_seller = models.ForeignKey(
        "advertisement.advertisementseller",
        verbose_name=_("Seller"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="advertiser_main_seller",
    )

    class Meta:
        verbose_name = _("Advertiser")
        verbose_name_plural = _("Advertisers")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("advertiser_detail", kwargs={"pk": self.pk})

    def get_advertisement_activies(self, status=None):
        if self.advertisementactivity_set.exists():
            qs = self.advertisementactivity_set.all()
            if type:
                qs = qs.filter(status=status)
            return qs
        else:
            return None

    def get_latest_pending_activity(self):
        if self.advertisementactivity_set.exists():
            return self.get_advertisement_activies("P").latest()
        else:
            return None

    def get_latest_completed_activity(self):
        if self.advertisementactivity_set.exists():
            return self.get_advertisement_activies("C").latest()
        else:
            return None


class Agency(models.Model):
    # This model is used to store the advertisement agencies
    class Priority(models.TextChoices):
        HIGH = "1", _("High")
        MID = "2", _("Mid")
        LOW = "3", _("Low")

    name = models.CharField(_("Name"), max_length=100)
    main_contact = models.ForeignKey(
        "core.Contact",
        verbose_name=_("Main contact"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agency_main_contact",
    )
    other_contacts = models.ManyToManyField(
        "core.Contact", verbose_name=_("Other contacts"), related_name="other_agencies", blank=True
    )
    priority = models.CharField(_("Importance"), max_length=2, choices=Priority.choices, default=Priority.MID)
    email = models.EmailField(_("Email"), max_length=254, null=True, blank=True)
    phone = models.CharField(_("Phone"), max_length=50, null=True, blank=True)

    # Billing data
    billing_name = models.CharField(_("Billing name"), max_length=50, null=True, blank=True)
    billing_id_document = models.CharField(_("Billing ID document"), max_length=20, blank=True, null=True)
    utr = models.CharField(_("Unique taxpayer reference"), max_length=50, blank=True, null=True)
    billing_phone = models.CharField(_("Billing phone"), max_length=50, null=True, blank=True)
    billing_address = models.CharField(_("Billing address"), max_length=50, null=True, blank=True)
    billing_email = models.EmailField(_("Billing email field"), max_length=254, null=True, blank=True)
    main_seller = models.ForeignKey(
        "advertisement.advertisementseller",
        verbose_name=_("Seller"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="agency_main_seller",
    )

    class Meta:
        verbose_name = _("Agency")
        verbose_name_plural = _("Agencies")

    def __str__(self):
        return self.name


class AdvertisementSeller(models.Model):
    # This model is used to store the sellers of advertisements
    name = models.CharField(_("Name"), max_length=50)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = _("Advertisement seller")
        verbose_name_plural = _("Advertisement sellers")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("AdvertisementSeller_detail", kwargs={"pk": self.pk})


class AdType(models.Model):
    # This model is used to store the types of advertisements
    name = models.CharField(_("Name"), max_length=50)
    description = models.TextField(_("Description"))
    reference_price = models.PositiveIntegerField(_("Reference price"), null=True, blank=True)
    advertise_in_products = models.ManyToManyField("core.product", verbose_name=_("Advertise in these products"))

    class Meta:
        verbose_name = _("Ad type")
        verbose_name_plural = _("Ad types")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("AdType_detail", kwargs={"pk": self.pk})


class Ad(models.Model):
    # This model is used to store the advertisements
    order = models.ForeignKey("advertisement.adpurchaseorder", null=True, blank=True, on_delete=models.CASCADE)
    adtype = models.ForeignKey("advertisement.adtype", verbose_name=_("Advertisement type"), on_delete=models.CASCADE)
    description = models.CharField(_("Description"), max_length=200)
    price = models.PositiveIntegerField(_("Price"))
    start_date = models.DateField(_("Start date"), blank=True, null=True)
    end_date = models.DateField(_("End date"), blank=True, null=True)

    class Meta:
        verbose_name = _("Ad")
        verbose_name_plural = _("Ad")

    def __str__(self):
        return self.description

    def get_absolute_url(self):
        return reverse("Ad_detail", kwargs={"pk": self.pk})


class AdPurchaseOrder(models.Model):
    # This model is used to store the purchase orders for advertisements
    date_created = models.DateField(_("Date created"), auto_now_add=True)
    billed = models.BooleanField(_("billed"), default=False)
    advertiser = models.ForeignKey("advertisement.advertiser", verbose_name=_("Advertiser"), on_delete=models.CASCADE)
    taxes = models.PositiveIntegerField(_("Taxes"), blank=True, null=True)
    total_price = models.PositiveIntegerField(_("Total price"), blank=True, null=True)
    notes = models.TextField(_("Notes"))

    # Option 1: Bill to existing advertiser (IE: Agency)
    bill_to = models.ForeignKey(
        "advertisement.agency",
        verbose_name=_("Bill to agency"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="billing_agency",
    )

    seller = models.ForeignKey(
        "advertisement.advertisementseller", verbose_name=_("Seller"), on_delete=models.CASCADE, blank=True, null=True
    )
    seller_commission = models.PositiveSmallIntegerField(null=True, blank=True)
    agency = models.ForeignKey(
        "advertisement.agency",
        null=True,
        blank=True,
        verbose_name=_("Agency"),
        on_delete=models.CASCADE,
    )
    agency_commission = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("Ad purchase order")
        verbose_name_plural = _("Ad purchase orders")

    def __str__(self):
        return _("Order created at %(d)s for %(a)s") % {"d": self.date_created, "a": self.advertiser}

    def get_absolute_url(self):
        return reverse("AdPurchaseOrder_detail", kwargs={"pk": self.pk})


class AdvertisementActivity(models.Model):
    # This model is used to store the activities related to an advertisement
    class Directions(models.TextChoices):
        IN = "I", _("In")
        OUT = "O", _("Out")

    class Types(models.TextChoices):
        VISIT = "V", _("Visit")
        EMAIL = "E", _("Email")
        PHONE_CALL = "P", _("Phone call")
        INSTANT_MESSAGING = "M", _("Instant messaging")

    class Status(models.TextChoices):
        PENDING = "P", _("Pending")
        COMPLETED = "C", _("Completed")

    date_created = models.DateTimeField(_("Creation date"), auto_now_add=True)
    date = models.DateTimeField(_("Date"), null=True, blank=True)
    advertiser = models.ForeignKey("advertisement.advertiser", verbose_name=_("Advertiser"), on_delete=models.CASCADE)
    agency = models.ForeignKey(
        "advertisement.agency", on_delete=models.CASCADE, verbose_name=_("Agency"), blank=True, null=True
    )
    direction = models.CharField(choices=Directions.choices, default="O", max_length=1)
    type = models.CharField(choices=Types.choices, max_length=1, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    seller = models.ForeignKey("advertisement.advertisementseller", verbose_name=_("Seller"), on_delete=models.CASCADE)
    status = models.CharField(choices=Status.choices, default="P", max_length=1)
    purchase_order = models.ForeignKey(
        "advertisement.adpurchaseorder",
        verbose_name=_("Purchase order"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Advertisement activity")
        verbose_name_plural = _("Advertisement activities")
        get_latest_by = "id"

    def __str__(self):
        return _("Activity of type %(t)s for %(a)s at %(d)s") % {
            "t": self.get_type_display(),
            "a": self.advertiser,
            "d": self.date_created,
        }

    def get_absolute_url(self):
        return reverse("AdvertisementActivity_detail", kwargs={"pk": self.pk})


class Agent(models.Model):
    # This model is used to store the relationship between an agency, an advertiser and a contact

    agency = models.ForeignKey("advertisement.agency", on_delete=models.CASCADE)
    advertiser = models.ForeignKey("advertisement.advertiser", on_delete=models.CASCADE)
    contact = models.ForeignKey("core.Contact", on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(_("Email"), max_length=254, null=True, blank=True)
    notes = models.TextField(_("Notes"), null=True, blank=True)

    class Meta:
        verbose_name = _("Agent")
        verbose_name_plural = _("Agents")

    def __str__(self):
        return f"{self.contact} - {self.agency} - {self.advertiser}"
