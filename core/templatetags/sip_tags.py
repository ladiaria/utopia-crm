# coding=utf-8
from phonenumbers import normalize_digits_only

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter(name='national_number')
def national_number(value):
    """
    @param value: phonenumber_field.phonenumber.PhoneNumber instance
    @return: national number
    """
    return normalize_digits_only(value.as_national) if value else ''


@register.filter(name='sip')
def sip_filter(value):
    """
    @param value: phonenumber_field.phonenumber.PhoneNumber instance
    @return: html with a button to call the phone number using SIP
    """
    # TODO: think what to do if value is not a valid phone number
    try:
        normalized_number = national_number(value)
    except AttributeError:
        normalized_number = value
    return mark_safe(
        '%s <a class="button btn-sm btn-primary" href="sip://%s%s"><i class="fas fa-phone"></i> Llamar</a>' % (
            normalized_number, getattr(settings, 'SIP_DIALOUT', ''), normalized_number
        ) if value else ''
    )
