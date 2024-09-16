from invoicing.models import MercadoPagoData
from django.conf import settings
import mercadopago
from datetime import date
from core.models import Address, Subscription, Product  # Updated import
from django.db import transaction
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext_lazy as _


def mercadopago_debit(invoice, debug=False):
    """
    Calls the MercadoPago API to send the payment. Generates the card token and register the payment.
    """
    if getattr(settings, "DISABLE_MERCADOPAGO", False):
        print("Mercadopago debit skipped by settings.")
        return

    # avoid duplicate charge if this invoice was already paid or debited
    if invoice.paid or invoice.debited:
        return

    # Get MercadoPago data for the contact
    try:
        mp_data = MercadoPagoData.objects.get(contact=invoice.contact)
    except MercadoPagoData.DoesNotExist:
        error_status = "MercadoPago data not found for this contact"
        _update_invoice_notes(invoice, error_status, debug)
        return

    # Get MercadoPago access token from settings with a fallback
    mp_access_token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not mp_access_token:
        error_status = "MercadoPago access token not found in settings"
        _update_invoice_notes(invoice, error_status, debug)
        return

    # Create a MercadoPago API instance
    sdk = mercadopago.SDK(mp_access_token)

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
    card_token_response = sdk.card_token().create(card_token_post_data).get("response")

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
            payment_response = sdk.payment().create(payment_data).get("response", {})
            payment_response_status = payment_response.get("status")

            # max attempts to resend the request if we get a 400 or 500 status (this happens frequently in test API)
            mp_max_attempts = getattr(settings, "MERCADOPAGO_API_MAX_ATTEMPTS", 10)
            mp_attempts = 0
            while payment_response_status in (400, 500) and mp_attempts < mp_max_attempts:
                payment_response = sdk.payment().create(payment_data).get("response", {})
                payment_response_status = payment_response.get("status")
                mp_attempts += 1

            if payment_response_status == "approved":
                invoice.debited, invoice.payment_date = True, date.today()
                invoice.payment_reference = f"MP-{payment_response['id']}"
                if invoice.notes and "MercadoPago - Pago no aprobado" in invoice.notes:
                    invoice.notes = invoice.notes + f"\n{date.today()} MercadoPago - Pago procesado correctamente"
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
    invoice.notes += f"{date.today()} {error_status}"
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

    # Create or update MercadoPagoData
    mp_data, created = MercadoPagoData.objects.update_or_create(
        contact=contact,
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

    subscription = Subscription.objects.create(
        contact=contact,
        type="N",  # The subscription will be Normal
        status="OK",  # Can be switched to awaiting payment later
        payment_type="M",  # Mercadopago
        send_bill_copy_by_email=True,
        start_date=start_date or date.today(),
        next_billing=start_date or date.today(),
        end_date=None,
    )

    # We should add the products to the subscription
    product = Product.objects.get(slug=product_slug)
    subscription.add_product(product, new_address)

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
        start_date = date.today()

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
    two_years_ago = date.today() + relativedelta(years=-2)
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
