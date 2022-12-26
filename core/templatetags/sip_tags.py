# coding=utf-8
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='sip')
def sip_filter(value):
    return mark_safe('%s <a class="button btn-sm btn-primary" href="sip://%s%s"><i class="fas fa-phone"></i> Llamar</a>' % (
        value, getattr(settings, 'SIP_DIALOUT', ''), value.split('/')[0]) if value else '')
