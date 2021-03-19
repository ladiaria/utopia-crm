# -*- encoding: utf-8 -*-

import csv
from datetime import date, timedelta

from django.shortcuts import render, reverse, get_object_or_404
from django.http import (
    HttpResponseRedirect, HttpResponse)
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

from reportlab.pdfgen.canvas import Canvas

from core.models import SubscriptionProduct, Product
from core.choices import PRODUCT_WEEKDAYS
from logistics.models import Route, Edition
from support.models import Issue

from util.dates import next_business_day
from .labels import LogisticsLabel, LogisticsLabel96x30, Roll, Roll96x30


PRODUCT_LIST = Product.objects.filter(type='S', bundle_product=False)


@login_required
def assign_routes(request):
    """
    Assigns routes to contacts that have no route. The assignation is per SubscriptionProduct.
    """
    product_id = 'all'
    if request.POST:
        for name, value in request.POST.items():
            if name.startswith('sp') and value:
                # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                sp_id = name.replace('sp-', '')
                # Next we get the SubscriptionProject object from the DB
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                # Finally we set the value of whatever route we set, and then save the sp
                route = Route.objects.get(number=value)
                sp.route = route
                sp.order = None
                sp.special_instructions = request.POST.get('instructions-{}'.format(sp_id), None)
                sp.label_message = request.POST.get('message-{}'.format(sp_id), None)
                sp.save()
        return HttpResponseRedirect(reverse('assign_routes'))

    subscription_products = SubscriptionProduct.objects.filter(
        subscription__active=True, route__isnull=True).exclude(
            product__name__contains='digital').order_by('subscription__contact')
    if request.GET:
        product_id = request.GET.get('product_id', 'all')
        if product_id != 'all':
            subscription_products = subscription_products.filter(product_id=product_id)
        exclude = request.GET.get('exclude', None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    return render(
        request, 'assign_routes.html', {
            'subscription_products': subscription_products,
            'product_list': PRODUCT_LIST
        })


@login_required
def order_route(request, route=1):
    """
    Orders contacts inside of a route by SubscriptionProduct. Takes to route 1 by default.

    TODO: Do something to quickly change route from the template itself.
    """
    product_id = 'all'
    route_object = get_object_or_404(Route, pk=route)
    if request.POST:
        for name, value in request.POST.items():
            if name.startswith('sp-order') and value:
                # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                sp_id = name.replace('sp-order-', '')
                # Next we get the SubscriptionProject object from the DB
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                # Finally we set the value of whatever route we set, and then save the sp
                order = value
                sp.order = order
                sp.special_instructions = request.POST.get('instructions-{}'.format(sp_id), None)
                sp.label_message = request.POST.get('message-{}'.format(sp_id), None)
                sp.save()

    subscription_products = SubscriptionProduct.objects.filter(
        route=route_object, subscription__active=True).exclude(
            product__name__contains='digital').order_by('order', 'address__address_1')
    if request.GET:
        product_id = request.GET.get('product_id', 'all')
        if product_id != 'all':
            subscription_products = subscription_products.filter(product_id=product_id)
        exclude = request.GET.get('exclude', None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    return render(
        request, 'order_route.html', {
            'subscription_products': subscription_products,
            'route': route,
            'product_list': PRODUCT_LIST,
            'product_id': product_id})


@login_required
def change_route(request, route=1):
    """
    Changes route to a contact on a particular route.

    TODO: Do something to quickly change route form the template itself.
    """
    product_id = 'all'
    route_object = get_object_or_404(Route, pk=route)
    if request.POST:
        for name, value in request.POST.items():
            if name.startswith('sp-routechange') and value:
                # We get the id of the subscription id here, removing the prefix 'sp-' from the name of the item
                sp_id = name.replace('sp-routechange-', '')
                # Next we get the SubscriptionProject object from the DB
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                # Finally we set the value of whatever route we set, and then save the sp
                route = Route.objects.get(number=value)
                sp.route = route
                sp.order = None
                sp.special_instructions = request.POST.get('instructions-{}'.format(sp_id), None)
                sp.label_message = request.POST.get('message-{}'.format(sp_id), None)
                sp.save()

    subscription_products = SubscriptionProduct.objects.filter(
        route=route_object, subscription__active=True).exclude(
            product__name__contains='digital').order_by('address__address_1')
    if request.GET:
        product_id = request.GET.get('product_id', 'all')
        if product_id != 'all':
            subscription_products = subscription_products.filter(product_id=product_id)
        exclude = request.GET.get('exclude', None)
        if exclude:
            subscription_products = subscription_products.exclude(product_id=exclude)
    return render(
        request, 'change_route.html', {
            'subscription_products': subscription_products, 'route': route, 'product_list': PRODUCT_LIST,
            'product_id': product_id})


@login_required
def list_routes(request):
    """
    List all the routes and gives options for all of them.

    TODO: Allow changing
    """
    route_list = []
    routes = Route.objects.all()
    today = date.today()
    weekdays = dict(PRODUCT_WEEKDAYS)
    if today.isoweekday() in (6, 7):
        # This means it's Saturday or Sunday, we're going to show data for the product that goes out on Monday
        show_day = 1
    else:
        # If it's not Sautrday or Sunday, we're going to show data for the product that goes out tomorrow
        # This is only considering we don't have a product on Sundays.
        show_day = today.isoweekday() + 1
    tomorrow_product = Product.objects.get(weekday=show_day)
    for route in routes:
        route.copies = route.sum_copies_per_product(tomorrow_product)
        route.contacts = route.contacts_in_route_count()
        route.promotions = route.sum_promos_per_product(tomorrow_product)
        route.new = route.sum_copies_per_product(tomorrow_product, new=True)
        route.invoices = route.invoices_in_route()
        route_list.append(route)
    return render(
        request, 'list_routes.html', {
            'route_list': route_list, 'day': weekdays[show_day], 'tomorrow_product': tomorrow_product
        })


@login_required
def print_labels(request, page='Roll', list_type='', route_list='', product_id=None):
    today = date.today()
    tomorrow = date.today() + timedelta(1)
    next_day = next_business_day()
    isoweekday = next_day.isoweekday()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = \
        'attachment; filename=individual-labels-{}.pdf'.format(next_day.strftime('%Y%m%d'))
    Page = globals()[page]
    canvas = Canvas(response, pagesize=(Page.width, Page.height))
    sheet = Page(LogisticsLabel, canvas)
    iterator = sheet.iterator()
    if list_type and list_type.startswith('route'):
        # First we initialize the queryset making it empty
        subscription_products = SubscriptionProduct.objects.none()
        for route_number in route_list.split(','):
            if route_number != '':
                # Then for each route, we add to that empty queryset all those values
                subscription_products = subscription_products | SubscriptionProduct.objects.filter(
                    product__weekday=isoweekday, subscription__active=True, route__number=route_number,
                    subscription__start_date__lte=tomorrow).exclude(
                    route__print_labels=False).order_by('route', 'order', 'address__address_1')
    else:
        # If not, all the queryset gets rendered into the labels
        subscription_products = SubscriptionProduct.objects.filter(
            product__weekday=isoweekday, subscription__active=True,
            subscription__start_date__lte=tomorrow).exclude(
            route__print_labels=False).order_by('route', 'order', 'address__address_1')

    days = 2 if today.isoweekday() == 6 else 1

    old_route = 0

    for sp in subscription_products:

        # If the subscription_product has no route, then we'll skip it.
        if sp.route is None:
            continue

        # If the subscription_product has no address, continue. There should be a way to control this doesn't happen
        if sp.address is None:
            continue

        # Separator label
        if old_route != sp.route:
            label = iterator.next()
            label.separador()
            old_route = sp.route

        # Here we'll show a label if the contact has one of the payment types marked on settings.
        label_invoice_payment_types = getattr(settings, 'LABEL_INVOICE_PAYMENT_TYPES')
        has_invoice = label_invoice_payment_types and sp.subscription.payment_type and \
            sp.subscription.payment_type in label_invoice_payment_types and not sp.subscription.billing_address and \
            sp.subscription.contact.invoice_set.filter(creation_date__gt=date.today() - timedelta(6))

        for copy in range(sp.copies):

            label, route_suffix = iterator.next(), ''
            tomorrow_isoweekday = tomorrow.isoweekday()

            if sp.product:
                if tomorrow_isoweekday == 1:
                    route_suffix = _('MONDAY')
                elif tomorrow_isoweekday == 2:
                    route_suffix = _('TUESDAY')
                elif tomorrow_isoweekday == 3:
                    route_suffix = _('WEDNESDAY')
                elif tomorrow_isoweekday == 4:
                    route_suffix = _('THURSDAY')
                elif tomorrow_isoweekday == 5:
                    route_suffix = _('FRIDAY')
                label.route_suffix = route_suffix

                label.has_invoice = has_invoice and sp.subscription.get_first_day_of_the_week() + 1 == \
                    tomorrow_isoweekday

            # Here we determine if the subscription needs an envelope. We might need to move those words to a setting
            if sp.subscription.envelope or sp.subscription.free_envelope or (
                    sp.subscription.start_date >= next_business_day() -
                    timedelta(days) and sp.address and (
                    sp.address.address_1.find(' ap ') != -1 or
                    sp.address.address_1.find(' of ') != -1 or
                    sp.address.address_1.find(' esc ') != -1)):
                label.envelope = True

            if sp.subscription.start_date == next_business_day():
                label.new = True

            if sp.special_instructions:
                label.special_instructions = True

            if sp.label_message and sp.label_message.strip():
                label.message_for_contact = sp.label_message
            else:
                if sp.subscription.type == 'P':
                    if sp.subscription.seller:
                        ref = sp.subscription.seller.name
                    else:
                        ref = _('a friend')
                    label.message_for_contact = "{}\n{}".format(_('Subscription suggested by\n'), ref)
                # When we have a 2x1 plan we should put it here
                # elif getattr(sp.subscription.product, 'id', None) == 6:
                #     label.message_for_contact = "2x1"

            label.name = sp.subscription.contact.name.upper()
            label.address = (sp.address.address_1 or '') + '\n' + (sp.address.address_2 or '')
            label.route = sp.route.number
            label.route_order = sp.order
            label.draw()
    sheet.flush()
    canvas.save()
    return response


@login_required
def print_labels_for_product(request, page='Roll', product_id=None, list_type='', route_list=''):
    """
    Print labels for a specific product.
    """
    product = get_object_or_404(Product, pk=product_id)
    today = date.today()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = \
        'attachment; filename=labels-for-{}-{}.pdf'.format(product.name, today.strftime('%Y%m%d'))
    Page = globals()[page]
    canvas = Canvas(response, pagesize=(Page.width, Page.height))
    sheet = Page(LogisticsLabel, canvas)
    iterator = sheet.iterator()
    if list_type and list_type.startswith('route'):
        # First we initialize the queryset making it empty
        subscription_products = SubscriptionProduct.objects.none()
        for route_number in route_list.split(','):
            if route_number != '':
                # Then for each route, we add to that empty queryset all those values
                subscription_products = subscription_products | SubscriptionProduct.objects.filter(
                    product=product, subscription__active=True, route__number=route_number,
                    subscription__start_date__lte=today).exclude(
                    route__print_labels=False).order_by('route', 'order', 'address__address_1')
    else:
        # If not, all the queryset gets rendered into the labels
        subscription_products = SubscriptionProduct.objects.filter(
            product=product, subscription__active=True,
            subscription__start_date__lte=today).exclude(
            route__print_labels=False).order_by('route', 'order', 'address__address_1')

    old_route = 0

    for sp in subscription_products:

        # Separator between routes
        if sp.route and old_route != sp.route:
            label = iterator.next()
            label.separador()
            old_route = sp.route

        for copy in range(sp.copies):

            label = iterator.next()

            # Aqui se determina cuando el cliente recibe con sobre, puede
            # ser en base a los flags sobre[_gratis] o los 2 primeros dias
            # en base a las palabras ' ap ', ' of ', ' esc ' en la
            # direccion de entrega
            if sp.subscription.envelope or sp.subscription.free_envelope or (
                    sp.subscription.start_date >= today and sp.address and (
                    sp.address.address_1.find(' ap ') != -1 or
                    sp.address.address_1.find(' of ') != -1 or
                    sp.address.address_1.find(' esc ') != -1)):
                label.envelope = True

            if sp.subscription.start_date == next_business_day():
                label.new = True

            if sp.special_instructions:
                label.special_instructions = True

            if sp.label_message and sp.label_message.strip():
                label.message_for_contact = sp.label_message
            else:
                if sp.subscription.type == 'P':
                    if sp.subscription.seller:
                        ref = sp.subscription.seller.name
                    else:
                        ref = _('a friend')
                    label.message_for_contact = "{}\n{}".format(_('Subscription suggested by\n'), ref)
                # When we have a 2x1 plan we should put it here
                # elif getattr(sp.subscription.product, 'id', None) == 6:
                #     eti.comunicar_cliente = "2x1"

            label.name = sp.subscription.contact.name.upper()
            label.address = (sp.address.address_1 or '') + '\n' + (sp.address.address_2 or '')
            if sp.route:
                label.route = sp.route.number
                label.route_order = sp.order
            else:
                label.route = None
                label.route_order = None
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
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=labels-from-csv.pdf'
        canvas = Canvas(response, pagesize=(Roll.width, Roll.height))
        hoja = Roll(LogisticsLabel, canvas)

        if request.POST.get('96x30'):
            canvas = Canvas(response, pagesize=(Roll96x30.width, Roll96x30.height))
            hoja = Roll96x30(LogisticsLabel96x30, canvas)

        iterator = hoja.iterator()
        label_list = csv.reader(request.FILES.get('labels'))
        label_list.next()  # consumo header

        for row in label_list:
            label = iterator.next()
            label.name = row[0].upper()
            label.address = '\n'.join(row[1:])
            label.draw()

        hoja.flush()
        canvas.save()
        return response
    else:
        return render(request, 'print_labels_from_csv.html')


@login_required
def issues_labels(request):
    today = date.today()
    if today.isoweekday() == 1:
        labels_date = date.today() - timedelta(2)
    else:
        labels_date = date.today() - timedelta(1)
    # If the user has an issue with copies and a subscriptionproduct
    issues = Issue.objects.filter(
        category='L',  # We're only getting the Logistics issues...
        copies__gte=0,  # ...that have more than zero copies
        date=labels_date,  # If it's monday we're going to select the issues that are on Saturday
    )

    if issues:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=labels-from-csv.pdf'
        canvas = Canvas(response, pagesize=(Roll.width, Roll.height))
        hoja = Roll(LogisticsLabel, canvas)

        if request.POST.get('96x30'):
            canvas = Canvas(response, pagesize=(Roll96x30.width, Roll96x30.height))
            hoja = Roll96x30(LogisticsLabel96x30, canvas)

        iterator = hoja.iterator()

        for issue in issues:
            if not issue.subscription_product:
                continue
            if not issue.copies:
                continue
            for copy in range(issue.copies):
                label = iterator.next()
                label.nombre = issue.contact.name.upper()
                label.direccion = (
                    issue.subscription_product.address.address_1 or '') + '\n' + (
                    issue.subscription_product.address.address_2 or '')
                label.ruta = issue.subscription_product.route.number
                label.ruta_orden = issue.subscription_product.order
                # Add the day of the product to the labels.
                if issue.subscription_product.product.weekday == 1:  # Monday
                    route_suffix = _('MONDAY')
                elif issue.subscription_product.product.weekday == 2:  # Tuesday
                    route_suffix = _('TUESDAY')
                elif issue.subscription_product.product.weekday == 3:
                    route_suffix = _('WEDENESDAY')
                elif issue.subscription_product.product.weekday == 4:
                    route_suffix = _('THURSDAY')
                elif issue.subscription_product.product.weekday == 5:
                    route_suffix = _('FRIDAY')
                elif issue.subscription_product.product.weekday == 6:
                    route_suffix = _('SATURDAY')
                elif issue.subscription_product.product.weekday == 7:
                    route_suffix = _('SUNDAY')
                elif issue.subscription_product.product.weekday == 10:
                    route_suffix = _('WEEKEND')
                else:
                    route_suffix = issue.subscription_product.product.name
                label.ruta_sufijo = route_suffix
                label.draw()
        hoja.flush()
        canvas.save()
        return response
    else:
        return HttpResponseRedirect('/logistics/')


@login_required
def route_details(request, route_list):
    """
    Shows details for a selected route.
    """
    day = next_business_day()
    one_month_ago = day - timedelta(30)
    isoweekday = day.isoweekday()

    route_list = route_list.split(',')
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
        subscription_products = SubscriptionProduct.objects.filter(
            route=route, subscription__active=True, product__weekday=isoweekday).exclude(
                product__slug__contains='digital').order_by('order', 'address__address_1').select_related(
                'subscription')
        if not subscription_products.exists():
            continue
        subscription_products_dict[str(route.number)] = subscription_products

        routes_dict[str(route.number)] = route

        routes_with_subscriptions.append(str(route.number))

        copies = subscription_products.aggregate(sum_copies=Sum('copies'))['sum_copies'] or 0
        copies_dict[str(route.number)] = copies

        changes_list = route.routechange_set.filter(dt__gt=day - timedelta(4)).order_by('-dt')
        changes_dict[str(route.number)] = changes_list

        # new_subscriptions = SubscriptionProduct.objects.filter(
        #     route=route, subscription__start_date__gte=date.today() - timedelta(2), product__weekday=isoweekday)
        closing_subscriptions = SubscriptionProduct.objects.filter(
            route=route, subscription__end_date__gte=date.today() - timedelta(3)).exclude(
            product__slug__contains='digital').distinct('subscription')
        closing_subscriptions_dict[str(route.number)] = closing_subscriptions

        if route.directions:
            directions_dict[str(route.number)] = route.directions

        issues = Issue.objects.filter(subscription_product__route=route, category='L').exclude(
            status='X').exclude(status='S').distinct()
        issues_dict[str(route.number)] = issues

    return render(request, 'route_details.html', {
        'route_list': routes_with_subscriptions,
        'routes_dict': routes_dict,
        'copies_dict': copies_dict,
        'changes_dict': changes_dict,
        'directions_dict': directions_dict,
        'issues_dict': issues_dict,
        'closing_subscriptions_dict': closing_subscriptions_dict,
        'day': day,
        'one_month_ago': one_month_ago,
        'product': product,
        'subscription_products_dict': subscription_products_dict,
        'deactivated_list': []  # lista_desactivados,
    })


@login_required
def edition_time(request, direction):
    edition = Edition.objects.latest('date')
    if request.POST:
        # If someone types 24:00, it should be moved to 23:59
        time = request.POST['time']
        if time == '24:00':
            time = '23:59'
        if direction == 'arrival':
            edition.start_time = time
            edition.save()
        else:
            edition.end_time = time
            edition.save()
        return HttpResponseRedirect(reverse('edition_time', kwargs={'direction': direction}))

    what = _('{} time'.format(direction))
    last_editions = Edition.objects.all().order_by('-id')[:5]
    return render(request, 'edition_time.html', {
        'edition': edition, 'last_editions': last_editions, 'what': what})
