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
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy
from django.views.generic import CreateView
from django.db import transaction
from django.utils.decorators import method_decorator

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from .filters import InvoiceFilter
from .forms import InvoiceForm, InvoiceItemFormSet
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

    return render(request, 'contact_invoices.html', {'contact': contact, 'invoice_list': invoice_list, 'debt': debt})


def bill_subscription(subscription_id, billing_date=None, dpp=10, check_route=False, debug=False):
    """
    # TODO: debug arg is not used, use/remove it.
    Bills a single subscription into an only invoice. Returns the created invoice.
    """
    billing_date = billing_date or date.today()
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    contact = subscription.contact
    invoice, invoice_items, balance_item = None, None, None

    # Check that the subscription is active
    assert subscription.active, _('This subscription is not active and should not be billed.')

    # Check that the subscription is normal
    assert subscription.type == 'N', _('This subscription is not normal and should not be billed.')

    # Check that the next billing date exists or we need to raise an exception.
    assert subscription.next_billing, _("Could not bill because next billing date does not exist")

    # Check that the subscription has a payment type
    assert subscription.payment_type, _("The subscription has no payment type, it can't be billed")

    # Check that the subscription's next billing is smaller than end date if it has it
    if subscription.end_date:
        error_msg = _("This subscription has an end date greater than its next billing")
        assert subscription.next_billing < subscription.end_date, error_msg

    if subscription.next_billing > billing_date + timedelta(settings.BILLING_EXTRA_DAYS):
        raise Exception(_('This subscription should not be billed yet.'))

    # We need to get all the subscription data. The priority is defined in the billing_priority column of the product.
    # If this first product doesn't have the required data, then we can't bill the subscription.
    billing_data = subscription.get_billing_data_by_priority()

    if not billing_data and not getattr(settings, "FORCE_DUMMY_MISSING_BILLING_DATA", False):
        raise Exception(
            "Subscription {} for contact {} contains no billing data.".format(subscription.id, subscription.contact.id)
        )

    if billing_data and billing_data["address"] is None:
        raise Exception(
            "Subscription {} for contact {} requires an address to be billed.".format(
                subscription.id, subscription.contact.id
            )
        )

    if billing_data and settings.REQUIRE_ROUTE_FOR_BILLING:
        if billing_data["route"] is None:
            raise Exception(
                "Subscription {} for contact {} requires a route to be billed.".format(
                    subscription.id, subscription.contact.id
                )
            )

        elif billing_data["route"] in settings.EXCLUDE_ROUTES_FROM_BILLING_LIST:
            raise Exception(
                "Subscription {} for contact {} can't be billed since it's on route {}.".format(
                    subscription.id, subscription.contact.id, billing_data["route"]
                )
            )

    invoice_items = []

    # TODO: the same calculation code is repeated in utils.calc_price_from_products, but here we need to add items,
    #       we can somehow pass the invoice to that function to deduplicate calculation code, for example.
    # First we're going to form all the invoiceitems from the processed products the subscription has.
    # This gives a dictionary with product_id and copies so we need to call the items of said dictionary
    percentage_discount_product = None
    product_summary = subscription.product_summary(with_pauses=True)
    all_list, discount_list, non_discount_list, advanced_discount_list = product_summary.items(), [], [], []

    # 1. partition the input by discount products / non discount products
    for product_id, copies in all_list:
        try:
            product = Product.objects.get(pk=int(product_id))
        except Product.DoesNotExist:
            pass
        else:
            (non_discount_list if product.type in ('S', 'O') else discount_list).append(product)

    # 2. obtain 2 total cost amounts: affectable/non-affectable by discounts
    subtotal_affectable, subtotal_non_affectable = 0.0, 0.0
    for product in non_discount_list:
        copies = int(product_summary[product.id])

        if getattr(settings, 'DEBUG_PRODUCTS', False):
            print(
                f"{product.name} {copies}x{'-' if product.type == 'D' else ''}"
                f"{product.price} = {'-' if product.type == 'D' else ''}{product.price * copies}"
            )

        # For each product we're making an invoiceitem. Items of frequency 4 are one-shot products, so we'll remove
        # them from the subscription after billing them. They also don't have a frequency, so we'll bill them once.
        item = InvoiceItem()
        frequency_extra = (
            _(' {} months'.format(subscription.frequency))
            if subscription.frequency > 1 and product.edition_frequency != 4
            else ''
        )
        item.description = format_lazy('{} {}', product.name, frequency_extra)
        item.price = product.price * subscription.frequency if product.edition_frequency != 4 else product.price
        item.product = product
        item.copies = copies
        item.type = 'I'  # This means this is a regular item on the invoice
        item.amount = item.price * item.copies
        # save all the package
        invoice_items.append(item)

        # check first if this product is affected to any of the discounts
        affectable = False
        for discount_product in [d for d in discount_list if d.target_product == product]:
            item_discount = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item_discount.description = format_lazy('{} {}', discount_product.name, frequency_extra)
            item_discount.price = discount_product.price * subscription.frequency
            item_discount.product = discount_product
            item_discount.copies = int(product_summary[discount_product.id])
            item_discount.type = "D"
            affectable_delta = float(item.amount)
            if discount_product.type == "D":
                item_discount.type_dr = 1
                affectable_delta -= float(item_discount.price * item_discount.copies)
            elif discount_product.type == "P":
                affectable_delta_discount = (affectable_delta * float(discount_product.price)) / 100
                affectable_delta -= affectable_delta_discount
            item_discount.amount = item_discount.price * item_discount.copies
            subtotal_affectable += affectable_delta
            invoice_items.append(item_discount)
            discount_list.remove(discount_product)
            affectable = True
            break
        if not affectable:
            # not affected by discounts but the product price can be also "affectable" if has_implicit_discount
            product_delta = float(item.amount)
            if product.has_implicit_discount:
                subtotal_affectable += product_delta
            else:
                subtotal_non_affectable += product_delta

    # 3. iterate over discounts left
    for product in discount_list:
        if product.type == 'D':
            item = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item.description = format_lazy('{} {}', product.name, frequency_extra)
            item.price = product.price * subscription.frequency
            item.product = product
            item.copies = int(product_summary[product.id])
            item.type = 'D'  # This means this is a discount item
            # We'll use the type of discount/surcharge of 1, that uses the numeric value instead of a percentage.
            item.type_dr = 1
            item.amount = item.price * item.copies
            # save all the package
            invoice_items.append(item)
            subtotal_non_affectable -= float(item.amount)
        elif product.type == 'P':
            # If it's a percentage discount we'll save it for last, after the entire price has been calculated
            percentage_discount_product = product
        elif product.type == 'A':
            # if it's an advanced discount, save it for last too
            advanced_discount_list.append(product)

    # After calculating the prices of the product, we check out every product in the advanced_discount_list
    # TODO: this must be tested
    for discount_product in advanced_discount_list:
        try:
            advanced_discount = AdvancedDiscount.objects.get(discount_product=discount_product)
        except AdvancedDiscount.DoesNotExist:
            continue
        else:
            if advanced_discount.value_mode == 1:
                discounted_product_price = advanced_discount.value
            else:
                discounted_product_price = 0
                for product in advanced_discount.find_products.all():
                    if product.id in product_summary:
                        if product.type == 'S':
                            discounted_product_price += int(product_summary[product.id]) * product.price
                        else:
                            discounted_product_price -= int(product_summary[product.id]) * product.price
                discounted_product_price = (discounted_product_price * advanced_discount.value) / 100
            item = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item.description = format_lazy('{} {}', discount_product.name, frequency_extra)
            item.price = discounted_product_price  # This is to calculate the $
            item.type = 'D'
            item.type_dr = 1
            item.product = discount_product
            item.copies = 1
            item.amount = item.price  # Copies is 1 so this is also the amount
            invoice_items.append(item)
            subtotal_non_affectable -= item.amount

    if percentage_discount_product:
        # Then if we have the percentage discount, we'll calculate how much it is. We do this last to make sure
        # the price is calculated with the entire sum of the subscription
        item = InvoiceItem()
        frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
        item.description = format_lazy('{} {}', percentage_discount_product.name, frequency_extra)
        item.price = (subtotal_non_affectable * float(percentage_discount_product.price)) / 100  # calculate the $
        item.type = 'D'
        item.type_dr = 1
        item.product = percentage_discount_product
        item.copies = 1
        item.amount = item.price  # Copies is 1 so this is also the amount
        subtotal_non_affectable -= item.amount
        invoice_items.append(item)

    # After adding all of the invoiceitems, we need to check if the subscription has an envelope. In future reviews
    # this should be deprecated and envelopes should be its own product, because here you'd end up adding envelopes
    # to digital products potentially. Fancy digital envelopes huh?
    if (
        hasattr(settings, 'ENVELOPE_PRICE')
        and SubscriptionProduct.objects.filter(subscription=subscription, has_envelope=1).exists()
    ):
        envelope_price = settings.ENVELOPE_PRICE
        # Get the amount of days per week the subscription gets the paper
        products_with_envelope_count = SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1
        ).count()
        # Then we multiply the amount of days by 4.25 (average of weeks per
        # month) and that amount by the price of the envelope
        amount = products_with_envelope_count * envelope_price * subscription.frequency
        # We now pack the value into an InvoiceItem and add it to the list
        envelope_item = InvoiceItem()
        envelope_item.description = _('Envelope')
        envelope_item.amount = amount
        envelope_item.subscription = subscription
        invoice_items.append(envelope_item)
        subtotal_affectable += envelope_item.amount

    expiration_date = billing_date + timedelta(int(dpp))
    service_from = subscription.next_billing

    # check if it is necessary to add discounts by frequency.
    discount_pct = subscription.get_frequency_discount()
    if discount_pct:
        # Pack the discount invoiceitem and add it to the list
        frequency_discount_item = InvoiceItem()
        frequency_discount_item.description = _(
            '{} months discount ({} discount)'.format(subscription.frequency, discount_pct)
        )
        frequency_discount_item.amount = (subtotal_non_affectable * discount_pct) / 100
        # 1 means it's a plain value. This is just in case you want to use percentage discounts.
        frequency_discount_item.type_dr = 1
        # This means the item is a discount.
        frequency_discount_item.type = 'D'
        invoice_items.append(frequency_discount_item)
        subtotal_non_affectable -= frequency_discount_item.amount

    if invoice_items:
        try:
            amount = subtotal_affectable + subtotal_non_affectable

            # After we calculated the invoice amount, we'll make sure the balance item isn't
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
                    amount -= float(balance_item.amount)  # And then we subtract that value from the invoice
                elif subscription.balance < 0:
                    # If the balance is negative, it means the person owes us money, we'll make a surcharge.
                    balance_item.description = _('Balance owed')
                    balance_item.type_dr = 1  # 1 means it's a plain value
                    balance_item.type = 'R'  # This means the item is a surcharge
                    balance_item.amount = abs(subscription.balance)  # The entire balance is applied to the item
                    amount += float(balance_item.amount)  # And then we add that value to the invoice
                # We don't want any negative shenanigans so we'll use the absolute.
                balance_item.amount = abs(balance_item.amount)
                invoice_items.append(balance_item)

            # Finally we make the rounding and add the invoiceitem needed. This had to be changed to be made after the
            # balance because this was causing to make the invoices to have decimal places.
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

            # If the subscription doesn't have next_billing, we'll create one using the start_date of the subscription.

            payment_method = subscription.payment_type

            # Meanwhile we'll create the invoice object
            if amount > 0:
                invoice = Invoice.objects.create(
                    contact=contact,
                    payment_type=payment_method,
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
                    billing_document=subscription.get_billing_document(),
                    subscription=subscription,
                    amount=amount,
                )

                # We add all invoice items to the invoice. We need to remove the products that are one-shot
                for item in invoice_items:
                    item.save()
                    invoice.invoiceitem_set.add(item)
                    if item.product.edition_frequency == 4:  # One-shot
                        invoice.subscription.remove_product(item.product)

                # When the invoice has finally been created and every date has been moved where it should have been,
                # we're going to check if there's any temporary discounts, and remove them if it applies.
                ii_qs = invoice.invoiceitem_set.filter(product__temporary_discount_months__gte=1)
                for ii in ii_qs:
                    temporary_discount = ii.product
                    months = temporary_discount.temporary_discount_months
                    if invoice.subscription.months_in_invoices_with_product(temporary_discount.slug) >= months:
                        invoice.subscription.remove_product(temporary_discount)


            # Then finally we need to change everything on the subscription
            if subscription.balance:
                if subscription.balance > 0 and balance_item:
                    subscription.balance -= balance_item.amount  # Then subtract the balance
                if subscription.balance <= 0:
                    subscription.balance = None  # Then if it is zero or less, remove it completely.
            subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
                months=subscription.frequency
            )
            subscription.save()
            # We do this here because we also need to change the subscription dates even if the amount is 0, but
            # we don't want to execute anything of this if the invoice creation process failed for whatever reason.
            assert amount, _("This subscription wasn't billed since amount is 0")

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
                messages.error(request, e)
            else:
                messages.success(request, _("Invoice {} has been created successfully".format(invoice.id)))
        return HttpResponseRedirect(reverse("contact_invoices", args=(contact_id,)))
    else:
        return render(
            request,
            'bill_subscriptions_for_one_contact.html',
            {
                'contact': contact,
                'today': date.today(),
            },
        )


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

    return render(
        request,
        'billing_invoices.html',
        {
            'billing': billing,
            'invoice_list': invoice_list,
        },
    )


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
    table_style = TableStyle(
        [
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]
    )
    for page in range(1, 3):
        c.setFont("Roboto", 12)
        c.drawImage(
            settings.INVOICE_LOGO, 17 * mm, height - 38 * mm, width=40 * mm, preserveAspectRatio=True, mask='auto'
        )
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
            writer.writerow(
                [
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
                ]
            )
        return response

    invoices_sum = invoice_filter.qs.aggregate(Sum('amount'))['amount__sum']
    invoices_count = invoice_filter.qs.count()

    pending = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__gt=date.today()
    )
    pending_sum = pending.aggregate(Sum('amount'))['amount__sum']
    pending_count = pending.count()

    overdue = invoice_filter.qs.filter(
        canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__lte=date.today()
    )
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
        request,
        'invoice_filter.html',
        {
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
        },
    )


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


@method_decorator(staff_member_required, name='dispatch')
class InvoiceNonSubscriptionCreateView(CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'invoice_non_subscription_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contact_id = kwargs.get('contact_id')
        if self.contact_id:
            self.contact = get_object_or_404(Contact, pk=self.contact_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = InvoiceItemFormSet(self.request.POST)
        else:
            data['formset'] = InvoiceItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        print(formset)
        if form.is_valid() and formset.is_valid():
            products = []
            for sub_form in formset:
                product = sub_form.cleaned_data.get('product')
                if product:
                    products.append(product)
            self.object = self.contact.add_single_invoice_with_products(products)
            return super().form_valid(form)
        else:
            print(form.errors)
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('contact_invoices', args=[self.contact_id])
