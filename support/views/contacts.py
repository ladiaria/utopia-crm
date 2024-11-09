import csv
import pandas as pd
from datetime import date
from functools import reduce
from operator import or_

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.views.generic import UpdateView, CreateView, DetailView, ListView, FormView
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.views.decorators.http import require_POST

from core.models import (
    Contact,
    Subscription,
    Product,
    MailtrainList,
    update_web_user_newsletters,
    State,
    Country,
    Address,
)
from core.filters import ContactFilter
from core.forms import ContactAdminForm
from core.mixins import BreadcrumbsMixin
from core.utils import get_mailtrain_lists

from support.forms import ImportContactsForm


@method_decorator(staff_member_required, name="dispatch")
class ContactListView(ListView):
    # Implementation of ListView to work without the need of a FilterView. It still uses django-filter for the filter.
    model = Contact
    template_name = "contact_list.html"
    filterset_class = ContactFilter
    paginate_by = 50
    page_kwarg = "p"

    def get(self, request, *args, **kwargs):
        if request.GET.get("export"):
            return self.export_csv()
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("subscriptions", "activity_set").select_related()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        return context

    def export_csv(self):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="contacts_export.csv"'
        writer = csv.writer(response)
        header = [
            _("Id"),
            _("Full name"),
            _("Email"),
            _("Phone"),
            _("Mobile"),
            _("Has active subscriptions"),
            _("Active products"),
            _("Last activity"),
            _("Overdue invoices"),
            _("Address"),
            _("State"),
            _("City"),
        ]
        writer.writerow(header)
        for contact in self.get_queryset().all():
            active_products, address_1, state, city = "", "", "", ""
            for index, sp in enumerate(contact.get_active_subscriptionproducts()):
                if index > 0:
                    active_products += ", "
                active_products += sp.product.name
            first_subscription = contact.get_first_active_subscription()
            if first_subscription:
                address = first_subscription.get_full_address_by_priority()
                if address:
                    address_1, state, city = address.address_1, address.state_name, address.city
            writer.writerow(
                [
                    contact.id,
                    contact.get_full_name(),
                    contact.email,
                    contact.phone,
                    contact.mobile,
                    contact.has_active_subscription(),
                    active_products,
                    contact.last_activity().datetime if contact.last_activity() else None,
                    contact.expired_invoices_count(),
                    address_1,
                    state,
                    city,
                ]
            )
        return response


@method_decorator(staff_member_required, name="dispatch")
class ContactDetailView(BreadcrumbsMixin, DetailView):
    model = Contact
    template_name = "contact_detail/detail.html"

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": self.object.get_full_name(), "url": reverse("contact_detail", args=[self.object.id])},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["georef_activated"] = getattr(settings, "GEOREF_SERVICES", False)
        context["subscription_groups"] = self.get_subscription_groups()
        context["overview_subscriptions"] = self.get_overview_subscriptions()
        # Unpack all querysets
        context.update(self.get_all_querysets_and_lists())
        # Unpack subscriptions for overview
        context.update(self.get_overview_subscriptions())
        context["invoices"] = self.get_invoices()
        return context

    def get_invoices(self):
        return self.object.invoice_set.all().prefetch_related("invoiceitem_set")

    def get_all_querysets_and_lists(self):
        return {
            "addresses": self.object.addresses.all(),
            "activities": self.object.activity_set.all().order_by("-datetime", "id")[:3],
            "newsletters": self.object.get_newsletters(),
            "issues": self.object.issue_set.all().order_by("-date", "id")[:3],
            "last_paid_invoice": self.object.get_last_paid_invoice(),
            "all_activities": self.object.activity_set.all().order_by("-datetime", "id"),
            "all_issues": self.object.issue_set.all().order_by("-date", "id"),
            "all_scheduled_tasks": self.object.scheduledtask_set.all().order_by("-creation_date", "id"),
            "all_campaigns": self.object.contactcampaignstatus_set.all().order_by("-date_created", "id"),
        }

    def get_overview_subscriptions(self):
        active_subscriptions = Subscription.objects.filter(contact=self.object, active=True).exclude(status="AP")
        future_subscriptions = Subscription.objects.filter(
            contact=self.object, active=False, start_date__gte=date.today()
        ).exclude(status="AP")
        awaiting_payment_subscriptions = Subscription.objects.filter(contact=self.object, status="AP")
        overview_subscriptions_count = (
            active_subscriptions.count() + future_subscriptions.count() + awaiting_payment_subscriptions.count()
        )
        return {
            "active_subscriptions": active_subscriptions,
            "future_subscriptions": future_subscriptions,
            "awaiting_payment_subscriptions": awaiting_payment_subscriptions,
            "overview_subscriptions_count": overview_subscriptions_count,
        }

    def get_subscription_groups(self):
        subscription_groups = [
            {
                'title': _("Active subscriptions"),
                'subscriptions': self.object.subscriptions.filter(active=True).exclude(status="AP"),
                'collapsed': False,
            },
            {
                'title': _("Future Subscriptions"),
                'subscriptions': self.object.subscriptions.filter(active=False, start_date__gte=date.today()).exclude(
                    status__in=("AP", "ER")
                ),
                'collapsed': False,
            },
            {
                'title': _("Subscriptions awaiting payment"),
                'subscriptions': self.object.subscriptions.filter(status="AP"),
                'collapsed': True,
            },
            {
                'title': _("Subscriptions with errors"),
                'subscriptions': self.object.subscriptions.filter(status="ER"),
                'collapsed': True,
            },
            {
                'title': _("Paused Subscriptions"),
                'subscriptions': self.object.subscriptions.filter(status="PA"),
                'collapsed': True,
            },
            {
                'title': _("Inactive subscriptions"),
                'subscriptions': self.object.subscriptions.filter(active=False, start_date__lt=date.today()).exclude(
                    status__in=("AP", "ER")
                ),
                'collapsed': True,
            },
        ]
        return subscription_groups


@method_decorator(staff_member_required, name="dispatch")
class ContactUpdateView(BreadcrumbsMixin, UpdateView):
    model = Contact
    form_class = ContactAdminForm
    template_name = "create_contact/create_contact.html"
    success_url = reverse_lazy("contact_list")

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": self.object.get_full_name(), "url": reverse("contact_detail", args=[self.object.id])},
            {"label": _("Edit"), "url": ""},
        ]

    def form_valid(self, form):
        skip_clean_set = False
        if not getattr(self.object, "_skip_clean", False):
            self.object._skip_clean, skip_clean_set = True, True
        try:
            form.save()
        except Exception as e:
            if skip_clean_set:
                del self.object._skip_clean
            messages.error(self.request, "Error: {}".format(e))
        else:
            if skip_clean_set:
                del self.object._skip_clean
            messages.success(self.request, self.get_success_message())
        return super().form_valid(form)

    def get_success_message(self):
        return _("Contact saved successfully")

    def get_success_url(self):
        return reverse("contact_detail", args=[self.object.id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_newsletters"] = Product.objects.filter(type="N", active=True)
        context["contact_newsletters"] = self.object.get_newsletter_products()
        context["mailtrain_lists"] = MailtrainList.objects.filter(is_active=True)
        context["contact_mailtrain_lists"] = get_mailtrain_lists(self.object.email)
        return context


@method_decorator(staff_member_required, name="dispatch")
class ContactCreateView(BreadcrumbsMixin, CreateView):
    model = Contact
    form_class = ContactAdminForm
    template_name = "create_contact/create_contact.html"
    success_url = reverse_lazy("contact_list")

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": _("Create"), "url": ""},
        ]

    def get_success_url(self) -> str:
        return reverse("contact_detail", args=[self.object.id])


@require_POST
@staff_member_required
def edit_newsletters(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    all_newsletters = Product.objects.filter(type="N", active=True)

    # Track which newsletters changed
    newsletter_changes = []
    for newsletter in all_newsletters:
        has_newsletter = contact.has_newsletter(newsletter.id)
        should_have = bool(request.POST.get(str(newsletter.id)))

        if has_newsletter != should_have:
            if should_have:
                contact.add_newsletter(newsletter.id)
            else:
                contact.remove_newsletter(newsletter.id)
            newsletter_changes.append(newsletter.id)

    if newsletter_changes:
        update_web_user_newsletters(contact)
        messages.success(request, _("Newsletters edited successfully"))
        return HttpResponseRedirect(reverse("edit_contact", args=[contact_id]))

    return HttpResponseNotFound()


@method_decorator(staff_member_required, name="dispatch")
class ImportContactsView(FormView):
    template_name = 'import_contacts.html'
    form_class = ImportContactsForm
    success_url = reverse_lazy('import_contacts')

    def get_address_column_names(self):
        return ['address_1', 'address_2', 'city', 'state', 'country']

    def form_valid(self, form):
        csv_file = form.cleaned_data['file']
        tags = self.parse_tags(form.cleaned_data)

        results = self.process_csv(csv_file, tags)

        self.display_messages(results)

        return super().form_valid(form)

    def parse_tags(self, cleaned_data):
        tag_types = ['tags', 'tags_existing', 'tags_active', 'tags_in_campaign']
        return {tag_type: [tag.strip() for tag in cleaned_data.get(tag_type, '').split(',')] for tag_type in tag_types}

    def process_csv(self, csv_file, tags):
        results = {
            'new_contacts': [],
            'in_active_campaign': [],
            'active_contacts': [],
            'existing_inactive_contacts': [],
            'errors': [],
            'added_emails': 0,
            'added_phones': 0,
            'added_mobiles': 0,
        }

        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            results['errors'].append(str(e))
            return results

        for index, row in df.iterrows():
            try:
                contact_data = self.parse_row(row)
                self.process_contact(contact_data, tags, results)
            except Exception as e:
                results['errors'].append(
                    f"CSV Row {index + 2}: {e}"
                )  # +2 because pandas index starts at 0 and we want to account for header

        return results

    def parse_row(self, row, use_headers=False):
        # TODO: Allow this to be configured through the settings or the UI
        if use_headers:
            return {
                'name': row['name'],
                'last_name': row['last_name'] if pd.notna(row['last_name']) else "",
                'email': row['email'].lower() if pd.notna(row['email']) else None,
                'phone': str(row['phone']) if pd.notna(row['phone']) else "",
                'mobile': str(row['mobile']) if pd.notna(row['mobile']) else "",
                'notes': row['notes'].strip() if pd.notna(row['notes']) else None,
                'address_1': row['address_1'] if pd.notna(row['address_1']) else None,
                'address_2': row['address_2'] if pd.notna(row['address_2']) else None,
                'city': row['city'] if pd.notna(row['city']) else None,
                'state': row['state'].strip() if pd.notna(row['state']) else None,
                'country': row['country'] if pd.notna(row['country']) else None,
                'id_document_type': row['id_document_type'] if pd.notna(row['id_document_type']) else None,
                'id_document': row['id_document'] if pd.notna(row['id_document']) else None,
                'ranking': row['ranking'] if pd.notna(row['ranking']) else None,
            }
        else:
            return {
                'name': row.iloc[0],
                'last_name': row.iloc[1] if pd.notna(row.iloc[1]) else "",
                'email': row.iloc[2].lower() if pd.notna(row.iloc[2]) else None,
                'phone': str(row.iloc[3]) if pd.notna(row.iloc[3]) else "",
                'mobile': str(row.iloc[4]) if pd.notna(row.iloc[4]) else "",
                'notes': row.iloc[5].strip() if pd.notna(row.iloc[5]) else None,
                'address_1': row.iloc[6] if pd.notna(row.iloc[6]) else None,
                'address_2': row.iloc[7] if pd.notna(row.iloc[7]) else None,
                'city': row.iloc[8] if pd.notna(row.iloc[8]) else None,
                'state': row.iloc[9].strip() if pd.notna(row.iloc[9]) else None,
                'country': row.iloc[10] if pd.notna(row.iloc[10]) else None,
                'id_document_type': row.iloc[11] if pd.notna(row.iloc[11]) else None,
                'id_document': row.iloc[12] if pd.notna(row.iloc[12]) else None,
                'ranking': row.iloc[13] if pd.notna(row.iloc[13]) else None,
            }

    @transaction.atomic
    def process_contact(self, contact_data, tags, results):
        matches = self.find_matching_contacts(contact_data)

        if matches.exists():
            self.update_existing_contacts(matches, contact_data, tags, results)
        else:
            self.create_new_contact(contact_data, tags, results)

    def find_matching_contacts(self, contact_data):
        # Build a list of Q objects for fields that are not empty (email, phone, or mobile)
        conditions = [
            Q(**{field: contact_data[field]}) for field in ['email', 'phone', 'mobile'] if contact_data[field]
        ]

        # If we have any conditions, combine them with an OR operator (|).
        # The reduce function here takes all Q objects in the list and applies the OR (|) operator between them.
        # The 'or_' from the operator module is used to apply this OR operator between all Q objects.
        # If no conditions exist (list is empty), we fall back to an empty Q() object.
        query = reduce(or_, conditions, Q())

        # Return the filtered Contact objects based on the query we built
        return Contact.objects.filter(query)

    def update_existing_contacts(self, matches, contact_data, tags, results):
        for contact in matches:
            self.categorize_contact(contact, tags, results)
            if matches.count() == 1:
                self.update_contact_info(contact, contact_data, results)

    def categorize_contact(self, contact, tags, results):
        if contact.contactcampaignstatus_set.filter(campaign__active=True).exists():
            results['in_active_campaign'].append(contact.id)
            self.add_tags(contact, tags['tags_in_campaign'])
        elif contact.has_active_subscription():
            results['active_contacts'].append(contact.id)
            self.add_tags(contact, tags['tags_active'])
        else:
            results['existing_inactive_contacts'].append(contact.id)
            self.add_tags(contact, tags['tags_existing'])

    def update_contact_info(self, contact, contact_data, results):
        for field in ['email', 'phone', 'mobile']:
            if not getattr(contact, field) and contact_data[field]:
                try:
                    setattr(contact, field, contact_data[field])
                    contact.save()
                    results[f'added_{field}s'] += 1
                except Exception as e:
                    results['errors'].append(
                        f"Could not add {field} {contact_data[field]} to contact {contact.id}: {e}"
                    )

    def create_new_contact(self, contact_data, tags, results):
        new_contact = Contact.objects.create(
            **{k: v for k, v in contact_data.items() if k not in self.get_address_column_names()}
        )

        state_data = contact_data.get('state', None)
        contact_data['state'] = State.objects.filter(name=state_data).first()

        country_data = contact_data.get('country', None)
        contact_data['country'] = Country.objects.filter(name=country_data).first()

        if contact_data['address_1']:
            Address.objects.create(
                contact=new_contact,
                address_1=contact_data['address_1'],
                address_2=contact_data['address_2'],
                city=contact_data['city'],
                address_type="physical",  # Default
                state=contact_data['state'],
                country=contact_data['country'],
            )

        results['new_contacts'].append(new_contact)
        self.add_tags(new_contact, tags['tags'])

    def add_tags(self, contact, tag_list):
        for tag in tag_list:
            contact.tags.add(tag)

    def display_messages(self, results):
        messages.success(self.request, f"{len(results['new_contacts'])} contacts imported successfully")
        messages.warning(self.request, f"{len(results['in_active_campaign'])} contacts were found in active campaigns")
        messages.warning(
            self.request, f"{len(results['active_contacts'])} contacts were found with active subscriptions"
        )
        messages.warning(
            self.request,
            _(f"{len(results['existing_inactive_contacts'])} contacts were found without active subscriptions"),
        )
        messages.success(self.request, f"{results['added_emails']} emails were added to existing contacts")
        messages.success(self.request, f"{results['added_phones']} phone numbers were added to existing contacts")
        messages.success(self.request, f"{results['added_mobiles']} mobile numbers were added to existing contacts")

        for error in results['errors']:
            messages.error(self.request, error)
