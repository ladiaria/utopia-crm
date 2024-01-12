# coding=utf-8
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

# from core.views import updateuserfromweb, createinvoicefromweb


handler404 = 'core.views.handler404'
handler403 = 'core.views.handler403'
handler500 = 'core.views.handler500'

urlpatterns = []


# Used to add customized url patterns from a custom app, they're declared up here so you can add your own custom apps
# and override existing URLs if you need.
urls_custom_modules = getattr(settings, 'URLS_CUSTOM_MODULE', None)
if urls_custom_modules:
    urlpatterns += __import__(urls_custom_modules, fromlist=['urlpatterns']).urlpatterns

urlpatterns += [
    # Django admindocs and admin
    path('user/', include('django.contrib.auth.urls')),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    re_path(r'^admin/', admin.site.urls),
    path('', login_required(TemplateView.as_view(template_name='main_menu.html')), name="main_menu"),
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
