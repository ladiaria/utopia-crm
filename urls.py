# coding=utf-8
from pydoc import locate

from django.conf import settings
from django.urls import include, path
from django.views.generic import TemplateView
from django.contrib import admin
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required

from core.views import (
    contact_api,
    contact_exists,
    search_contacts_htmx,
    mailtrain_list_subscription,
    mailtrain_lists,
    get_mailtrain_list_subscribed_emails,
    toggle_mailtrain_subscription,
    create_oneshot_invoice_from_web,
    contact_by_emailprefix,
    TermsAndConditionsDetailView,
)
from core.serializers import router
from invoicing import api as invoicing_api


# Custom error handlers. These are used to override the default Django error handlers and are defined in the core app.
handler404 = 'core.views.handler404'
handler403 = 'core.views.handler403'
handler500 = 'core.views.handler500'

# Used to add customized url patterns from a custom app, they're declared up here so you can add your own custom apps
# and override existing URLs if you need.
urls_custom_modules = getattr(settings, 'URLS_CUSTOM_MODULE', None)
urlpatterns = locate(urls_custom_modules).urlpatterns if urls_custom_modules else []

# Django admindocs and admin
urlpatterns += [
    path('user/', include('django.contrib.auth.urls')),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('', login_required(TemplateView.as_view(template_name='main_menu.html')), name='home'),
]

# apis and views
urlpatterns += [
    path('api/', include(router.urls)),
    path("api/existsuserweb/", contact_exists),
    path("api/updateuserweb/", contact_api),
    path("api/contact_by_emailprefix/", contact_by_emailprefix),
    path('api/search_contacts/', search_contacts_htmx, name="search_contacts_htmx"),
    path('api/search_contacts/<str:name>/', search_contacts_htmx, name="search_contacts_htmx_alt"),
    path('api/mailtrain_list_subscription/', mailtrain_list_subscription, name="mailtrain_list_subscription"),
    path('api/mailtrain_lists/', mailtrain_lists, name="mailtrain_lists"),
    path("api/mailtrain_subscribers/list/<str:list_id>/", get_mailtrain_list_subscribed_emails),
    path(
        "mailtrain/toggle_subscription/<int:contact_id>/<str:cid>/",
        toggle_mailtrain_subscription,
        name="toggle_mailtrain_subscription",
    ),
    path(
        "api/create_oneshot_invoice_from_web/", create_oneshot_invoice_from_web, name="create_oneshot_invoice_from_web"
    ),
    path('terms_and_conditions/<int:pk>/', TermsAndConditionsDetailView.as_view(), name='terms_and_conditions_detail'),
]

if 'support' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('support/', include('support.urls'), name='support_menu'),
    ]

if 'invoicing' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('invoicing/', include('invoicing.urls')),
    ]
    # Invocing API
    urlpatterns += [
        path('api/createinvoicefromweb/', invoicing_api.createinvoicefromweb, name='createinvoicefromweb'),
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

if 'debug_toolbar' in settings.INSTALLED_APPS:
    # WARNING/TODO: more settings are needed to use django-debug-toolbar.
    import debug_toolbar
    urlpatterns.insert(0, path('__debug__/', include(debug_toolbar.urls)))

if getattr(settings, 'SERVE_MEDIA', False):
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )

# Select2 URLs
urlpatterns += [
    path('select2/', include('django_select2.urls')),
]
