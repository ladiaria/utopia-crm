# coding=utf-8
from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.forms.models import model_to_dict
from django.test import RequestFactory, TestCase
from django.urls import reverse

from invoicing.models import Invoice, InvoiceItem

from tests.factory import create_contact


class TestInvoiceAdminAmount(TestCase):
    """The invoice admin must not save an invoice without an amount."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password")
        contact = create_contact("Contact", "29000808", "contact@example.com")
        cls.invoice = Invoice.objects.create(
            contact=contact,
            payment_type="R",
            amount=400,
            creation_date=date.today(),
            expiration_date=date.today() + timedelta(10),
            service_from=date.today(),
            service_to=date.today() + timedelta(30),
        )

    def build_form(self, **changes):
        # Whatever admin is registered for Invoice (a customization package may subclass InvoiceAdmin)
        model_admin = admin.site._registry[Invoice]
        request = RequestFactory().post("/")
        request.user = self.user
        form_class = model_admin.get_form(request, self.invoice, change=True)
        data = {key: value for key, value in model_to_dict(self.invoice).items() if value is not None}
        data.update(changes)
        return form_class(data=data, instance=self.invoice)

    def test_amount_is_required(self):
        form = self.build_form(amount="")

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_amount_present_is_accepted(self):
        form = self.build_form(amount="350.00")

        form.is_valid()
        self.assertNotIn("amount", form.errors)


class TestInvoiceItemOnlyThroughInvoice(TestCase):
    """
    Invoice items are seen and edited inside their invoice. A change page of their own would build a dropdown with
    every invoice and another with every subscription: opening one ran the production server out of memory.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password")
        contact = create_contact("Contact", "29000808", "contact@example.com")
        cls.invoice = Invoice.objects.create(
            contact=contact,
            payment_type="R",
            amount=400,
            creation_date=date.today(),
            expiration_date=date.today() + timedelta(10),
            service_from=date.today(),
            service_to=date.today() + timedelta(30),
        )
        InvoiceItem.objects.create(invoice=cls.invoice, description="Inline item", amount=400, price=400, copies=1)

    def test_invoice_item_has_no_admin_of_its_own(self):
        self.assertFalse(admin.site.is_registered(InvoiceItem))

    def test_items_are_shown_in_the_invoice_admin(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("admin:invoicing_invoice_change", args=[self.invoice.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="invoiceitem_set-0-description"')
        self.assertContains(response, "Inline item")
