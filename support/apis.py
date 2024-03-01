# import require method from django
from django.views.decorators.http import require_POST
from django.http import HttpResponseNotAllowed, HttpResponseBadRequest, HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import Contact
from support.models import Issue



@require_POST
def create_issue_api(request):
    """
    Description: Create a new issue.
    """
    api_key = request.POST.get('api_key')
    if not hasattr(settings, 'API_KEY'):
        return HttpResponseBadRequest(_("Not properly configured"))
    if not api_key:
        return HttpResponseForbidden()
    if api_key != settings.API_KEY:
        return HttpResponseForbidden()

    # create the issue
    contact_id = request.POST.get('contact_id')
    subcategory = request.POST.get('subcategory')
    description = request.POST.get('description')
    
    if not contact_id or not subcategory or not description:
        return HttpResponseBadRequest(_("Missing parameters"))
    
    if Contact.objects.filter(id=contact_id).exists():
        try:
            issue = Issue.create_issue(contact_id, subcategory, description)
            issue.save()
            return HttpResponse(status_code=201)
        except Exception as e:
            return HttpResponseBadRequest(_(f"Error creating the issue: {e}"))
