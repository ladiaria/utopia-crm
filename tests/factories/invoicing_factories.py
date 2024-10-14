from datetime import date, timedelta

from django.conf import settings

from factory import Faker, SubFactory, post_generation, lazy_attribute
from factory.django import DjangoModelFactory

from invoicing.models import Invoice, InvoiceItem
from tests.factories import ContactFactory, ProductFactory


class InvoiceFactory(DjangoModelFactory):
    """
    Factory for creating Invoice instances. Default settings create an unpaid invoice.
    """
    class Meta:
        model = Invoice

    contact = SubFactory(ContactFactory)
    payment_type = Faker("random_element", elements=[choice[0] for choice in settings.INVOICE_PAYMENT_METHODS])
    paid = False
    debited = False
    canceled = False
    uncollectible = False
    creation_date = date.today()
    expiration_date = date.today() + timedelta(days=14)
    service_from = date.today()
    service_to = date.today() + timedelta(days=30)

    @post_generation
    def set_overdue_date(self, create, extracted, **kwargs):
        if not create:
            return
        # Overriding expiration_date if passed as an argument
        if extracted:
            self.expiration_date = extracted

    @post_generation
    def set_invoice_items(self, create, extracted, **kwargs):
        if not create:
            return
        # Create multiple invoice items if 'extracted' contains a number or list of items
        if extracted:
            if isinstance(extracted, int):
                # Create 'extracted' number of InvoiceItem instances
                InvoiceItemFactory.create_batch(extracted, invoice=self)
            else:
                # Assuming extracted is a list of pre-created invoice items
                for item in extracted:
                    item.invoice = self
                    item.save()
        else:
            # Create one default invoice item if none are passed
            InvoiceItemFactory.create(invoice=self)


class InvoiceItemFactory(DjangoModelFactory):
    class Meta:
        model = InvoiceItem

    invoice = SubFactory(InvoiceFactory)
    product = SubFactory(ProductFactory)
    copies = Faker("random_int", min=1, max=10)
    price = Faker("random_int", min=1, max=1000)

    @lazy_attribute
    def amount(self):
        return self.copies * self.price
