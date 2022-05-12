# coding=utf-8
import csv
from datetime import date, timedelta, datetime

from dateutil.relativedelta import relativedelta

from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.utils.text import format_lazy

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from .filters import InvoiceFilter
from invoicing.models import Invoice, InvoiceItem, Billing, CreditNote
from core.models import Contact, Subscription, Product, SubscriptionProduct, AdvancedDiscount


reportlab.rl_config.TTFSearchPath.append(str(settings.STATIC_ROOT) + '/fonts')
pdfmetrics.registerFont(TTFont('3of9', 'static/fonts/FREE3OF9.TTF'))


@staff_member_required
def contact_invoices(request, contact_id):
    """
    Shows a page with the invoices for a chosen contact.
    """
    contact = get_object_or_404(Contact, id=contact_id)

    invoice_list = []
    for invoice in contact.invoice_set.all().order_by('-id'):
        if invoice.canceled:
            invoice.status = 'null'
        elif invoice.paid or invoice.debited:
            invoice.status = 'paid'
        else:
            if invoice.expiration_date < date.today():
                invoice.status = 'expired'
                # si es incobrable hay que mostrarlo
                if invoice.uncollectible:
                    invoice.status = 'uncollectible'
            elif invoice.uncollectible:
                # se podria dar que no este vencida pero igual sea incobrable
                invoice.status = 'uncollectible'
            else:
                invoice.status = 'pending'
        invoice_list.append(invoice)

    debt = contact.get_debt()

    return render(
        request,
        'contact_invoices.html', {'contact': contact, 'invoice_list': invoice_list, 'debt': debt}
    )


def bill_subscription(subscription_id, billing_date=None, dpp=10, check_route=False, debug=False):
    """
    Bills a single subscription into an only invoice. Returns the created invoice.
    """
    billing_date = billing_date or date.today()
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    contact = subscription.contact
    invoice, invoice_items = None, None

    # Check that the subscription is active
    assert subscription.active, _('This subscription is not active and should not be billed.')

    # Check that the subscription is normal
    assert subscription.type == 'N', _('This subscription is not normal and should not be billed.')

    # Check that the next billing date exists or we need to raise an exception.
    assert subscription.next_billing, (_("Could not bill because next billing date does not exist"))

    # Check that the subscription has a payment type
    assert subscription.payment_type, (_("The subscription has no payment type, it can't be billed"))

    # Check that the subscription's next billing is smaller than end date if it has it
    if subscription.end_date:
        error_msg = _("This subscription has an end date greater than its next billing")
        assert subscription.next_billing < subscription.end_date, (error_msg)

    if subscription.next_billing > billing_date + timedelta(settings.BILLING_EXTRA_DAYS):
        raise Exception(_('This subscription should not be billed yet.'))

    # We need to get all the subscription data. The priority is defined in the billing_priority column of the product.
    # If this first product doesn't have the required data, then we can't bill the subscription.
    billing_data = subscription.get_billing_data_by_priority()

    if not billing_data and not getattr(settings, "FORCE_DUMMY_MISSING_BILLING_DATA", False):
        raise Exception(
            "Subscription {} for contact {} contains no billing data.".format(
                subscription.id, subscription.contact.id
            )
        )

    if billing_data and billing_data["address"] is None:
        raise Exception(
            "Subscription {} for contact {} requires an address to be billed.".format(
                subscription.id, subscription.contact.id
            )
        )

    if billing_data and getattr(settings, "REQUIRE_ROUTE_FOR_BILLING", False):
        if billing_data["route"] is None:
            raise Exception(
                "Subscription {} for contact {} requires a route to be billed.".format(
                    subscription.id, subscription.contact.id
                )
            )

        elif billing_data["route"] in getattr(settings, "EXCLUDE_ROUTES_FROM_BILLING_LIST", []):
            raise Exception(
                "Subscription {} for contact {} can't be billed since it's on route {}.".format(
                    subscription.id, subscription.contact.id, billing_data["route"]
                )
            )

    invoice_items = []

    # First we're going to form all the invoiceitems from the processed products the subscription has.
    # This gives a dictionary with product_id and copies so we need to call the items of said dictionary
    percentage_discount_product = None
    subtotal = 0
    product_summary = subscription.product_summary()
    advanced_discount_list = []

    for product_id, copies in list(product_summary.items()):
        # For each product we're making an invoiceitem. These are common for both discounts and subscriptions
        product = Product.objects.get(pk=int(product_id))
        if product.type == 'P':
            # If it's a percentage discount we'll save it for last, after the entire price has been calculated
            percentage_discount_product = product
            continue
        elif product.type == 'A':
            # if it's an advanced discount, save it for last too
            advanced_discount_list.append(product)
            continue
        item = InvoiceItem()
        frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
        item.description = format_lazy('{} {}', product.name, frequency_extra)
        item.price = int(product.price * subscription.frequency)
        item.product = product
        if product.type == 'S':
            # If the product is a subscription
            copies = int(copies)
            item.type = 'I'  # This means this is a regular item on the invoice
            subtotal += item.price
        elif product.type == 'D':
            copies = 1  # If the product is a discount, the copies are always 1
            item.type = 'D'  # This means this is a discount item
            # We'll use the type of discount/surcharge of 1, that uses the numeric value instead of a percentage.
            item.type_dr = 1
            subtotal -= item.price
        item.amount = item.price * item.copies
        # save all the package
        invoice_items.append(item)

    # After calculating the prices of the product, we check out every product in the advanced_discount_list
    for discount_product in advanced_discount_list:
        advanced_discount = AdvancedDiscount.objects.get(discount_product=discount_product)
        discounted_product_price = 0
        for product in advanced_discount.find_products.all():
            if product.id in list(product_summary.keys()):
                if product.type == 'S':
                    discounted_product_price += int(product_summary[product.id]) * product.price
                else:
                    discounted_product_price -= int(product_summary[product.id]) * product.price
        if advanced_discount.value_mode == 1:
            discounted_product_price = advanced_discount.value
        else:
            discounted_product_price = round((discounted_product_price * advanced_discount.value) / 100)
        item = InvoiceItem()
        frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
        item.description = format_lazy('{} {}', discount_product.name, frequency_extra)
        item.price = int(round(discounted_product_price))  # This is to calculate the $
        item.type = 'D'
        item.type_dr = 1
        item.product = discount_product
        item.copies = 1
        item.amount = item.price  # Copies is 1 so this is also the amount
        invoice_items.append(item)

    if percentage_discount_product:
        # Then if we have the percentage discount, we'll calculate how much it is. We do this last to make sure
        # the price is calculated with the entire sum of the subscription
        item = InvoiceItem()
        frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
        item.description = format_lazy('{} {}', percentage_discount_product.name, frequency_extra)
        item.price = int(round((subtotal * percentage_discount_product.price) / 100))  # This is to calculate the $
        item.type = 'D'
        item.type_dr = 1
        item.product = percentage_discount_product
        item.copies = 1
        item.amount = item.price  # Copies is 1 so this is also the amount
        invoice_items.append(item)

    # After adding all of the invoiceitems, we need to check if the subscription has an envelope. In future reviews
    # this should be deprecated and envelopes should be its own product, because here you'd end up adding envelopes
    # to digital products potentially. Fancy digital envelopes huh?
    if SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1).exists() and getattr(settings, 'ENVELOPE_PRICE', None):
        envelope_price = settings.ENVELOPE_PRICE
        # Get the amount of days per week the subscription gets the paper
        products_with_envelope_count = SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1).count()
        # Then we multiply the amount of days by 4.25 (average of weeks per
        # month) and that amount by the price of the envelope
        amount = products_with_envelope_count * envelope_price * subscription.frequency
        # We now pack the value into an InvoiceItem and add it to the list
        envelope_item = InvoiceItem()
        envelope_item.description = _('Envelope')
        envelope_item.amount = int(amount)
        envelope_item.subscription = subscription
        invoice_items.append(envelope_item)

    expiration_date = billing_date + timedelta(int(dpp))
    service_from = subscription.next_billing

    # The next part before the append is only to add frequency discounts
    if subscription.frequency > 1:
        # We sum all the money from this subscription
        sub_items_amount = sum([item.amount for item in invoice_items if item.type == 'I'])
        # Then we make the sum of all discount InvoiceItems
        sub_discounts_amount = sum([item.amount for item in invoice_items if item.type == 'D'])
        # Subtract discount from totals
        sub_total = sub_items_amount - sub_discounts_amount
        # Then we check if it is necessary to add discounts. The discount percentage comes from this method
        discount_pct = subscription.get_frequency_discount()
        # Then we add that to the corresponding invoiceitem
        discount_amount = int(round((sub_total * discount_pct) / 100))
        # Pack the discount invoiceitem and add it to the list
        frequency_discount_item = InvoiceItem()
        frequency_discount_item.description = _('{} months discount ({} discount)'.format(
            subscription.frequency, discount_pct))
        frequency_discount_item.amount = discount_amount
        # 1 means it's a plain value. This is just in case you want to use percentage discounts.
        frequency_discount_item.type_dr = 1
        # This means the item is a discount.
        frequency_discount_item.type = 'D'
        invoice_items.append(frequency_discount_item)

    if invoice_items:
        try:
            # Make the sum of all InvoiceItems of the type 'I' and 'R'
            total = sum([item.amount for item in invoice_items if item.type in 'IR'])
            discounts = sum([item.amount for item in invoice_items if item.type == 'D'])

            amount = total - discounts

            # Finally we make the rounding and add the invoiceitem needed
            if amount != round(amount):
                amount_rounded = round(amount) - amount
                round_item = InvoiceItem()
                if amount_rounded < 0:
                    round_item.type = 'D'
                elif amount_rounded > 0:
                    round_item.type = 'R'
                round_item.description = _('Rounding')
                round_item.type_dr = 1
                round_item.amount = abs(amount_rounded)
                amount = int(round(amount))
                invoice_items.append(round_item)

            # After we did the rounding and calculated the invoice amount, we'll make sure the balance item isn't
            # greater than the invoice, we don't want a negative value invoice!
            if subscription.balance and subscription.balance != 0:
                balance_item = InvoiceItem()
                if subscription.balance > 0:
                    # If the balance is positive, it means this invoice will have a discount.
                    balance_item.description = _('Balance')
                    balance_item.type = 'D'  # This means the item is a discount.
                    if subscription.balance > amount:
                        balance_item.amount = amount
                    else:
                        balance_item.amount = subscription.balance
                    balance_item.type_dr = 1  # 1 means it's a plain value
                    subscription.balance -= balance_item.amount  # Then subtract the balance
                    amount -= float(balance_item.amount)  # And then we subtract that value from the invoice
                elif subscription.balance < 0:
                    # If the balance is negative, it means the person owes us money, we'll make a surcharge.
                    balance_item.description = _('Balance owed')
                    balance_item.type_dr = 1  # 1 means it's a plain value
                    balance_item.type = 'R'  # This means the item is a surcharge
                    balance_item.amount = abs(subscription.balance)  # The entire balance is applied to the item
                    subscription.balance = None  # After that, we can deplete it from the subscription
                    amount += float(balance_item.amount)  # And then we add that value to the invoice
                # We don't want any negative shenanigans so we'll use the absolute.
                balance_item.amount = abs(balance_item.amount)
                invoice_items.append(balance_item)

            # We need to move the next billing even if the subscription is not billed
            subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
                months=subscription.frequency)
            subscription.save()

            # Move the next billing to how many months it's necessary.
            # If the subscription doesn't have next_billing, we'll create one using the start_date of the subscription.

            assert amount, _("This subscription won't be billed since amount is 0")

            payment_method = subscription.payment_type

            # Meanwhile we'll create the invoice object
            invoice = Invoice.objects.create(
                contact=contact,
                payment_type=payment_method,
                # amount=amount,
                creation_date=billing_date,
                service_from=service_from,
                service_to=service_from + relativedelta(months=subscription.frequency),
                billing_name=billing_data['name'],
                billing_address=billing_data['address'],
                billing_state=billing_data['state'],
                billing_city=billing_data['city'],
                route=billing_data['route'],
                order=billing_data['order'],
                expiration_date=expiration_date,
                billing_document=subscription.rut,
                subscription=subscription,
                amount=amount,
            )

            # We add all invoice items to the invoice.
            for item in invoice_items:
                item.save()
                invoice.invoiceitem_set.add(item)

            # When the invoice has finally been created and every date has been moved where it should have been, we're
            # going to check if there's any temporary discounts, and remove them if it applies.
            if getattr(settings, 'TEMPORARY_DISCOUNT', None):
                temporary_discount_list = list(getattr(settings, 'TEMPORARY_DISCOUNT').items())
                for discount_slug, months in temporary_discount_list:
                    if (
                        invoice.has_product(discount_slug)
                        and invoice.subscription.months_in_invoices_with_product(discount_slug) >= months
                    ):
                        invoice.subscription.remove_product(Product.objects.get(slug=discount_slug))

        except Exception as e:
            raise Exception("Contact {} Subscription {}: {}".format(subscription.contact.id, subscription.id, e))
    else:
        # If for whatever reasons there are no invoice items, we did something wrong, we'll have to return nothing.
        return None
    return invoice


@staff_member_required
def bill_subscriptions_for_one_contact(request, contact_id):
    """
    Bills all subscriptions for a single contact. If the contact has more than one active subscription, it will
    generate more than one invoice.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST.get('creation_date'):
        creation_date = request.POST.get('creation_date', date.today())
        creation_date = datetime.strptime(creation_date, "%Y-%m-%d").date()
        dpp = request.POST.get('dpp', 10)
        for subscription in contact.subscriptions.filter(active=True, next_billing__lte=creation_date):
            try:
                invoice = bill_subscription(subscription.id, creation_date, dpp)
            except Exception as e:
                messages.error(request, e.message)
            else:
                messages.success(request, _("Invoice {} has been created successfully".format(invoice.id)))
        return HttpResponseRedirect(
            reverse("contact_invoices", args=(contact_id,)))
    else:
        return render(
            request, 'bill_subscriptions_for_one_contact.html', {
                'contact': contact,
                'today': date.today(),
            })


@staff_member_required
def billing_invoices(request, billing_id):
    """
    Shows a list of invoices from a billing.
    """
    billing = get_object_or_404(Billing, id=billing_id)

    invoice_list = []
    for invoice in billing.invoice_set.all().order_by('-id'):
        if invoice.canceled:
            invoice.status = 'null'
        elif invoice.paid or invoice.debited:
            invoice.status = 'paid'
        else:
            if invoice.expiration_date < date.today():
                invoice.status = 'expired'
                # si es incobrable hay que mostrarlo
                if invoice.uncollectible:
                    invoice.status = 'uncollectible'
            elif invoice.uncollectible:
                # se podria dar que no este vencida pero igual sea incobrable
                invoice.status = 'uncollectible'
            else:
                invoice.status = 'pending'
        invoice_list.append(invoice)

    return render(request, 'billing_invoices.html', {
        'billing': billing, 'invoice_list': invoice_list,
    })


@permission_required(('invoicing.change_invoice', 'invoicing.change_creditnote'), raise_exception=True)
def cancel_invoice(request, invoice_id):
    """
    Marks the invoice as canceled with today's date and creaates a credit note.
    """
    i = get_object_or_404(Invoice, pk=invoice_id)
    error = _('The invoice is already canceled') if i.canceled else False
    notes = []
    if not error:
        # search for a matching credit note already created
        notes = CreditNote.objects.filter(invoice=i)
        if notes:
            messages.error(request, _("This invoice already has credit notes."))
        else:
            CreditNote.objects.create(invoice=i)
            i.canceled, i.cancelation_date = True, date.today()
            i.save()
            messages.success(request, _("This invoice was successfully canceled"))
    else:
        messages.error(request, _("This invoice could not be canceled: {}".format(error)))
    return HttpResponseRedirect(reverse("admin:invoicing_invoice_change", args=[invoice_id]))


@staff_member_required
def download_invoice(request, invoice_id):
    """
    Prints a single product invoice. In the future this should allow for different templates and will probably be a lot
    more customizable than this. This is just the first version.

    TODO: - Add all billing data.
          - Add a decent template.
          - Improve the drawing of the table with platypus elements.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)
    response = HttpResponse(content_type='application/pdf')
    width = 80 * mm
    height = 110 * mm if getattr(settings, 'USE_SQUASHED_SUBSCRIPTION_INVOICEITEMS', False) else 140 * mm
    c = Canvas(response, pagesize=(width, height))
    logo = getattr(settings, 'INVOICE_LOGO')
    table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])
    for page in range(1, 3):
        c.setFont("Roboto", 12)
        c.drawImage(logo, 17 * mm, height - 38 * mm, width=40 * mm, preserveAspectRatio=True, mask='auto')
        c.drawString(10 * mm, height - 35 * mm, _('Issue date: {}'.format(invoice.creation_date.strftime("%d/%m/%Y"))))
        c.drawString(10 * mm, height - 40 * mm, _('Due date: {}'.format(invoice.expiration_date.strftime("%d/%m/%Y"))))
        c.drawString(10 * mm, height - 50 * mm, '{}'.format(invoice.contact.name))
        c.setFont("Roboto", 5)
        table_data = []
        table_data.append((_('Item'), _('Un.'), _('Price'), _('Total')))
        if getattr(settings, 'USE_SQUASHED_SUBSCRIPTION_INVOICEITEMS', False) and invoice.subscription:
            product = _('Subscription {}'.format(invoice.subscription.id))
            copies = 1
            total_amount = 0
            for item in invoice.invoiceitem_set.all():
                if item.type == 'D':
                    total_amount -= item.amount
                else:
                    total_amount += item.amount
            table_data.append([product, copies, total_amount, total_amount])
        elif invoice.subscription:
            for item in invoice.invoiceitem_set.all():
                table_data.append([item.description, item.copies, item.price, item.amount])
        table_data.append(['', '', _('Total'), invoice.amount])
        table = Table(table_data)
        table.setStyle(table_style)
        table.wrapOn(c, width, height)
        table.drawOn(c, 3 * mm, 30 * mm)
        c.setFont("Roboto", 11)
        c.drawString(10 * mm, 15 * mm, _("Payment method"))
        c.drawString(10 * mm, 10 * mm, '{}'.format(invoice.get_payment_type()))
        if page == 1:
            c.setFont("Roboto", 10)
            c.drawCentredString(40 * mm, 4 * mm, '%s' % _("Original invoice"))
            c.showPage()
        else:
            c.setFont("Roboto", 10)
            c.drawCentredString(40 * mm, 4 * mm, '%s' % _("Customer invoice"))
    c.save()
    return response


@staff_member_required
def invoice_filter(request):
    if not request.GET:
        queryset = Invoice.objects.select_related('contact').filter(creation_date=date.today())
    else:
        queryset = Invoice.objects.select_related('contact').all()
    page_number = request.GET.get("p")
    invoice_queryset = queryset.order_by("-id")
    invoice_filter = InvoiceFilter(request.GET, queryset=invoice_queryset)
    paginator = Paginator(invoice_filter.qs, 200)
    try:
        invoices = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        invoices = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        invoices = paginator.page(paginator.num_pages)
    if request.GET.get('export'):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoices_export.csv"'
        writer = csv.writer(response)
        header = [
            _("Id"),
            _("Contact name"),
            _("Subscriptions"),
            _("Amount"),
            _("Payment type"),
            _("Date"),
            _("Due"),
            _("Service from"),
            _("Service to"),
            _("Status"),
            _("Payment date"),
            _("Serie"),
            _("Number"),
            _("Payment reference"),
        ]
        writer.writerow(header)
        for invoice in invoice_filter.qs.iterator():
            products = ""
            for index, invoiceitem in enumerate(invoice.invoiceitem_set.all()):
                if index > 0 and len(products) > 1:
                    products += ", "
                if invoiceitem.product:
                    products += invoiceitem.product.name
            writer.writerow([
                invoice.id,
                invoice.contact.name,
                invoice.get_invoiceitem_description_list(html=False),
                invoice.amount,
                invoice.get_payment_type(),
                invoice.creation_date,
                invoice.expiration_date,
                invoice.service_from,
                invoice.service_to,
                invoice.get_status(with_date=False),
                invoice.payment_date,
                invoice.serie,
                invoice.numero,
                invoice.payment_reference,
            ])
        return response

    invoices_sum = invoice_filter.qs.aggregate(Sum('amount'))['amount__sum']
    invoices_count = invoice_filter.qs.count()

    pending = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__gt=date.today())
    pending_sum = pending.aggregate(Sum('amount'))['amount__sum']
    pending_count = pending.count()

    overdue = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__lte=date.today())
    overdue_sum = overdue.aggregate(Sum('amount'))['amount__sum']
    overdue_count = overdue.count()

    paid = invoice_filter.qs.filter(Q(paid=True) | Q(debited=True))
    paid_sum = paid.aggregate(Sum('amount'))['amount__sum']
    paid_count = paid.count()

    canceled = invoice_filter.qs.filter(canceled=True)
    canceled_sum = canceled.aggregate(Sum('amount'))['amount__sum']
    canceled_count = canceled.count()

    uncollectible = invoice_filter.qs.filter(uncollectible=True)
    uncollectible_sum = uncollectible.aggregate(Sum('amount'))['amount__sum']
    uncollectible_count = uncollectible.count()

    return render(
        request, 'invoice_filter.html', {
            'invoices': invoices,
            'page': page_number,
            'paginator': paginator,
            'invoice_filter': invoice_filter,
            'invoices_count': invoices_count,
            'pending_count': pending_count,
            'overdue_count': overdue_count,
            'paid_count': paid_count,
            'canceled_count': canceled_count,
            'invoices_sum': invoices_sum,
            'paid_sum': paid_sum,
            'pending_sum': pending_sum,
            'overdue_sum': overdue_sum,
            'canceled_sum': canceled_sum,
            'uncollectible_sum': uncollectible_sum,
            'uncollectible_count': uncollectible_count,
        })


@staff_member_required
def force_cancel_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if invoice.canceled:
        messages.error(request, _("Invoice is already canceled"))
    else:
        if invoice.creditnote_set.exists() and invoice.canceled is False:
            invoice.canceled, invoice.cancelation_date = True, date.today()
            invoice.save()
            messages.success(request, _("Invoice was canceled successfully"))
        else:
            messages.error(request, _("Invoice can't be canceled"))
    return HttpResponseRedirect(reverse("admin:invoicing_invoice_change", args=[invoice_id]))
