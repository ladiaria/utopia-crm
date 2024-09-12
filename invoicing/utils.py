from invoicing.models import MercadoPagoData
from django.conf import settings
import mercadopago
from datetime import date


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
