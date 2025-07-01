import csv
from datetime import date, datetime, timedelta

import pandas as pd
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Min, Sum
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, RedirectView, UpdateView
from django_filters.views import FilterView
from taggit.models import Tag

from core import choices as core_choices
from core.filters import ContactFilter
from core.forms import AddressForm
from core.mixins import BreadcrumbsMixin
from core.models import (
    Activity,
    Address,
    Campaign,
    Contact,
    ContactCampaignStatus,
    DoNotCallNumber,
    DynamicContactFilter,
    Product,
    Subscription,
    SubscriptionNewsletter,
    SubscriptionProduct,
)
from core.utils import (
    calc_price_from_products,
    logistics_is_installed,
    process_products,
)
from support.choices import ISSUE_ANSWERS, ISSUE_CATEGORIES
from support.filters import (
    CampaignFilter,
    ContactCampaignStatusFilter,
    InvoicingIssueFilter,
    IssueFilter,
    SalesRecordFilter,
    SalesRecordFilterForSeller,
)
from support.forms import (
    AddressComplementaryInformationForm,
    ContactCampaignStatusByDateForm,
    InvoicingIssueChangeForm,
    IssueChangeForm,
    IssueStartForm,
    NewActivityForm,
    NewDynamicContactFilterForm,
    SalesRecordCreateForm,
    SubscriptionPaymentCertificateForm,
    SugerenciaGeorefForm,
    ValidateSubscriptionForm,
)
from support.models import Issue, IssueStatus, IssueSubcategory, SalesRecord, Seller

now = datetime.now()


def csv_sreader(src):
    """(Magic) CSV String Reader"""

    # Auto-detect the dialect
    dialect = csv.Sniffer().sniff(src, delimiters=",;")
    return csv.reader(src.splitlines(), dialect=dialect)


@login_required
def edit_address(request, contact_id, address_id=None):
    """
    View used in various points where we need to change the address of the contact.
    """
    if request.POST:
        if address_id:
            edited_address = Address.objects.get(pk=address_id)
            address_form = AddressForm(request.POST, instance=edited_address)
        else:
            address_form = AddressForm(request.POST)
        if address_form.is_valid():
            address_form.save()
        return render(request, "close.html")
    else:
        contact = Contact.objects.get(pk=contact_id)
        if address_id:
            form = AddressForm(
                instance=Address.objects.get(pk=address_id),
                initial={"contact": contact},
            )
        else:
            form = AddressForm(initial={"contact": contact})
        form.fields["contact"].widget = forms.HiddenInput()
        return render(
            request,
            "seller_console_edit_address.html",
            {
                "contact": contact,
                "address_form": form,
                "address_id": address_id,
            },
        )


@login_required
def default_newsletters_dialog(request, contact_id):
    if request.method == "POST":
        if request.POST.get("answer") == "yes":
            try:
                Contact.objects.get(id=contact_id).add_default_newsletters()
            except Contact.DoesNotExist:
                pass
        return HttpResponseRedirect(request.POST.get("next_page"))
    else:
        try:
            next_page = request.GET["next_page"]
        except KeyError:
            return HttpResponseNotFound()
        else:
            return render(
                request, "default_newsletters_dialog.html", {"contact_id": contact_id, "next_page": next_page}
            )


@login_required
def assign_campaigns(request):
    """
    Allows a manager to add contacts to campaigns, using tags or a csv file.
    """
    count, errors, in_campaign, debtors = 0, 0, 0, 0
    campaigns = Campaign.objects.filter(active=True)
    if request.POST and request.POST.get("tags"):
        campaign = request.POST.get("campaign")
        tags = request.POST.get("tags")
        tag_list = tags.split(",")
        for tag in tag_list:
            try:
                Tag.objects.get(name=tag)
            except Tag.DoesNotExist:
                messages.error(request, f"El tag {tag} no existe.")
                return HttpResponseRedirect(reverse("assign_campaigns"))
        contacts = Contact.objects.filter(tags__name__in=tag_list)
        for contact in contacts.iterator():
            try:
                if request.POST.get("ignore_in_active_campaign", False):
                    if contact.contactcampaignstatus_set.filter(campaign__active=True).exists():
                        in_campaign += 1
                        continue
                if request.POST.get("ignore_debtors", False):
                    if contact.is_debtor():
                        debtors += 1
                        continue
                contact.add_to_campaign(campaign)
                count += 1
            except Exception:
                errors += 1
        messages.success(request, f"{count} contactos fueron agregados a la campaña con éxito.")
        if errors:
            messages.error(request, f"{errors} contactos ya pertenecían a esta campaña.")
        if in_campaign:
            messages.error(request, f"{in_campaign} contactos ya están en campañas activas.")
        if debtors:
            messages.error(request, f"{debtors} contactos son deudores y no pudieron ser agregados.")
        return HttpResponseRedirect(reverse("assign_campaigns"))
    return render(
        request,
        "assign_campaigns.html",
        {
            "campaigns": campaigns,
        },
    )


@login_required
def list_campaigns_with_no_seller(request):
    """
    Shows a list of contacts in campaigns that have no seller.
    """
    campaigns = Campaign.objects.filter(contactcampaignstatus__seller=None).distinct()
    campaign_list = []
    for campaign in campaigns:
        count = (
            ContactCampaignStatus.objects.filter(campaign=campaign, seller=None, campaign_resolution=None)
            .exclude(status__in=(6, 7))
            .count()
        )
        campaign.count = count
        campaign.morning = ContactCampaignStatus.objects.filter(campaign=campaign, seller=None, status=6).count()
        campaign.afternoon = ContactCampaignStatus.objects.filter(campaign=campaign, seller=None, status=7).count()
        campaign_list.append(campaign)

    return render(
        request,
        "distribute_campaigns.html",
        {"campaign_list": campaign_list},
    )


@login_required
def assign_seller(request, campaign_id):
    """
    Shows a list of sellers to assign contacts to.
    """
    campaign = Campaign.objects.get(pk=campaign_id)
    ccs_qs_regular = ContactCampaignStatus.objects.filter(campaign=campaign, seller=None).exclude(status__in=[6, 7])
    ccs_qs_morning = ContactCampaignStatus.objects.filter(campaign=campaign, seller=None, status=6)
    ccs_qs_afternoon = ContactCampaignStatus.objects.filter(campaign=campaign, seller=None, status=7)
    ccs_qs = ccs_qs_regular
    shift = request.GET.get("shift", None)
    if shift == "mo":
        ccs_qs = ccs_qs_morning
    elif shift == "af":
        ccs_qs = ccs_qs_afternoon

    campaign.count = ccs_qs.count()
    message = ""

    if request.POST:
        seller_list = []
        for name, value in list(request.POST.items()):
            if name.startswith("seller"):
                seller_list.append([name.replace("seller-", ""), value or 0])
        total = 0
        for seller, amount in seller_list:
            total += int(amount)
        if total > campaign.count:
            messages.error(request, "Cantidad de clientes superior a la que hay.")
            return HttpResponseRedirect(reverse("assign_sellers", args=[campaign_id]))
        assigned_total = 0
        for seller, amount in seller_list:
            if amount:
                amount = int(amount)
                assigned_total += amount
                for status in ccs_qs[:amount]:
                    status.seller = Seller.objects.get(pk=seller)
                    status.date_assigned = date.today()
                    if status.status in (6, 7):
                        status.status = 1
                    try:
                        status.save()
                    except Exception as e:
                        messages.error(request, e)
                        return HttpResponseRedirect(reverse("assign_sellers"))
        messages.success(request, f"{assigned_total} contactos fueron repartidos con éxito.")
        return HttpResponseRedirect(reverse("assign_sellers", args=[campaign_id]))

    sellers = Seller.objects.filter(internal=True)
    seller_list = []
    for seller in sellers:
        seller.contacts = ContactCampaignStatus.objects.filter(seller=seller, campaign=campaign).count()
        seller_list.append(seller)
    if message:
        # Refresh value if some subs were distributed
        campaign.count = ccs_qs.count()
    return render(
        request,
        "assign_sellers.html",
        {
            "seller_list": seller_list,
            "campaign": campaign,
            "message": message,
            "shift": shift,
            "regular_count": ccs_qs_regular.count(),
            "morning_count": ccs_qs_morning.count(),
            "afternoon_count": ccs_qs_afternoon.count(),
        },
    )


@login_required
def release_seller_contacts(request, seller_id=None):
    """
    Releases all the unworked contacts from a seller to allow them to be assigned to other sellers.
    """
    seller_qs = (
        Seller.objects.filter(contactcampaignstatus__status=1)
        .annotate(campaign_contacts=Count("contactcampaignstatus"))
        .filter(campaign_contacts__gte=1)
    )

    if seller_id:
        seller = get_object_or_404(Seller, pk=seller_id)
        seller.contactcampaignstatus_set.filter(status__lt=4).update(seller=None)
        messages.success(request, f"Los contactos de {seller} fueron liberados")
        return HttpResponseRedirect(reverse("release_seller_contacts"))
    else:
        for seller in seller_qs:
            seller.contacts_not_worked = seller.contactcampaignstatus_set.filter(status__lt=4).count()
        return render(request, "release_seller_contacts.html", {"seller_list": seller_qs})


@staff_member_required
def release_seller_contacts_by_campaign(request, seller_id, campaign_id=None):
    seller_obj = get_object_or_404(Seller, pk=seller_id)
    active_campaigns = seller_obj.get_active_campaigns()
    if campaign_id:
        campaign_obj = get_object_or_404(Campaign, pk=campaign_id)
        seller_obj.contactcampaignstatus_set.filter(status__lt=4, campaign=campaign_obj).update(seller=None)
        messages.success(request, f"Los contactos de {seller_obj} fueron liberados de la campaña {campaign_obj.name}")
        return HttpResponseRedirect(reverse("release_seller_contacts"))
    else:
        for campaign in active_campaigns:
            campaign.contacts_not_worked = campaign.contactcampaignstatus_set.filter(
                status__lt=4, seller=seller_obj
            ).count()
        return render(
            request,
            "release_seller_contacts_by_campaign.html",
            {"active_campaigns": active_campaigns, "seller": seller_obj},
        )


@login_required
def edit_products(request, subscription_id):
    """
    Allows editing products in a subscription.
    """
    products = Product.objects.filter(offerable=True)
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    contact = subscription.contact
    contact_addresses = Address.objects.filter(contact=contact)
    subscription_products_through = subscription.subscriptionproduct_set.all()
    subscription_products = subscription.products.all()
    # import pdb; pdb.set_trace()
    if request.POST:
        pass
    return render(
        request,
        "edit_products.html",
        {
            "addresses": contact_addresses,
            "subscription": subscription,
            "products": products,
            "subscription_products": subscription_products,
            "subscription_products_through": subscription_products_through,
        },
    )


@login_required
def list_issues(request):
    """
    Shows a very basic list of issues.
    """
    if logistics_is_installed():
        issues_queryset = Issue.objects.all().order_by(
            "-date", "subscription_product__product", "-subscription_product__route__number", "-id"
        )
    else:
        issues_queryset = Issue.objects.all().order_by("-date", "subscription_product__product", "-id")
    issues_filter = IssueFilter(request.GET, queryset=issues_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(issues_filter.qs, 100)
    if request.GET.get("export"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="issues_export.csv"'
        writer = csv.writer(response)
        header = [
            _("Start date"),
            _("Contact ID"),
            _("Contact name"),
            _("Category"),
            _("Subcategory"),
            _("Activities count"),
            _("Status"),
            _("Assigned to"),
        ]
        writer.writerow(header)
        for issue in issues_filter.qs.all():
            writer.writerow(
                [
                    issue.date,
                    issue.contact.id,
                    issue.contact.get_full_name(),
                    issue.get_category(),
                    issue.get_subcategory(),
                    issue.activity_count(),
                    issue.get_status(),
                    issue.get_assigned_to(),
                ]
            )
        return response
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.page(paginator.num_pages)
    return render(
        request,
        "list_issues.html",
        {"page": page, "paginator": paginator, "issues_filter": issues_filter, "count": issues_filter.qs.count()},
    )


@login_required
def new_issue(request, contact_id, category="L"):
    """
    Creates an issue of a selected category and subcategory.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST:
        form = IssueStartForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("new_address"):
                address = Address.objects.create(
                    contact=contact,
                    address_1=form.cleaned_data.get("new_address_1"),
                    address_2=form.cleaned_data.get("new_address_2"),
                    city=form.cleaned_data.get("new_address_city"),
                    state=form.cleaned_data.get("new_address_state"),
                    notes=form.cleaned_data.get("new_address_notes"),
                )
            else:
                address = form.cleaned_data.get("contact_address")
            if form.cleaned_data["status"]:
                status = form.cleaned_data["status"]
            elif form.cleaned_data["assigned_to"]:
                status = IssueStatus.objects.get(slug=settings.ISSUE_STATUS_ASSIGNED)
            else:
                status = IssueStatus.objects.get(slug=settings.ISSUE_STATUS_UNASSIGNED)
            new_issue = Issue.objects.create(
                contact=form.cleaned_data["contact"],
                category=form.cleaned_data["category"],
                sub_category=form.cleaned_data["sub_category"],
                notes=form.cleaned_data["notes"],
                copies=form.cleaned_data["copies"],
                subscription=form.cleaned_data["subscription"],
                subscription_product=form.cleaned_data["subscription_product"],
                product=form.cleaned_data["product"],
                inside=False,
                manager=request.user,
                assigned_to=form.cleaned_data["assigned_to"],
                envelope=form.cleaned_data["envelope"],
                address=address,
                status=status,
            )
            Activity.objects.create(
                datetime=datetime.now(),
                contact=contact,
                issue=new_issue,
                notes=_("See related issue"),
                activity_type=form.cleaned_data["activity_type"],
                status="C",  # completed
                direction="I",
            )
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = IssueStartForm(
            initial={
                "copies": 1,
                "contact": contact,
                "category": category,
                "activity_type": "C",
            }
        )
    form.fields["subscription_product"].queryset = contact.get_active_subscriptionproducts()
    form.fields["subscription"].queryset = contact.get_active_subscriptions()
    form.fields["contact_address"].queryset = contact.addresses.all()
    if category == "M":
        form.fields["sub_category"].queryset = IssueSubcategory.objects.filter(
            category="I"
        )  # Invoicing and collections share subcategories
    else:
        form.fields["sub_category"].queryset = IssueSubcategory.objects.filter(category=category)
    dict_categories = dict(ISSUE_CATEGORIES)
    category_name = dict_categories[category]
    breadcrumbs = [
        {"url": reverse("contact_list"), "label": _("Contacts")},
        {"url": reverse("contact_detail", args=[contact.id]), "label": contact.get_full_name()},
        {"label": _("New issue")},
    ]
    return render(
        request,
        "new_issue.html",
        {"contact": contact, "form": form, "category_name": category_name, "breadcrumbs": breadcrumbs},
    )


@login_required
def view_issue(request, issue_id):
    """
    Shows a logistics type issue.
    """
    issue = get_object_or_404(Issue, pk=issue_id)
    invoicing = False
    has_active_subscription = issue.contact.has_active_subscription()
    if request.POST:
        if issue.category in ("I", "M"):
            form = InvoicingIssueChangeForm(request.POST, instance=issue)
            invoicing = True
        else:
            form = IssueChangeForm(request.POST, instance=issue)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse("view_issue", args=(issue_id,)))
    else:
        if issue.category in ("I", "M"):
            subcategories = IssueSubcategory.objects.filter(category="I")
            form = InvoicingIssueChangeForm(instance=issue)
            invoicing = True
        else:
            subcategories = IssueSubcategory.objects.filter(category=issue.category)
            form = IssueChangeForm(instance=issue)
        form.fields["sub_category"].queryset = subcategories

    activities = issue.activity_set.all().order_by("-datetime", "id")
    activity_form = NewActivityForm(
        initial={
            "contact": issue.contact,
            "direction": "O",
            "activity_type": "C",
        }
    )
    activity_form.fields["contact"].label = False
    return render(
        request,
        "view_issue.html",
        {
            "has_active_subscription": has_active_subscription,
            "invoicing": invoicing,
            "form": form,
            "issue": issue,
            "activities": activities,
            "activity_form": activity_form,
            "invoice_list": issue.contact.invoice_set.all().order_by("-creation_date", "id"),
        },
    )


def api_new_address(request, contact_id):
    # Convertir en api para llamar a todas las direcciones. TODO: is this a "to-do"?
    """
    To be called by ajax methods. Creates a new address and responds with the created address on a JSON.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    data = {}
    if request.method == "POST" and request.META.get('HTTP_X_REQUESTED_WITH') == "XMLHttpRequest":
        form = SugerenciaGeorefForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            if getattr(settings, "GEOREF_SERVICES", False):
                if address.lat is None:
                    address.needs_georef = True
            address.contact = contact
            address.save()
            data = {address.id: "{} {} {}".format(address.address_1, address.city, address.state)}
            return JsonResponse(data)
    else:
        return HttpResponseNotFound()


@csrf_exempt
def api_dynamic_prices(request):
    """
    Uses price rules to calculate products and prices depending on the products that have been selected on one of the
    views to add new products to a subscription.
    """
    if request.method == "POST" and request.META.get('HTTP_X_REQUESTED_WITH') == "XMLHttpRequest":
        frequency, product_copies = 1, {}
        for key, value in list(request.POST.items()):
            if key == "frequency":
                frequency = value
            else:
                product_copies[key] = value
        product_copies = process_products(product_copies)
        price = calc_price_from_products(product_copies, frequency)
        return JsonResponse({"price": price})
    else:
        return HttpResponseNotFound()


@csrf_exempt
def api_get_addresses(request, contact_id):
    if request.method == "POST" and request.META.get('HTTP_X_REQUESTED_WITH') == "XMLHttpRequest":
        contact = get_object_or_404(Contact, pk=contact_id)
        addresses_list = []
        addresses_qs = contact.addresses.all()
        for address in addresses_qs:
            addresses_list.append({"value": address.id, "text": f"{address.address_1} {address.city} {address.state}"})
        return JsonResponse(addresses_list, safe=False)
    else:
        return HttpResponseNotFound()


@login_required
def dynamic_contact_filter_new(request):
    if request.POST:
        form = NewDynamicContactFilterForm(request.POST)
        if form.is_valid():
            description = form.cleaned_data["description"]
            products = form.cleaned_data["products"]
            newsletters = form.cleaned_data["newsletters"]
            allow_promotions = form.cleaned_data["allow_promotions"]
            allow_polls = form.cleaned_data["allow_polls"]
            mode = form.cleaned_data["mode"]
            mailtrain_id = form.cleaned_data["mailtrain_id"]
            autosync = form.cleaned_data["autosync"]
            if request.POST.get("confirm", None):
                dcf = DynamicContactFilter(
                    description=description,
                    allow_promotions=allow_promotions,
                    allow_polls=allow_polls,
                    mode=mode,
                    mailtrain_id=mailtrain_id,
                    autosync=autosync,
                )
                dcf.save()
                if mode == 3:
                    for newsletter in newsletters:
                        dcf.newsletters.add(newsletter)
                else:
                    for product in products:
                        dcf.products.add(product)
                return HttpResponseRedirect(reverse("dynamic_contact_filter_list"))

            # After getting the data, process it to find out how many records there are for the filter
            if mode == 3:
                subscription_newsletters = SubscriptionNewsletter.objects.all()
                for newsletter in newsletters:
                    subscription_newsletters = subscription_newsletters.filter(product=newsletter)
                subscription_newsletters = subscription_newsletters.filter(contact__email__isnull=False)
                count = subscription_newsletters.count()
                email_sample = subscription_newsletters.values("contact__email")[:50]
            else:
                if mode == 1:  # At least one of the products
                    subscriptions = Subscription.objects.filter(active=True, products__in=products)
                elif mode == 2:  # All products must match
                    subscriptions = Subscription.objects.annotate(count=Count("products")).filter(
                        active=True, count=products.count()
                    )
                    for product in products:
                        subscriptions = subscriptions.filter(products=product)
                if allow_promotions:
                    subscriptions = subscriptions.filter(contact__allow_promotions=True)
                if allow_polls:
                    subscriptions = subscriptions.filter(contact__allow_polls=True)
                if debtor_contacts:
                    only_debtors = subscriptions.filter(
                        contact__invoice__expiration_date__lte=date.today(),
                        contact__invoice__paid=False,
                        contact__invoice__debited=False,
                        contact__invoice__canceled=False,
                        contact__invoice__uncollectible=False,
                    ).prefetch_related("contact__invoice_set")
                    if debtor_contacts == 1:
                        subscriptions = subscriptions.exclude(pk__in=only_debtors.values('pk'))
                    elif debtor_contacts == 2:
                        subscriptions = only_debtors
                # Finally we remove the ones who don't have emails and apply distinct by contact
                if mode == 1:
                    subscriptions = subscriptions.filter(contact__email__isnull=False).distinct("contact")
                else:
                    subscriptions = subscriptions.filter(contact__email__isnull=False)
                count = subscriptions.count()
                email_sample = subscriptions.values("contact__email")[:50]

            return render(
                request,
                "dynamic_contact_filter.html",
                {
                    "email_sample": email_sample,
                    "form": form,
                    "confirm": True,
                    "count": count,
                },
            )
    else:
        form = NewDynamicContactFilterForm()
        return render(request, "dynamic_contact_filter.html", {"form": form})


@login_required
def dynamic_contact_filter_list(request):
    dcf_list = DynamicContactFilter.objects.all()
    return render(
        request,
        "dynamic_contact_filter_list.html",
        {
            "dcf_list": dcf_list,
            "mailtrain_url": settings.MAILTRAIN_URL,
        },
    )


@login_required
def dynamic_contact_filter_edit(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    form = NewDynamicContactFilterForm(instance=dcf)
    if request.POST:
        form = NewDynamicContactFilterForm(request.POST, instance=dcf)
        if form.is_valid():
            description = form.cleaned_data["description"]
            products = form.cleaned_data["products"]
            newsletters = form.cleaned_data["newsletters"]
            allow_promotions = form.cleaned_data["allow_promotions"]
            allow_polls = form.cleaned_data["allow_polls"]
            mode = form.cleaned_data["mode"]
            mailtrain_id = form.cleaned_data["mailtrain_id"]
            autosync = form.cleaned_data["autosync"]
            debtor_contacts = form.cleaned_data["debtor_contacts"]
            if request.POST.get("confirm", None):
                dcf.description = description
                dcf.allow_promotions = allow_promotions
                dcf.allow_polls = allow_polls
                dcf.mode = mode
                dcf.mailtrain_id = mailtrain_id
                dcf.autosync = autosync
                dcf.products = products
                dcf.newsletters = newsletters
                dcf.debtor_contacts = debtor_contacts
                dcf.save()
                return HttpResponseRedirect(reverse("dynamic_contact_filter_edit", args=[dcf.id]))

            # After getting the data, process it to find out how many records there are for the filter
            if mode == 3:
                subscription_newsletters = SubscriptionNewsletter.objects.all()
                for newsletter in newsletters:
                    subscription_newsletters = subscription_newsletters.filter(product=newsletter)
                subscription_newsletters = subscription_newsletters.filter(contact__email__isnull=False)
                count = subscription_newsletters.count()
            else:
                if mode == 1:  # At least one of the products
                    subscriptions = Subscription.objects.filter(active=True, products__in=products)
                elif mode == 2:  # All products must match
                    subscriptions = Subscription.objects.annotate(count=Count("products")).filter(
                        active=True, count=products.count()
                    )
                    for product in products:
                        subscriptions = subscriptions.filter(products=product)
                if allow_promotions:
                    subscriptions = subscriptions.filter(contact__allow_promotions=True)
                if allow_polls:
                    subscriptions = subscriptions.filter(contact__allow_polls=True)
                if debtor_contacts:
                    only_debtors = subscriptions.filter(
                        contact__invoice__expiration_date__lte=date.today(),
                        contact__invoice__paid=False,
                        contact__invoice__debited=False,
                        contact__invoice__canceled=False,
                        contact__invoice__uncollectible=False,
                    ).prefetch_related("contact__invoice_set")
                    if debtor_contacts == 1:
                        subscriptions = subscriptions.exclude(pk__in=only_debtors.values('pk'))
                    elif debtor_contacts == 2:
                        subscriptions = only_debtors
                # Finally we remove the ones who don't have emails and apply distinct by contact
                if mode == 1:
                    subscriptions = subscriptions.filter(contact__email__isnull=False).distinct("contact")
                else:
                    subscriptions = subscriptions.filter(contact__email__isnull=False)
                count = subscriptions.count()

            return render(
                request,
                "dynamic_contact_filter_details.html",
                {
                    "dcf": dcf,
                    "form": form,
                    "confirm": True,
                    "count": count,
                },
            )
    return render(request, "dynamic_contact_filter_details.html", {"dcf": dcf, "form": form})


@login_required
def export_dcf_emails(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dcf_list_{}.csv"'.format(dcf.id)

    writer = csv.writer(response)
    for email in dcf.get_emails():
        writer.writerow([email])

    return response


@login_required
def advanced_export_dcf_list(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dcf_advanced_list_{}.csv"'.format(dcf.id)

    writer = csv.writer(response)
    header = [
        _("Contact ID"),
        _("Name"),
        _("Email"),
        _("id document"),
        _("Phone"),
        _("Mobile"),
        _("Institutional phone"),
    ]
    writer.writerow(header)
    for contact in dcf.get_contacts():
        row = [
            contact.id,
            contact.get_full_name(),
            contact.id_document,
            contact.email,
            contact.phone,
            contact.mobile,
            contact.work_phone,
        ]
        writer.writerow(row)
    return response


@login_required
def sync_with_mailtrain(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    if not dcf.mailtrain_id:
        messages.error(
            request,
            _(
                "This filter has no mailtrain id. To use the sync function"
                f" choose a list id from {settings.MAILTRAIN_URL}lists"
            ),
        )
        return HttpResponseRedirect(reverse("dynamic_contact_filter_edit", args=[dcf.id]))
    try:
        dcf.sync_with_mailtrain_list()
    except Exception as e:
        messages.error(request, _(f"Error: {e}"))
    return HttpResponseRedirect(reverse("dynamic_contact_filter_edit", args=[dcf.id]))


@staff_member_required
def register_activity(request):
    issue_id = request.GET.get("issue_id", None)
    form = NewActivityForm(request.POST)
    if form.is_valid():
        Activity.objects.create(
            contact=form.cleaned_data["contact"],
            issue_id=issue_id,
            direction=form.cleaned_data["direction"],
            notes=form.cleaned_data["notes"],
            datetime=datetime.now(),
            activity_type=form.cleaned_data["activity_type"],
            status="C",  # it should be completed
        )
    if issue_id:
        return HttpResponseRedirect(reverse("view_issue", args=[issue_id]))
    else:
        return HttpResponseRedirect(reverse("contact_detail", args=[form.cleaned_data["contact"].id]))


@staff_member_required
def toggle_mailtrain_subscription(request, contact_id, list):
    get_object_or_404(Contact, pk=contact_id)
    return HttpResponseRedirect(reverse("edit_contact", args=[contact_id]) + "#newsletters")


@staff_member_required
def edit_envelopes(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    if request.POST:
        try:
            for name, value in list(request.POST.items()):
                if name.startswith("env-"):
                    sp_id = name.replace("env-", "")
                    sp = SubscriptionProduct.objects.get(pk=sp_id)
                    if sp.subscription != subscription:
                        raise _
                    if value == "-":
                        sp.has_envelope = None
                    else:
                        sp.has_envelope = value
                    sp.save()
        except Exception as e:
            messages.error(request, e)
            return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact_id]))

        messages.success(request, _("Envelope data has been saved."))
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact_id]))

    return render(
        request,
        "edit_envelopes.html",
        {
            "subscription": subscription,
            "subscription_products": subscription.get_subscriptionproducts(without_discounts=True),
        },
    )


@staff_member_required
def upload_payment_certificate(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    if request.POST:
        form = SubscriptionPaymentCertificateForm(request.POST, request.FILES, instance=subscription)
        if form.is_valid():
            form.save()
            messages.success(request, _("Payment certificate has been uploaded successfully"))
            return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact_id]))
    else:
        form = SubscriptionPaymentCertificateForm(instance=subscription)

    return render(
        request,
        "upload_payment_certificate.html",
        {
            "subscription": subscription,
            "form": form,
        },
    )


@staff_member_required
def invoicing_issues(request):
    """
    Shows a more comprehensive list of issues for debtors.
    """
    issues_queryset = (
        Issue.objects.filter(
            category="I",
            contact__invoice__paid=False,
            contact__invoice__debited=False,
            contact__invoice__canceled=False,
            contact__invoice__uncollectible=False,
            contact__invoice__expiration_date__lte=date.today(),
        )
        .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
        .annotate(owed_invoices=Count("contact__invoice"))
        .annotate(debt=Sum("contact__invoice__amount"))
        .annotate(oldest_invoice=Min("contact__invoice__creation_date"))
    )
    sort_by = request.GET.get("sort_by", "owed_invoices")
    order = request.GET.get("order", "desc")
    if sort_by:
        if order == "desc":
            issues_queryset = issues_queryset.order_by("-{}".format(sort_by))
        else:
            issues_queryset = issues_queryset.order_by(sort_by)
    issues_filter = InvoicingIssueFilter(request.GET, queryset=issues_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(issues_filter.qs, 100)
    if request.GET.get("export"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoicing_issues_{}.csv"'.format(date.today())
        writer = csv.writer(response)
        header = [
            _("Start date"),
            _("Contact ID"),
            _("Contact name"),
            _("Activities count"),
            _("Status"),
            _("Next action date"),
            _("Owed invoices"),
            _("Debt amount"),
            _("Oldest invoice"),
            _("Assigned to"),
        ]
        writer.writerow(header)
        for issue in issues_filter.qs.all():
            writer.writerow(
                [
                    issue.date,
                    issue.contact.id,
                    issue.contact.get_full_name(),
                    issue.activity_count(),
                    issue.get_status(),
                    issue.owed_invoices,
                    issue.debt,
                    issue.oldest_invoice,
                    issue.get_assigned_to(),
                ]
            )
        return response
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.page(paginator.num_pages)
    return render(
        request,
        "invoicing_issues.html",
        {
            "page": page,
            "paginator": paginator,
            "issues_filter": issues_filter,
            "count": issues_filter.qs.count(),
            "sort_by": sort_by,
            "order": order,
        },
    )


@staff_member_required
def debtor_contacts(request):
    """
    Shows a comprehensive list of contacts that are debtors.
    """
    debtor_queryset = (
        Contact.objects.filter(
            invoice__paid=False,
            invoice__debited=False,
            invoice__canceled=False,
            invoice__uncollectible=False,
            invoice__expiration_date__lte=date.today(),
        )
        .annotate(owed_invoices=Count("invoice", distinct=True))
        .annotate(debt=Sum("invoice__amount"))
        .annotate(oldest_invoice=Min("invoice__creation_date"))
    )
    sort_by = request.GET.get("sort_by", "owed_invoices")
    order = request.GET.get("order", "desc")
    if sort_by:
        if order == "desc":
            debtor_queryset = debtor_queryset.order_by("-{}".format(sort_by))
        else:
            debtor_queryset = debtor_queryset.order_by(sort_by)
    debtor_filter = ContactFilter(request.GET, queryset=debtor_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(debtor_filter.qs, 100)
    if request.GET.get("export"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="debtors_{}.csv"'.format(date.today())
        writer = csv.writer(response)
        header = [
            _("Contact ID"),
            _("Contact name"),
            _("Has active subscriptions"),
            _("Owed invoices"),
            _("Unfinished invoicing issues"),
            _("Finished invoicing issues"),
            _("Debt amount"),
            _("Oldest invoice"),
        ]
        writer.writerow(header)
        for contact in debtor_queryset.all():
            writer.writerow(
                [
                    contact.id,
                    contact.get_full_name(),
                    contact.has_active_subscription(),
                    contact.owed_invoices,
                    contact.get_open_issues_by_category_count("I"),
                    contact.get_finished_issues_by_category_count("I"),
                    contact.get_debt(),
                    contact.oldest_invoice,
                ]
            )
        return response
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.page(paginator.num_pages)
    return render(
        request,
        "debtor_contacts.html",
        {
            "page": page,
            "paginator": paginator,
            "debtor_filter": debtor_filter,
            # "count": debtor_filter.qs.count(),
            "count": debtor_filter.qs.count(),
            "sum": debtor_filter.qs.aggregate(total_sum=Sum("invoice__amount"))["total_sum"],
            "sort_by": sort_by,
            "order": order,
        },
    )


@staff_member_required
def campaign_statistics_list(request):
    campaigns_filter = CampaignFilter(request.GET, queryset=Campaign.objects.all())
    for campaign in campaigns_filter.qs:
        contacts = campaign.contactcampaignstatus_set.count() or 1
        campaign.called_count = campaign.contactcampaignstatus_set.filter(status__gte=2).count()
        campaign.called_pct = (campaign.called_count * 100) / contacts
        campaign.contacted_count = campaign.contactcampaignstatus_set.filter(status__in=(2, 4)).count()
        campaign.contacted_pct = (campaign.contacted_count * 100) / contacts
        campaign.success_count = campaign.contactcampaignstatus_set.filter(
            campaign_resolution__in=("S1", "S2")
        ).count()
        campaign.success_over_total_pct = (campaign.success_count * 100) / (contacts or 1)
        campaign.success_over_contacted_pct = (campaign.success_count * 100) / (campaign.contacted_count or 1)
    return render(
        request,
        "campaign_statistics_list.html",
        {
            "campaigns": campaigns_filter.qs,
            "campaigns_filter": campaigns_filter,
        },
    )


@staff_member_required
def campaign_statistics_detail(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    ccs_queryset = campaign.contactcampaignstatus_set.all()
    ccs_filter = ContactCampaignStatusFilter(request.GET, queryset=ccs_queryset)
    assigned_count = campaign.contactcampaignstatus_set.filter(seller__isnull=False).count()
    not_assigned_count = campaign.contactcampaignstatus_set.filter(seller__isnull=True).count()
    filtered_count = ccs_filter.qs.count()
    total_count = campaign.contactcampaignstatus_set.count()
    not_contacted_yet_count = ccs_filter.qs.filter(status=1).count()
    tried_to_contact_count = ccs_filter.qs.filter(status=3).count()
    contacted_count = ccs_filter.qs.filter(status__in=[2, 4]).count()
    could_not_contact_count = ccs_filter.qs.filter(status=5).count()

    ccs_with_resolution = ccs_filter.qs.filter(campaign_resolution__isnull=False)
    ccs_with_resolution_contacted_count = ccs_with_resolution.filter(status__in=[2, 4]).count()
    ccs_with_resolution_not_contacted_count = ccs_with_resolution.filter(status__in=[3, 5]).count()
    # unused, see if we want to use this
    # ccs_with_resolution_count = ccs_with_resolution.count()

    success_with_direct_sale_count = ccs_with_resolution.filter(campaign_resolution="S2").count()
    success_with_promotion_count = ccs_with_resolution.filter(campaign_resolution="S1").count()
    scheduled_count = ccs_with_resolution.filter(campaign_resolution="SC").count()
    call_later_count = ccs_with_resolution.filter(campaign_resolution="CL").count()
    unreachable_count = ccs_with_resolution.filter(campaign_resolution="UN").count()
    error_in_promotion_count = ccs_with_resolution.filter(campaign_resolution="EP").count()
    started_promotion_count = ccs_with_resolution.filter(campaign_resolution="SP").count()

    # Rejects section
    total_rejects = ccs_with_resolution.filter(campaign_resolution__in=("AS", "DN", "LO", "NI"))
    total_rejects_count = total_rejects.count()
    rejects_with_reason = total_rejects.filter(resolution_reason__isnull=False)
    rejects_with_reason_count = rejects_with_reason.count()
    rejects_without_reason_count = total_rejects.filter(resolution_reason__isnull=True).count()
    rejects_by_reason = {}
    for ccs in rejects_with_reason.iterator():
        reason = ccs.get_resolution_reason_display()
        item = rejects_by_reason.get(reason, 0)
        item += 1
        rejects_by_reason[reason] = item
    for index, item in list(rejects_by_reason.items()):
        pct = (item * 100) / (rejects_with_reason_count or 1)
        rejects_by_reason[index] = (item, pct)

    success_rate_count = success_with_promotion_count + success_with_direct_sale_count
    success_rate_pct = ((success_with_promotion_count + success_with_direct_sale_count) * 100) / (filtered_count or 1)

    if ccs_filter.data.get("seller", None):
        seller = Seller.objects.get(pk=ccs_filter.data["seller"])
        seller_assigned_count = campaign.contactcampaignstatus_set.filter(seller=seller).count()
    else:
        seller, seller_assigned_count = None, None

    # Per product section
    subs_dict = {}
    subscription_products = SubscriptionProduct.objects.filter(subscription__campaign=campaign)
    if seller:
        subscription_products = subscription_products.filter(seller=seller)
    for product in Product.objects.filter(offerable=True, type="S"):
        subs_dict[product.name] = subscription_products.filter(product=product).count()
    try:
        most_sold = max(subs_dict, key=subs_dict.get)
        most_sold_count = subs_dict[max(subs_dict, key=subs_dict.get)]
    except Exception:
        most_sold, most_sold_count = None, None

    return render(
        request,
        "campaign_statistics_detail.html",
        {
            "campaign": campaign,
            "filter": ccs_filter,
            "filtered_count": ccs_filter.qs.count(),
            "total_count": total_count,
            "assigned_count": assigned_count,
            "not_assigned_count": not_assigned_count,
            "not_contacted_yet_count": not_contacted_yet_count,
            "not_contacted_yet_pct": float((not_contacted_yet_count * 100) / (filtered_count or 1)),
            "tried_to_contact_count": tried_to_contact_count,
            "tried_to_contact_pct": float((tried_to_contact_count * 100) / (filtered_count or 1)),
            "contacted_count": contacted_count,
            "contacted_pct": (contacted_count * 100) / (filtered_count or 1),
            "could_not_contact_count": could_not_contact_count,
            "could_not_contact_pct": (could_not_contact_count * 100) / (filtered_count or 1),
            "total_rejects_count": total_rejects_count,
            "total_rejects_pct": (total_rejects_count * 100) / (ccs_with_resolution_contacted_count or 1),
            "rejects_by_reason": rejects_by_reason,
            "rejects_without_reason_count": rejects_without_reason_count,
            "success_with_promotion_count": success_with_promotion_count,
            "success_with_promotion_pct": (success_with_promotion_count * 100)
            / (ccs_with_resolution_contacted_count or 1),
            "success_with_direct_sale_count": success_with_direct_sale_count,
            "success_with_direct_sale_pct": (success_with_direct_sale_count * 100)
            / (ccs_with_resolution_contacted_count or 1),
            "scheduled_count": scheduled_count,
            "scheduled_pct": (scheduled_count * 100) / (ccs_with_resolution_contacted_count or 1),
            "call_later_count": call_later_count,
            "call_later_pct": (call_later_count * 100) / (ccs_with_resolution_contacted_count or 1),
            "started_promotion_count": started_promotion_count,
            "started_promotion_pct": (started_promotion_count * 100) / (ccs_with_resolution_contacted_count or 1),
            "unreachable_count": unreachable_count,
            "unreachable_pct": (unreachable_count * 100) / (ccs_with_resolution_not_contacted_count or 1),
            "error_in_promotion_count": error_in_promotion_count,
            "error_in_promotion_pct": (error_in_promotion_count * 100)
            / (ccs_with_resolution_not_contacted_count or 1),
            "success_rate_count": success_rate_count,
            "success_rate_pct": success_rate_pct,
            "subs_dict": subs_dict,
            "most_sold": most_sold,
            "most_sold_count": most_sold_count,
            "seller": seller,
            "seller_assigned_count": seller_assigned_count,
        },
    )


@staff_member_required
def campaign_statistics_per_seller(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    sellers = Seller.objects.filter(internal=True).order_by("name")
    assigned_count = campaign.contactcampaignstatus_set.filter(seller__isnull=False).count()
    not_assigned_count = campaign.contactcampaignstatus_set.filter(seller__isnull=True).count()
    for seller in sellers:
        seller.assigned_count = seller.contactcampaignstatus_set.filter(campaign=campaign).count()
        assigned = seller.assigned_count or 1
        seller.not_contacted_yet_count = seller.contactcampaignstatus_set.filter(campaign=campaign, status=1).count()
        seller.not_contacted_yet_pct = (seller.not_contacted_yet_count * 100) / assigned
        seller.called_count = seller.contactcampaignstatus_set.filter(campaign=campaign, status__gte=2).count()
        seller.called_pct = (seller.called_count * 100) / assigned
        seller.contacted_count = seller.contactcampaignstatus_set.filter(campaign=campaign, status__in=[2, 4]).count()
        seller.contacted_pct = (seller.contacted_count * 100) / assigned
        seller.success_count = seller.contactcampaignstatus_set.filter(
            campaign=campaign, campaign_resolution__in=("S1", "S2")
        ).count()
        seller.success_pct = (seller.success_count * 100) / assigned
        seller.rejected_count = seller.contactcampaignstatus_set.filter(
            campaign=campaign, campaign_resolution__in=("AS", "DN", "LO", "NI")
        ).count()
        seller.rejected_pct = (seller.rejected_count * 100) / assigned
        seller.unreachable_count = seller.contactcampaignstatus_set.filter(campaign=campaign, status=5).count()
        seller.unreachable_pct = (seller.unreachable_count * 100) / assigned
    return render(
        request,
        "campaign_statistics_per_seller.html",
        {
            "campaign": campaign,
            "assigned_count": assigned_count,
            "not_assigned_count": not_assigned_count,
            "sellers": sellers,
        },
    )


@staff_member_required
def seller_performance_by_time(request):
    sellers = Seller.objects.filter(internal=True).order_by("name")
    date_from = date(date.today().year, date.today().month, 1)
    date_to = date(
        date.today().year + 1 if date.today().month == 12 else date.today().year,
        1 if date.today().month == 12 else date.today().month + 1,
        1,
    ) - timedelta(1)
    if request.GET:
        ccs_queryset = ContactCampaignStatus.objects.all()
        form = ContactCampaignStatusByDateForm(request.GET)
        if form.is_valid():
            date_from = form.cleaned_data["date_gte"]
            date_to = form.cleaned_data["date_lte"]
    else:
        form = ContactCampaignStatusByDateForm(initial={"date_gte": date_from, "date_lte": date_to})
    ccs_queryset = ContactCampaignStatus.objects.filter(
        last_action_date__gte=date_from,
        last_action_date__lte=date_to,
    )
    assigned_count = ccs_queryset.filter(seller__isnull=False).count() or 1
    called_count = ccs_queryset.filter(seller__isnull=False, status__gte=2).count()
    called_pct = (called_count * 100) / assigned_count
    contacted_count = ccs_queryset.filter(seller__isnull=False, status__in=[2, 4]).count()
    contacted_pct = (contacted_count * 100) / assigned_count
    success_count = ccs_queryset.filter(seller__isnull=False, campaign_resolution__in=("S1", "S2")).count()
    success_pct = (success_count * 100) / assigned_count

    for seller in sellers:
        seller.assigned_count = ccs_queryset.filter(seller=seller).count()
        seller.not_contacted_yet_count = ccs_queryset.filter(seller=seller, status=1).count()
        seller.not_contacted_yet_pct = (seller.not_contacted_yet_count * 100) / (seller.assigned_count or 1)
        seller.called_count = ccs_queryset.filter(seller=seller, status__gte=2).count()
        seller.called_pct = (seller.called_count * 100) / (seller.assigned_count or 1)
        seller.contacted_count = ccs_queryset.filter(seller=seller, status__in=[2, 4]).count()
        seller.contacted_pct = (seller.contacted_count * 100) / (seller.assigned_count or 1)
        seller.success_count = ccs_queryset.filter(seller=seller, campaign_resolution__in=("S1", "S2")).count()
        seller.success_pct = (seller.success_count * 100) / (seller.assigned_count or 1)
        seller.rejected_count = ccs_queryset.filter(
            seller=seller, campaign_resolution__in=("AS", "DN", "LO", "NI")
        ).count()
        seller.rejected_pct = (seller.rejected_count * 100) / (seller.assigned_count or 1)
        seller.unreachable_count = ccs_queryset.filter(seller=seller, status=5).count()
        seller.unreachable_pct = (seller.unreachable_count * 100) / (seller.assigned_count or 1)
    return render(
        request,
        "seller_performance_by_time.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "form": form,
            "sellers": sellers,
            "assigned_count": assigned_count,
            "called_count": called_count,
            "called_pct": called_pct,
            "contacted_count": contacted_count,
            "contacted_pct": contacted_pct,
            "success_count": success_count,
            "success_pct": success_pct,
        },
    )


@staff_member_required
def edit_address_complementary_information(request, address_id):
    address = get_object_or_404(Address, pk=address_id)
    if request.POST:
        form = AddressComplementaryInformationForm(request.POST, request.FILES, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, _("Address information has been updated successfully"))
            return HttpResponseRedirect(reverse("contact_detail", args=[address.contact_id]))
    else:
        form = AddressComplementaryInformationForm(instance=address)

    return render(
        request,
        "edit_address_complementary_information.html",
        {
            "address": address,
            "form": form,
        },
    )


def history_build_aux(object, tags=False):
    history_qs = object.history.all().order_by('-history_date')
    history_dict = {}
    for history in history_qs:
        if history.prev_record:
            list_of_changes = []
            delta = history.diff_against(history.prev_record)
            for change in delta.changes:
                if tags and change.field == "tags":
                    continue
                old, new = change.old, change.new
                if isinstance(object, Issue):
                    if change.field == "status":
                        if change.old:
                            old = IssueStatus.objects.get(pk=change.old).name
                        if change.new:
                            new = IssueStatus.objects.get(pk=change.new).name
                    if change.field == "sub_category":
                        if change.old:
                            old = IssueSubcategory.objects.get(pk=change.old).name
                        if change.new:
                            new = IssueSubcategory.objects.get(pk=change.new).name
                    if change.field == "answer_1":
                        issue_answer_dict = dict(ISSUE_ANSWERS)
                        old = issue_answer_dict.get(change.old, None)
                        new = issue_answer_dict.get(change.new, None)
                list_of_changes.append([change.field, old, new])
            history_dict[history] = list_of_changes
        else:
            history_dict[history] = (["created"],)
    return history_dict


@staff_member_required
def history_extended(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    contact_history_dict = history_build_aux(contact, tags=True)

    # Subscriptions
    subscriptions = contact.subscriptions.all().order_by("-start_date")
    subscriptions_list = [subscription for subscription in subscriptions if subscription.history.count() > 1]
    subscriptions_history_dict = {}
    for subscription in subscriptions_list:
        history_dict = history_build_aux(subscription)
        subscriptions_history_dict[subscription] = history_dict

    # Issues
    issues = contact.issue_set.all().order_by("-date_created")
    issues_list = [issue for issue in issues if issue.history.count() > 1]
    issues_history_dict = {}
    for issue in issues_list:
        history_dict = history_build_aux(issue)
        issues_history_dict[issue] = history_dict
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": contact.get_full_name(),
            "url": reverse("contact_detail", args=[contact.id]),
        },
        {"label": _("History"), "url": ""},
    ]
    return render(
        request,
        "history_extended.html",
        {
            "contact": contact,
            "contact_history_dict": contact_history_dict,
            "subscriptions_history_dict": subscriptions_history_dict,
            "issues_history_dict": issues_history_dict,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def upload_do_not_call_numbers(request):
    if request.FILES:
        decoded_file = request.FILES.get("do_not_call_numbers").read().decode("utf-8").splitlines()
        numbers = csv.reader(decoded_file)
        if numbers:
            # Remove both headers
            next(numbers)
            next(numbers)

            DoNotCallNumber.delete_all_numbers()
            DoNotCallNumber.upload_new_numbers(numbers)

            messages.success(request, _("Numbers have been uploaded successfully."))
            return HttpResponseRedirect("/")

    return render(
        request,
        "upload_do_not_call_numbers.html",
    )


@staff_member_required
def tag_contacts(request):
    if request.FILES:
        decoded_file = request.FILES.get("file").read().decode("utf-8").splitlines()
        csvfile = csv.reader(decoded_file)
        count = 0
        errors = []
        if csvfile:
            for row in csvfile:
                try:
                    contact = Contact.objects.get(pk=row[0])
                    contact.tags.add(row[1].lower())
                    count += 1
                except Contact.DoesNotExist:
                    errors.append(f"Contacto con id {row[0]} no existe.")
            messages.success(request, f"Se agregaron {count} etiquetas.")
            if errors:
                messages.error(request, f"{len(errors)} contactos no existen")
            return HttpResponseRedirect(reverse("tag_contacts"))

    return render(
        request,
        "tag_contacts.html",
    )


@staff_member_required
def not_contacted_campaign(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)
    contacts = Contact.objects.filter(contactcampaignstatus__campaign=campaign_obj, contactcampaignstatus__status=5)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{campaign_obj.name}_inubicables_{date.today()}.csv"'
    writer = csv.writer(response)
    header = [
        _("Contact ID"),
        _("Contact name"),
        _("Email"),
        _("Phone"),
        _("Mobile"),
        "Inubicables",
    ]
    writer.writerow(header)
    for c in contacts.order_by('id'):
        writer.writerow([c.id, c.name, c.email, c.phone, c.mobile])
    return response


@method_decorator(staff_member_required, name="dispatch")
class SalesRecordFilterSellersView(FilterView):
    # This view is similar to the previous one but for the seller to see what sales they have made.
    filterset_class = SalesRecordFilterForSeller
    template_name = "sales_record_filter.html"
    paginate_by = 100
    queryset = (
        SalesRecord.objects.all()
        .prefetch_related("products")
        .select_related("subscription__contact")
        .order_by("-date_time")
    )
    seller = None
    page_kwarg = 'p'

    def get_queryset(self):
        queryset = super().get_queryset()
        self.seller = self.request.user.seller_set.first()
        if self.seller:
            self.queryset = queryset.filter(seller=self.seller)
        filterset = self.filterset_class(self.request.GET, queryset=self.queryset)
        return filterset.qs

    def get_sales_distribution_by_product(self, queryset) -> dict:
        # Assuming you have a list of dictionaries with each sale record's id and total_products
        # This queryset fetches all sales records with their product counts
        sales_records = queryset.annotate(total_products=Count('products')).values('id', 'total_products')
        df = pd.DataFrame(sales_records)
        special_product_sales_ids = list(
            queryset.filter(products__slug='la-diaria-5-dias').values_list('id', flat=True)
        )
        # Mark rows that contain the special product
        df['has_special_product'] = df['id'].isin(special_product_sales_ids)
        # Adjust counts
        df['adjusted_count'] = df['total_products'] + df['has_special_product']
        # Ensure counts do not exceed 4
        df['adjusted_count'] = df['adjusted_count'].clip(upper=4)
        # Create the distribution
        distribution = df['adjusted_count'].value_counts().sort_index().to_dict()
        return distribution

    def get_sales_distribution_by_payment_type(self, queryset) -> dict:
        sales_records = queryset.values('subscription__payment_type')
        df = pd.DataFrame(sales_records)
        # Only show values whose keys are in settings.SELLER_COMMISSION_PAYMENT_METHODS keys, if the setting exists
        if hasattr(settings, 'SELLER_COMMISSION_PAYMENT_METHODS'):
            df = df[df['subscription__payment_type'].isin(settings.SELLER_COMMISSION_PAYMENT_METHODS.keys())]
        if hasattr(settings, 'SUBSCRIPTION_PAYMENT_METHODS'):
            # Convert choices to a dictionary
            payment_type_dict = dict(settings.SUBSCRIPTION_PAYMENT_METHODS)
            # Map the payment types to their display values in the DataFrame
            df['payment_type_display'] = df['subscription__payment_type'].map(payment_type_dict)
            distribution = df["payment_type_display"].value_counts().sort_index().to_dict()
        else:
            distribution = df["subscription__payment_type"].value_counts().to_dict()
        return distribution

    def get_sales_distribution_by_subscription_frequency(self, queryset) -> dict:
        sales_records = queryset.values('subscription__frequency')
        df = pd.DataFrame(sales_records)
        frequencies_dict = dict(core_choices.FREQUENCY_CHOICES)
        df['frequency_display'] = df['subscription__frequency'].map(frequencies_dict)
        distribution = df['frequency_display'].value_counts().sort_index().to_dict()
        return distribution

    def get_commissions(self, queryset):
        return queryset.aggregate(total_commission=Sum('total_commission_value'))["total_commission"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context["seller"] = self.seller
        context["total_commission"] = self.get_commissions(queryset)
        if not queryset.exists():
            messages.error(self.request, _("You have no sales records."))
            return context
        context["sales_distribution_product_count"] = self.get_sales_distribution_by_product(queryset)
        context["sales_distribution_payment_type"] = self.get_sales_distribution_by_payment_type(
            queryset.filter(sale_type=SalesRecord.SALE_TYPE.FULL)
        )
        context["sales_distribution_by_subscription_frequency"] = (
            self.get_sales_distribution_by_subscription_frequency(queryset)
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
class SalesRecordFilterManagersView(SalesRecordFilterSellersView):
    # This view is only for managers to see the sales records of all sellers.
    filterset_class = SalesRecordFilter
    is_manager = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.groups.filter(name="Managers").exists():
            messages.error(request, _("You are not authorized to see this page"))
            return HttpResponseRedirect(reverse("home"))
        if not SalesRecord.objects.exists():
            messages.error(request, _("There are no sales records."))
            return HttpResponseRedirect(reverse("home"))
        self.is_manager = True
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = self.is_manager
        return context

    def export_to_csv(self):
        queryset = self.get_queryset()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales_records_export.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_NONNUMERIC)
        header = [
            _("Contact ID"),
            _("Date"),
            _("Seller"),
            _("Subscription start date"),
            _("Products"),
            _("Campaign"),
            _("Sale Type"),
            _("Total Commission"),
            _("Validated"),
        ]
        writer.writerow(header)
        for sr in queryset:
            writer.writerow(
                [
                    sr.subscription.contact.id,
                    sr.date_time,
                    sr.seller.name if sr.seller else "",
                    sr.subscription.start_date,
                    ", ".join([p.name for p in sr.products.all()]),
                    sr.campaign.name if sr.campaign else "",
                    sr.get_sale_type_display(),
                    sr.calculate_total_commission(),
                    sr.subscription.validated,
                ]
            )
        return response

    def get(self, request, *args, **kwargs):
        if request.GET.get("export"):
            return self.export_to_csv()
        return super().get(request, *args, **kwargs)


@method_decorator(staff_member_required, name="dispatch")
class ValidateSubscriptionSalesRecord(BreadcrumbsMixin, UpdateView):
    # This view is only available to managers. It allows them to validate a subscription and set if the
    # SaleRecord can be used for commission.
    model = SalesRecord
    form_class = ValidateSubscriptionForm
    template_name = "validate_subscription_sales_record.html"

    def breadcrumbs(self):
        return [
            {"url": reverse("contact_list"), "label": _("Contacts")},
            {
                "url": reverse("contact_detail", args=[self.object.subscription.contact.id]),
                "label": self.object.subscription.contact.get_full_name(),
            },
            {"label": _("Validate subscription")},
        ]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.groups.filter(name="Managers").exists():
            messages.error(request, _("You are not authorized to see this page"))
            return HttpResponseRedirect(reverse("home"))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if self.object.sale_type != SalesRecord.SALE_TYPE.FULL:
            initial["can_be_commissioned"] = False
            initial["subscription"] = self.object.subscription
            initial["seller"] = self.object.seller
        return initial

    def get_success_url(self):
        return reverse("sales_record_filter")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subscription"] = self.object.subscription
        return context

    def form_valid(self, form):
        messages.success(self.request, _("The sale and subscription have been validated."))
        subscription = self.object.subscription
        sales_record = form.instance
        subscription.validate(user=self.request.user)
        if form.cleaned_data["can_be_commissioned"]:
            sales_record.can_be_commisioned = True
            SubscriptionProduct.objects.filter(subscription=subscription, product__type="S").update(
                seller=sales_record.seller
            )
            if form.cleaned_data["override_commission_value"]:
                sales_record.total_commission_value = form.cleaned_data["override_commission_value"]
            else:
                sales_record.set_commissions(force=True)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error validating the sale and subscription."))
        # Show errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


@method_decorator(staff_member_required, name="dispatch")
class ValidateSubscriptionRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        subscription = get_object_or_404(Subscription, pk=kwargs["pk"])
        sales_record = subscription.salesrecord_set.first()
        if not sales_record:
            messages.error(self.request, _("This subscription has no sales record."))
            return reverse("sales_record_filter")
        if subscription.validated:
            messages.error(self.request, _("This subscription has already been validated."))
            return reverse("sales_record_filter")
        return reverse("validate_sale", args=[sales_record.id])


@method_decorator(staff_member_required, name="dispatch")
class SalesRecordCreateView(CreateView):
    model = SalesRecord
    form_class = SalesRecordCreateForm
    template_name = "sales_record_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["subscription"] = self.subscription
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subscription"] = self.subscription
        return context

    def dispatch(self, request, *args, **kwargs):
        self.subscription = get_object_or_404(Subscription, pk=self.kwargs["subscription_id"])
        if self.subscription.salesrecord_set.exists():
            messages.error(self.request, _("This subscription already has a sales record."))
            return HttpResponseRedirect(reverse("sales_record_filter"))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("sales_record_filter")

    def form_valid(self, form: forms.BaseModelForm) -> HttpResponse:
        sales_record_obj = form.save()
        sales_record_obj.products.set(self.subscription.products.filter(type="S"))
        sales_record_obj.price = self.subscription.get_price_for_full_period()
        subscription = sales_record_obj.subscription
        SubscriptionProduct.objects.filter(subscription=subscription, product__type="S").update(
            seller=sales_record_obj.seller
        )
        self.subscription.validate(user=self.request.user)
        return super().form_valid(form)


def last_read_articles(request, contact_id):
    # TODO: Move this from la diaria project to the main project. This is an htmx view.
    # contact = get_object_or_404(Contact, id=contact_id)
    return HttpResponse("")
