# import require method from django
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from core.models import Contact
from support.models import Issue


@require_POST
@csrf_exempt
def create_issue_api(request):
    """
    Description: Create a new issue.
    """
    api_key = request.POST.get('api_key')
    if not hasattr(settings, 'CRM_API_KEY'):
        return HttpResponseBadRequest(_("Not properly configured"))
    if not api_key:
        return HttpResponseForbidden()
    if api_key != settings.CRM_API_KEY:
        return HttpResponseForbidden()

    # create the issue
    contact_id = request.POST.get('contact_id')
    sub_category = request.POST.get('sub_category')
    notes = request.POST.get('notes')
    
    if not contact_id or not sub_category or not notes:
        return HttpResponseBadRequest(_("Missing parameters"))
    
    if Contact.objects.filter(id=contact_id).exists():
        try:
            issue = Issue.create_issue(contact_id, sub_category, notes)
            issue.save()
            return JsonResponse(
                {"issue_id": issue.id}, status=201
            )
        except Exception as e:
            return HttpResponseBadRequest(_(f"Error creating the issue: {e}"))
