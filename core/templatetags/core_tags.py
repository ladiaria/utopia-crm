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
