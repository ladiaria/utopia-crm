# coding=utf-8
# @Author: Phu Hoang
# @Date:   2017-01-19 17:20:24
# @Last Modified by:   Phu Hoang
# @Last Modified time: 2017-01-19 18:57:18

from django import template

import re

from django.urls import reverse


class _Menu:
    parents = []
    children = []
    models_icon = {}

    def clear(self):
        self.parents = []
        self.children = []

    def add(self, label, link='', icon='', id_='', parent=''):

        if id_ == '':
            id_ = label

        if parent != '':
            child = {id_: {'label': label, 'link': link, 'icon': icon, 'children': []}}

            self.children.append(child)

            for idx, parent_item in enumerate(self.parents):

                if parent in parent_item:
                    self.parents[idx][parent]['children'].append(child)
                else:
                    for idx, child_item in enumerate(self.children):
                        if parent in child_item:
                            self.children[idx][parent]['children'].append(child)

        else:
            self.parents.append({id_: {'label': label, 'link': link, 'icon': icon, 'children': []}})

    def render(self, context, menus=None):
        menus = {} if menus is None else menus
        request = context['request']

        r = ''

        if len(menus) <= 0:
            # sorted(self.parents)
            menus = self.parents
            r = (
                '<li class="nav-item">'
                f'<a href="{reverse("home")}" class="nav-link">'
                '<i class="nav-icon fas fa-home"></i>'
                '<p>Home</p>'
                '</a>'
                '</li>'
            )

            admin_url = reverse('admin:index')
            admin_active = ' active' if request.path == admin_url else ''
            r += (
                '<li class="nav-item">'
                f'<a href="{admin_url}" class="nav-link{admin_active}">'
                '<i class="nav-icon fas fa-tachometer-alt"></i>'
                '<p>Admin</p>'
                '</a>'
                '</li>'
            )

        for group in menus:
            key = [key for key in group][0]
            icon = '<i class="far fa-circle nav-icon"></i>'

            if group[key]['icon'] != '':
                if re.match(r'\<([a-z]*)\b[^\>]*\>(.*?)\<\/\1\>', group[key]['icon']):
                    icon = group[key]['icon']
                else:
                    icon = f'<i class="{group[key]["icon"]}"></i>'

            if len(group[key]['children']) > 0:
                r += (
                    '<li class="nav-item has-treeview">'
                    f'<a href="#" class="nav-link">{icon} <span>{group[key]["label"]}</span>'
                    '<span class="pull-right-container"><i class="fas fa-angle-left right"></i></span></a>'
                    '<ul class="treeview-menu">\n'
                )
                r += self.render(context, group[key]['children'])
                r += '</ul></li>\n'
            else:
                r += (
                    '<li class="nav-item">'
                    f'<a href="{group[key]["link"]}" class="nav-link">'
                    f'{icon} <p>{group[key]["label"]}</p>'
                    '</a>'
                    '</li>\n'
                )

        return r

    def admin_apps(self, context, r):
        request = context['request']
        for app in context['available_apps']:
            is_active = str(app['app_url']) in request.path
            active_class = ' active' if is_active else ''
            menu_open = ' menu-open' if is_active else ''

            r += (
                f'<li class="nav-item has-treeview{menu_open}">'
                f'<a href="#" class="nav-link{active_class}">'
                '<i class="nav-icon fas fa-edit"></i>'
                f'<p>{app["name"]}</p>'
                '<p><i class="fas fa-angle-left right"></i></p>'
                '</a>'
                '<ul class="nav nav-treeview">\n'
            )

            for model in app['models']:
                if 'add_url' in model:
                    url = model['add_url']

                if 'change_url' in model:
                    url = model['change_url']

                # if 'delete_url' in model:
                #     url = model['delete_url']

                if 'admin_url' in model:
                    url = model['admin_url']

                icon = '<i class="far fa-circle nav-icon"></i>'
                if model['object_name'].title() in self.models_icon:
                    if self.models_icon[model['object_name'].title()] != '':
                        if re.match(
                            r'\<([a-z]*)\b[^\>]*\>(.*?)\<\/\1\>', self.models_icon[model['object_name'].title()]
                        ):
                            icon = self.models_icon[model['object_name'].title()]
                        else:
                            icon = f'<i class="{self.models_icon[model["object_name"].title()]}"></i>'
                active = ' active' if request.path == url else ''
                r += f'<li class="nav-item"><a href="{url}" class="nav-link{active}">{icon} {model["name"]}</a></li>'
            r += '</ul></li>\n'

        return r

    def set_model_icon(self, model_name, icon):
        self.models_icon[model_name.title()] = icon

    def get_model_icon(self, context):
        icon = '<i class="far fa-circle nav-icon"></i>'
        if context['model']['object_name'].title() in self.models_icon:
            if self.models_icon[context['model']['object_name'].title()] != '':
                model_icon = self.models_icon[context['model']['object_name'].title()]
                if re.match(r'<([a-z]*)\b[^>]*>(.*?)</\1>', model_icon):
                    icon = model_icon
                else:
                    icon = f'<i class="{model_icon}"></i>'

        return icon


register = template.Library()

Menu = _Menu()


@register.simple_tag(takes_context=True, name='menu')
def menu_tag(context):
    return Menu.admin_apps(context, Menu.render(context))


@register.simple_tag(takes_context=True, name='icon')
def icon_tag(context):
    return Menu.get_model_icon(context)
