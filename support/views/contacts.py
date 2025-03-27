import csv
import pandas as pd
from datetime import date
from functools import reduce
from operator import or_

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Prefetch, Case, When, Value, BooleanField, Count
from django.views.generic import UpdateView, CreateView, DetailView, ListView, FormView
from django.forms import ModelMultipleChoiceField, CheckboxSelectMultiple
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseNotFound
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.utils.functional import cached_property
import io

from core.models import (
    Contact,
    Product,
    MailtrainList,
    State,
    Country,
    Address,
    Subscription,
)
from core.filters import ContactFilter
from core.forms import ContactAdminForm
from core.mixins import BreadcrumbsMixin
from core.utils import get_mailtrain_lists

from support.forms import ImportContactsForm, CheckForExistingContactsForm

from invoicing.models import Invoice, CreditNote


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
        queryset = (
            super()
            .get_queryset()
            .prefetch_related(
                "activity_set",
                "activity_set__contact",
                "addresses__state",
                "addresses__country",
                "subscriptions__subscriptionproduct_set",
            )
        )
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

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .prefetch_related(
                "subscriptions",
                "addresses",
                "activity_set",
                "subscriptionnewsletter_set",
                "issue_set",
                "tags",
            )
            .select_related()
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["georef_activated"] = getattr(settings, "GEOREF_SERVICES", False)
        context["subscription_groups"] = self.get_subscription_groups()
        context["overview_subscriptions"] = self.get_overview_subscriptions()
        # Unpack all querysets
        context.update(self.get_all_querysets_and_lists())
        # Unpack subscriptions for overview
        context.update(self.get_overview_subscriptions())
        context.update(self.get_expensive_calculations())
        context["subscriptions_count"] = self.get_subscriptions().count()
        return context

    def get_all_querysets_and_lists(self):
        addresses = self.object.addresses.all().prefetch_related("state", "country")
        activities = self.object.activity_set.all().order_by("-datetime", "id")[:3]
        newsletters = self.object.get_newsletters()
        all_issues = self.object.issue_set.all().order_by("-date", "id").select_related("status", "sub_category")
        last_issues = all_issues[:3]
        last_paid_invoice = self.object.get_last_paid_invoice()
        all_activities = self.object.activity_set.all().order_by("-datetime", "id")
        all_scheduled_tasks = self.object.scheduledtask_set.all().order_by("-creation_date", "id")
        all_campaigns = self.object.contactcampaignstatus_set.all().order_by("-date_created", "id")
        return {
            "addresses": addresses,
            "activities": activities,
            "newsletters": newsletters,
            "all_issues": all_issues,
            "last_issues": last_issues,
            "last_paid_invoice": last_paid_invoice,
            "all_activities": all_activities,
            "all_scheduled_tasks": all_scheduled_tasks,
            "all_campaigns": all_campaigns,
        }

    @cached_property
    def prefetched_subscriptions(self):
        prefetched_subscriptions = self.object.subscriptions.all().prefetch_related(
            Prefetch(
                "subscriptionproduct_set__product",
                queryset=Product.objects.all(),
            ),
            "subscriptionproduct_set",
            "subscriptionproduct_set__address",
            "subscriptionproduct_set__address__state",
            "subscriptionproduct_set__address__country",
        )
        return prefetched_subscriptions

    def get_subscriptions(self):
        return self.prefetched_subscriptions

    def get_overview_subscriptions(self):
        active_subscriptions = self.get_subscriptions().filter(active=True).exclude(status="AP")
        future_subscriptions = (
            self.get_subscriptions().filter(active=False, start_date__gte=date.today()).exclude(status="AP")
        )
        awaiting_payment_subscriptions = self.get_subscriptions().filter(status="AP")
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
                'subscriptions': self.get_subscriptions().filter(active=True).exclude(status="AP"),
                'collapsed': False,
            },
            {
                'title': _("Future Subscriptions"),
                'subscriptions': self.get_subscriptions()
                .filter(active=False, start_date__gte=date.today())
                .exclude(status__in=("AP", "ER")),
                'collapsed': False,
            },
            {
                'title': _("Subscriptions awaiting payment"),
                'subscriptions': self.get_subscriptions().filter(status="AP"),
                'collapsed': True,
            },
            {
                'title': _("Subscriptions with errors"),
                'subscriptions': self.get_subscriptions().filter(status="ER"),
                'collapsed': True,
            },
            {
                'title': _("Paused Subscriptions"),
                'subscriptions': self.get_subscriptions().filter(status="PA"),
                'collapsed': True,
            },
            {
                'title': _("Inactive subscriptions"),
                'subscriptions': self.get_subscriptions()
                .filter(active=False, start_date__lt=date.today())
                .exclude(status__in=("AP", "ER"))
                .order_by('-start_date'),
                'collapsed': True,
            },
        ]
        return subscription_groups

    def get_expensive_calculations(self):
        debt = self.object.get_debt()
        last_paid_invoice = self.object.get_last_paid_invoice()
        latest_invoice = self.object.get_latest_invoice()
        expired_invoices_count = self.object.expired_invoices_count()
        return {
            "debt": debt,
            "last_paid_invoice": last_paid_invoice,
            "latest_invoice": latest_invoice,
            "expired_invoices_count": expired_invoices_count,
        }


class ContactAdminFormWithNewsletters(ContactAdminForm):
    newsletters = ModelMultipleChoiceField(
        queryset=Product.objects.filter(type="N", active=True),
        widget=CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, request=None, **kwargs):
        contact = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if contact:
            self.fields['newsletters'].initial = contact.get_newsletter_products()

    def save(self, commit=True):
        contact = super().save(commit=False)
        if commit:
            contact.save()
        # Handle newsletters explicitly
        selected_newsletters = self.cleaned_data.get('newsletters')
        if contact.pk:  # Ensure the contact is saved before modifying M2M

            all_newsletters = self.fields['newsletters'].queryset
            current_newsletters = self.fields['newsletters'].initial

            # Add new subscriptions for newsletters
            for newsletter in all_newsletters:
                if newsletter not in current_newsletters and newsletter in selected_newsletters:
                    contact.add_newsletter(newsletter.id)
                elif newsletter in current_newsletters and newsletter not in selected_newsletters:
                    contact.remove_newsletter(newsletter.id)
        return contact

    class Media:
        css = {"all": ("css/contact_edit_newsletters.css",)}


@method_decorator(staff_member_required, name="dispatch")
class ContactUpdateView(BreadcrumbsMixin, UpdateView):
    model = Contact
    form_class = ContactAdminFormWithNewsletters
    template_name = "create_contact/create_contact.html"

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
            form.save(False)
        except Exception as e:
            if skip_clean_set:
                del self.object._skip_clean
            messages.error(self.request, "Error: {}".format(e))
        else:
            if skip_clean_set:
                del self.object._skip_clean
            messages.success(self.request, self.get_success_message())
        # At this point, the CMS api was already called, to avoid call it again we use the 'updatefromweb' flag
        # TODO: Only apply the prev. line indication (commented) if fields marked to be synced are unchanged
        # self.object.updatefromweb = True
        result = super().form_valid(form)
        # del self.object.updatefromweb
        return result

    def get_success_message(self):
        return _("Contact saved successfully")

    def get_success_url(self):
        if getattr(self.object, "sync_error", None):
            messages.warning(self.request, f"CMS sync error: {self.object.sync_error}")
            del self.object.sync_error
        return reverse("contact_detail", args=[self.object.id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_newsletters"] = Product.objects.filter(type="N", active=True)
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


@method_decorator(staff_member_required, name="dispatch")
class ImportContactsView(FormView):
    template_name = 'import_contacts.html'
    form_class = ImportContactsForm
    success_url = reverse_lazy('import_contacts')

    def get_address_column_names(self):
        return ['address_1', 'address_2', 'city', 'state', 'country']

    def form_valid(self, form):
        csvfile = form.cleaned_data['file']
        tags = self.parse_tags(form.cleaned_data)

        results = self.process_csv(csvfile, tags)

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


@csrf_protect
def contact_invoices_htmx(request, contact_id):
    # Make sure the request comes from my HTMX library
    if request.headers.get("HX-Request") != "true":
        return HttpResponseNotFound()

    contact = get_object_or_404(Contact, pk=contact_id)
    invoices = (
        Invoice.objects.filter(contact=contact)
        .select_related("subscription", "contact")
        .prefetch_related("invoiceitem_set")
    ).order_by("-id")
    credit_notes = CreditNote.objects.filter(invoice__in=invoices)
    return render(
        request, "contact_detail/htmx/_invoices_htmx.html", {"invoices": invoices, "credit_notes": credit_notes}
    )


class CheckForExistingContactsView(BreadcrumbsMixin, FormView):
    template_name = "check_for_existing_contacts.html"
    form_class = CheckForExistingContactsForm

    def breadcrumbs(self):
        return [
            {"url": reverse("home"), "label": "Home"},
            {"url": reverse("contact_list"), "label": "Contacts"},
            {"label": "Check for existing contacts"},
        ]

    def get_success_url(self):
        return reverse("contact_list")

    def check_contact(self, email, phone, mobile):
        # Checks for a contact. Returns the contact if found, and what made it unique
        # Returns None if no contact was found
        contact = Contact.objects.filter(email=email).first()
        if not contact:
            return None
        return contact

    def find_matching_contacts(self, email, phone, mobile):
        # Find matching contacts based on email, phone, and mobile
        # Returns a list of contacts that match the given criteria
        contacts = (
            Contact.objects.filter(Q(email__iexact=email) | Q(phone__iexact=phone) | Q(mobile__iexact=mobile))
            .prefetch_related(
                Prefetch('subscriptions', queryset=Subscription.objects.filter(active=True, status__in=['OK', 'G']))
            )
            .prefetch_related('contactcampaignstatus_set')
            # Annotate matches in a single query
            .annotate(
                is_email_match=Case(
                    When(email__iexact=email, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                is_phone_match=Case(
                    When(phone__iexact=phone, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                is_mobile_match=Case(
                    When(mobile__iexact=mobile, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                active_campaign_count=Count(
                    'contactcampaignstatus',
                    filter=Q(contactcampaignstatus__campaign__active=True),
                    distinct=True
                )
            )
            .distinct()
        )

        return contacts

    def process_file(self, file):
        results = []
        non_matches = []
        for row_number, row in enumerate(csv.DictReader(file, delimiter=',', quotechar='"', lineterminator='\r\n')):
            email = row.get('email', None)
            phone = row.get('phone', None)
            mobile = row.get('mobile', None)

            if not any([email, phone, mobile]):
                non_matches.append(row)
                continue

            contacts = self.find_matching_contacts(email, phone, mobile)

            if contacts:
                for contact in contacts:
                    results.append(
                        {
                            'contact': contact,
                            'count': contacts.count(),
                            'email_matches': contact.is_email_match,
                            'phone_matches': contact.is_phone_match,
                            'mobile_matches': contact.is_mobile_match,
                            'has_active_subscription': bool(contact.subscriptions.all()),
                            'is_in_active_campaign': contact.active_campaign_count > 0,
                            'csv_email': email,
                            'csv_phone': phone,
                            'csv_mobile': mobile,
                            'csv_row': row_number + 1,
                        }
                    )
            else:
                non_matches.append(row)

            if (row_number + 1) % 100 == 0 and settings.DEBUG:
                print(f"processed {row_number + 1} rows")

        return results, non_matches

    def form_valid(self, form):
        csvfile = form.cleaned_data['file']
        decoded_file = io.StringIO(csvfile.read().decode('utf-8'))
        results, non_matches = self.process_file(decoded_file)
        context = self.get_context_data(form=form)
        context['results'] = results
        context['non_matches'] = non_matches
        active_subscriptions = sum(1 for result in results if result['has_active_subscription'])
        context['active_subscriptions'] = active_subscriptions
        active_campaigns = sum(1 for result in results if result['is_in_active_campaign'])
        context['active_campaigns'] = active_campaigns
        return self.render_to_response(context)
