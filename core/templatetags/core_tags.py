from django import template
from core.models import SubscriptionProduct
from django.template.loader_tags import do_include
from django.template.defaulttags import CommentNode

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


@register.filter('in_group')
def in_group(user, group_name):
    """
    TODO: Improve this using generic names with settings.
    """
    if user.is_superuser:
        return True
    if user.groups.filter(name="Admins").exists():
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False


@register.filter('get_address_id_from_subscription')
def get_address_id_from_subscription(subscription_id, product_slug):
    try:
        sp = SubscriptionProduct.objects.filter(
            subscription_id=subscription_id, product__slug=product_slug
        ).first()
        return sp.address.id
    except Exception:
        return ''


@register.tag('include_if_exists')
def do_include_maybe(parser, token):
    "Source: http://stackoverflow.com/a/18951166/15690"
    bits = token.split_contents()
    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            "%r tag takes at least one argument: "
            "the name of the template to be included." % bits[0])

    try:
        silent_node = do_include(parser, token)
    except template.TemplateDoesNotExist:
        # Django < 1.7
        return CommentNode()

    _orig_render = silent_node.render

    def wrapped_render(*args, **kwargs):
        try:
            return _orig_render(*args, **kwargs)
        except template.TemplateDoesNotExist:
            return CommentNode()
    silent_node.render = wrapped_render
    return silent_node
