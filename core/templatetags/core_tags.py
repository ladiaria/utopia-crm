from django import template

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
    if user.groups.filter(name=group_name).exists():
        return True
    return False
