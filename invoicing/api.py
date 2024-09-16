from datetime import date
import json
import traceback
from time import sleep

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import mail_managers
from django.db import DataError
from django.http import HttpResponse, HttpResponseBadRequest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import HasAPIKey

from core.models import Contact
from invoicing.models import Subscription
from invoicing.views import bill_subscription
from .utils import contact_update_mp_wrapper, create_mp_subscription_for_contact, mercadopago_debit


@api_view(['POST'])
@permission_classes([HasAPIKey])
def createinvoicefromweb(request):
    """
    This is the entry point for the webhook from MercadoPago.
    """

    def error_handler(error_msg, error_exc=None):
        if error_exc:
            mail_managers("createinvoicefromweb error", error_exc, True)
        return HttpResponseBadRequest(error_msg)

    required_params = [
        "product_slug",
        "mp_payment_method_id",
        "mp_identification_type",
        "identification_number",
        "mp_customer_id",
        "mp_card_id",
        "expiration_month",
    ]
    if not all(param in request.POST for param in required_params):
        return error_handler("Parámetros requeridos faltantes")

    sleep_secs = getattr(settings, "WEB_UPDATE_MP_FORCE_SLEEP", 0)
    if sleep_secs:
        sleep(sleep_secs)

    subscription = None
    try:
        product_slug = request.POST["product_slug"]
        mp_payment_method_id = request.POST["mp_payment_method_id"]
        mp_identification_type = request.POST["mp_identification_type"]
        identification_number = request.POST["identification_number"]
        card_issuer = request.POST["card_issuer"]
        mp_customer_id = request.POST["mp_customer_id"]
        mp_card_id = request.POST["mp_card_id"]
        expiration_month = request.POST["expiration_month"]
        expiration_year = request.POST["expiration_year"]
    except KeyError as ke:
        return error_handler("Parámetro '%s' requerido" % ke.args[0])

    if not product_slug:
        return error_handler("Product slug is required")

    customer_email = request.POST.get("customer_email").strip()
    customer_telephone = request.POST.get("customer_telephone")
    customer_address = request.POST.get("customer_address")
    customer_city = request.POST.get("customer_city")
    customer_province = request.POST.get("customer_province")

    try:
        contact = Contact.objects.get(email=customer_email)

        func_result = contact_update_mp_wrapper(
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
            mp_payment_method_id=mp_payment_method_id,
            mp_identification_type=mp_identification_type,
            identification_number=identification_number,
        )

        if type(func_result) is Subscription:
            subscription = func_result
        else:
            return error_handler(*func_result)

    except Contact.DoesNotExist:
        # try to get by document
        try:
            contact = Contact.objects.get(id_document=identification_number)

            func_result = contact_update_mp_wrapper(
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
                mp_payment_method_id=mp_payment_method_id,
                mp_identification_type=mp_identification_type,
            )

            if type(func_result) is Subscription:
                subscription = func_result
            else:
                return error_handler(*func_result)

        except Contact.DoesNotExist:
            try:
                # TODO: analizar si esto no deberia estar en una transaction
                contact = Contact.objects.create(
                    id_document=identification_number,
                    name=request.POST["customer_name"],
                    last_name=request.POST["customer_last_name"],
                    email=customer_email,
                    subtype_id=getattr(settings, "WEB_UPDATE_MP_SUBTIPO_ID", None),
                    phone=customer_telephone,
                )
                subscription = create_mp_subscription_for_contact(
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
                )
            except KeyError as exc:
                return error_handler(("Nombre de cliente requerido", exc))

        except (ValidationError, DataError) as exc:
            return error_handler(("Error de validación de datos de cliente", exc))

        except Contact.MultipleObjectsReturned as exc:
            return error_handler(("Más de un cliente con ese documento", exc))

    except Contact.MultipleObjectsReturned as exc:
        return error_handler(("Más de un cliente con ese email", exc))

    invoice, bill_exc = None, None
    try:
        invoice = bill_subscription(subscription.id, date.today(), 30)
        mercadopago_debit(invoice)
    except Exception as exc:
        bill_exc = exc
        if settings.DEBUG:
            traceback.print_exc()
    if not invoice or not (invoice.paid or invoice.debited):
        if subscription:
            subscription.status = "ER"  # Pausa
            subscription.active = False
            subscription.save()
    if invoice:
        response_content = {
            "invoice_id": invoice.id,
            "paid": invoice.paid or invoice.debited,
            "contact_id": contact.id,
        }
        if subscription and subscription.active:
            response_content["plan_id"] = [
                (subscription.type, list(subscription.products.filter(type="S").values_list("slug", flat=True)))
            ]
            if contact.offer_default_newsletters_condition():
                response_content["nl_added"] = contact.add_default_newsletters()
        return HttpResponse(json.dumps(response_content), content_type="application/json")
    else:
        return error_handler("Could not bill", bill_exc)
