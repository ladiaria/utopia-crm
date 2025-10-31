import csv
import json
import pandas as pd
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Prefetch, Case, When, Value, BooleanField, Count, Exists, OuterRef
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
    ContactCampaignStatus,
    IdDocumentType,
)
from core.filters import ContactFilter
from core.forms import ContactAdminForm
from core.mixins import BreadcrumbsMixin
from core.utils import get_mailtrain_lists, detect_csv_delimiter

from support.forms import ImportContactsForm, CheckForExistingContactsForm

from invoicing.models import Invoice, CreditNote
from taggit.models import Tag


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
        widget=CheckboxSelectMultiple(attrs={'class': 'form-check', 'style': 'float:left;margin-right:7px'}),
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
        self.save_tags()
        # del self.object.updatefromweb
        return result

    def get_success_message(self):
        return _("Contact saved successfully")

    def get_success_url(self):
        if getattr(self.object, "sync_error", None):
            messages.warning(self.request, f"CMS sync error: {self.object.sync_error}")
            del self.object.sync_error
        return reverse("contact_detail", args=[self.object.id])

    def save_tags(self):
        # This method had to be added because in this update logic, the tags are not saved for whatever reason
        raw_tags = self.request.POST.get("tags")
        if raw_tags and raw_tags != "[]":
            try:
                parsed_tags = json.loads(raw_tags)
                if isinstance(parsed_tags, list) and all("value" in tag for tag in parsed_tags):
                    tag_list = [tag["value"] for tag in parsed_tags]
                    self.object.tags.set(tag_list)
            except json.JSONDecodeError:
                pass
        else:
            self.object.tags.clear()

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

    def get(self, request, *args, **kwargs):
        # Handle template download
        if 'download_template' in request.GET:
            return self.download_template()
        return super().get(request, *args, **kwargs)

    def download_template(self):
        """
        Generate and return a CSV template file for contact imports.

        Returns:
            HttpResponse: CSV file with proper headers and example data
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="import_contacts_template.csv"'

        writer = csv.writer(response)

        # Write header row with exact column names expected by the view
        writer.writerow([
            'name', 'last_name', 'email', 'phone', 'mobile', 'notes',
            'address_1', 'address_2', 'city', 'state', 'country',
            'id_document_type', 'id_document'
        ])

        # Write example rows
        writer.writerow([
            'Juan', 'Perez', 'juan.perez@example.com', '24000000', '092123456', 'Example contact',
            '18 de Julio 1234', 'Apt 8', 'Montevideo', 'Montevideo', 'Uruguay',
            'CI', '12345678'
        ])

        return response

    def get_address_column_names(self):
        return ['address_1', 'address_2', 'city', 'state', 'country']

    def resolve_id_document_type(self, id_doc_type_str, row_number=None):
        """
        Resolve ID document type string to IdDocumentType object.
        Returns None if not found and logs a warning.

        Args:
            id_doc_type_str: String identifier for document type (e.g., 'CI', 'CC', 'RUT')
            row_number: Optional row number for warning messages

        Returns:
            IdDocumentType object or None
        """
        if not id_doc_type_str:
            return None

        # Try to find by name (case-insensitive)
        doc_type = IdDocumentType.objects.filter(name__iexact=id_doc_type_str).first()

        if not doc_type:
            # Log warning for invalid document type
            row_info = f" (Row {row_number})" if row_number else ""
            messages.warning(
                self.request,
                _(f"Invalid ID document type '{id_doc_type_str}'{row_info}. Contact created without document type.")
            )
            return None

        return doc_type

    def form_valid(self, form):
        csvfile = form.cleaned_data['file']
        use_headers = form.cleaned_data.get('use_headers', True)
        tags = self.parse_tags(form.cleaned_data)

        results = self.process_csv(csvfile, tags, use_headers)

        self.display_messages(results)

        return super().form_valid(form)

    def parse_tags(self, cleaned_data):
        tag_types = ['tags', 'tags_existing', 'tags_active', 'tags_in_campaign']
        return {tag_type: [tag.strip() for tag in cleaned_data.get(tag_type, '').split(',')] for tag_type in tag_types}

    def process_csv(self, csv_file, tags, use_headers=True):
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
            if use_headers:
                df = pd.read_csv(csv_file, dtype=str, keep_default_na=False)
            else:
                # Read without headers and assign column names manually
                df = pd.read_csv(csv_file, header=None, dtype=str, keep_default_na=False)
                df.columns = [
                    'name', 'last_name', 'email', 'phone', 'mobile', 'notes',
                    'address_1', 'address_2', 'city', 'state', 'country',
                    'id_document_type', 'id_document'
                ]
        except Exception as e:
            results['errors'].append(str(e))
            return results

        for index, row in df.iterrows():
            try:
                # Calculate row number for error messages
                row_number = index + 2 if use_headers else index + 1
                # Always use use_headers=True for parse_row since we assign column names
                contact_data = self.parse_row(row, use_headers=True, row_number=row_number)
                self.process_contact(contact_data, tags, results)
            except Exception as e:
                results['errors'].append(
                    f"CSV Row {index + 2 if use_headers else index + 1}: {e}"
                )  # +2 for headers (pandas index + header row), +1 for no headers

        return results

    def parse_row(self, row, use_headers=True, row_number=None):
        """
        Parse a row from the CSV file into contact data dictionary.
        Since we read CSV with dtype=str, all values are strings and empty strings are preserved.

        Args:
            row: DataFrame row to parse
            use_headers: Whether the CSV had headers (kept for compatibility)
            row_number: Row number for warning messages
        """
        # Resolve ID document type, returns None if invalid
        id_doc_type_obj = self.resolve_id_document_type(row['id_document_type'], row_number)

        return {
            'name': row['name'] if row['name'] else None,
            'last_name': row['last_name'] if row['last_name'] else "",
            'email': row['email'].lower() if row['email'] else None,
            'phone': row['phone'] if row['phone'] else "",
            'mobile': row['mobile'] if row['mobile'] else "",
            'notes': row['notes'].strip() if row['notes'] else None,
            'address_1': row['address_1'] if row['address_1'] else None,
            'address_2': row['address_2'] if row['address_2'] else None,
            'city': row['city'] if row['city'] else None,
            'state': row['state'].strip() if row['state'] else None,
            'country': row['country'] if row['country'] else None,
            'id_document_type': id_doc_type_obj,
            'id_document': row['id_document'] if row['id_document'] else None,
        }

    @transaction.atomic
    def process_contact(self, contact_data, tags, results):
        email = contact_data.get('email')
        phone = contact_data.get('phone')

        # Try to match by email first
        matches = self.find_matching_contacts_by_email(email) if email else Contact.objects.none()

        # If no email match, try to match by phone
        if not matches.exists() and phone:
            matches = self.find_matching_contacts_by_phone(phone)
            if matches.exists():
                # Matched by phone - update email if contact doesn't have one
                self.update_existing_contacts(matches, contact_data, tags, results, matched_by_phone=True)
                return

        if matches.exists():
            self.update_existing_contacts(matches, contact_data, tags, results)
        else:
            self.create_new_contact(contact_data, tags, results)

    def find_matching_contacts_by_email(self, email):
        return Contact.objects.filter(email=email)

    def find_matching_contacts_by_phone(self, phone):
        return Contact.objects.filter(phone=phone) | Contact.objects.filter(mobile=phone)

    def update_existing_contacts(self, matches, contact_data, tags, results, matched_by_phone=False):
        for contact in matches:
            self.categorize_contact(contact, tags, results)
            if matches.count() == 1:
                # Update email if matched by phone and contact doesn't have an email
                if matched_by_phone and not contact.email:
                    email_from_csv = contact_data.get('email')
                    if email_from_csv:
                        contact.email = email_from_csv
                        contact.save()
                        results['added_emails'] += 1
                else:
                    self.update_contact_phone(contact, contact_data, results)

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

    def update_contact_phone(self, contact, contact_data, results):
        phone_from_csv = contact_data.get('phone', '')
        if not phone_from_csv:
            return  # No phone to update

        try:
            # If phone already exists and is not empty, update the mobile field, else update the phone field
            if contact.phone:
                setattr(contact, 'mobile', phone_from_csv)
            else:
                setattr(contact, 'phone', phone_from_csv)
            contact.save()
            results['added_phones'] += 1
        except Exception as e:
            results['errors'].append(
                f"Could not add phone {phone_from_csv} to contact {contact.id}: {e}"
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
        tag_list = [tag for tag in tag_list if isinstance(tag, str) and tag.strip()]
        if not tag_list:
            return
        contact.tags.add(*tag_list)

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

    def find_matching_contacts_by_email(self, email):
        """
        Find matching contacts based on email only.
        Returns a list of contacts that match the given email.
        """
        contacts = (
            Contact.objects.filter(email__iexact=email)
            .prefetch_related(
                Prefetch('subscriptions', queryset=Subscription.objects.filter(active=True, status__in=['OK', 'G']))
            )
            .prefetch_related('contactcampaignstatus_set')
            .annotate(
                is_email_match=Case(
                    When(email__iexact=email, then=Value(True)),
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
        """
        Process CSV file with automatic delimiter detection.
        Only processes email column for contact matching.
        """
        results = []
        non_matches = []

        # Detect delimiter automatically
        delimiter = detect_csv_delimiter(file)

        for row_number, row in enumerate(csv.DictReader(file, delimiter=delimiter, quotechar='"')):
            email = row.get('email', '').strip()

            if not email:
                non_matches.append({'email': email or 'N/A', 'row_number': row_number + 1})
                continue

            contacts = self.find_matching_contacts_by_email(email)

            if contacts:
                for contact in contacts:
                    results.append(
                        {
                            'contact': contact,
                            'count': contacts.count(),
                            'email_matches': contact.is_email_match,
                            'has_active_subscription': bool(contact.subscriptions.all()),
                            'is_in_active_campaign': contact.active_campaign_count > 0,
                            'csv_email': email,
                            'csv_row': row_number + 1,
                        }
                    )
            else:
                non_matches.append({'email': email, 'row_number': row_number + 1})

            if (row_number + 1) % 100 == 0 and settings.DEBUG:
                print(f"processed {row_number + 1} rows")

        return results, non_matches, delimiter

    def get(self, request, *args, **kwargs):
        """Handle GET requests, including CSV template download."""
        if 'download_template' in request.GET:
            return self.download_template()
        return super().get(request, *args, **kwargs)

    def download_template(self):
        """
        Generate and return a CSV template file for users to download.
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contact_check_template.csv"'

        writer = csv.writer(response)
        # Header row
        writer.writerow(['email'])
        # Sample data rows with instructions
        writer.writerow(['example1@company.com'])
        writer.writerow(['example2@domain.org'])
        writer.writerow(['user@example.net'])

        return response

    def form_valid(self, form):
        csvfile = form.cleaned_data['file']
        decoded_file = io.StringIO(csvfile.read().decode('utf-8'))
        results, non_matches, delimiter = self.process_file(decoded_file)

        context = self.get_context_data(form=form)
        context['results'] = results
        context['non_matches'] = non_matches
        context['detected_delimiter'] = 'semicolon (;)' if delimiter == ';' else 'comma (,)'

        active_subscriptions = sum(1 for result in results if result['has_active_subscription'])
        context['active_subscriptions'] = active_subscriptions
        active_campaigns = sum(1 for result in results if result['is_in_active_campaign'])
        context['active_campaigns'] = active_campaigns

        return self.render_to_response(context)


@method_decorator(staff_member_required, name="dispatch")
class TagAnalysisView(BreadcrumbsMixin, ListView):
    """
    View to analyze taggit tags used by contacts.
    Shows statistics for each tag including:
    - Total contacts with this tag
    - Contacts in campaigns (any campaign)
    - Contacts in active campaigns
    """
    model = Tag
    template_name = "tag_analysis.html"
    context_object_name = "tags"
    paginate_by = 50
    page_kwarg = "p"

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": _("Tag Analysis"), "url": ""},
        ]

    def get_queryset(self):
        """
        Get all tags used by contacts with statistics annotations.
        """
        # Get tags that are used by contacts with statistics
        queryset = Tag.objects.filter(
            taggit_taggeditem_items__content_type__model='contact'
        ).annotate(
            # Total contacts with this tag
            total_contacts=Count(
                'taggit_taggeditem_items__object_id',
                filter=Q(taggit_taggeditem_items__content_type__model='contact'),
                distinct=True
            ),
            # Contacts in any campaign - using EXISTS subquery
            contacts_in_campaigns=Count(
                'taggit_taggeditem_items__object_id',
                filter=Q(
                    taggit_taggeditem_items__content_type__model='contact'
                ) & Q(
                    Exists(
                        ContactCampaignStatus.objects.filter(
                            contact_id=OuterRef('taggit_taggeditem_items__object_id')
                        )
                    )
                ),
                distinct=True
            ),
            # Contacts in active campaigns - using EXISTS subquery
            contacts_in_active_campaigns=Count(
                'taggit_taggeditem_items__object_id',
                filter=Q(
                    taggit_taggeditem_items__content_type__model='contact'
                ) & Q(
                    Exists(
                        ContactCampaignStatus.objects.filter(
                            contact_id=OuterRef('taggit_taggeditem_items__object_id'),
                            campaign__active=True
                        )
                    )
                ),
                distinct=True
            )
        ).filter(
            total_contacts__gt=0  # Only show tags that have contacts
        ).order_by('-total_contacts', 'name')

        # Apply name filter if provided
        name_filter = self.request.GET.get('name')
        if name_filter:
            queryset = queryset.filter(name__icontains=name_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['name_filter'] = self.request.GET.get('name', '')

        # Add summary statistics
        total_tags = self.get_queryset().count()
        total_contacts_with_tags = Contact.objects.filter(tags__isnull=False).distinct().count()

        context.update({
            'total_tags': total_tags,
            'total_contacts_with_tags': total_contacts_with_tags,
        })

        return context
