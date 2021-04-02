# coding=utf-8
import unicodecsv
from datetime import date, timedelta, datetime

from dateutil.relativedelta import relativedelta

from django.urls import reverse
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseServerError, HttpResponseRedirect, HttpResponse
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
from core.models import Contact, Subscription, Product


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

    return render(request, 'contact_invoices.html', {
        'contact': contact, 'invoice_list': invoice_list, 'debt': debt
    })


def bill_subscription(subscription_id, billing_date=date.today(), dpp=10, check_route=False, debug=False):
    """
    Bills a single subscription into an only invoice. Returns the created invoice.
    """
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    contact = subscription.contact
    invoice, invoice_items = None, None

    # Check that the next billing date exists or we need to raise an exception.
    assert subscription.next_billing, (_("Could not bill because next billing date does not exist"))

    # Check that the subscription has a payment type
    assert subscription.payment_type, (_("The subscription has no payment type, it can't be billed"))

    # First we need to check if the subscription has the Normal type, is active, and next billing is less than the
    # selected billing date. This probably has to be filtered in the function that calls this one. But just in case
    # this will be controlled here too. A bypass can be programmed to ignore this
    active = subscription.active
    subscription_type_is_normal = subscription.type == 'N'
    next_billing_lte_billing_date = subscription.next_billing <= billing_date
    if not (active and subscription_type_is_normal and next_billing_lte_billing_date):
        return

    # TODO: SOMETHING HAS TO BE DONE TO NOT BILL SUBSCRIPTIONS IN CERTAIN
    # ROUTES.

    # We need to get all the subscription data. The priority is defined on the settings.
    billing_data = subscription.get_billing_data_by_priority()

    if subscription.next_billing > billing_date + timedelta(1):
        raise Exception(('Next billing date is {}'.format(subscription.next_billing)))

    invoice_items = []
    # We only take the normal subscriptions, not promo or free
    try:
        # First we're going to form all the invoiceitems from the processed products the subscription has.
        # This gives a dictionary with product_id and copies so we need to call the items of said dictionary
        product_summary = subscription.product_summary()
        for product_id, copies in product_summary.items():
            # For each item we're going to make an invoiceitem. These are common for both discounts and subscriptions
            item = InvoiceItem()
            product = Product.objects.get(pk=int(product_id))
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item.description = format_lazy('{} {}', product.name, frequency_extra)
            item.price = product.price * subscription.frequency
            item.product = product
            if product.type == 'S':
                # If the product is a subscription
                copies = int(copies)
                item.type = 'I'  # This means this is a regular item on the invoice
            elif product.type == 'D':
                # If the product is a discount, the copies are 1
                copies = 1
                item.type = 'D'  # This means this is a discount item
                # For a discount, we'll use the type of discount/surcharge of 1, that uses the value
                # instead of a percentage.
                item.type_dr = 1
            item.amount = item.price * item.copies
            # save all the package
            item.save()
            invoice_items.append(item)
        # After adding all of the invoiceitems, we need to check if the subscription has an envelope. In future reviews
        # this should be deprecated and envelopes should be its own product, because here you'd end up adding envelopes
        # to digital products potentially. Fancy digital envelopes huh?
        if subscription.envelope and getattr(settings, 'ENVELOPE_PRICE'):
            envelope_price = settings.ENVELOPE_PRICE
            # Get the amount of days per week the subscription gets the paper
            products_count = subscription.get_product_count()
            # Then we multiply the amount of days by 4.25 (average of weeks per
            # month) and that amount by the price of the envelope
            amount = 4.25 * products_count * envelope_price * subscription.frequency
            # We now pack the value into an InvoiceItem and add it to the list
            envelope_item = InvoiceItem()
            envelope_item.description = _('Envelope')
            envelope_item.amount = amount
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
            discount_amount = round((sub_total * discount_pct) / 100)
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

        # Then we add or subtract the balance if it exists
        if subscription.balance and subscription.balance != 0:
            balance_item = InvoiceItem()
            if subscription.balance > 0:
                balance_item.description = _('Balance')
                # This means the item is a discount.
                balance_item.type = 'D'
                balance_item.amount = float(subscription.balance)
                # 1 means it's a plain value
                balance_item.type_dr = 1
            elif subscription.balance < 0:
                balance_item.description = _('Balance owed')
                # 1 means it's a plain value
                balance_item.type_dr = 1
                # This means the item is a surcharge
                balance_item.type = 'R'
            # We don't want any negative shenanigans so we'll use the absolute.
            balance_item.amount = abs(float(subscription.balance))
            invoice_items.append(balance_item)
            subscription.balance = None
    except Exception as e:
        raise
        raise Exception(e.message)

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
                amount = round(amount)
                invoice_items.append(round_item)

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
                subscription=subscription
            )

            # We add all invoice items to the invoice.
            for item in invoice_items:
                item.invoice = invoice
                item.save()

            # Finally we add the amount to the invoice, so we make sure everything is correct when you try to send them
            # to your preferred electronic invoicing provider.
            invoice.amount = amount
            invoice.save()

            # Move the next billing to how many months it's necessary.
            # If the subscription doesn't have next_billing, we'll create one using the start_date of the subscription.
            # TODO: this collides with the assert at the beginning of this view, is that ok?

            # TODO: Add or remove discounts to the invoice, maybe
            subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
                months=subscription.frequency)
            subscription.save()

            # TODO:
            # - Notes
        except Exception as e:
            raise Exception("Contact {} Subscription {}: {}".format(
                subscription.contact.id, subscription.id, e.message))
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
        for subscription in contact.subscriptions.filter(active=True, next_billing__lte=date.today()):
            try:
                bill_subscription(subscription.id, creation_date, dpp)
            except Exception as e:
                # TODO: Use a fancier error page
                return HttpResponse(e.message)
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


@staff_member_required
def cancel_invoice(request, invoice_id):
    """
    Marks the invoice as canceled with today's date.
    Generates a credit note.
    """
    i = Invoice.objects.get(pk=invoice_id)
    if i.canceled:
        return HttpResponseServerError(_('Invoice already canceled'))
    n = CreditNote(invoice_id=invoice_id)
    return render(request, 'cancel_invoice.html', {
        'invoice_id': invoice_id,
        'credit_note': n
    })


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
        c.drawString(10 * mm, height - 50 * mm, u'{}'.format(invoice.contact.name))
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
        queryset = Invoice.objects.filter(creation_date=date.today())
    else:
        queryset = Invoice.objects.all()
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
        writer = unicodecsv.writer(response)
        header = [
            _("Id"),
            _("Contact name"),
            _("Subscriptions"),
            _("Amount"),
            _("Payment type"),
            _("Date"),
            _("Due"),
            _("Status"),
            _("Serie"),
            _("Number"),
        ]
        writer.writerow(header)
        for invoice in invoice_filter.qs.all():
            writer.writerow([
                invoice.id,
                invoice.contact.name,
                invoice.subscription.show_products_html(br=False) if invoice.subscription else None,
                invoice.amount,
                invoice.get_payment_type(),
                invoice.creation_date,
                invoice.expiration_date,
                invoice.get_status(),
                invoice.serie,
                invoice.numero,
            ])
        return response
    invoices_count = invoice_filter.qs.count()
    pending_count = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__gt=date.today()).count()
    overdue_count = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__lte=date.today()).count()
    paid_count = invoice_filter.qs.filter(Q(paid=True) | Q(debited=True)).count()
    canceled_count = invoice_filter.qs.filter(canceled=True).count()
    uncollectible_count = invoice_filter.qs.filter(uncollectible=True).count()
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
            'uncollectible_count': uncollectible_count,
        })
