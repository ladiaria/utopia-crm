# coding: utf-8
from rest_framework.decorators import api_view, permission_classes
from rest_framework_api_key.permissions import HasAPIKey

from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden
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
)


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


@api_view(['POST', "PUT", "DELETE"])
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
        c = Contact.objects.get(pk=contact_id)
        if request.method == "DELETE":
            if contact_is_safe_to_delete(c):
                c.delete()
            else:
                return HttpResponseForbidden()
        else:
            update_customer(c, newmail, field, value)
    except Contact.DoesNotExist:
        if mail:
            try:
                c = Contact.objects.get(email=mail)
                if request.method == "DELETE":
                    if contact_is_safe_to_delete(c):
                        c.delete()
                    else:
                        return HttpResponseForbidden()
                else:
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
