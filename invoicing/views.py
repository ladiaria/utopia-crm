# coding=utf-8
import csv
from datetime import date, datetime


from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Sum, Min, Max, Prefetch
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

from django_filters.views import FilterView

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from .filters import InvoiceFilter
from .forms import InvoiceForm, InvoiceItemFormSet
from invoicing.models import Invoice, InvoiceItem, Billing, CreditNote
from core.models import Contact, Product
from core.mixins import BreadcrumbsMixin


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


@staff_member_required
def bill_subscriptions_for_one_contact(request, contact_id):
    """
    Bills all subscriptions for a single contact. If the contact has more than one active subscription, it will
    generate more than one invoice.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    active_subscriptions = contact.subscriptions.filter(active=True, type="N", next_billing__lte=date.today())

    # Precompute subscription prices
    subscriptions_with_prices = []
    for subscription in active_subscriptions:
        price = subscription.get_price_for_full_period()  # Call it once per subscription
        subscriptions_with_prices.append({
            'subscription': subscription,
            'price': price,
        })

    if request.POST.get('creation_date'):
        creation_date = request.POST.get('creation_date', date.today())
        creation_date = datetime.strptime(creation_date, "%Y-%m-%d").date()
        dpp = request.POST.get('dpp', 10)
        for subscription in contact.subscriptions.filter(active=True, next_billing__lte=creation_date):
            try:
                invoice = subscription.bill(creation_date, dpp)
            except Exception as e:
                messages.error(request, e)
            else:
                messages.success(request, _("Invoice {} has been created successfully".format(invoice.id)))
        return HttpResponseRedirect(reverse("contact_detail", args=(contact_id,)) + "#invoices")
    breadcrumbs = [
        {"label": _("Home"), "url": reverse("home")},
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": contact.get_full_name(),
            "url": reverse("contact_detail", args=[contact.id]) + "#invoices",
        },
        {"label": _("Invoice detail"), "url": ""},
    ]
    return render(
        request,
        'bill_subscriptions_for_one_contact.html',
        {
            'contact': contact,
            'today': date.today(),
            'breadcrumbs': breadcrumbs,
            'active_subscriptions': active_subscriptions,
            'subscriptions_with_prices': subscriptions_with_prices,
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


def check_fonts():
    # to test:
    # >>> from invoicing.views import check_fonts
    # >>> open("/tmp/check_fonts.pdf", "w+b").write(check_fonts().content)
    response = HttpResponse(content_type='application/pdf')
    c = Canvas(response, pagesize=(80 * mm, 110 * mm))
    c.setFont("Roboto", 12)
    c.drawString(10 * mm, 10 * mm, "Hello, world!")
    c.save()
    return response


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
        c.drawString(
            10 * mm, height - 35 * mm, _('Issue date: {date}').format(date=invoice.creation_date.strftime("%d/%m/%Y"))
        )
        c.drawString(
            10 * mm, height - 40 * mm, _('Due date: {date}').format(date=invoice.expiration_date.strftime("%d/%m/%Y"))
        )
        c.drawString(10 * mm, height - 50 * mm, f"{invoice.contact.get_full_name()}")
        c.setFont("Roboto", 5)
        table_data = []
        table_data.append((_('Item'), _('Un.'), _('Price'), _('Total')))
        if getattr(settings, 'USE_SQUASHED_SUBSCRIPTION_INVOICEITEMS', False) and invoice.subscription:
            product = _('Subscription {id}').format(id=invoice.subscription.id)
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
        c.drawString(10 * mm, 10 * mm, f"{invoice.get_payment_type()}")
        if page == 1:
            c.setFont("Roboto", 10)
            c.drawCentredString(40 * mm, 4 * mm, _("Original invoice"))
            c.showPage()
        else:
            c.setFont("Roboto", 10)
            c.drawCentredString(40 * mm, 4 * mm, _("Customer invoice"))
    c.save()
    return response


@method_decorator(staff_member_required, name='dispatch')
class InvoiceFilterView(BreadcrumbsMixin, FilterView):
    model = Invoice
    template_name = 'invoice_filter.html'
    filterset_class = InvoiceFilter
    paginate_by = 200
    page_kwarg = 'p'
    context_object_name = 'invoices'

    def breadcrumbs(self):
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Invoice filter"), "url": ""},
        ]

    def get_queryset(self):
        return Invoice.objects.all().select_related(
            'contact', 'subscription'
        ).prefetch_related(
            'invoiceitem_set',
        ).order_by('-id')

    def get(self, request, *args, **kwargs):
        if not request.GET:
            return HttpResponseRedirect('?creation_date=today')
        if request.GET.get('export'):
            return self.export_csv()
        return super().get(request, *args, **kwargs)

    def export_csv(self):
        import io

        filterset = self.get_filterset(self.filterset_class)

        def generate_csv_rows():
            buffer = io.StringIO()
            writer = csv.writer(buffer)

            header = [
                _("Id"),
                _("Contact name"),
                _("Items"),
                _("Contact id"),
                _("ID document"),
                _("Email"),
                _("Phone"),
                _("Mobile"),
                _("Subscription id"),
                _("Subscription Payment Type"),
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
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

            for invoice in filterset.qs.select_related('contact', 'subscription').iterator(chunk_size=1000):
                writer.writerow(
                    [
                        invoice.id,
                        invoice.contact.get_full_name(),
                        invoice.get_invoiceitem_description_list(html=False),
                        invoice.contact.id,
                        invoice.contact.id_document,
                        invoice.contact.email,
                        str(invoice.contact.phone) if invoice.contact.phone else "",
                        str(invoice.contact.mobile) if invoice.contact.mobile else "",
                        invoice.subscription.id if invoice.subscription else None,
                        invoice.subscription.get_payment_type_display() if invoice.subscription else None,
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
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

        response = StreamingHttpResponse(generate_csv_rows(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoices_export.csv"'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtered_qs = context['filter'].qs

        invoices_sum = filtered_qs.aggregate(Sum('amount'))['amount__sum']
        invoices_count = filtered_qs.count()

        pending = filtered_qs.filter(
            canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__gt=date.today()
        )
        pending_sum = pending.aggregate(Sum('amount'))['amount__sum']
        pending_count = pending.count()

        overdue = filtered_qs.filter(
            canceled=False, uncollectible=False, paid=False, debited=False, expiration_date__lt=date.today()
        )
        overdue_sum = overdue.aggregate(Sum('amount'))['amount__sum']
        overdue_count = overdue.count()

        paid = filtered_qs.filter(Q(paid=True) | Q(debited=True))
        paid_sum = paid.aggregate(Sum('amount'))['amount__sum']
        paid_count = paid.count()

        canceled = filtered_qs.filter(canceled=True)
        canceled_sum = canceled.aggregate(Sum('amount'))['amount__sum']
        canceled_count = canceled.count()

        uncollectible = filtered_qs.filter(uncollectible=True)
        uncollectible_sum = uncollectible.aggregate(Sum('amount'))['amount__sum']
        uncollectible_count = uncollectible.count()

        date_range = filtered_qs.aggregate(
            oldest_date=Min('creation_date'),
            newest_date=Max('creation_date'),
        )

        context.update({
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
            'oldest_date': date_range['oldest_date'],
            'newest_date': date_range['newest_date'],
        })
        return context


# Keep backward compatibility
invoice_filter = InvoiceFilterView.as_view()


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
        if settings.DEBUG:
            print(f"DEBUG: InvoiceNonSubscriptionCreateView: formset={formset}")
        if form.is_valid() and formset.is_valid():
            products = []
            for sub_form in formset:
                product = sub_form.cleaned_data.get('product')
                if product:
                    products.append(product)
            self.object = self.contact.add_single_invoice_with_products(products)
            return super().form_valid(form)
        else:
            if settings.DEBUG:
                print(f"DEBUG: InvoiceNonSubscriptionCreateView: form.errors={form.errors}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('contact_invoices', args=[self.contact_id])


class InvoiceDetailView(BreadcrumbsMixin, LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoice/invoice_detail.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            discount_total=Sum('invoiceitem__amount', filter=Q(invoiceitem__type='D')),
            product_total=Sum('invoiceitem__amount', filter=Q(invoiceitem__type='I')),
        ).select_related('contact', 'subscription').prefetch_related(
            Prefetch(
                'invoiceitem_set',
                queryset=InvoiceItem.objects.filter(type='I').select_related('product', 'product__target_product'),
                to_attr='product_items'
            ),
            Prefetch(
                'invoiceitem_set',
                queryset=InvoiceItem.objects.filter(type='D').select_related('product', 'product__target_product'),
                to_attr='discount_items'
            ),
            Prefetch(
                'subscription__subscriptionproduct_set__product',
                queryset=Product.objects.select_related('target_product')
            ),
            'creditnote_set',
        )
        return queryset

    def breadcrumbs(self):
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {
                "label": self.object.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.object.contact.id]) + "#invoices",
            },
            {"label": _("Invoice detail"), "url": ""},
        ]
