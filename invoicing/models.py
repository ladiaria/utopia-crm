# coding=utf-8
from datetime import date
from typing import Iterable

from simple_history.models import HistoricalRecords

from django.conf import settings
from django.db import models
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from core.models import Subscription, Contact
from invoicing.choices import INVOICEITEM_TYPE_CHOICES, INVOICEITEM_DR_TYPE_CHOICES, BILLING_STATUS


class Invoice(models.Model):
    contact = models.ForeignKey("core.Contact", on_delete=models.CASCADE)
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
    fiscal_invoice_code = models.CharField(max_length=50, blank=True, null=True)
    internal_provider_text = models.TextField(blank=True, null=True)

    billing = models.ForeignKey("invoicing.Billing", blank=True, null=True, on_delete=models.SET_NULL)
    history = HistoricalRecords()

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

    @property
    def is_paid(self):
        return self.paid or self.debited

    @property
    def is_overdue(self):
        if self.canceled or self.uncollectible:
            return False
        return self.expiration_date <= date.today() and not self.paid and not self.debited

    @property
    def is_pending(self):
        return not self.is_paid and not self.is_overdue

    def get_status(self, with_date=True):
        if self.canceled:
            return _("Canceled")
        elif self.uncollectible:
            return _("Uncollectible")
        elif self.is_paid:
            if with_date:
                return _("Paid on {}".format(self.payment_date))
            else:
                return _("Paid")
        elif self.is_overdue:
            return _("Overdue")
        else:
            return _("Pending")

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

    def add_item(self, product, amount=None, copies=1, description=None, price=None, discount=None, notes=None):
        """
        Adds a product to the invoice. If the product is a discount, the amount should be negative.
        """
        if not description:
            description = product.name
        if not price:
            price = product.price
        amount = price * copies if not amount else amount
        item = InvoiceItem(
            invoice=self,
            amount=amount,
            product=product,
            copies=copies,
            description=description,
            price=price,
            discount=discount,
            notes=notes,
        )
        item.save()

    def get_total_amount(self):
        total = 0
        for item in self.invoiceitem_set.all():
            total += item.amount
        return total

    def get_discount_items(self):
        return self.invoiceitem_set.filter(type="D")

    def get_product_items(self):
        return self.invoiceitem_set.filter(type="I")

    def get_discount_total(self):
        """Returns the total amount of all discount items"""
        return self.invoiceitem_set.filter(type="D").aggregate(
            total=Sum('amount')
        )['total'] or 0

    def get_product_total(self):
        """Returns the total amount of all product items"""
        return self.invoiceitem_set.filter(type="I").aggregate(
            total=Sum('amount')
        )['total'] or 0

    class Meta:
        verbose_name = "invoice"
        verbose_name_plural = "invoices"
        ordering = ["creation_date"]
        permissions = [
            ("can_download_pdf", "Can download PDF"),
            ("can_cancel_invoice", "Can cancel invoice"),
            ("can_generate_invoices", "Can generate invoices"),
            ("can_send_duplicate_via_email", "Can send duplicate via email"),
            ("can_send_to_mercadopago", "Can send to MercadoPago"),
        ]


class InvoiceCopy(Invoice):
    """
    Simplemente para dar acceso de sólo lectura a algunos usuarios para poder
    ver las facturas en el admin.
    """

    class Meta:
        proxy = True


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text=_("Total amount"), readonly=True)
    product = models.ForeignKey("core.Product", blank=True, null=True, on_delete=models.SET_NULL)
    subscription = models.ForeignKey("core.Subscription", blank=True, null=True, on_delete=models.SET_NULL)
    copies = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=500)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text=_("Price per copy"))
    discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    service_from = models.DateField(null=True, blank=True)
    service_to = models.DateField(null=True, blank=True)

    # Fields for CFE
    type = models.CharField(max_length=1, default="I", choices=INVOICEITEM_TYPE_CHOICES)
    type_dr = models.CharField(max_length=1, blank=True, null=True, choices=INVOICEITEM_DR_TYPE_CHOICES, default="1")

    def __str__(self):
        return str(self.description)

    def save(self, *args, **kwargs):
        if self.type == "I":
            self.amount = self.price * self.copies
        else:
            self.amount = self.price
        return super().save(*args, **kwargs)

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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name="created_by")
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name="started_by")
    product = models.ForeignKey("core.Product", on_delete=models.CASCADE, blank=True, null=True)
    payment_type = models.CharField(
        max_length=2,
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

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    uuid = models.CharField(max_length=36, blank=True, null=True)
    serie = models.CharField(max_length=1, editable=False, blank=True, null=True)
    numero = models.PositiveIntegerField(editable=False, blank=True, null=True)
    history = HistoricalRecords()

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


class MercadoPagoData(models.Model):
    contact = models.OneToOneField("core.Contact", on_delete=models.CASCADE, related_name='mercadopago_data')
    card_id = models.CharField(max_length=255, blank=True, null=True)
    customer_id = models.CharField(max_length=255, blank=True, null=True)
    payment_method_id = models.CharField(max_length=255, blank=True, null=True)
    identification_type = models.CharField(max_length=50, blank=True, null=True)

    # Consider adding these fields:
    identification_number = models.CharField(max_length=50, blank=True, null=True)
    last_four_digits = models.CharField(max_length=4, blank=True, null=True)
    payment_method_type = models.CharField(max_length=50, blank=True, null=True)
    token = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Mercado Pago Data for {self.contact}"

    class Meta:
        verbose_name = "Mercado Pago Data"
        verbose_name_plural = "Mercado Pago Data"
