# coding: utf-8
from rest_framework.decorators import api_view, permission_classes
from rest_framework_api_key.permissions import HasAPIKey

from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_list_or_404
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email

from .models import Contact, update_customer
from .utils import subscribe_email_to_mailtrain_list, get_emails_from_mailtrain_list


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


@api_view(['POST', "PUT"])
@permission_classes([HasAPIKey])
def updateuserfromweb(request):
    """
    Updates or Inserts a contact. Sets updatefromweb flag to the contact to avoid ws loop.
    """
    # TODO: change name to update_contact_api (or similiar)
    try:
        contact_id = request.data.get("contact_id", 0)
        mail = request.data.get("email")
        newmail = request.data.get("newemail")
        field = request.data.get("field")
        value = request.data.get("value")
    except AttributeError:
        return HttpResponseBadRequest()

    try:
        c = Contact.objects.get(pk=contact_id)
        update_customer(c, newmail, field, value)
    except Contact.DoesNotExist:
        if mail:
            try:
                c = Contact.objects.get(email=mail)
                update_customer(c, newmail, field, value)
            except Contact.DoesNotExist:
                if request.method == "POST":  # create
                    c = Contact.objects.create(name=request.data.get("name"))
                    update_customer(c, mail, field, value)
            except (Contact.MultipleObjectsReturned, IntegrityError) as m_ie_exc:
                # TODO Notificar por mail a los managers
                return HttpResponseBadRequest(m_ie_exc)
    except IntegrityError as ie_exc:
        # TODO Notificar por mail a los managers
        return HttpResponseBadRequest(ie_exc)
    return HttpResponse("OK", content_type="application/json")


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
@permission_classes([HasAPIKey])
def add_email_to_mailtrain_list(request):
    """
    View to handle adding emails to a mailtrain list.

    Args:
    - `request`: Django HttpRequest object.

    Expected POST Parameters:
    - `email`: Email to be added to the list.
    - `list_id`: ID of the mailtrain list to add the email to.
    - `api_key`: Our API key to use for the operation.

    Returns a JSON response with the result of the operation.
    """
    email = request.POST.get("email", None)
    list_id = request.POST.get("list_id", None)
    if not email:
        return JsonResponse({"status": "error", "message": "Email is required."}, status=400)
    if not list_id:
        return JsonResponse({"status": "error", "message": "List ID is required."}, status=400)
    try:
        validate_email(email)
    except Exception:
        return JsonResponse({"status": "error", "message": f"{email} is not a valid email address."}, status=400)
    result = subscribe_email_to_mailtrain_list(email, list_id)
    return HttpResponse(result, content_type="application/json")
