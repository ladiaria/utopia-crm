# -*- encoding: utf-8 -*-

import csv
from datetime import date, timedelta, datetime
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from django.shortcuts import render, reverse, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseNotFound
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import F, Q
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from difflib import SequenceMatcher

from reportlab.pdfgen.canvas import Canvas

from core.models import SubscriptionProduct, Subscription, Product, Address
from core.choices import PRODUCT_WEEKDAYS
from core.mixins import BreadcrumbsMixin
from logistics.models import Route, Edition
from support.models import Issue

from util.dates import next_business_day, format_date
from .labels import LogisticsLabel, LogisticsLabel96x30, Roll, Roll96x30
from .filters import OrderRouteFilter, AddressGeorefFilter
from .utils import create_issue_for_special_route


@login_required
def assign_routes(request):
    """
    Assigns routes to contacts that have no route. The assignation is per SubscriptionProduct.
    """
    product_list = Product.objects.filter(type="S", offerable=True)
    product_id, product = "all", None
    if request.POST:
        for name, value in list(request.POST.items()):
            if name.startswith("sp") and value:
                try:
                    # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                    sp_id = name.replace("sp-", "")
                    # Next we get the SubscriptionProject object from the DB
                    sp = SubscriptionProduct.objects.get(pk=sp_id)
                    # Finally we set the value of whatever route we set, and then save the sp
                    route = Route.objects.get(number=int(value))
                    sp.route = route
                    sp.order = None
                    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
                    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
                    sp.save()
                except Route.DoesNotExist:
                    messages.error(
                        request,
                        _(
                            "Contact {} - Product {}: Route {} does not exist".format(
                                sp.subscription.contact.get_full_name(), sp.product.name, value
                            )
                        ),
                    )
        return HttpResponseRedirect(reverse("assign_routes"))

    subscription_products = (
        SubscriptionProduct.objects.filter(
            subscription__active=True, route__isnull=True, product__type="S", product__offerable=True
        )
        .exclude(product__digital=True)
        .select_related("subscription__contact", "address")
        .order_by("subscription__contact")
    )
    if request.GET:
        product_id = request.GET.get("product_id", "all")
        if product_id != "all":
            product = Product.objects.get(pk=product_id)
            subscription_products = subscription_products.filter(product=product)
        exclude = request.GET.get("exclude", None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    return render(
        request,
        "assign_routes.html",
        {
            "subscription_products": subscription_products,
            "product_list": product_list,
            "product": product,
        },
    )


@login_required
def assign_routes_future(request):
    """
    Assigns routes to contacts that have no route. The assignation is per SubscriptionProduct.
    """
    product_list = Product.objects.filter(type="S", offerable=True)
    product_id, product = "all", None
    if request.POST:
        for name, value in list(request.POST.items()):
            if name.startswith("sp") and value:
                try:
                    # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                    sp_id = name.replace("sp-", "")
                    # Next we get the SubscriptionProject object from the DB
                    sp = SubscriptionProduct.objects.get(pk=sp_id)
                    # Finally we set the value of whatever route we set, and then save the sp
                    route = Route.objects.get(number=int(value))
                    sp.route = route
                    sp.order = None
                    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
                    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
                    sp.save()
                except Route.DoesNotExist:
                    messages.error(
                        request,
                        _(
                            "Contact {} - Product {}: Route {} does not exist".format(
                                sp.subscription.contact.get_full_name(), sp.product.name, value
                            )
                        ),
                    )
        return HttpResponseRedirect(reverse("assign_routes"))

    subscription_products = (
        SubscriptionProduct.objects.filter(
            subscription__active=False,
            route__isnull=True,
            product__type="S",
            product__offerable=True,
            subscription__start_date__gte=date.today(),
        )
        .exclude(product__digital=True)
        .select_related("subscription__contact", "address")
        .order_by("subscription__contact")
    )
    if request.GET:
        product_id = request.GET.get("product_id", "all")
        if product_id != "all":
            product = Product.objects.get(pk=product_id)
            subscription_products = subscription_products.filter(product=product)
        exclude = request.GET.get("exclude", None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    return render(
        request,
        "assign_routes.html",
        {
            "subscription_products": subscription_products,
            "product_list": product_list,
            "product": product,
        },
    )


@login_required
def order_route_list(request):
    """
    Shows a list of routes to be ordered.
    """
    orderable_routes = Route.objects.filter(active=True, print_labels=True).order_by("number")
    for route in orderable_routes:
        route.unordered_active = route.subscriptionproduct_set.filter(
            order__isnull=True, subscription__active=True
        ).count()
        route.unordered_future = route.subscriptionproduct_set.filter(
            order__isnull=True, subscription__active=False, subscription__start_date__gte=date.today()
        ).count()
    return render(
        request,
        "order_routes_list.html",
        {
            "orderable_routes": orderable_routes,
        },
    )


@login_required
def order_route(request, route_id=1):
    """
    Orders contacts inside of a route by SubscriptionProduct. Takes to route 1 by default.

    TODO: Do something to quickly change route from the template itself.
    """
    route_object = get_object_or_404(Route, pk=route_id)
    product_list = Product.objects.filter(type="S", offerable=True)
    if request.GET.get("product", None):
        product = Product.objects.get(pk=request.GET.get("product", None))
    else:
        product = None
    if request.POST:
        for name, value in list(request.POST.items()):
            if name.startswith("sp-order") and value:
                # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                sp_id = name.replace("sp-order-", "")
                # Next we get the SubscriptionProject object from the DB
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                # Finally we set the value of whatever route we set, and then save the sp
                if sp.order != int(value):
                    sp.order = int(value)
                    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
                    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
                    sp.save()
        return HttpResponseRedirect(reverse("order_route", args=[route_id]))

    subscription_products = (
        SubscriptionProduct.objects.filter(route=route_object)
        .exclude(product__digital=True)
        .order_by("order", "address__address_1")
    )
    subscription_products_filter = OrderRouteFilter(request.GET, queryset=subscription_products)
    if request.GET:
        if request.GET.get("print", None):
            return render(
                request,
                "order_route_print.html",
                {
                    "subscription_products": subscription_products_filter.qs,
                    "route": route_object,
                    "product_list": product_list,
                    "product": product,
                },
            )
    return render(
        request,
        "order_route.html",
        {
            "subscription_products": subscription_products_filter.qs,
            "filter": subscription_products_filter,
            "count": subscription_products_filter.qs.count(),
            "route": route_object,
            "product_list": product_list,
            "product": product,
        },
    )


@login_required
def print_unordered_subscriptions(request):
    product_list = Product.objects.filter(type="S", offerable=True)
    product_id, product, routes, dict_routes = "all", None, [], defaultdict(list)
    if request.POST:
        subscription_products = (
            SubscriptionProduct.objects.filter(subscription__active=True, product__type="S", product__offerable=True)
            .exclude(product__digital=True)
            .select_related("subscription__contact", "address")
            .order_by("order", "address__address_1")
        )
        product_id = request.POST.get("product_id", "all")
        if product_id != "all":
            product = Product.objects.get(pk=product_id)
            subscription_products = subscription_products.filter(product=product)
        if request.POST.get("only_unordered", None):
            subscription_products = subscription_products.filter(order=None)
        for sp in subscription_products:
            if sp.route:
                route_key = sp.route.number
            else:
                route_key = -1
            dict_routes[route_key].append(sp)
        route_list = list(dict_routes.keys())
        route_list = sorted(route_list, reverse=True)
        for route_number in route_list:
            routes.append(
                {
                    "number": route_number if route_number != -1 else None,
                    "subscription_products": dict_routes[route_number],
                }
            )

        return render(
            request,
            "print_unordered_subscriptions_list.html",
            {
                "product": product,
                "routes": routes,
            },
        )

    return render(
        request,
        "print_unordered_subscriptions_form.html",
        {
            "product_list": product_list,
        },
    )


@login_required
def change_route(request, route_id=1):
    """
    Changes route to a contact on a particular route.
    Automatically creates an Issue when a route is changed to a special route (50-55).

    TODO: Do something to quickly change route form the template itself.
    """
    product_list = Product.objects.filter(type="S", offerable=True)
    product_id, product = "all", None
    route_object = get_object_or_404(Route, pk=route_id)
    if request.POST:
        issues_created = []
        for name, value in list(request.POST.items()):
            if name.startswith("sp-") and value and int(value) != route_object.number:
                try:
                    # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                    sp_id = name.replace("sp-", "")
                    # Next we get the SubscriptionProject object from the DB
                    sp = SubscriptionProduct.objects.get(pk=sp_id)
                    # Finally we set the value of whatever route we set, and then save the sp
                    route = Route.objects.get(number=value)
                    sp.route = route
                    sp.order = None
                    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
                    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
                    sp.save()

                    # Create issue if it's a special route (50-55)
                    custom_notes = request.POST.get("issue-notes-{}".format(sp_id), None)
                    issue = create_issue_for_special_route(sp.subscription, route.number, request.user, custom_notes)
                    if issue:
                        issues_created.append(route.number)

                except Route.DoesNotExist:
                    messages.error(
                        request,
                        _(
                            "Contact {} - Product {}: Route {} does not exist".format(
                                sp.subscription.contact.get_full_name(), sp.product.name, value
                            )
                        ),
                    )

        # Show success message if issues were created
        if issues_created:
            route_list = ", ".join(map(str, set(issues_created)))
            messages.warning(
                request,
                _("Routes updated. Issues created for special routes: {}").format(route_list)
            )

        return HttpResponseRedirect(reverse("change_route", args=[route_id]))

    subscription_products = (
        SubscriptionProduct.objects.filter(
            route=route_object, subscription__active=True, product__type="S", product__offerable=True
        )
        .exclude(product__digital=True)
        .select_related("subscription__contact", "address")
        .order_by("address__address_1")
    )
    if request.GET:
        product_id = request.GET.get("product_id", "all")
        if product_id != "all":
            product = Product.objects.get(pk=product_id)
            subscription_products = subscription_products.filter(product=product)
        exclude = request.GET.get("exclude", None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    breadcrumbs = [
        {"label": _("Home"), "url": reverse("home")},
        {"label": _("Change routes"), "url": reverse("change_route", args=[route_id])},
        {"label": str(route_object), "url": ""},
    ]
    return render(
        request,
        "change_route.html",
        {
            "subscription_products": subscription_products,
            "route": route_object,
            "product_list": product_list,
            "product_id": product_id,
            "product": product,
            "breadcrumbs": breadcrumbs,
        },
    )


@login_required
def list_routes(request):
    """
    List all the routes and gives options for all of them.

    TODO: Allow changing
    """
    route_list = Route.objects.all()
    return render(
        request,
        "list_routes.html",
        {
            "route_list": route_list,
        },
    )


@login_required
def list_routes_detailed(request):
    """
    List all the routes and gives options for all of them.

    TODO: Allow changing
    """
    route_list = []
    routes = Route.objects.all()
    weekdays = dict(PRODUCT_WEEKDAYS)
    if datetime.now().hour in range(0, 3):
        show_day = date.today().isoweekday()
    else:
        show_day = next_business_day().isoweekday()
    tomorrow_product = Product.objects.get(weekday=show_day)
    for route in routes:
        route.copies = route.sum_copies_per_product(tomorrow_product)
        route.contacts = route.contacts_in_route_count()
        route.promotions = route.sum_promos_per_product(tomorrow_product)
        route.new = route.sum_copies_per_product(tomorrow_product, new=True)
        route.invoices = route.invoices_in_route()
        route_list.append(route)
    return render(
        request,
        "list_routes_detailed.html",
        {"route_list": route_list, "day": weekdays[show_day], "tomorrow_product": tomorrow_product},
    )


@login_required
def print_labels(request, page="Roll", list_type="", route_list="", product_id=None):
    if request.POST:
        if request.FILES:
            decoded_file = request.FILES.get("mark_contacts").read().decode("utf-8").splitlines()
            mark_contacts = csv.reader(decoded_file)
            mark_contacts_list = list(mark_contacts)
            # flatten the list
            mark_contacts_list = [int(item) for sublist in mark_contacts_list for item in sublist]
        else:
            mark_contacts_list = []
        if settings.DEBUG:
            print(f"DEBUG: print_labels: mark_contacts_list={mark_contacts_list}")
        if request.GET.get("date", None):
            date_string = request.GET.get("date")
            next_day = datetime.strptime(date_string, "%Y-%m-%d")
            tomorrow = next_day
        else:
            tomorrow = date.today() + timedelta(1)
            if datetime.now().hour in range(0, 3):
                next_day = date.today()
            else:
                next_day = next_business_day()
        isoweekday = next_day.isoweekday()
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=individual-labels-{}.pdf".format(
            next_day.strftime("%Y%m%d")
        )
        Page = globals()[page]
        canvas = Canvas(response, pagesize=(Page.width, Page.height))
        sheet = Page(LogisticsLabel, canvas)
        iterator = sheet.iterator()
        if list_type and list_type.startswith("route"):
            # First we initialize the queryset making it empty
            subscription_products = SubscriptionProduct.objects.none()
            for route_number in route_list.split(","):
                if route_number != "":
                    # Then for each route, we add to that empty queryset all those values
                    subscription_products = subscription_products | SubscriptionProduct.objects.filter(
                        active=True,
                        product__weekday=isoweekday,
                        subscription__active=True,
                        route__number=route_number,
                        subscription__start_date__lte=tomorrow,
                    ).exclude(route__print_labels=False).order_by(
                        "route", F("order").asc(nulls_first=True), "address__address_1"
                    )
        else:
            # If not, all the queryset gets rendered into the labels
            subscription_products = (
                SubscriptionProduct.objects.filter(
                    active=True,
                    product__weekday=isoweekday,
                    subscription__active=True,
                    subscription__start_date__lte=tomorrow,
                )
                .exclude(route__print_labels=False)
                .order_by("route", F("order").asc(nulls_first=True), "address__address_1")
            )

        old_route = 0

        for sp in subscription_products:

            # If the subscription_product has no route, then we'll skip it.
            if sp.route is None:
                continue

            # If the subscription_product has no address, continue. TODO: precond validation to prevent this situation
            if sp.address is None:
                continue

            # Separator label
            if old_route != sp.route:
                label = next(iterator)
                label.separador()
                old_route = sp.route

            # Here we'll show an icon if the contact has one of the payment types marked on settings.
            has_invoice = (
                sp.subscription.payment_type
                and sp.subscription.payment_type in settings.LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES
                and not sp.subscription.billing_address
                and sp.subscription.contact.invoice_set.filter(print_date__gte=date.today() - timedelta(6)).exists()
            )

            for copy in range(sp.copies):

                label, route_suffix = next(iterator), ""

                # TODO: take in account also here the time of execution from 0:00 to 2:59 (after midnight)
                #       maybe next_day.isoweekday() instead of tomorrow.isoweekday() is the solution, make tests cases.
                #       Another improvement (for performance) is to make the route_suffix assignment before first loop.
                #       And yet another: it's also possible to obtain locale and get the day name localized,
                #                        google this: "django get locale", "python get day name localized".
                tomorrow_isoweekday = tomorrow.isoweekday()

                if sp.product:
                    if tomorrow_isoweekday == 1:
                        route_suffix = _("MONDAY")
                    elif tomorrow_isoweekday == 2:
                        route_suffix = _("TUESDAY")
                    elif tomorrow_isoweekday == 3:
                        route_suffix = _("WEDNESDAY")
                    elif tomorrow_isoweekday == 4:
                        route_suffix = _("THURSDAY")
                    elif tomorrow_isoweekday == 5:
                        route_suffix = _("FRIDAY")
                    label.route_suffix = route_suffix

                    label.has_invoice = (
                        has_invoice
                        and sp.subscription.get_first_product_by_priority().weekday
                        and sp.subscription.get_first_product_by_priority().weekday == tomorrow_isoweekday
                    )

                # Here we determine if the subscription needs an envelope.
                if sp.has_envelope:
                    label.envelope = True

                if sp.subscription.start_date == next_business_day():
                    label.new = True

                if sp.special_instructions:
                    label.special_instructions = True

                if sp.label_message and sp.label_message.strip():
                    label.message_for_contact = sp.label_message
                else:
                    if sp.subscription.type == "P":
                        # TODO: the seller name can be obtained here to use it instead of "a friend"
                        #       (also check the use case of this label, isn't the "referer" a better option?)
                        if sp.seller:
                            ref = sp.seller.name
                        else:
                            ref = "un amigo"  # TODO: i18n
                        label.message_for_contact = "Recomendado por {}".format(ref)  # TODO: i18n
                    # When we have a 2x1 plan we should put it here
                    # elif getattr(sp.subscription.product, 'id', None) == 6:
                    #     label.message_for_contact = "2x1"

                if sp.label_contact:
                    label.name = sp.label_contact.get_full_name().upper()
                else:
                    label.name = sp.subscription.contact.get_full_name().upper()

                if mark_contacts_list and sp.subscription.contact.id in mark_contacts_list:
                    label.partial = True

                label.address = (sp.address.address_1 or "") + "\n" + (sp.address.address_2 or "")
                label.route = sp.route.number
                label.route_order = sp.order
                label.draw()
        sheet.flush()
        canvas.save()
        return response
    else:
        return render(request, "print_labels.html", {})


@login_required
def print_labels_for_day(request):
    page = "Roll"
    if request.POST:
        if request.FILES:
            decoded_file = request.FILES.get("exclude_contacts").read().decode("utf-8").splitlines()
            exclude_contacts = csv.reader(decoded_file)
            exclude_contacts_list = list(exclude_contacts)
        else:
            exclude_contacts = None
        isoweekday = request.POST.get("isoweekday")
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=individual-labels-{}.pdf".format(isoweekday)
        Page = globals()[page]
        if request.POST.get("96x30"):
            canvas = Canvas(response, pagesize=(Roll96x30.width, Roll96x30.height))
            sheet = Roll96x30(LogisticsLabel96x30, canvas)
        else:
            canvas = Canvas(response, pagesize=(Page.width, Page.height))
            sheet = Page(LogisticsLabel, canvas)
        iterator = sheet.iterator()

        subscription_products = (
            SubscriptionProduct.objects.filter(
                active=True,
                product__weekday=isoweekday,
                subscription__active=True,
                subscription__start_date__lte=date.today(),
            )
            .exclude(route__print_labels=False)
            .order_by("route", F("order").asc(nulls_first=True), "address__address_1")
        )

        if exclude_contacts:
            subscription_products = subscription_products.exclude(subscription__contact_id__in=exclude_contacts_list)
        old_route = 0

        for sp in subscription_products:

            # If the subscription_product has no route, then we'll skip it.
            if sp.route is None:
                continue

            # If the subscription_product has no address, continue. TODO: precond validation to prevent this situation
            if sp.address is None:
                continue

            # Separator label
            if old_route != sp.route:
                label = next(iterator)
                label.separador()
                old_route = sp.route

            # Here we'll show an icon if the contact has one of the payment types marked on settings.
            has_invoice = (
                sp.subscription.payment_type
                and sp.subscription.payment_type in settings.LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES
                and not sp.subscription.billing_address
                and sp.subscription.contact.invoice_set.filter(print_date__gte=date.today() - timedelta(6)).exists()
            )

            for copy in range(sp.copies):

                label, route_suffix = next(iterator), ""

                if sp.product:
                    if isoweekday == "1":
                        route_suffix = _("MONDAY")
                    elif isoweekday == "2":
                        route_suffix = _("TUESDAY")
                    elif isoweekday == "3":
                        route_suffix = _("WEDNESDAY")
                    elif isoweekday == "4":
                        route_suffix = _("THURSDAY")
                    elif isoweekday == "5":
                        route_suffix = _("FRIDAY")
                    label.route_suffix = route_suffix

                    label.has_invoice = (
                        has_invoice
                        and sp.subscription.get_first_product_by_priority().weekday
                        and sp.subscription.get_first_product_by_priority().weekday == isoweekday
                    )

                # Here we determine if the subscription needs an envelope.
                if sp.has_envelope:
                    label.envelope = True

                if sp.subscription.start_date == next_business_day():
                    label.new = True

                if sp.special_instructions:
                    label.special_instructions = True

                if sp.label_message and sp.label_message.strip():
                    label.message_for_contact = sp.label_message
                else:
                    if sp.subscription.type == "P":
                        # TODO: the seller name can be obtained here to use it instead of "a friend"
                        #       (also check the use case of this label, isn't the "referer" a better option?)
                        if sp.seller:
                            ref = sp.seller.name
                        else:
                            ref = "un amigo"  # TODO: i18n
                        label.message_for_contact = "Recomendado por {}".format(ref)  # TODO: i18n
                    # When we have a 2x1 plan we should put it here
                    # elif getattr(sp.subscription.product, 'id', None) == 6:
                    #     label.message_for_contact = "2x1"

                if sp.label_contact:
                    label.name = sp.label_contact.get_full_name().upper()
                else:
                    label.name = sp.subscription.contact.get_full_name().upper()
                label.address = (sp.address.address_1 or "") + "\n" + (sp.address.address_2 or "")
                label.route = sp.route.number
                label.route_order = sp.order
                label.draw()
        sheet.flush()
        canvas.save()
        return response
    else:
        return render(request, "print_labels_for_day.html", {})


@login_required
def print_labels_for_product(request, page="Roll", product_id=None, list_type="", route_list=""):
    """
    Print labels for a specific product.
    """
    product = get_object_or_404(Product, pk=product_id)
    today = date.today()
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=labels-for-{}-{}.pdf".format(
        product.name, today.strftime("%Y%m%d")
    )
    Page = globals()[page]
    canvas = Canvas(response, pagesize=(Page.width, Page.height))
    sheet = Page(LogisticsLabel, canvas)
    iterator = sheet.iterator()
    if list_type and list_type.startswith("route"):
        # First we initialize the queryset making it empty
        subscription_products = SubscriptionProduct.objects.none()
        for route_number in route_list.split(","):
            if route_number != "":
                # Then for each route, we add to that empty queryset all those values
                subscription_products = subscription_products | SubscriptionProduct.objects.filter(
                    active=True,
                    product=product,
                    subscription__active=True,
                    route__number=route_number,
                    subscription__start_date__lte=today + timedelta(5),
                ).order_by("route", F("order").asc(nulls_first=True), "address__address_1")
    else:
        # If not, all the queryset gets rendered into the labels
        subscription_products = SubscriptionProduct.objects.filter(
            active=True, product=product, subscription__active=True, subscription__start_date__lte=today + timedelta(5)
        ).order_by("route", F("order").asc(nulls_first=True), "address__address_1")

    old_route = 0

    for sp in subscription_products:

        if sp.address is None:
            continue

        # Separator between routes
        if sp.route and old_route != sp.route:
            label = next(iterator)
            label.separador()
            old_route = sp.route

        # Here we'll show an icon if the contact has one of the payment types marked on settings.
        has_invoice = (
            sp.subscription.payment_type
            and sp.subscription.payment_type in settings.LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES
            and not sp.subscription.billing_address
            and sp.subscription.contact.invoice_set.filter(print_date__gte=date.today() - timedelta(30)).exists()
        )

        for copy in range(sp.copies):

            label = next(iterator)

            if sp.has_envelope:
                label.envelope = True

            if sp.subscription.start_date == next_business_day():
                label.new = True

            if sp.special_instructions:
                label.special_instructions = True

            if sp.label_message and sp.label_message.strip():
                label.message_for_contact = sp.label_message
            else:
                if sp.subscription.type == "P":
                    if sp.seller:
                        ref = sp.seller.name
                    else:
                        ref = "un amigo"  # TODO: i18n
                    label.message_for_contact = "Recomendado por {}".format(ref)  # TODO: i18n
                # When we have a 2x1 plan we should put it here
                # elif getattr(sp.subscription.product, 'id', None) == 6:
                #     eti.comunicar_cliente = "2x1"

            if sp.label_contact:
                label.name = sp.label_contact.get_full_name().upper()
            else:
                label.name = sp.subscription.contact.get_full_name().upper()
            label.address = (sp.address.address_1 or "") + "\n" + (sp.address.address_2 or "")
            if sp.route:
                label.route = sp.route.number
                label.route_order = sp.order
            else:
                label.route = None
                label.route_order = None

            label.has_invoice = (
                has_invoice
                and sp.subscription.get_first_product_by_priority()
                and sp.subscription.get_first_product_by_priority() == product
            )

            label.draw()
    sheet.flush()
    canvas.save()
    return response


@login_required
def print_labels_from_csv(request):
    """
    Generates a PDF with labels from a CSV.
    """
    if request.FILES:
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=labels-from-csv.pdf"
        canvas = Canvas(response, pagesize=(Roll.width, Roll.height))
        hoja = Roll(LogisticsLabel, canvas)

        if request.POST.get("96x30"):
            canvas = Canvas(response, pagesize=(Roll96x30.width, Roll96x30.height))
            hoja = Roll96x30(LogisticsLabel96x30, canvas)
        use_separators = request.POST.get("separators", None)

        iterator = hoja.iterator()
        decoded_file = request.FILES.get("labels").read().decode("utf-8").splitlines()
        label_list = csv.reader(decoded_file)
        next(label_list)  # consumo header

        old_route = 0
        for row in label_list:
            try:
                if row[3] and old_route != row[3] and use_separators:
                    label = next(iterator)
                    label.separador()
                    old_route = row[3]
                label = next(iterator)
                label.name = row[0].upper()
                label.address = "{}\n{}".format(row[1], row[2])
                label.route = row[3] or ""
                label.route_order = row[4] or ""
                label.message = row[5] or ""
                label.route_suffix = row[6] or ""
                label.draw()
            except IndexError:
                messages.error(request, _("Columns count is wrong"))
                return render(request, "print_labels_from_csv.html")

        hoja.flush()
        canvas.save()
        return response
    else:
        return render(request, "print_labels_from_csv.html")


@login_required
def issues_labels(request):
    today = date.today()
    if today.isoweekday() == 1:
        labels_date = date.today() - timedelta(2)
    else:
        labels_date = date.today() - timedelta(1)
    # If the user has an issue with copies and a subscriptionproduct
    issues = Issue.objects.filter(
        category="L",  # We're only getting the Logistics issues...
        copies__gte=0,  # ...that have more than zero copies
        date=labels_date,  # If it's monday we're going to select the issues that are on Saturday
    ).order_by("-date", "-id")

    if issues:
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=labels-from-csv.pdf"
        canvas = Canvas(response, pagesize=(Roll.width, Roll.height))
        hoja = Roll(LogisticsLabel, canvas)

        if request.POST.get("96x30"):
            canvas = Canvas(response, pagesize=(Roll96x30.width, Roll96x30.height))
            hoja = Roll96x30(LogisticsLabel96x30, canvas)

        iterator = hoja.iterator()

        for issue in issues:
            if not issue.copies:
                continue
            for copy in range(issue.copies):
                label = next(iterator)
                if issue.subscription_product and issue.subscription_product.label_contact:
                    label.name = issue.subscription_product.label_contact.get_full_name().upper()
                else:
                    label.name = issue.contact.get_full_name().upper()
                if issue.address:
                    label.address = (issue.address.address_1 or "") + "\n" + (issue.address.address_2 or "")
                    label.route = ""
                    label.route_order = ""
                else:
                    label.address = (
                        (issue.subscription_product.address.address_1 or "")
                        + "\n"
                        + (issue.subscription_product.address.address_2 or "")
                    )
                if issue.subscription_product and issue.subscription_product.route:
                    label.route = issue.subscription_product.route.number
                    label.route_order = issue.subscription_product.order
                else:
                    label.route, label.route_order = None, None
                # Add the day of the product to the labels.
                if issue.subscription_product:
                    if issue.subscription_product.product.weekday == 1:  # Monday
                        label.message_for_contact = _("MONDAY")
                    elif issue.subscription_product.product.weekday == 2:  # Tuesday
                        label.message_for_contact = _("TUESDAY")
                    elif issue.subscription_product.product.weekday == 3:
                        label.message_for_contact = _("WEDNESDAY")
                    elif issue.subscription_product.product.weekday == 4:
                        label.message_for_contact = _("THURSDAY")
                    elif issue.subscription_product.product.weekday == 5:
                        label.message_for_contact = _("FRIDAY")
                    elif issue.subscription_product.product.weekday == 6:
                        label.message_for_contact = _("SATURDAY")
                    elif issue.subscription_product.product.weekday == 7:
                        label.message_for_contact = _("SUNDAY")
                    elif issue.subscription_product.product.weekday == 10:
                        label.message_for_contact = _("WEEKEND")
                    else:
                        label.message_for_contact = issue.subscription_product.product.name
                elif issue.product:
                    label.message_for_contact = issue.product.name
                if issue.envelope:
                    label.envelope = True
                label.draw()
        hoja.flush()
        canvas.save()
        return response
    else:
        return HttpResponseRedirect("/logistics/")


@login_required
def route_details(request, route_list):
    """
    Shows details for a selected route.
    """
    if request.GET.get("date", None):
        date_string = request.GET.get("date")
        day = datetime.strptime(date_string, "%Y-%m-%d")
    else:
        if datetime.now().hour in range(0, 3):
            day = date.today()
        else:
            day = next_business_day()
    one_month_ago = day - timedelta(30)
    isoweekday = day.isoweekday()

    route_list = route_list.split(",")
    route_list = [r for r in route_list if r.isdigit()]
    routes = Route.objects.filter(number__in=route_list)

    product = Product.objects.get(weekday=isoweekday)

    routes_dict = {}
    changes_dict = {}
    copies_dict = {}
    subscription_products_dict = {}
    # new_subscriptions_dict = {}
    closing_subscriptions_dict = {}
    directions_dict = {}
    issues_dict = {}
    routes_with_subscriptions = []

    for route in routes:
        subscription_products = (
            SubscriptionProduct.objects.filter(
                route=route, active=True, subscription__active=True, product__weekday=isoweekday
            )
            .exclude(product__digital=True)
            .order_by("order", "address__address_1")
            .select_related("subscription")
        )
        if not subscription_products.exists():
            continue
        subscription_products_dict[str(route.number)] = subscription_products

        routes_dict[str(route.number)] = route

        routes_with_subscriptions.append(str(route.number))

        copies = subscription_products.aggregate(sum_copies=Sum("copies"))["sum_copies"] or 0
        copies_dict[str(route.number)] = copies

        changes_list = route.routechange_set.filter(dt__gt=day - timedelta(4)).order_by("-dt")
        changes_dict[str(route.number)] = changes_list

        # new_subscriptions = SubscriptionProduct.objects.filter(
        #     route=route, subscription__start_date__gte=date.today() - timedelta(2), product__weekday=isoweekday)
        closing_subscriptions = (
            SubscriptionProduct.objects.filter(
                active=True, route=route, subscription__end_date__gte=date.today() - timedelta(3)
            )
            .exclude(product__digital=True)
            .distinct("subscription")
        )
        closing_subscriptions_dict[str(route.number)] = closing_subscriptions

        if route.directions:
            directions_dict[str(route.number)] = route.directions

        issues = (
            Issue.objects.filter(subscription_product__route=route, category="L")
            .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
            .distinct()
        )
        issues_dict[str(route.number)] = issues

    return render(
        request,
        "route_details.html",
        {
            "route_list": routes_with_subscriptions,
            "routes_dict": routes_dict,
            "copies_dict": copies_dict,
            "changes_dict": changes_dict,
            "directions_dict": directions_dict,
            "issues_dict": issues_dict,
            "closing_subscriptions_dict": closing_subscriptions_dict,
            "day": day,
            "one_month_ago": one_month_ago,
            "product": product,
            "subscription_products_dict": subscription_products_dict,
            "deactivated_list": [],  # lista_desactivados,
        },
    )


@login_required
def edition_time(request, direction):
    edition = Edition.objects.latest("date")
    if request.POST:
        # If someone types 24:00, it should be moved to 23:59
        time = request.POST["time"]
        if time == "24:00":
            time = "23:59"
        if direction == "arrival":
            edition.start_time = time
            edition.save()
        else:
            edition.end_time = time
            edition.save()
        return HttpResponseRedirect(reverse("edition_time", kwargs={"direction": direction}))

    what = _("{} time".format(direction))
    last_editions = Edition.objects.all().order_by("-id")[:5]
    return render(request, "edition_time.html", {"edition": edition, "last_editions": last_editions, "what": what})


@login_required
def logistics_issues_statistics(request, category="L"):
    # TODO: Maybe we need to switch subscriptionproduct for subscriptions
    days = []
    weeks = []
    months = []

    start_date = date.today() - timedelta(7)
    end_date = date.today()

    control_date = start_date

    while control_date <= end_date:
        day = {}
        isoweekday = control_date.isoweekday()
        day["date"] = format_date(control_date)
        day["issues"] = Issue.objects.filter(date=control_date, category=category).count()
        day["start"] = control_date.strftime("%Y-%m-%d")
        if day["issues"]:
            count = (
                SubscriptionProduct.objects.filter(subscription__active=True, product__weekday=isoweekday)
                .exclude(product__digital=True)
                .count()
            )
            if count > 0:
                day["pct"] = float(day["issues"]) * 100 / count
                day["pct"] = "%.2f" % day["pct"]
            else:
                day["pct"] = "N/A"
        days.append(day)

        control_date += timedelta(1)

    start_date = date.today() - timedelta(7 * 4)
    end_date = date.today() - timedelta(date.today().isoweekday() - 1)

    control_date = start_date

    while control_date <= end_date:
        week = {}
        week["date"] = format_date(control_date)

        week["issues"] = Issue.objects.filter(
            category=category, date__gte=control_date, date__lte=control_date + timedelta(6)
        ).count()

        if week["issues"]:
            count = Subscription.objects.filter(active=True).exclude(products__digital=True).count()
            if count > 0:
                week["pct"] = float(week["issues"]) * 100 / (count * 6)
                week["pct"] = "%.2f" % week["pct"]
            else:
                week["pct"] = "N/A"

        week["start"] = control_date.strftime("%Y-%m-%d")
        week["end"] = (control_date + timedelta(6)).strftime("%Y-%m-%d")
        weeks.append(week)
        control_date += timedelta(7)

    start_date = date.today() + relativedelta(months=-4)
    end_date = date(date.today().year, date.today().month, 1)

    control_date = start_date

    while control_date <= end_date:
        month = {}
        month["date"] = str(control_date.month)

        month["issues"] = Issue.objects.filter(
            category=category, date__gte=control_date, date__lte=control_date + relativedelta(months=+1) - timedelta(1)
        ).count()

        if month["issues"]:
            count = Subscription.objects.filter(active=True).exclude(products__digital=True).count()
            if count > 0:
                month["pct"] = float(month["issues"]) * 100 / (count * 24)
                month["pct"] = "%.2f" % month["pct"]
            else:
                month["pct"] = "N/A"

        month["start"] = control_date.strftime("%Y-%m-%d")
        month["end"] = (control_date + relativedelta(months=+1) - timedelta(1)).strftime("%Y-%m-%d")
        months.append(month)
        control_date = control_date + relativedelta(months=+1)

    return render(
        request, "issues_statistics.html", {"days": days, "weeks": weeks, "months": months, "category": category}
    )


@login_required
def issues_per_route(request, route, start_date, end_date, category="L"):
    route = get_object_or_404(Route, pk=route)
    issues = Issue.objects.filter(
        subscription_product__route=route, date__gte=start_date, date__lte=end_date, category="L"
    )
    subscription_list = SubscriptionProduct.objects.filter(
        subscription__start_date=next_business_day(), route=route, special_instructions__isnull=False
    ).distinct("subscription")
    return render(
        request, "issues_per_route.html", {"issues": issues, "route": route, "subscription_list": subscription_list}
    )


@login_required
def issues_route_list(request, start_date, end_date):
    routes = Route.objects.filter(print_labels=True)
    routes_list = []
    days = 0
    control_date = datetime.strptime(start_date, "%Y-%m-%d")
    while control_date <= datetime.strptime(end_date, "%Y-%m-%d"):
        if control_date.isoweekday() <= 5:
            days += 1
        control_date += timedelta(1)

    for r in routes:
        route_dict = {}
        route_dict["route_number"] = r.number
        route_dict["issues_count"] = Issue.objects.filter(
            subscription_product__route=r, date__gte=start_date, date__lte=end_date, category="L"
        ).count()
        route_dict["subscriptions_count"] = (
            Subscription.objects.filter(
                active=True,
                subscriptionproduct__route=r,
            )
            .exclude(products__digital=True)
            .count()
        )
        if route_dict["issues_count"] > 0:
            route_dict["pct"] = float(route_dict["issues_count"]) * 100 / (route_dict["subscriptions_count"] * days)
            route_dict["pct"] = "%.2f%%" % route_dict["pct"]
        else:
            route_dict["pct"] = "N/A"
        routes_list.append(route_dict)
    return render(
        request,
        "issues_route_list.html",
        {"start_date": start_date, "end_date": end_date, "routes_list": routes_list, "days": days},
    )


@login_required
def print_routes_simple(request, route_list):
    product_list = Product.objects.filter(type="S", offerable=True)
    product_id = "all"
    route_list = route_list.split(",")
    route_list = [r for r in route_list if r.isdigit()]
    routes = Route.objects.filter(number__in=route_list)
    if not routes:
        return HttpResponseNotFound()
    route_dict = {}

    for route_number in route_list:
        try:
            route_object = Route.objects.get(pk=route_number)
        except Route.DoesNotExist:
            messages.error(request, _("Route {} does not exist".format(route_number)))
            return HttpResponseRedirect(reverse("home"))

        subscription_products = (
            SubscriptionProduct.objects.filter(route=route_object, subscription__active=True, product__type="S")
            .exclude(product__digital=True)
            .select_related("subscription__contact", "address")
            .order_by("order", "address__address_1")
        )

        if request.GET:
            product_id = request.GET.get("product_id", "all")
            if product_id != "all":
                subscription_products = subscription_products.filter(product_id=product_id)
            exclude = request.GET.get("exclude", None)
            if exclude:
                subscription_products = subscription_products.exclude(product_id=exclude)

        route_dict[route_number] = subscription_products

    route_dict = sorted(route_dict.items())

    return render(
        request,
        "print_routes_simple.html",
        {
            "route_dict": route_dict,
            "route_list": route_list,
            "product_list": product_list,
            "product_id": product_id,
            "product_name": Product.objects.get(pk=product_id).name if product_id != "all" else None,
        },
    )


@permission_required("logistics.change_route")
def convert_orders_to_tens(request, route_id, product_id=None):
    route = get_object_or_404(Route, pk=route_id)
    if product_id:
        product = get_object_or_404(Product, pk=product_id)
        order_i = 10
        for sp in SubscriptionProduct.objects.filter(product=product, route=route, order__isnull=False).order_by(
            "order"
        ):
            sp.order = order_i
            sp.save()
            order_i += 10
    else:
        for product in Product.objects.filter(offerable=True, type="S"):
            order_i = 10
            for sp in SubscriptionProduct.objects.filter(product=product, route=route, order__isnull=False).order_by(
                "order"
            ):
                sp.order = order_i
                sp.save()
                order_i += 10
    messages.success(request, _("All orders have been converted to tens."))
    return HttpResponseRedirect(reverse("order_route", args=[route.number]))


@login_required
def print_labels_for_product_date(request):
    """
    Print labels for a specific product on a specific date
    """
    if request.POST:
        product = get_object_or_404(Product, pk=request.POST.get("product_id", None))
        date_str = request.POST.get("date", None)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=labels-{}-{}.pdf".format(product.name, date_str)
        Page = globals()["Roll"]  # It's always a roll for now. TODO: Change
        canvas = Canvas(response, pagesize=(Page.width, Page.height))
        sheet = Page(LogisticsLabel, canvas)
        iterator = sheet.iterator()
        # If not, all the queryset gets rendered into the labels
        subscription_products = SubscriptionProduct.objects.filter(
            Q(subscription__end_date__gte=date_obj) | Q(subscription__end_date__isnull=True),
            active=True,
            product=product,
            subscription__status="OK",
            subscription__start_date__lte=date_obj,
        ).order_by("route", F("order").asc(nulls_first=True), "address__address_1")

        if request.POST.get("download-csv", None):
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="etiquetas_{}_{}.csv"'.format(
                product.name, date_str
            )
            writer = csv.writer(response)
            header = [
                "id_cliente",
                "id_suscripción",
                "producto",
                "copies",
                "contact_name",
                "nombre_etiqueta",
                "dirección_1",
                "dirección_2",
                "ciudad",
                "departamento",
                "ruta",
                "orden",
                "mensaje",
                "instrucciones",
                "sobre",
                "start_date",
                "end_date",
            ]
            writer.writerow(header)
            for sp in subscription_products:
                label_name = sp.subscription.contact.get_full_name()
                subscription_id = sp.subscription.id
                product = sp.product.name
                if sp.address:
                    address_1 = sp.address.address_1
                    address_2 = sp.address.address_2
                    city = sp.address.city
                    state = sp.address.state_name
                else:
                    address_1, address_2, city, state = None, None, None, None
                if sp.route:
                    route = sp.route.number
                else:
                    route = None
                order = sp.order
                message = sp.label_message
                instructions = sp.special_instructions

                writer.writerow(
                    [
                        sp.subscription.contact.id,
                        subscription_id,
                        product,
                        sp.copies,
                        sp.subscription.contact.get_full_name(),
                        label_name,
                        address_1,
                        address_2,
                        city,
                        state,
                        route,
                        order,
                        message,
                        instructions,
                        sp.subscription.start_date,
                        sp.subscription.end_date,
                    ]
                )
            return response

        old_route = 0

        for sp in subscription_products:

            if sp.address is None:
                continue

            # Separator between routes
            if sp.route and old_route != sp.route:
                label = next(iterator)
                label.separador()
                old_route = sp.route

            # Here we'll show an icon if the contact has one of the payment types marked on settings.
            has_invoice = (
                sp.subscription.payment_type
                and sp.subscription.payment_type in settings.LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES
                and not sp.subscription.billing_address
                and sp.subscription.contact.invoice_set.filter(print_date__gte=date.today() - timedelta(30)).exists()
            )

            for copy in range(sp.copies):

                label = next(iterator)

                if sp.has_envelope:
                    label.envelope = True

                if sp.subscription.start_date == next_business_day():
                    label.new = True

                if sp.special_instructions:
                    label.special_instructions = True

                if sp.label_message and sp.label_message.strip():
                    label.message_for_contact = sp.label_message
                else:
                    if sp.subscription.type == "P":
                        if sp.seller:
                            ref = sp.seller.name
                        else:
                            ref = "un amigo"  # TODO: i18n
                        label.message_for_contact = "Recomendado por {}".format(ref)  # TODO: i18n
                    # When we have a 2x1 plan we should put it here
                    # elif getattr(sp.subscription.product, 'id', None) == 6:
                    #     eti.comunicar_cliente = "2x1"

                if sp.label_contact:
                    label.name = sp.label_contact.get_full_name().upper()
                else:
                    label.name = sp.subscription.contact.get_full_name().upper()
                label.address = (sp.address.address_1 or "") + "\n" + (sp.address.address_2 or "")
                if sp.route:
                    label.route = sp.route.number
                    label.route_order = sp.order
                else:
                    label.route = None
                    label.route_order = None

                label.has_invoice = (
                    has_invoice
                    and sp.subscription.get_first_product_by_priority()
                    and sp.subscription.get_first_product_by_priority() == product
                )
                label.draw()
        sheet.flush()
        canvas.save()
        return response
    else:
        products = Product.objects.filter(offerable=True, type="S")
        return render(
            request,
            "print_labels_for_product_date.html",
            {
                "products": products,
            },
        )


@staff_member_required
def addresses_with_complementary_information(request):
    addresses_qs = Address.objects.filter((~Q(picture=None) & ~Q(picture="")) | Q(google_maps_url__isnull=False))
    if request.GET.get("show_hidden", None):
        show_hidden = True
    else:
        addresses_qs = addresses_qs.filter(do_not_show=False)
        show_hidden = False
    return render(
        request,
        "addresses_with_complementary_information.html",
        {"addresses": addresses_qs, "show_hidden": show_hidden},
    )


@staff_member_required
def mass_georef_address(request):
    addr_queryset = Address.objects.filter(verified=False).order_by("subscriptionproduct__route").distinct()
    if not request.session.get("mass_georef_address_form") or request.GET:
        addr_filter = AddressGeorefFilter(request.GET, addr_queryset)
        request.session['mass_georef_address_form'] = addr_filter.data
    else:
        form = request.session.get("mass_georef_address_form")
        addr_filter = AddressGeorefFilter(form, addr_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(addr_filter.qs, 100)
    try:
        addresses = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        addresses = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        addresses = paginator.page(paginator.num_pages)
    return render(
        request,
        "mass_georef_address_filter.html",
        {
            "paginator": paginator,
            "filter": addr_filter,
            "addresses": addresses,
            "page": page_number,
            "total_pages": paginator.num_pages,
            "count": addr_filter.qs.count(),
            "now": datetime.now(),
            "url": request.META["PATH_INFO"],
        },
    )


class MergeCompareAddressesView(BreadcrumbsMixin, TemplateView):
    """
    Class-based view for comparing two addresses side-by-side before merging.
    Allows user to select which address to keep and which fields to preserve.
    Can be accessed with a contact_id to show dropdowns of that contact's addresses,
    or with address_1 and address_2 IDs for direct comparison.
    """
    template_name = "merge_compare_addresses.html"

    @method_decorator(login_required)
    @method_decorator(permission_required('core.can_merge_addresses', raise_exception=True))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def breadcrumbs(self):
        from django.urls import reverse
        breadcrumbs_list = [
            {"url": reverse("home"), "label": _("Home")},
            {"label": _("Merge addresses"), "url": reverse("merge_compare_addresses")},
        ]

        # Add contact breadcrumb if we have a contact_id (step 1)
        contact_id = self.request.GET.get("contact_id")
        if contact_id:
            try:
                from core.models import Contact
                contact = Contact.objects.get(pk=contact_id)
                breadcrumbs_list.insert(1, {
                    "label": _("Contact list"),
                    "url": reverse("contact_list")
                })
                breadcrumbs_list.insert(2, {
                    "label": contact.get_full_name(),
                    "url": reverse("contact_detail", args=[contact.id])
                })
            except Contact.DoesNotExist:
                pass
        else:
            # Step 2: Check if addresses being compared have a contact
            address_1_id = self.request.GET.get("address_1")
            address_2_id = self.request.GET.get("address_2")
            if address_1_id and address_2_id:
                try:
                    address1 = Address.objects.select_related('contact').get(pk=address_1_id)
                    if address1.contact:
                        breadcrumbs_list.insert(1, {
                            "label": _("Contact list"),
                            "url": reverse("contact_list")
                        })
                        breadcrumbs_list.insert(2, {
                            "label": address1.contact.get_full_name(),
                            "url": reverse("contact_detail", args=[address1.contact.id])
                        })
                except Address.DoesNotExist:
                    pass

        return breadcrumbs_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        contact_id = self.request.GET.get("contact_id", None)
        address_1_id = self.request.GET.get("address_1", None)
        address_2_id = self.request.GET.get("address_2", None)

        # If contact_id is provided, show address selection dropdowns
        if contact_id:
            try:
                from core.models import Contact
                contact = Contact.objects.prefetch_related('addresses').get(pk=contact_id)
                addresses = contact.addresses.select_related('state', 'country', 'city_fk').all()

                if addresses.count() < 2:
                    messages.warning(self.request, _("Contact must have at least 2 addresses to merge"))
                    return context

                context.update({
                    'contact': contact,
                    'available_addresses': addresses,
                })
            except Contact.DoesNotExist:
                messages.error(self.request, _("Contact {id} does not exist").format(id=contact_id))
                return context

        # If both address IDs are provided, show comparison
        if address_1_id and address_2_id:
            if address_1_id == address_2_id:
                messages.error(self.request, _("Address IDs must be different"))
                return context

            try:
                address1 = Address.objects.select_related('contact', 'state', 'country', 'city_fk').get(pk=address_1_id)
            except Address.DoesNotExist:
                messages.error(self.request, _("Address {id} does not exist").format(id=address_1_id))
                return context

            try:
                address2 = Address.objects.select_related('contact', 'state', 'country', 'city_fk').get(pk=address_2_id)
            except Address.DoesNotExist:
                messages.error(self.request, _("Address {id} does not exist").format(id=address_2_id))
                return context

            # Get counts of related objects for each address
            address1_sp_count = address1.subscriptionproduct_set.count()
            address2_sp_count = address2.subscriptionproduct_set.count()
            address1_issue_count = address1.issue_set.count()
            address2_issue_count = address2.issue_set.count()
            address1_task_count = address1.scheduledtask_set.count()
            address2_task_count = address2.scheduledtask_set.count()

            # Calculate similarity between address_1 fields
            similarity_ratio = 0.0
            show_similarity_warning = False
            if address1.address_1 and address2.address_1:
                # Normalize strings for comparison (lowercase, strip whitespace)
                addr1_normalized = address1.address_1.lower().strip()
                addr2_normalized = address2.address_1.lower().strip()

                # Calculate similarity ratio (0.0 to 1.0)
                similarity_ratio = SequenceMatcher(None, addr1_normalized, addr2_normalized).ratio()

                # Show warning if similarity is below 40% (very different addresses)
                if similarity_ratio < 0.4:
                    show_similarity_warning = True

            context.update({
                'address1': address1,
                'address2': address2,
                'address1_sp_count': address1_sp_count,
                'address2_sp_count': address2_sp_count,
                'address1_issue_count': address1_issue_count,
                'address2_issue_count': address2_issue_count,
                'address1_task_count': address1_task_count,
                'address2_task_count': address2_task_count,
                'similarity_ratio': similarity_ratio,
                'similarity_percentage': int(similarity_ratio * 100),
                'show_similarity_warning': show_similarity_warning,
            })

        return context


class ProcessMergeAddressesView(View):
    """
    Class-based view for processing the address merge.
    Handles POST request with selected fields and executes the merge.
    """

    @method_decorator(require_POST)
    @method_decorator(login_required)
    @method_decorator(permission_required('core.can_merge_addresses', raise_exception=True))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        address1_id = request.POST.get("address1_id")
        address2_id = request.POST.get("address2_id")
        selected_address_id = request.POST.get("selected_address_id")

        # Determine which is source and which is target
        source_address_id_list = [address1_id, address2_id]
        source_address_id_list.remove(selected_address_id)

        try:
            source_address = Address.objects.get(pk=source_address_id_list[0])
            target_address = Address.objects.get(pk=selected_address_id)
        except Address.DoesNotExist:
            messages.error(request, _("One of the addresses does not exist"))
            return HttpResponseRedirect(reverse("merge_compare_addresses"))

        # Get field overrides from POST data
        new_address_1 = request.POST.get("new_address_1", None)
        new_address_2 = request.POST.get("new_address_2", None)
        new_city = request.POST.get("new_city", None)
        new_email = request.POST.get("new_email", None)
        new_address_type = request.POST.get("new_address_type", None)
        new_notes = request.POST.get("new_notes", None)
        new_default = request.POST.get("new_default") == "True"
        new_name = request.POST.get("new_name", None)
        new_state_id = request.POST.get("new_state_id", None)
        new_country_id = request.POST.get("new_country_id", None)
        new_city_fk_id = request.POST.get("new_city_fk_id", None)
        new_latitude = request.POST.get("new_latitude", None)
        new_longitude = request.POST.get("new_longitude", None)
        new_google_maps_url = request.POST.get("new_google_maps_url", None)

        # Convert string IDs to integers or None
        new_state_id = int(new_state_id) if new_state_id and new_state_id != "" else None
        new_country_id = int(new_country_id) if new_country_id and new_country_id != "" else None
        new_city_fk_id = int(new_city_fk_id) if new_city_fk_id and new_city_fk_id != "" else None

        # Convert latitude/longitude, handling both comma and dot as decimal separator
        if new_latitude and new_latitude != "":
            new_latitude = float(new_latitude.replace(',', '.'))
        else:
            new_latitude = None

        if new_longitude and new_longitude != "":
            new_longitude = float(new_longitude.replace(',', '.'))
        else:
            new_longitude = None

        # Store contact for redirect
        contact = target_address.contact

        # Execute the merge
        errors = target_address.merge_other_address_into_this(
            source_address,
            address_1=new_address_1,
            address_2=new_address_2,
            city=new_city,
            email=new_email,
            address_type=new_address_type,
            notes=new_notes,
            default=new_default,
            name=new_name,
            state_id=new_state_id,
            country_id=new_country_id,
            city_fk_id=new_city_fk_id,
            latitude=new_latitude,
            longitude=new_longitude,
            google_maps_url=new_google_maps_url,
        )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(
                request,
                _("Addresses merged into address {id}. Address {source_id} has been deleted.").format(
                    id=target_address.id,
                    source_id=source_address.id
                )
            )

        # Redirect to contact detail if address has a contact, otherwise to merge page
        if contact:
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
        else:
            return HttpResponseRedirect(reverse("merge_compare_addresses"))


@login_required
def change_subscription_routes(request, subscription_id):
    """
    Changes routes for all subscription products in a single subscription.
    Automatically creates an Issue when a route is changed to a special route (50-55).
    """
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    contact = subscription.contact

    if request.POST:
        special_route_numbers = []
        for name, value in list(request.POST.items()):
            if name.startswith("sp-") and value:
                try:
                    # Get the subscription product ID
                    sp_id = name.replace("sp-", "")
                    sp = SubscriptionProduct.objects.get(pk=sp_id)

                    # Get the new route
                    new_route = Route.objects.get(number=int(value))

                    # Check if route actually changed
                    if sp.route != new_route:
                        # Update the route
                        sp.route = new_route
                        sp.order = None
                        sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
                        sp.label_message = request.POST.get("message-{}".format(sp_id), None)
                        sp.save()

                        # Track special route numbers for a single issue
                        if new_route.number in range(50, 56):
                            special_route_numbers.append(new_route.number)

                except Route.DoesNotExist:
                    messages.error(
                        request,
                        _(
                            "Product {}: Route {} does not exist".format(
                                sp.product.name, value
                            )
                        ),
                    )
                except SubscriptionProduct.DoesNotExist:
                    messages.error(request, _("Subscription product not found"))

        # Create a single issue for all special route changes
        if special_route_numbers:
            custom_notes = request.POST.get("issue-notes", None)
            issue = create_issue_for_special_route(
                subscription, user=request.user, custom_notes=custom_notes, route_numbers=special_route_numbers
            )
            if issue:
                route_list = ", ".join(map(str, sorted(set(special_route_numbers))))
                messages.warning(
                    request,
                    _("Routes updated. Issue created for special routes: {}").format(route_list)
                )
            else:
                messages.success(request, _("Routes updated successfully"))
        else:
            messages.success(request, _("Routes updated successfully"))

        return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))

    # Get all subscription products for this subscription
    subscription_products = (
        SubscriptionProduct.objects.filter(subscription=subscription)
        .exclude(product__digital=True)
        .select_related("product", "address", "route")
        .order_by("product__name")
    )

    # Get all available routes
    routes = Route.objects.filter(active=True).order_by("number")

    return render(
        request,
        "change_subscription_routes.html",
        {
            "subscription": subscription,
            "contact": contact,
            "subscription_products": subscription_products,
            "routes": routes,
        },
    )
