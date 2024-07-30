from django import template
from django.template.loader_tags import do_include
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.safestring import mark_safe

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
