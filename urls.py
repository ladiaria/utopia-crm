# coding=utf-8
import debug_toolbar

from django.conf import settings
from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.contrib import admin
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required


# from core.views import updateuserfromweb, createinvoicefromweb


urlpatterns = [
    # Django admindocs and admin
    url(r'^user/', include('django.contrib.auth.urls')),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^honey/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    url(r'^$', login_required(TemplateView.as_view(template_name='main_menu.html'))),
]

if 'support' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^support/', include('support.urls'), name='support_menu'),
    ]

if 'invoicing' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^invoicing/', include('invoicing.urls')),
    ]

if 'logistics' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^logistics/', include('logistics.urls')),
    ]

# API REST
# urlpatterns += [
#     url(r'^api/updateuserweb/$', updateuserfromweb),
#     url(r'^api/createinvoiceweb/$', createinvoicefromweb),
# ]

# test
urlpatterns += [
    url(r'^test/$', TemplateView.as_view(template_name='tests/index.html'))
]

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^rosetta/', include('rosetta.urls'))
    ]

if settings.DEBUG:
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

if getattr(settings, 'SERVE_MEDIA', False):
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
