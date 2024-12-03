from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import SubscriptionProduct
from invoicing.models import InvoiceItem
from core.utils import calc_price_from_products

from invoicing.models import Invoice


def bill_subscription(subscription, billing_date=None, dpp=10):
    """
    Bills a single subscription into an only invoice. Returns the created invoice.
    """

    # Safely get settings with default values
    billing_extra_days = getattr(settings, 'BILLING_EXTRA_DAYS', 0)
    force_dummy_missing_billing_data = getattr(settings, 'FORCE_DUMMY_MISSING_BILLING_DATA', False)
    require_route_for_billing = getattr(settings, 'REQUIRE_ROUTE_FOR_BILLING', False)
    exclude_routes_from_billing_list = getattr(settings, 'EXCLUDE_ROUTES_FROM_BILLING_LIST', [])
    envelope_price = getattr(settings, 'ENVELOPE_PRICE', 0)

    billing_date = billing_date or date.today()
    invoice = None

    # Check that the subscription is active
    assert subscription.active, _('This subscription is not active and should not be billed.')

    # Check that the subscription is normal
    assert subscription.type in ('N', 'C'), _('This subscription is not normal or corporate and should not be billed.')

    # Check that the next billing date exists or we need to raise an exception.
    assert subscription.next_billing, _("Could not bill because next billing date does not exist")

    # Check that the subscription has a payment type
    assert subscription.payment_type, _("The subscription has no payment type, it can't be billed")

    # Check that the subscription's next billing is smaller than end date if it has it
    if subscription.end_date:
        error_msg = _("This subscription has an end date greater than its next billing")
        assert subscription.next_billing < subscription.end_date, error_msg

    if subscription.next_billing > billing_date + timedelta(billing_extra_days):
        raise Exception(_('This subscription should not be billed yet.'))

    # We need to get all the subscription data
    billing_data = subscription.get_billing_data_by_priority()

    if not billing_data and not force_dummy_missing_billing_data:
        raise Exception(
            f"Subscription {subscription.id} for contact {subscription.contact.id} contains no billing data."
        )

    if billing_data and billing_data["address"] is None:
        raise Exception(
            f"Subscription {subscription.id} for contact {subscription.contact.id} requires an address to be billed."
        )

    if billing_data and require_route_for_billing:
        if billing_data["route"] is None:
            raise Exception(
                f"Subscription {subscription.id} for contact {subscription.contact.id} requires a route to be billed."
            )

        elif billing_data["route"] in exclude_routes_from_billing_list:
            raise Exception(
                f"Subscription {subscription.id} for contact {subscription.contact.id} can't be billed since it's on"
                f"route {billing_data['route']}."
            )

    product_summary = subscription.product_summary(with_pauses=True)

    # Calculate price and get invoice items
    amount, invoice_items = calc_price_from_products(
        product_summary,
        subscription.frequency,
        debug_id=f"subscription_{subscription.id}",
        create_items=True,
        subscription=subscription
    )
    print("Invoice items are:", invoice_items, "amount is", amount)

    # Handle envelope price if needed
    if envelope_price and SubscriptionProduct.objects.filter(subscription=subscription, has_envelope=1).exists():
        products_with_envelope_count = SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1
        ).count()
        envelope_amount = products_with_envelope_count * envelope_price * subscription.frequency
        envelope_item = InvoiceItem(
            description=_('Envelope'),
            amount=envelope_amount,
            subscription=subscription
        )
        invoice_items.append(envelope_item)
        amount += envelope_amount

    overdue_date = billing_date + timedelta(int(dpp))
    service_from = subscription.next_billing

    try:
        # Create invoice if amount is greater than 0
        if amount > 0:
            invoice = Invoice.objects.create(
                contact=subscription.get_billing_contact(),
                payment_type=subscription.payment_type,
                creation_date=billing_date,
                service_from=service_from,
                service_to=service_from + relativedelta(months=subscription.frequency),
                billing_name=billing_data['name'],
                billing_address=billing_data['address'],
                billing_state=billing_data['state'],
                billing_city=billing_data['city'],
                route=billing_data['route'],
                order=billing_data['order'],
                expiration_date=overdue_date,
                billing_document=subscription.get_billing_document(),
                subscription=subscription,
                amount=amount,
            )

            # Add all invoice items to the invoice
            for item in invoice_items:
                print("Adding item", item.product.slug)
                item.save()
                invoice.invoiceitem_set.add(item)
                # TODO: We need a better way to identify one-shot products than checking the edition frequency
                if item.product and item.product.edition_frequency == 4:
                    invoice.subscription.remove_product(item.product)
                    # After this if the subscription has no products left, we should end it
                    if not invoice.subscription.products.exists():
                        invoice.subscription.end_date = billing_date
                        invoice.subscription.active = False
                        invoice.subscription.save()

            # Remove temporary discounts if applicable
            invoiceitems_with_temporary_discount = invoice.invoiceitem_set.filter(
                product__temporary_discount_months__gte=1
            )
            for invoiceitem in invoiceitems_with_temporary_discount:
                temporary_discount = invoiceitem.product
                months = temporary_discount.temporary_discount_months
                if invoice.subscription.months_in_invoices_with_product(temporary_discount.slug) >= months:
                    invoice.subscription.remove_product(temporary_discount)

        # Update subscription billing date
        subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
            months=subscription.frequency
        )
        subscription.save()

        assert amount, _("This subscription wasn't billed since amount is 0")

    except Exception as e:
        raise Exception(f"Contact {subscription.contact.id} Subscription {subscription.id}: {e}")

    return invoice
