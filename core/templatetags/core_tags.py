import re

from phonenumbers import region_code_for_number
from phonenumber_field.phonenumber import PhoneNumber

from django import template
from django.template.loader_tags import do_include
from django.conf import settings
from django.utils.html import conditional_escape, format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone

from core.models import SubscriptionProduct

register = template.Library()


@register.simple_tag
def call_method(obj, method_name, *args):
    """
    Get any method from any object on a template. Pass arguments if necessary.

    Syntax: {% call_method object 'method' args %}

    Example of usage:

    {% call_method form_subscription 'get_message_for_product' product.id %}
    """
    method = getattr(obj, method_name)
    return method(*args)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter(is_safe=True)
def in_group(user, group_name):
    if user.is_superuser:
        return True
    if user.groups.filter(name="Admins").exists():
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False


def foreign_region(value):
    """
    Region code of a valid phone number from outside PHONENUMBER_DEFAULT_REGION, None for local, invalid or empty
    numbers and for plain strings.
    """
    if not isinstance(value, PhoneNumber) or not value.is_valid():
        return None
    region = region_code_for_number(value)
    return None if region == getattr(settings, "PHONENUMBER_DEFAULT_REGION", None) else region


@register.filter
def phone_display(value):
    """
    Numbers from PHONENUMBER_DEFAULT_REGION are shown in national format, as before. The rest are shown in
    international format with their country flag: in national format a foreign number loses its country code and
    reads as a local one.
    """
    if not value:
        return ""
    region = foreign_region(value)
    if region is None:
        return value.as_national
    return format_html(
        '{} <span class="flag-icon flag-icon-{}" title="{}"></span>', value.as_international, region.lower(), region
    )


@register.filter(is_safe=True)
def has_perm(user, perm):
    return user.has_perm(perm)


@register.filter(is_safe=True)
def in_group_exclusive(user, group_name):
    # Same as the previous one, but it doesn't check for the Admins group
    if user.is_superuser:
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False


@register.filter('get_address_id_from_subscription')
def get_address_id_from_subscription(subscription_id, product_slug):
    try:
        sp = SubscriptionProduct.objects.filter(subscription_id=subscription_id, product__slug=product_slug).first()
        return sp.address.id
    except Exception:
        return ''


@register.tag
def include_if_exists(parser, token):
    "Source: http://stackoverflow.com/a/18951166/15690"
    bits = token.split_contents()
    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            "%r tag takes at least one argument: " "the name of the template to be included." % bits[0]
        )

    silent_node = do_include(parser, token)

    _orig_render = silent_node.render

    def wrapped_render(*args, **kwargs):
        try:
            return _orig_render(*args, **kwargs)
        except template.TemplateDoesNotExist:
            return ""

    silent_node.render = wrapped_render
    return silent_node


@register.simple_tag
def show_unbilled_ad_purchase_orders():
    # This is primarily used in finances to show the number of unbilled ad purchase orders
    if 'advertisement' in settings.INSTALLED_APPS:
        from advertisement.models import AdPurchaseOrder

        orders = AdPurchaseOrder.objects.filter(billed=False).count()
        if orders == 0:
            return ""
        orders_span = f'<span class="badge badge-light">{orders}</span>'
        button_label = _('Unbilled Ad Purchase Orders')
        button_url = reverse('ad_purchase_order_list') + '?billed=False'
        html_button = f'<a href="{button_url}" class="btn btn-danger">{button_label} {orders_span}</a>'
        return mark_safe(html_button)
    else:
        return ""


@register.filter(is_safe=True)
def is_app_installed(app_name):
    # To check in a template if an app is installed
    return app_name in settings.INSTALLED_APPS


@register.simple_tag
def is_app_hidden(app_name):
    hidden_apps = getattr(settings, 'DISABLED_APPS', [])
    return app_name in hidden_apps


@register.simple_tag
def days_until(target_date):
    current_date = timezone.now().date()
    try:
        if current_date > target_date:
            return _("Expired")
    except Exception:
        return "-"

    delta = target_date - current_date

    msg = _('{days} days remaining').format(days=delta.days)
    return msg


@register.simple_tag
def pending_email_takeovers():
    """
    How many email takeover requests are waiting for a decision, for the sidebar badge.

    Returns the number so the template can render a real badge (and skip it at zero). Defensive on
    purpose: a badge is never a reason for a page not to render.
    """
    try:
        from core.models import EmailTakeoverRequest

        return EmailTakeoverRequest.objects.filter(status=EmailTakeoverRequest.PENDING).count()
    except Exception:
        return 0


@register.simple_tag
def pending_sales_records():
    """
    How many sales records are still waiting for a manager to validate them, for the sidebar badge.

    Validation lives on the subscription (``Subscription.validated``), not on the sales record, so
    this counts records whose subscription is still unvalidated. Same defensive shape as
    ``pending_email_takeovers``: a badge is never a reason for a page not to render.
    """
    try:
        from support.models import SalesRecord

        return SalesRecord.objects.filter(subscription__validated=False).count()
    except Exception:
        return 0


@register.filter(needs_autoescape=True)
def highlight(text, query, autoescape=True):
    """
    Wraps the case-insensitive matches of ``query`` in ``text`` with ``<mark>``. The text is split on the matches
    and every piece escaped on its own, so a match never lands inside an escaped entity.
    """
    text = text or ""
    escape = conditional_escape if autoescape else (lambda value: value)
    if not query:
        return escape(text)
    pieces = re.split(f"({re.escape(query)})", text, flags=re.IGNORECASE)
    # re.split with a capturing group leaves the matches at the odd positions
    return mark_safe(
        "".join(f"<mark>{escape(piece)}</mark>" if i % 2 else escape(piece) for i, piece in enumerate(pieces))
    )


ACTIVITY_TYPE_ICONS = {
    "S": "fas fa-bullhorn",
    "C": "fas fa-phone",
    "M": "fas fa-envelope",
    "L": "fas fa-link",
    "W": "fab fa-whatsapp",
    "E": "fas fa-calendar-check",
    "I": "fas fa-handshake",
    "N": "fas fa-sticky-note",
}
ACTIVITY_DIRECTION_COLORS = {"I": "bg-info", "O": "bg-primary", "N": "bg-gray", "R": "bg-warning"}
# Completed is the usual state, so it stays quiet and the others stand out
ACTIVITY_STATUS_BADGES = {"C": "badge-light", "P": "badge-warning", "D": "bg-orange", "E": "badge-danger"}


@register.filter
def activity_icon(activity):
    """
    CSS classes for the icon of an activity in a timeline: the icon tells the type, the color the direction.
    Activity types are configurable (``CUSTOM_ACTIVITY_TYPES``), so an unknown one gets a generic icon.
    """
    icon = ACTIVITY_TYPE_ICONS.get(activity.activity_type, "fas fa-circle")
    return f"{icon} {ACTIVITY_DIRECTION_COLORS.get(activity.direction, 'bg-secondary')}"


@register.filter
def activity_status_badge(activity):
    """CSS class for the status badge of an activity."""
    return ACTIVITY_STATUS_BADGES.get(activity.status, "badge-secondary")
