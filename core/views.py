# coding: utf-8
from rest_framework.decorators import api_view, permission_classes
from rest_framework_api_key.permissions import HasAPIKey

from django.conf import settings
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, get_list_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.validators import validate_email

from .models import Contact, update_customer
from .utils import subscribe_email_to_mailtrain_list


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


@api_view(['POST'])
@permission_classes([HasAPIKey])
def updateuserfromweb(request):
    """
    Updates a contact. Sets updatefromweb flag to the contact to avoid ws loop.
    """
    # TODO: change name to update_contact_api (or similiar)
    try:
        contact_id = request.POST.get("contact_id", 0)
        mail = request.POST.get("email")
        newmail = request.POST.get("newemail")
        field = request.POST.get("field")
        value = request.POST.get("value")
    except KeyError:
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
                pass
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


@require_POST
@csrf_exempt
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
    if not request.POST.get("api_key", None):
        return HttpResponseForbidden()
    if request.POST["api_key"] != getattr(settings, "CRM_API_KEY", None):
        return HttpResponseForbidden()
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
