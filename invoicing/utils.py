from dateutil.relativedelta import relativedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now, timedelta
from django.utils.translation import gettext_lazy as _

from invoicing.models import MercadoPagoData
from invoicing.models import InvoiceItem, Invoice

# TODO: explain or remove the "Updated import" comment in next line
from core.models import Address, Subscription, Product, SubscriptionProduct  # Updated import
from core.utils import calc_price_from_products, create_invoiceitem_for_corporate_subscription, mercadopago_sdk


def mercadopago_debit(invoice, debug=False):
    """
    Calls the MercadoPago API to send the payment. Generates the card token and register the payment.
    Not suitable for subscriptions integration.
    """
    if not getattr(settings, "MERCADOPAGO_INVOICE_DEBIT_ENABLED", True):
        if settings.DEBUG:
            print("DEBUG: mercadopago_debit: Mercadopago debit skipped by settings.")
        return

    # avoid duplicate charge if this invoice was already paid or debited
    if invoice.paid or invoice.debited:
        return

    # Get MercadoPago data for the subscription
    if not invoice.subscription:
        error_status = "Invoice has no subscription associated"
        _update_invoice_notes(invoice, error_status, debug)
        return

    try:
        mp_data = MercadoPagoData.objects.get(subscription=invoice.subscription)
    except MercadoPagoData.DoesNotExist:
        error_status = "MercadoPago data not found for this subscription"
        _update_invoice_notes(invoice, error_status, debug)
        return

    # Create a MercadoPago API instance
    sdk, mp_access_token = mercadopago_sdk(False)
    if not sdk:
        error_status = "MercadoPago API could not be initialized"
        _update_invoice_notes(invoice, error_status, debug)
        return

    if mp_access_token.startswith("TEST") and mp_data.card_id == "1111111111111":
        # MP test api: Simulate a not approved payment (if forced to fail by settings).
        #              Or an approved payment for this card_id (using the "bypass" setting in utopia_cms_ladiaria),
        #              because we couldn't get a successful test payment yet, last attempts made all returned
        #              { ... status': 'rejected', 'status_detail': 'cc_rejected_other_reason' ... } wo reason info.
        if getattr(settings, "MERCADOPAGO_FORCE_FAIL_PAYMENT", False):
            return
        invoice.debited, invoice.payment_date, invoice.payment_reference = True, invoice.creation_date, "MP-0000000000"
        invoice.save()
        return

    # load status for notification on error
    error_status = None

    card_token_post_data = {"card_id": mp_data.card_id}
    if mp_access_token.startswith("TEST"):
        # the "test" security_code is needed in testing environment (TODO: recheck this need)
        card_token_post_data["security_code"] = "123"
    card_token_response = sdk.card_token().create(card_token_post_data).get("response")  # TODO: register in api log

    if card_token_response:
        # binary_mode in True indicates that the payment cannot be delayed,
        # no pending payment status, only approved or not approved.
        # more info in: https://www.mercadopago.com.ar/developers/es/guides/notifications/ipn/
        # and: https://www.mercadopago.com.ar/developers/es/guides/payments/api/handling-responses/
        payment_data = {
            "transaction_amount": float(invoice.amount),
            "token": card_token_response.get("id"),
            "description": "Suscripciones la diaria",
            "installments": 1,
            "binary_mode": True,
            "payment_method_id": mp_data.payment_method_id,
            "payer": {"id": mp_data.customer_id},
        }
        try:
            if debug:
                print(f"DEBUG: calling mp.post with\n{payment_data}")
            payment_response = sdk.payment().create(payment_data).get("response", {})  # TODO: register in api log
            payment_response_status = payment_response.get("status")

            # max attempts to resend the request if we get a 400 or 500 status (this happens frequently in test API)
            mp_max_attempts = getattr(settings, "MERCADOPAGO_API_MAX_ATTEMPTS", 10)
            mp_attempts = 0
            while payment_response_status in (400, 500) and mp_attempts < mp_max_attempts:
                payment_response = sdk.payment().create(payment_data).get("response", {})  # TODO: register in api log
                payment_response_status = payment_response.get("status")
                mp_attempts += 1

            if payment_response_status == "approved":
                today = now().date()
                invoice.debited, invoice.payment_date = True, today
                invoice.payment_reference = f"MP-{payment_response['id']}"
                if invoice.notes and "MercadoPago - Pago no aprobado" in invoice.notes:
                    invoice.notes = invoice.notes + f"\n{today} MercadoPago - Pago procesado correctamente"
                invoice.save()
            else:
                if debug:
                    print(f"DEBUG: MP response:\n{payment_response}")
                error_status = "MercadoPago - Pago no aprobado"
        except TypeError as type_error:
            error_status = str(type_error)
    else:
        error_status = "MercadoPago - No se obtuvo respuesta"

    if error_status:
        _update_invoice_notes(invoice, error_status, debug)


def _update_invoice_notes(invoice, error_status, debug):
    if debug:
        print(f"DEBUG: {error_status}")
    if invoice.notes:
        invoice.notes += "\n"
    else:
        invoice.notes = ""
    invoice.notes += f"{now().date()} {error_status}"
    invoice.save()


def create_mp_subscription_for_contact(
    contact,
    customer_address,
    customer_city,
    customer_province,
    customer_email,
    mp_customer_id,
    mp_card_id,
    card_issuer,
    expiration_month,
    expiration_year,
    product_slug,
    mp_payment_method_id,
    mp_identification_type,
    start_date=None,
):
    """
    This block of code will be used in both createinvoicefromweb and contact_update_mp, and it's better if it's only
    in one site.
    """

    # Simple check if the product_slug is valid
    if not Product.objects.filter(slug=product_slug).exists():
        raise ValueError(f"Product with slug {product_slug} does not exist")

    # We first check if the contact already has an address with the same name
    existing_address = Address.objects.filter(contact=contact, address_1=customer_address).first()
    if existing_address:
        new_address = existing_address
    else:
        new_address = Address.objects.create(
            contact=contact,
            address_1=customer_address,
            city=customer_city,
            state=customer_province,
            email=customer_email,
            default=True,
            address_type="physical",
        )

    today = now().date()
    subscription = Subscription.objects.create(
        contact=contact,
        type="N",  # The subscription will be Normal
        status="OK",  # Can be switched to awaiting payment later
        payment_type="M",  # Mercadopago
        send_bill_copy_by_email=True,
        start_date=start_date or today,
        next_billing=start_date or today,
        end_date=None,
    )

    # We should add the products to the subscription
    product = Product.objects.get(slug=product_slug)
    subscription.add_product(product, new_address)

    # Create or update MercadoPagoData for this subscription
    mp_data, created = MercadoPagoData.objects.update_or_create(
        subscription=subscription,
        defaults={
            'customer_id': mp_customer_id,
            'card_id': mp_card_id,
            'card_issuer': card_issuer,
            'expiration_month': expiration_month,
            'expiration_year': expiration_year,
            'payment_method_id': mp_payment_method_id,
            'identification_type': mp_identification_type,
        },
    )

    return subscription, mp_data


@transaction.atomic
def contact_update_mp(
    contact,
    product_slug,
    customer_telephone,
    customer_address,
    customer_city,
    customer_province,
    card_issuer,
    mp_customer_id,
    mp_card_id,
    expiration_month,
    expiration_year,
    customer_email,
    mp_payment_method_id,
    mp_identification_type,
    identification_number,
):
    """Updates a Contact to get it ready to invoice with MercadoPago. Only used when the Contact already exists"""
    if contact.has_active_subscription():
        if getattr(settings, "ALLOW_QUEUE_SUBSCRIPTIONS", False):
            # Queue a new subscription to start after the active one ends
            active_subscription = contact.get_active_subscription()
            start_date = active_subscription.end_date or (active_subscription.next_billing + relativedelta(months=1))
            if getattr(settings, "DEBUG_MERCADOPAGO", False):
                print(
                    f"DEBUG: contact_update_mp queueing subscription to start after the active one ends: {start_date}"
                )
        else:
            return (_("Customer already has an active subscription."),)
    else:
        start_date = now().date()

    # Let's also update the contact with the things that are worth it
    contact.subtype_id = getattr(settings, "WEB_UPDATE_MP_SUBTIPO_ID", None)
    if customer_telephone:
        contact.phone = customer_telephone
    if customer_email:
        contact.email = customer_email
    if identification_number:
        contact.id_document = identification_number
    contact.send_pdf = False
    contact.inactivity_reason = None
    try:
        with transaction.atomic():
            contact.save()
            if settings.DEBUG:
                print("DEBUG: contact_update_mp contact saved in transaction with phone=%s" % customer_telephone)
            result = create_mp_subscription_for_contact(
                contact,
                customer_address,
                customer_city,
                customer_province,
                customer_email,
                mp_customer_id,
                mp_card_id,
                card_issuer,
                expiration_month,
                expiration_year,
                product_slug,
                mp_payment_method_id,
                mp_identification_type,
                start_date=start_date,  # Pass the start_date to the create function
            )
        if settings.DEBUG:
            print("DEBUG: contact_update_mp after atomic block, before returning '%s'" % result)
        return result
    except Exception as exc:
        if settings.DEBUG:
            print("contact_update_mp rollbacked", "Caused by: %s" % exc)
        return (
            "La suscripción no pudo ser procesada.",
            "contact_update_mp rollback (contact.id=%d, customer_email=%s) caused by: %s"
            % (contact.id, customer_email, exc),
        )


def contact_update_mp_wrapper(
    contact,
    product_slug,
    customer_telephone,
    customer_address,
    customer_city,
    customer_province,
    card_issuer,
    mp_customer_id,
    mp_card_id,
    expiration_month,
    expiration_year,
    customer_email=None,
    mp_payment_method_id=None,
    mp_identification_type=None,
    identification_number=None,
):
    expired = contact.get_expired_invoices()
    two_years_ago = now().date() + relativedelta(years=-2)
    # TODO: See if we need this filter to be removed, change the logic or change the settings
    if expired.filter(creation_date__gte=two_years_ago).exists():
        if getattr(settings, "MERCADOPAGO_DEBTOR_EMAIL_ALERT", False):
            pass  # Alert on email
        result = (_("Customer is debtor and not authorized to create a subscription."),)
    else:
        """
        Esta funcion es un wrapper de contact_update_mp y ademas de llamarla puede alertar si el cliente es moroso
        """
        result = contact_update_mp(
            contact,
            product_slug,
            customer_telephone,
            customer_address,
            customer_city,
            customer_province,
            card_issuer,
            mp_customer_id,
            mp_card_id,
            expiration_month,
            expiration_year,
            customer_email,
            mp_payment_method_id,
            mp_identification_type,
            identification_number,
        )
        if getattr(settings, "MERCADOPAGO_DEBTOR_EMAIL_ALERT", False) and expired.exists():
            pass  # Alert on email
    return result


def bill_subscription(
    subscription,
    billing_date=None,
    dpp=10,
    force_by_date=False,
    billing_date_override=None,
    payment_reference=None,
):
    """
    Bills a single subscription into an only invoice. Returns the created invoice.
    # TODO: Products have a field "active" which may not be used here. check and make fixes if any.
    """
    # Safely get settings with default values
    billing_extra_days = getattr(settings, 'BILLING_EXTRA_DAYS', 0)
    require_route_for_billing = getattr(settings, 'REQUIRE_ROUTE_FOR_BILLING', False)
    exclude_routes_from_billing_list = getattr(settings, 'EXCLUDE_ROUTES_FROM_BILLING_LIST', [])
    envelope_price = getattr(settings, 'ENVELOPE_PRICE', 0)

    billing_date = billing_date or now().date()
    invoice = None

    # Check that the subscription is normal
    assert subscription.type in ('N', 'C'), _('This subscription is not normal or corporate and should not be billed.')

    if not force_by_date:
        # Check that the next billing date exists or we need to raise an exception.
        assert subscription.next_billing, _("Could not bill because next billing date does not exist")

        if subscription.next_billing > billing_date + timedelta(billing_extra_days):
            raise Exception(_('This subscription should not be billed yet.'))

        # Check that the subscription is active
        assert subscription.active, _('This subscription is not active and should not be billed.')

    # Check that the subscription has a payment type
    assert subscription.payment_type or (subscription.payment_type_fk and subscription.payment_method_fk), _(
        "The subscription has no payment type, it can't be billed"
    )

    # Check that the subscription's next billing is smaller than or equal to end date if it has it
    if subscription.end_date:
        error_msg = _("This subscription has an end date greater than its next billing")
        assert subscription.next_billing <= subscription.end_date, error_msg

    # We need to get all the subscription data
    billing_data = subscription.get_billing_data_by_priority()
    err_msg = f"Subscription {subscription.id} for contact {subscription.contact.id}"
    err_msg += f" (with {subscription.get_product_count()} products)"

    if not billing_data or not billing_data.get("address"):
        raise Exception(f"{err_msg}, requires an address to be billed.")

    if billing_data and require_route_for_billing:
        if billing_data["route"] is None:
            raise Exception(f"{err_msg}, requires a route to be billed.")

        elif billing_data["route"] in exclude_routes_from_billing_list:
            raise Exception(f"{err_msg}, can't be billed since it's on route {billing_data['route']}.")

    product_summary = subscription.product_summary(with_pauses=True)

    # Calculate price and get invoice items
    if subscription.type == "C" and subscription.override_price:
        amount = subscription.override_price
        invoice_items = create_invoiceitem_for_corporate_subscription(subscription=subscription)
    else:
        amount, invoice_items = calc_price_from_products(
            product_summary,
            subscription.frequency,
            debug_id=f"subscription_{subscription.id}",
            create_items=True,
            subscription=subscription,
        )

    # Handle envelope price if needed
    if envelope_price and SubscriptionProduct.objects.filter(subscription=subscription, has_envelope=1).exists():
        products_with_envelope_count = SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1
        ).count()
        envelope_amount = products_with_envelope_count * envelope_price * subscription.frequency
        envelope_item = InvoiceItem(description=_('Envelope'), amount=envelope_amount, subscription=subscription)
        invoice_items.append(envelope_item)
        amount += envelope_amount

    overdue_date = billing_date + timedelta(int(dpp))
    service_from = subscription.next_billing
    # Check if the subscription has a balance
    if subscription.balance and subscription.balance != 0:
        balance_amount = abs(subscription.balance)
        balance_item = InvoiceItem(
            description=_('Balance' if subscription.balance > 0 else 'Balance owed'),
            type='D' if subscription.balance > 0 else 'R',
            amount=min(balance_amount, amount) if subscription.balance > 0 else balance_amount,
            type_dr=1,
        )
        amount += (-1 if subscription.balance > 0 else 1) * float(balance_item.amount)
        invoice_items.append(balance_item)

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
                payment_type_fk=subscription.payment_type_fk,
                payment_method_fk=subscription.payment_method_fk,
                payment_reference=payment_reference,
            )

            # Add all invoice items to the invoice
            for item in invoice_items:
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

        # Subscription balance needs to be updated if there's a balance item
        if subscription.balance:
            if subscription.balance > 0 and balance_item:
                subscription.balance = Decimal(subscription.balance) - Decimal(balance_item.amount)
            if subscription.balance <= 0:
                subscription.balance = None

        # Update subscription billing date. If force_by_date is True, we will use the billing_date_override.
        if force_by_date and billing_date_override:
            subscription.next_billing = billing_date_override
        else:
            subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
                months=subscription.frequency
            )
        subscription.save()

        assert amount > 0, _("This subscription wasn't billed since amount is not greater than 0")

    except Exception as e:
        raise
        raise Exception(f"Contact {subscription.contact.id} Subscription {subscription.id}: {e}")

    return invoice
