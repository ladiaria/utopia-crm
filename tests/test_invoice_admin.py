# coding=utf-8
from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.forms.models import model_to_dict
from django.test import RequestFactory, TestCase

from invoicing.models import Invoice

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
