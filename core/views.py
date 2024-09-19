# coding: utf-8
from rest_framework.decorators import api_view, permission_classes
from rest_framework_api_key.permissions import HasAPIKey

from django.db import IntegrityError

from django.http import (
    JsonResponse,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponseServerError,
    HttpResponseNotFound,
)
from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required

from .models import Contact, MailtrainList, update_customer
from .admin import contact_is_safe_to_delete
from .utils import (
    get_emails_from_mailtrain_list,
    get_mailtrain_lists,
    subscribe_email_to_mailtrain_list,
    delete_email_from_mailtrain_list,
    manage_mailtrain_subscription,
    process_invoice_request,
    api_view_auth_decorator,
)


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


@api_view(['POST'])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def contact_by_emailprefix(request):
    """
    Returns a JSON with contact_id and email, only if an exact one contact has an email starting with the given string.
    The prefix is received in the email_prefix data var and must contain more than 1 char and end with "@".
    """
    email_prefix = request.POST.get("email_prefix", "")
    if len(email_prefix) < 2 or not email_prefix.endswith("@"):
        return HttpResponseBadRequest()
    else:
        matches = Contact.objects.filter(email__startswith=email_prefix)
        if matches.count() != 1:
            return HttpResponseNotFound()
        else:
            c = matches[0]
            return JsonResponse({"contact_id": c.id, "email": c.email})


@api_view(['POST', "PUT", "DELETE"])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def contact_api(request):
    """
    Delete, update or create a contact. Sets updatefromweb flag to the contact to avoid ws loop.
    """
    try:
        contact_id = request.data.get("contact_id", 0)
        mail = request.data.get("email")
        newmail = request.data.get("newemail")
        field = request.data.get("field")
        value = request.data.get("value")
    except AttributeError:
        return HttpResponseBadRequest()

    try:
        id_contact = None
        c = Contact.objects.get(pk=contact_id)
        if request.method == "DELETE":
            if contact_is_safe_to_delete(c):
                c.delete()
            else:
                return HttpResponseForbidden()
        else:
            update_customer(c, newmail, field, value)
            id_contact = c.id
    except Contact.DoesNotExist:
        if mail:
            try:
                contact = Contact.objects.get(email=mail)
                if request.method == "DELETE":
                    if contact_is_safe_to_delete(contact):
                        contact.delete()
                    else:
                        return HttpResponseForbidden()
                else:
                    update_customer(contact, newmail, field, value)
                    id_contact = contact.id
            except Contact.DoesNotExist:
                if request.method == "POST":  # create
                    new_contact = Contact()
                    new_contact.name = request.data.get("name")
                    new_contact.updatefromweb = True
                    new_contact.save()
                    update_customer(new_contact, mail, field, value)
                    id_contact = new_contact.id
            except (Contact.MultipleObjectsReturned, IntegrityError) as m_ie_exc:
                # TODO Notificar por mail a los managers
                return HttpResponseBadRequest(m_ie_exc)
    except IntegrityError as ie_exc:
        # TODO Notificar por mail a los managers
        return HttpResponseBadRequest(ie_exc)
    return JsonResponse({"contact_id": id_contact}, content_type="application/json")


@api_view(["GET"])
@permission_classes([HasAPIKey])
def contact_exists(request):
    if request.method == "GET":
        contact_id = request.GET.get('contact_id')
        email = request.GET.get('email')
        if contact_id:
            exists = Contact.objects.filter(pk=contact_id).exists()
        elif email:
            exists = Contact.objects.filter(email=email).exists()
        else:
            return JsonResponse({'error': 'Either contact_id or email parameter is required'}, status=400)

        return JsonResponse({'exists': exists})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def search_contacts_htmx(request, name="contact"):

    """
    View to handle asynchronous contact search requests, to be used with HTMX.

    Args:
    - `request`: Django HttpRequest object.

    Expected GET Parameters:
    - `q` (optional): Search term for filtering contacts.
    - `user_id` (optional): User ID to filter contacts by user (current user by default).

    Returns an html with a select dropdown with the filtered contacts with a limit of 100 results.
    """
    if request.GET:
        q = request.GET.get("contact_id")
        contacts = get_list_or_404(Contact, pk__icontains=q)
        # limit this only to the first 100 results
        contacts = contacts[:100]
        context = {'contacts': contacts, 'name': name}
        return render(request, "partials/search_contacts_results.html", context)
    else:
        return HttpResponse()


@never_cache
@api_view(['GET'])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def get_mailtrain_list_subscribed_emails(request, list_id):
    """
    Returns a JSON object containing the email addresses of all subscribers in a Mailtrain list having status set to
    "Subscribed".

    Returns:
        dict: A JSON object with a list of email addresses.

    Example:
        {
            "subscribed_emails": [
                "email1@example.com",
                "email2@example.com",
                ...
            ]
        }
    """
    return JsonResponse({"subscribed_emails": get_emails_from_mailtrain_list(list_id, 1)})


@api_view(['POST'])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def mailtrain_lists(request):
    """
    Retrieve the lists that the user with :email (in POST data) has subscribed to.
    """
    email = request.POST.get("email", None)
    if not email:
        return JsonResponse({"status": "error", "message": "Email is required."}, status=400)
    result = get_mailtrain_lists(email)
    return JsonResponse({"lists": result})


@api_view(['POST', "DELETE"])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def mailtrain_list_subscription(request):
    """
    View to handle adding/remove an email to/from a mailtrain list.

    Args:
    - `request`: Django HttpRequest object.

    Expected "data" Parameters:
    - `email`: Email to be added/removed.
    - `list_id`: ID of the mailtrain list.

    Returns a JSON response with the result of the operation.
    """
    email = request.data.get("email", None)
    list_id = request.data.get("list_id", None)
    if not email or not list_id:
        return JsonResponse({"status": "error", "message": "Both email and list_id are required."}, status=400)

    action = "subscribe" if request.method == "POST" else "unsubscribe"  # DELETE method is used for unsubscribing

    try:
        result = manage_mailtrain_subscription(email, list_id, action=action)
        return HttpResponse(result, content_type="application/json")
    except ValueError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@staff_member_required
def toggle_mailtrain_subscription(request, contact_id: int, cid: str) -> HttpResponse:
    """For internal use only. Toggles the subscription of a contact to a Mailtrain list.

    Args:
        request (HttpRequest): The request object.
        contact_id (int): The ID of the contact.
        cid (str): The ID of the Mailtrain list. It's found in the ID column in the Mailtrain lists page.

    Returns:
        HttpResponse: A redirect response to the previous page.
    """
    mailtrain_list_obj = get_object_or_404(MailtrainList, cid=cid)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    contact_mailtrain_lists = get_mailtrain_lists(contact_obj.email)
    if cid in contact_mailtrain_lists:
        delete_email_from_mailtrain_list(contact_obj.email, cid)
        messages.success(request, f"Se ha eliminado el contacto {contact_obj.email} de la lista {mailtrain_list_obj}")
    else:
        subscribe_email_to_mailtrain_list(contact_obj.email, cid)
        messages.success(request, f"Se ha agregado el contacto {contact_obj.email} a la lista {mailtrain_list_obj}")
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@api_view(['POST'])
@api_view_auth_decorator
@permission_classes([HasAPIKey])
def create_oneshot_invoice_from_web(request):
    """
    Handles the creation of a one-time invoice for a user purchasing one or more products through the website.

    This view processes a POST request to create an invoice for a specified set of products,
    using the provided user information and payment details. The invoice is created for a
    single transaction, typically processed via an online payment gateway.

    Expected POST Data:
    - `product_slugs` (str): A comma-separated list of product slugs representing the products to be purchased.
    - `email` (str): The email address of the user making the purchase. This field is required.
    - `phone` (str, optional): The phone number of the user. If not provided, defaults to an empty string.
    - `name` (str, optional): The name of the user. If not provided, defaults to an empty string.
    - `payment_reference` (str, optional):
      A reference identifier for the payment transaction. Defaults to an empty string.
    - `payment_type` (str, optional):
      The type of payment used (e.g., credit card, PayPal). Defaults to an empty string.

    Process:
    1. Validates the presence of the required `email` field.
    2. Calls the `process_invoice_request` function to handle the core invoice creation logic:
        - Creates or selects a contact based on the provided email, name, and phone.
        - Retrieves the products associated with the provided slugs.
        - Creates a single invoice for the user with the specified products and payment details.
    3. Returns a JSON response containing the created `invoice_id` and `contact_id`.

    Responses:
    - `JsonResponse`: On success, returns a JSON object with the `invoice_id` and `contact_id`.
    - `HttpResponseBadRequest`:
      Returns an error if the required `email` is missing or if the product slugs are invalid.
    - `HttpResponseServerError`:
      Returns an error with the exception message if an unexpected issue occurs during processing.

    Permissions:
    - Requires a valid API key (`HasAPIKey`) to access this view.
    """
    try:
        product_slugs = request.data.get("product_slugs", "")
        email = request.data.get("email", "").strip()
        phone = request.data.get("phone", "")
        name = request.data.get("name", "")
        payment_reference = request.data.get("payment_reference", "")
        payment_type = request.data.get("payment_type", "")

        if not email:
            return HttpResponseBadRequest("Email requerido")

        response_data = process_invoice_request(product_slugs, email, phone, name, payment_reference, payment_type)
        return JsonResponse(response_data)

    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    except Exception as exc:
        return HttpResponseServerError(str(exc))
