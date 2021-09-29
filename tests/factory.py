# coding=utf-8
from datetime import date, timedelta

from core.models import Contact, Subscription

"""
Funciones de creacion de objetos, retornan el objeto creado pero re-evaluado
desde la base de datos; si no, hay riesgo de que valores por defecto
quieran pasarse por arriba, como por ejemplo la fecha de creado.
"""


def create_contact(name, phone, email=None):
    contact = Contact(name=name, phone=phone, email=email)
    if not email:
        contact.no_mail = True
    else:
        contact.no_mail = False
    contact.save()

    return Contact.objects.get(pk=contact.id)


def create_subscription(contact, subscription_type='N', payment_type='C'):
    # subscription_type is ('P', 'R', 'N', 'F')
    # F is Free
    subscription = Subscription(contact=contact)
    subscription.type = subscription_type
    subscription.payment_type = payment_type
    subscription.save()

    return Subscription.objects.get(pk=subscription.id)


def create_empty_invoice(contact, payment_type, amount=0, frequency_months=1):
    """ creates an empty invoice with creation_date today, expiration_date
    today + 10 days and service_from today and service_to today +
    frequency_months
    """
    from invoicing.models import Invoice
    DAYS_GAP = 10
    # amount = contact.get_billing_amount()
    # subscription = contact.get_billing_subscription()
    # service_from = date.today()
    # service_to = date.today() + subscription.frequency
    invoice = Invoice.objects.create(
        contact=contact,
        payment_type=payment_type,
        amount=amount,
        creation_date=date.today(),
        expiration_date=date.today() + DAYS_GAP,
        service_from=date.today(),
        service_to=date.today() + frequency_months,
        # TODO: ADD BILLING DATA
    )

    return Invoice.objects.get(pk=invoice.id)


def create_invoiceitem(invoice, product, copies=1):
    from invoicing.models import InvoiceItem
    invoice_item = InvoiceItem.objects.create(
        invoice=invoice,
        product=product,
        price=product.price,
        amount=product.price * copies,
        description='{} x {}UN'.format(product.name, copies),
    )

    return InvoiceItem.objects.get(pk=invoice_item.id)


def create_simple_invoice(contact, payment_type, product):
    """
    Creates an invoice with a single product and creation_date = Today, due date today + 10 days.
    """
    from invoicing.models import Invoice, InvoiceItem
    invoice = Invoice.objects.create(
        contact=contact,
        payment_type=payment_type,
        amount=product.price,
        creation_date=date.today(),
        expiration_date=date.today() + timedelta(10),
        service_from=date.today(),
        service_to=date.today() + timedelta(30),
    )

    InvoiceItem.objects.create(
        product=product,
        copies=1,
        price=product.price,
        amount=product.price,
        description='{} x {}un.'.format(product.name, 1),
        invoice=invoice,
    )

    return Invoice.objects.get(pk=invoice.pk)


def create_route(number, name):
    """ Creates a route with name: 'Route {number}' """
    from logistics.models import Route

    # add route.active field ???
    route = Route.objects.create(number=number, name='Route {}'.format(number))
    route.save()

    return Route.objects.get(pk=route.number)


def create_address(address_1, contact, address_type='physical'):
    from core.models import Address
    address = Address.objects.create(address_1=address_1, contact=contact, address_type=address_type)

    return Address.objects.get(pk=address.id)


def create_scheduled_task(contact, category, execution_date):
    from support.models import ScheduledTask
    scheduled_task = ScheduledTask.objects.create(contact=contact, category=category, execution_date=execution_date)

    return ScheduledTask.objects.get(pk=scheduled_task.id)


def create_issue(contact, date):
    from support.models import Issue
    issue = Issue.objects.create(contact=contact, date=date)

    return Issue.objects.get(pk=issue.id)


def create_product(name, price, type="S", billing_priority=1):
    from core.models import Product
    product = Product.objects.create(
        name=name, price=price, type=type, billing_priority=billing_priority)

    return Product.objects.get(pk=product.pk)


def create_campaign(name):
    from core.models import Campaign
    campaign = Campaign.objects.create(name=name)

    return Campaign.objects.get(pk=campaign.pk)


def create_subtype(name):
    from core.models import Subtype
    subtype = Subtype.objects.create(name=name)

    return Subtype.objects.get(pk=subtype.pk)


def create_dynamiccontactfilter(description, mode=1):
    from core.models import DynamicContactFilter
    dcf = DynamicContactFilter.objects.create(description=description, mode=mode)

    return DynamicContactFilter.objects.get(pk=dcf.pk)


def create_pricerule(products_pool, mode, add_wildcard, resulting_product=None, products_not_pool=[]):
    from core.models import PriceRule
    pr = PriceRule.objects.create(active=True, mode=mode, add_wildcard=add_wildcard)
    for p in products_pool:
        pr.products_pool.add(p)
    for p in products_not_pool:
        pr.products_not_pool.add(p)
    if resulting_product:
        pr.resulting_product = resulting_product
    pr.save()

    return PriceRule.objects.get(pk=pr.pk)
