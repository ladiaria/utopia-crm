# coding=utf-8

from datetime import date

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from django.conf import settings

from core.models import Subscription, Contact
from invoicing.choices import (
    INVOICEITEM_TYPE_CHOICES,
    INVOICEITEM_DR_TYPE_CHOICES,
    BILLING_STATUS,
)


class Invoice(models.Model):
    contact = models.ForeignKey("core.Contact")
    creation_date = models.DateField()
    expiration_date = models.DateField()
    service_from = models.DateField()
    service_to = models.DateField()

    balance = models.DecimalField(_("Balance"), max_digits=10, decimal_places=2, blank=True, null=True)
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2, blank=True, null=True)
    payment_type = models.CharField(_("Payment type"), max_length=2, choices=settings.INVOICE_PAYMENT_METHODS)
    debited = models.BooleanField(_("Debited"), default=False)
    paid = models.BooleanField(_("Paid"), default=False)
    payment_date = models.DateField(_("Payment date"), blank=True, null=True)
    payment_reference = models.CharField(_("Payment reference"), max_length=32, blank=True, null=True)
    notes = models.TextField(_("Invoice notes"), blank=True, null=True)
    canceled = models.BooleanField(_("Canceled"), default=False, editable=False)
    cancelation_date = models.DateField(_("Cancelation date"), blank=True, editable=False, null=True)
    uncollectible = models.BooleanField(_("Uncollectible"), default=False)
    subscription = models.ForeignKey("core.Subscription", blank=True, null=True, on_delete=models.SET_NULL)
    print_date = models.DateField(null=True, blank=True)

    uuid = models.CharField(max_length=36, editable=False, blank=True, null=True)
    serie = models.CharField(max_length=1, editable=False, blank=True, null=True)
    numero = models.PositiveIntegerField(editable=False, blank=True, null=True)
    pdf = models.FileField(upload_to=settings.INVOICES_PATH, editable=False, blank=True, null=True)

    # Fields for CFE
    billing_address = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Billing Address"))
    billing_state = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Billing State"))
    billing_city = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Billing City"))
    billing_document = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Billing Identifcation Document"),
    )
    billing_name = models.CharField(max_length=100, verbose_name=_("Billing Name"), null=True, blank=True)

    # Fields for logistics
    route = models.PositiveIntegerField(blank=True, null=True)
    order = models.PositiveIntegerField(blank=True, null=True)

    billing = models.ForeignKey("invoicing.Billing", blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '%s %d' % (_('Invoice'), self.id)

    def calc_total_amount(self):
        """
        Calculates the total amount of the invoice according to the items. If the item is a discount, then the amount
        will be subtracted.
        """
        amount = 0
        for i in self.invoiceitem_set.all():
            amount = amount - i.amount if i.type == "D" else amount + i.amount
        return amount

    def get_status(self, with_date=True):
        if self.paid or self.debited:
            if with_date:
                return _("Paid on {}".format(self.payment_date))
            else:
                return _("Paid")
        elif self.uncollectible:
            return _("Uncollectible")
        elif self.canceled:
            return _("Canceled")
        elif not (self.paid or self.debited) and self.expiration_date <= date.today():
            return _("Overdue")
        else:
            return _("Pending")

    def get_status_code(self):
        if self.paid or self.debited:
            return "p"
        elif self.uncollectible:
            return "u"
        elif self.canceled:
            return "c"
        elif not (self.paid or self.debited) and self.expiration_date <= date.today():
            return "o"
        else:
            return "d"

    def get_payment_type(self):
        types = dict(settings.INVOICE_PAYMENT_METHODS)
        return types.get(self.payment_type, _("Unspecified payment method"))

    def has_product(self, product_slug):
        return self.invoiceitem_set.filter(product__slug=product_slug).exists()

    def get_invoiceitem_count(self, ignore_type=None):
        if ignore_type is None:
            return self.invoiceitem_set.all().count()
        else:
            return self.invoiceitem_set.all().exclude(type=ignore_type).count()

    def get_invoiceitem_description_list(self, html=True):
        if html:
            resp = "<ul>"
        else:
            resp = ""
        if self.invoiceitem_set.exists():
            for index, item in enumerate(self.invoiceitem_set.all()):
                if html:
                    resp += "<li>{}</li>".format(item.description)
                else:
                    if index > 0:
                        resp += ", "
                    resp += str(item.description)
        if html:
            resp += "</ul>"
        return resp

    def get_creditnote(self):
        if self.creditnote_set.exists():
            return self.creditnote_set.first()
        else:
            return None

    class Meta:
        verbose_name = "invoice"
        verbose_name_plural = "invoices"
        ordering = ["creation_date"]


class InvoiceCopy(Invoice):
    """
    Simplemente para dar acceso de sólo lectura a algunos usuarios para poder
    ver las facturas en el admin.
    """

    class Meta:
        proxy = True


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    product = models.ForeignKey(
        "core.Product", blank=True, null=True, on_delete=models.SET_NULL
    )
    subscription = models.ForeignKey(
        "core.Subscription", blank=True, null=True, on_delete=models.SET_NULL
    )
    copies = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=500)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    notes = models.TextField(blank=True, null=True)
    service_from = models.DateField(null=True, blank=True)
    service_to = models.DateField(null=True, blank=True)

    # Fields for CFE
    type = models.CharField(max_length=1, default="I", choices=INVOICEITEM_TYPE_CHOICES)
    type_dr = models.CharField(
        max_length=1, blank=True, null=True, choices=INVOICEITEM_DR_TYPE_CHOICES
    )

    def __str__(self):
        return str(self.description)

    class Meta:
        verbose_name = "invoice item"
        verbose_name_plural = "invoice items"
        ordering = ["invoice"]


class InvoiceItemCopy(InvoiceItem):
    """
    Gives read-only access to Invoices for some users to prevent them from
    making changes to them. Used until read permissions are a thing.
    """

    class Meta:
        proxy = True


class Billing(models.Model):
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, blank=True, null=True, related_name="created_by"
    )
    started_by = models.ForeignKey(
        User, blank=True, null=True, related_name="started_by"
    )
    product = models.ForeignKey("core.Product", blank=True, null=True)
    payment_type = models.CharField(
        max_length=1,
        choices=settings.SUBSCRIPTION_PAYMENT_METHODS,
        null=True,
        blank=True,
    )
    errors = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    billing_date = models.DateField()
    dpp = models.PositiveSmallIntegerField(default=10)
    exclude = models.ManyToManyField(Contact)
    status = models.CharField(max_length=1, default="P", choices=BILLING_STATUS)

    # Used to generate an accurate progress
    processed_contacts = models.IntegerField(default=0)
    subscriber_amount = models.IntegerField(default=0)

    def progress(self):
        """
        Returns the percentage of progress for completion on this Billing object.
        """
        count = self.processed_contacts
        total = self.subscriber_amount
        if self.status == "C":
            return "100.00"
        if total > 0:
            return "{0:.2f}".format(float(count) * 100 / float(total))
        else:
            return 0

    def count(self):
        """
        Returns the amount of invoices this billing has.
        """
        return self.invoice_set.all().count()

    def amount_billed(self):
        """
        Returns the amount of money billed in this billing. It includes every invoice, even if it was canceled.
        """
        if self.invoice_set.exists():
            return self.invoice_set.aggregate(Sum("amount"))["amount__sum"]
        else:
            return "-"

    def subscriptions_to_bill(self, count=False):
        subscriptions = Subscription.objects.filter(
            Q(end_date=None) | Q(end_date__gt=self.billing_date),
            active=True,
            type="N",
            next_billing__lte=self.billing_date,
        )
        if self.payment_type:
            subscriptions = subscriptions.filter(payment_type=self.payment_type)
        return subscriptions.count() if count else subscriptions

    class Meta:
        app_label = "invoicing"
        verbose_name_plural = "billings"
        get_latest_by = "start"


class CreditNote(models.Model):
    """
    Esto modela las notas de crédito necesarias para la factura electrónica.
    """

    invoice = models.ForeignKey(Invoice)
    uuid = models.CharField(max_length=36, blank=True, null=True)
    serie = models.CharField(max_length=1, editable=False, blank=True, null=True)
    numero = models.PositiveIntegerField(editable=False, blank=True, null=True)

    class Meta:
        verbose_name_plural = "credit notes"

    def get_contact_id(self):
        return self.invoice.contact_id


class CreditNoteCopy(CreditNote):
    """
    Gives read-only access to CreditNotes for some users to prevent them from
    making changes to them. Used until read permissions are a thing.
    """

    class Meta:
        proxy = True
