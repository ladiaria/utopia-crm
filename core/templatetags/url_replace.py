# coding=utf-8
# CREDITS: Taken from Loud Noise Inc.'s Medium webpage
# https://medium.com/@sumitlni/paginate-properly-please-93e7ca776432
from django import template

register = template.Library()


@register.simple_tag
def url_replace(request, field, value):
    query_string = request.GET.copy()
    query_string[field] = value
    return query_string.urlencode()
