# coding=utf-8
from django import template
from django.conf import settings

register = template.Library()


class Setting(template.Node):

    def __init__(self, name):
        self.name = name

    def render(self, context):
        return getattr(settings, self.name)


@register.tag(name='setting')
def do_setting_tag(parser, token):
    return Setting(token.contents.split()[1])
