# coding=utf-8
import requests
from requests.auth import HTTPBasicAuth
from luhn import verify

from django.contrib.auth.models import User
from django.conf import settings
from django.forms import ValidationError

dnames = ('lunes', 'martes', 'miercoles', 'jueves', 'viernes')
cardtypes = {
    '4': 'Visa',
    '52': 'Master',
    '53': 'Master',
    '54': 'Oca',
    '6': 'Cabal'
}


class DummyStaffRequest(object):
    def __init__(self, staffusername):
        self.user = User.objects.get(username=staffusername)


def space_join(first_part, second_part):
    if first_part and second_part:
        return first_part + u' ' + second_part
    else:
        return first_part or second_part or u''


def validarNumeroTarjeta(number, cardtype=None):
    return  # BYPASS MIGRACION
    if number and not number.isdigit():
        raise ValidationError("Solo se admiten digitos")
    if number and len(number) != 16:
        raise ValidationError("El largo debe ser de 16 digitos")
    if number and number[:4] != '5898' and (
            verify(number) is False and cardtype != 'O'):
        raise ValidationError(u"El número de tarjeta es inválido")
    if number and cardtype:
        if number[:1] == '4' and cardtype != 'V':
            raise ValidationError(
                u"El número de tarjeta ingresado no corresponde con el tipo"
                u" (las tarjetas que inician con 4 son Visa)")
        elif number[:4] in ('5429', '5898') and cardtype != 'O':
            raise ValidationError(
                u"El número de tarjeta ingresado no corresponde con el tipo"
                u" (los cuatro primeros números corresponden a OCA)")
        elif number[:4] in ('5896', '6042') and cardtype != 'C':
            raise ValidationError(
                u"El número de tarjeta ingresado no corresponde con el tipo"
                u" (los cuatro primeros números corresponden a Cabal)")
        elif (
            number[:2] in ('51', '52', '53', '54', '55') and
                cardtype not in ('M', 'LD') and number[:4] != '5429'):
            raise ValidationError(
                u"El número de tarjeta ingresado no corresponde con el tipo"
                u" (los dos primeros números corresponden a Mastercard)")


def updatewebuser(id, email, newemail, field, value):
    """
    Esta es la funcion que hace el POST hacia la web, siempre recibe el mail
    actual y el nuevo (el que se esta actualizando) porque son necesarios para
    buscar la ficha en la web.
    Ademas recibe el nombre de campo y el nuevo valor actualizado, son utiles
    cuando se quiere sincronizar otros campos.
    ATENCION: No se sincroniza cuando el nuevo valor del campo es None
    """
    data = {
        "costumer_id": id, "email": email, "newemail": newemail,
        "field": field, "value": value,
        "ldsocial_api_key": getattr(settings, 'LDSOCIAL_API_KEY')}
    post_kwargs = {
        'data': data, 'timeout': (5, 20),
        'verify': settings.WEB_UPDATE_USER_VERIFY_SSL}
    http_basic_auth = getattr(settings, 'WEB_UPDATE_HTTP_BASIC_AUTH', None)
    if http_basic_auth:
        post_kwargs['auth'] = HTTPBasicAuth(*http_basic_auth)
    r = requests.post(settings.WEB_UPDATE_USER_URI, **post_kwargs)
    r.raise_for_status()


def validateEmailOnWeb(id, email):
    data = {
        "costumer_id": id,
        "email": email,
        "ldsocial_api_key": getattr(settings, 'LDSOCIAL_API_KEY')}
    post_kwargs = {
        'data': data, 'timeout': (5, 20),
        'verify': settings.WEB_UPDATE_USER_VERIFY_SSL}
    http_basic_auth = getattr(settings, 'WEB_UPDATE_HTTP_BASIC_AUTH', None)
    if http_basic_auth:
        post_kwargs['auth'] = HTTPBasicAuth(*http_basic_auth)
    try:
        r = requests.post(settings.WEB_EMAIL_CHECK_URI, **post_kwargs)
    except requests.exceptions.ReadTimeout:
        return u"TIMEOUT"
    else:
        return r.content
