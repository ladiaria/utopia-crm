# coding=utf-8
from django import template
from django.conf import settings

register = template.Library()


class Sip(template.Node):
    """
    Funciona de la siguiente forma: {% sip objeto.atributo %}
    Donde objeto es una variable del contexto y atributo es un atributo de
    dicha variable conteniendo un numero telefonico.
    Seria facil modificar luego para aceptar tambien numeros como texto, etc
    """
    def __init__(self, token):
        self.obj, self.attr = token.split('.')

    def render(self, context):
        number = getattr(context[self.obj], self.attr)
        return '%s  <a class="btn btn-sm btn-primary" href="sip://%s%s">llamar</a>' % (number, getattr(
          settings, 'SIP_DIALOUT', ''), number.split('/')[0]) if number else ''


@register.tag(name='sip')
def do_sip_tag(parser, token):
    return Sip(token.contents.split()[1])
