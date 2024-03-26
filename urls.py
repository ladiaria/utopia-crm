# coding=utf-8
from pydoc import locate

import debug_toolbar

from django.conf import settings
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.contrib import admin
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.conf.urls import handler404
from django.conf.urls import handler403
from django.conf.urls import handler500

from core.views import updateuserfromweb, search_contacts_htmx, add_email_to_mailtrain_list


# TODO: explain this 3 handlers
handler404 = 'core.views.handler404'  # noqa
handler403 = 'core.views.handler403'  # noqa
handler500 = 'core.views.handler500'  # noqa

# Used to add customized url patterns from a custom app, they're declared up here so you can add your own custom apps
# and override existing URLs if you need.
urls_custom_modules = getattr(settings, 'URLS_CUSTOM_MODULE', None)
urlpatterns = locate(urls_custom_modules).urlpatterns if urls_custom_modules else []

# Django admindocs and admin
urlpatterns += [
    path('user/', include('django.contrib.auth.urls')),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    re_path(r'^admin/', admin.site.urls),
    path('', login_required(TemplateView.as_view(template_name='main_menu.html')), name="main_menu"),
]

# Core views
urlpatterns += [
    path("api/updateuserweb/", updateuserfromweb),
    path('api/search_contacts/', search_contacts_htmx, name="htmx_search_contacts"),
    path('api/search_contacts/<str:name>/', search_contacts_htmx, name="htmx_search_contacts_alt"),
    path('api/subscribe_to_mailtrain/', add_email_to_mailtrain_list, name="subscribe_to_mailtrain"),
]

if 'support' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('support/', include('support.urls'), name='support_menu'),
    ]

if 'invoicing' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('invoicing/', include('invoicing.urls')),
    ]

if 'logistics' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('logistics/', include('logistics.urls')),
    ]

if 'advertisement' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('advertisement/', include('advertisement.urls')),
    ]

# test
urlpatterns += [path('test/', TemplateView.as_view(template_name='tests/index.html'))]

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [path('rosetta/', include('rosetta.urls'))]

if settings.DEBUG:
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns


if getattr(settings, 'SERVE_MEDIA', False):
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
