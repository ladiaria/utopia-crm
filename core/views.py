# coding: utf-8
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render, get_list_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from core.models import Contact
from core.utils import subscribe_email_to_mailtrain_list


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


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
    if request.POST:
        if not request.POST.get("api_key", None):
            return HttpResponseForbidden()
        if request.POST["api_key"] != getattr(settings, "CRM_API_KEY", None):
            return HttpResponseForbidden()
        email = request.POST.get("email")
        list_id = request.POST.get("list_id")
        result = subscribe_email_to_mailtrain_list(email, list_id)
        return HttpResponse(result, content_type="application/json")
    else:
        return HttpResponseNotFound()
