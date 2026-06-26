"""
Proxy views that let the CRM read and edit a contact's newsletters on demand against the CMS (the source
of truth), instead of relying on the local SubscriptionNewsletter mirror. The browser talks to the CRM
(htmx); the CRM talks to the CMS with the API key it already holds server-side via cms_rest_api_request.
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect

from core.models import Contact
from core.utils import cms_rest_api_request


def _fetch_cms_newsletters(contact):
    """
    Read the contact's newsletters from the CMS. Returns the parsed dict (with keys exists/publication/
    category) or None when the CMS is unreachable/errored (so the templates can show an error state).
    """
    result = cms_rest_api_request(
        "newsletters_read",
        settings.WEB_NEWSLETTERS_READ_URI,
        {"contact_id": contact.id, "email": contact.email or ""},
        method="POST",
    )
    return result if isinstance(result, dict) else None


@staff_member_required
def contact_newsletters_overview(request, contact_id):
    """Read-only partial for the contact overview card."""
    if request.headers.get("HX-Request") != "true":
        return HttpResponseNotFound()
    contact = get_object_or_404(Contact, pk=contact_id)
    nl_data = _fetch_cms_newsletters(contact)
    pub_subscribed, cat_subscribed = [], []
    if isinstance(nl_data, dict) and nl_data.get("exists"):
        pub_subscribed = [i for i in nl_data.get("publication", []) if i.get("subscribed")]
        cat_subscribed = [i for i in nl_data.get("category", []) if i.get("subscribed")]
    return render(
        request,
        "contact_detail/htmx/_newsletters_htmx.html",
        {
            "contact": contact,
            "nl_data": nl_data,
            "pub_subscribed": pub_subscribed,
            "cat_subscribed": cat_subscribed,
        },
    )


@staff_member_required
def contact_newsletters_form(request, contact_id):
    """Editable partial (checkboxes by type) for the edit_contact Newsletters tab."""
    if request.headers.get("HX-Request") != "true":
        return HttpResponseNotFound()
    contact = get_object_or_404(Contact, pk=contact_id)
    return render(
        request,
        "create_contact/htmx/_newsletters_form_htmx.html",
        {"contact": contact, "nl_data": _fetch_cms_newsletters(contact)},
    )


@staff_member_required
@csrf_protect
def contact_newsletter_toggle(request, contact_id):
    """
    Persist a single newsletter change straight to the CMS (delta, non-destructive). Independent of the
    main contact form submit, so it never goes through Contact.save() nor the local mirror.
    """
    if request.method != "POST" or request.headers.get("HX-Request") != "true":
        return HttpResponseNotFound()
    contact = get_object_or_404(Contact, pk=contact_id)
    # Namespaced keys (nl_*) sent via hx-vals, so they never collide with the contact form fields (e.g.
    # the contact's own "name") that may be serialized along with the request.
    nl_type = request.POST.get("nl_type")
    slug = request.POST.get("nl_slug")
    name = request.POST.get("nl_name") or slug
    action = "subscribe" if request.POST.get("nl_subscribed") else "unsubscribe"
    if settings.DEBUG:
        print(f"DEBUG: newsletter_toggle contact={contact_id} {action} {nl_type}:{slug}")

    result = cms_rest_api_request(
        "newsletter_update",
        settings.WEB_NEWSLETTERS_UPDATE_URI,
        {
            "contact_id": contact.id,
            "email": contact.email or "",
            "nl_type": nl_type,
            "slug": slug,
            "action": action,
        },
        method="POST",
    )
    ok = isinstance(result, dict) and result.get("exists")
    if settings.DEBUG:
        print(f"DEBUG: newsletter_toggle result ok={ok} cms={result}")
    subscribed = bool(result.get("subscribed")) if ok else (action != "subscribe")
    item = {"slug": slug, "name": name, "subscribed": subscribed}
    return render(
        request,
        "create_contact/htmx/_newsletter_item.html",
        {"contact": contact, "item": item, "nl_type": nl_type, "error": not ok},
    )
