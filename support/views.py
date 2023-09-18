# coding=utf-8
from __future__ import division, unicode_literals
import csv
import collections
from datetime import date, timedelta, datetime

from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Sum, Min
from django.http import (
    HttpResponseServerError,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings

from taggit.models import Tag

from core.filters import ContactFilter
from core.forms import AddressForm
from core.models import (
    Contact,
    Subscription,
    Campaign,
    Address,
    Product,
    Activity,
    SubscriptionProduct,
    ContactCampaignStatus,
    SubscriptionNewsletter,
    Subtype,
    DynamicContactFilter,
    DoNotCallNumber,
)
from core.choices import CAMPAIGN_RESOLUTION_REASONS_CHOICES

from .filters import (
    IssueFilter,
    InvoicingIssueFilter,
    ScheduledActivityFilter,
    ContactCampaignStatusFilter,
    UnsubscribedSubscriptionsByEndDateFilter,
    ScheduledTaskFilter,
    CampaignFilter,
)
from .forms import (
    NewPauseScheduledTaskForm,
    PartialPauseTaskForm,
    NewAddressChangeScheduledTaskForm,
    NewPromoForm,
    NewSubscriptionForm,
    IssueStartForm,
    IssueChangeForm,
    InvoicingIssueChangeForm,
    NewAddressForm,
    NewDynamicContactFilterForm,
    NewActivityForm,
    UnsubscriptionForm,
    ContactCampaignStatusByDateForm,
    SubscriptionPaymentCertificateForm,
    AddressComplementaryInformationForm,
    SugerenciaGeorefForm,
)
from logistics.models import Route
from .models import Seller, ScheduledTask, IssueStatus, Issue, IssueSubcategory
from .choices import ISSUE_CATEGORIES, ISSUE_ANSWERS
from support.management.commands.run_scheduled_tasks import run_address_change, run_start_of_total_pause
from core.utils import calc_price_from_products, process_products
from core.forms import ContactAdminForm
from util.dates import add_business_days


now = datetime.now()


def csv_sreader(src):
    """(Magic) CSV String Reader"""

    # Auto-detect the dialect
    dialect = csv.Sniffer().sniff(src, delimiters=",;")
    return csv.reader(src.splitlines(), dialect=dialect)


@staff_member_required
def import_contacts(request):
    """
    Imports contacts from a CSV file.
    Csv must consist of a header, and then:
    name, phone, email, mobile, work_phone, notes, address, address_2, city, state

    TODO: Pandas this
    """
    if request.POST and request.FILES:
        new_contacts_list = []
        in_active_campaign = []
        active_contacts = []
        existing_inactive_contacts = []
        errors_list = []
        tag_list, tag_list_in_campaign, tag_list_active, tag_list_existing = [], [], [], []
        tags = request.POST.get("tags", None)
        if tags:
            tags = tags.split(",")
            for tag in tags:
                tag_list.append(tag.strip())
        tags_existing = request.POST.get("tags_existing", None)
        if tags_existing:
            tags_existing = tags_existing.split(",")
            for tag in tags_existing:
                tag_list_existing.append(tag.strip())
        tags_active = request.POST.get("tags_active", None)
        if tags_active:
            tags_active = tags_active.split(",")
            for tag in tags_active:
                tag_list_active.append(tag.strip())
        tags_in_campaign = request.POST.get("tags_in_campaign", None)
        if tags_in_campaign:
            tags_in_campaign = tags_in_campaign.split(",")
            for tag in tags_in_campaign:
                tag_list_in_campaign.append(tag.strip())
        # check files for every possible match
        try:
            reader = csv_sreader(request.FILES["file"].read().decode("utf-8"))
            # consume header
            next(reader)
        except csv.Error:
            messages.error(request, _("No delimiters found in csv file. Please check the delimiters for csv files."))
            return HttpResponseRedirect(reverse("import_contacts"))

        for row_number, row in enumerate(reader, start=1):
            try:
                name = row[0]
                phone = row[1] or None
                email = row[2] or None
                mobile = row[3] or None
                work_phone = row[4] or None
                notes = row[5].strip() or None
                address_1 = row[6] or None
                address_2 = row[7] or None
                city = row[8] or None
                state = row[9].strip() or None
                # This is only valid for Uruguay. If needed we might move this to a custom function or setting
                if phone and phone.startswith("9"):
                    phone = "0{}".format(phone)
                if mobile and mobile.startswith("9"):
                    mobile = "0{}".format(mobile)
                if work_phone and work_phone.startswith("9"):
                    work_phone = "0{}".format(work_phone)
                if phone == "" or mobile == "" or work_phone == "" or not any([phone, mobile, work_phone]):
                    errors_list.append("CSV Row {}: {} has no phone".format(row_number, name))
                    continue
            except IndexError:
                messages.error(
                    request, _("The column count is wrong, please check that the file has at least 10 columns")
                )
                return HttpResponseRedirect(reverse("import_contacts"))
            cpx = Q()
            # We're going to look for all the fields with possible coincidences
            if email and email != "":
                cpx = cpx | Q(email=email)
            if phone and phone != "":
                cpx = cpx | Q(work_phone=phone) | Q(mobile=phone) | Q(phone=phone)
            if mobile and mobile != "":
                cpx = cpx | Q(work_phone=mobile) | Q(mobile=mobile) | Q(phone=mobile)
            if work_phone and work_phone != "":
                cpx = cpx | Q(work_phone=work_phone) | Q(mobile=work_phone) | Q(phone=work_phone)
            matches = Contact.objects.filter(cpx)
            if matches.count() > 0:
                # if we get more than one match, alert the user
                for c in matches:
                    if c.contactcampaignstatus_set.filter(campaign__active=True).exists():
                        in_active_campaign.append(c.id)
                        if tag_list_in_campaign:
                            for tag in tag_list_in_campaign:
                                c.tags.add(tag)
                    elif c.has_active_subscription():
                        active_contacts.append(C.id)
                        if tag_list_active:
                            for tag in tag_list_active:
                                c.tags.add(tag)
                    else:
                        existing_inactive_contacts.append(c.id)
                        if tag_list_existing:
                            for tag in tag_list_existing:
                                c.tags.add(tag)
            else:
                try:
                    new_contact = Contact.objects.create(
                        name=name, phone=phone, email=email, work_phone=work_phone, mobile=mobile, notes=notes
                    )
                    # Build the address if necessary
                    if address_1:
                        Address.objects.create(
                            contact=new_contact,
                            address_1=address_1,
                            address_2=address_2,
                            city=city,
                            state=state,
                            address_type="physical",
                            email=email,
                        )
                    new_contacts_list.append(new_contact)
                    if tag_list:
                        for tag in tag_list:
                            new_contact.tags.add(tag)
                except Exception as e:
                    errors_list.append("CSV Row {}: {}".format(row_number, e))
        return render(
            request,
            "import_contacts.html",
            {
                "new_contacts_count": len(new_contacts_list),
                "in_active_campaign": len(in_active_campaign),
                "active_contacts": len(active_contacts),
                "existing_inactive_contacts": len(existing_inactive_contacts),
                "errors_list": errors_list,
                "tag_list": tag_list,
            },
        )
    else:
        return render(
            request,
            "import_contacts.html",
        )


@staff_member_required
def seller_console_list_campaigns(request):
    """
    List all campaigns on a dashboard style list for sellers to use, so they can see which campaigns they have contacts
    in to call.
    """
    user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        messages.error(request, _("User has no seller selected. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))
    except Seller.MultipleObjectsReturned:
        messages.error(request, _("This seller is set in more than one user. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))

    special_routes = {}
    if getattr(settings, "SPECIAL_ROUTES_FOR_SELLERS_LIST", None):
        route_ids = settings.SPECIAL_ROUTES_FOR_SELLERS_LIST
        for route_id in route_ids:
            route = Route.objects.get(pk=route_id)
            special_routes[route_id] = (
                route.name,
                SubscriptionProduct.objects.filter(
                    seller=seller, route_id=route_id, subscription__active=True
                ).count(),
            )
    else:
        special_routes = None
    if special_routes and all(value[1] == 0 for value in list(special_routes.values())):
        special_routes = None

    # We'll make these lists so we can append the sub count to each campaign
    campaigns_with_not_contacted, campaigns_with_activities_to_do = [], []

    not_contacted_campaigns = seller.get_campaigns_by_status([1, 3])
    all_campaigns = seller.get_unfinished_campaigns()
    for campaign in not_contacted_campaigns:
        campaign.count = campaign.get_not_contacted_count(seller.id)
        campaign.successful = campaign.get_successful_count(seller.id)
        campaigns_with_not_contacted.append(campaign)
    for campaign in all_campaigns:
        campaign.pending = campaign.activity_set.filter(
            Q(campaign__end_date__isnull=True) | Q(campaign__end_date__gte=timezone.now()),
            seller=seller,
            status="P",
            activity_type="C",
            datetime__lte=timezone.now(),
        ).count()
        campaign.successful = campaign.get_successful_count(seller.id)
        if campaign.pending:
            campaigns_with_activities_to_do.append(campaign)
    upcoming_activity = seller.upcoming_activity()
    total_pending_activities = seller.total_pending_activities_count()
    return render(
        request,
        "seller_console_list_campaigns.html",
        {
            "campaigns_with_not_contacted": campaigns_with_not_contacted,
            "campaigns_with_activities_to_do": campaigns_with_activities_to_do,
            "seller": seller,
            "total_pending_activities": total_pending_activities,
            "upcoming_activity": upcoming_activity,
            "special_routes": special_routes,
        },
    )


@login_required
def seller_console(request, category, campaign_id):
    """
    Dashboard-like control panel for sellers to take actions on contacts in campaigns one by one, calling them and
    registering the activity they had with the contacts.
    """
    if request.POST and request.POST.get("result"):
        result = request.POST.get("result")
        offset = request.POST.get("offset")
        url = request.POST.get("url")
        campaign = get_object_or_404(Campaign, pk=request.POST.get("campaign_id"))
        category = request.POST.get("category")
        instance_id = request.POST.get("instance_id")
        seller_id = request.POST.get("seller_id")
        seller = Seller.objects.get(pk=seller_id)

        dict_resolution_reasons = dict(CAMPAIGN_RESOLUTION_REASONS_CHOICES)
        if request.POST.get("campaign_resolution_reason", None):
            resolution_reason = int(request.POST.get("campaign_resolution_reason"))
        else:
            resolution_reason = None
        chosen_resolution_reason = dict_resolution_reasons.get(resolution_reason, None)
        new_activity_notes = result
        if chosen_resolution_reason:
            new_activity_notes += " ({})".format(chosen_resolution_reason)
        if request.POST.get("notes", None):
            new_activity_notes += "\n" + request.POST.get("notes")

        if category == "act":
            activity = Activity.objects.get(pk=instance_id)
            contact = activity.contact
            try:
                ccs = ContactCampaignStatus.objects.get(campaign=campaign, contact=contact)
            except ContactCampaignStatus.DoesNotExist:
                messages.success(
                    request,
                    _(
                        "Activity {}: Contact {} is not present in campaign {}. Please report this error!".format(
                            activity.id, contact.id, campaign.id
                        )
                    ),
                )
                return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
            activity.notes = new_activity_notes
            activity.status = "C"
            activity.save()
            if result == _("Call later"):
                Activity.objects.create(
                    contact=contact,
                    activity_type="C",
                    datetime=datetime.now(),
                    campaign=campaign,
                    seller=seller,
                )
        elif category == "new":
            ccs = ContactCampaignStatus.objects.get(pk=instance_id)
            contact = ccs.contact
            activity = Activity.objects.create(
                contact=ccs.contact,
                activity_type="C",
                datetime=datetime.now(),
                campaign=campaign,
                seller=seller,
                status="C",
                notes=new_activity_notes,
            )
        if result == _("Schedule"):
            # Schedule customers
            ccs.campaign_resolution = "SC"
            ccs.status = 2
            call_date = request.POST.get("call_date")
            call_date = datetime.strptime(call_date, "%Y-%m-%d")
            call_time = request.POST.get("call_time")
            call_time = datetime.strptime(call_time, "%H:%M").time()
            call_datetime = datetime.combine(call_date, call_time)
            Activity.objects.create(
                contact=contact,
                activity_type="C",
                datetime=call_datetime,
                campaign=campaign,
                seller=seller,
                notes="{} {}".format(_("Scheduled for"), call_datetime),
            )

        elif result == "No encontrado, llamar más tarde":
            ccs.campaign_resolution = "CL"
            offset = int(offset) + 1
            ccs.status = 3

        elif result == _("Not interested"):
            ccs.campaign_resolution = "NI"
            ccs.status = 4

        elif result == "No volver a llamar":
            ccs.campaign_resolution = "DN"
            ccs.status = 4

        elif result == _("Logistics"):
            ccs.campaign_resolution = "LO"
            ccs.status = 4

        elif result == _("Already a subscriber"):
            ccs.campaign_resolution = "AS"
            ccs.status = 4

        elif result == "Inubicable, retirar de campaña":
            ccs.campaign_resolution = "UN"
            ccs.status = 5

        elif result == _("Error in promotion"):
            ccs.campaign_resolution = "EP"
            ccs.status = 5

        elif result == "Mover a la mañana":
            ccs.status = 6
            ccs.seller = None

        elif result == "Mover a la tarde":
            ccs.status = 7
            ccs.seller = None

        if request.POST.get("campaign_resolution_reason", None):
            ccs.resolution_reason = request.POST.get("campaign_resolution_reason", None)

        ccs.save()

        return HttpResponseRedirect(
            reverse("seller_console", args=[category, campaign.id]) + "?offset={}".format(offset) if offset else None
        )
    else:
        """
        This is if the user has not selected any option.
        """
        campaign = get_object_or_404(Campaign, pk=campaign_id)
        user = User.objects.get(username=request.user.username)
        try:
            seller = Seller.objects.get(user=user)
        except Seller.DoesNotExist:
            messages.error(request, _("User has no seller selected. Please contact your manager."))
            return HttpResponseRedirect(reverse("main_menu"))

        offset, activity_id = None, None
        if request.GET.get("offset"):
            offset = request.GET.get("offset")
        elif request.GET.get("a"):
            activity_id = request.GET.get("a")
        else:
            offset = request.POST.get("offset")

        offset = int(offset) if offset else 1
        call_datetime = datetime.strftime(date.today() + timedelta(1), "%Y-%m-%d")

        if category == "new":
            console_instances = campaign.get_not_contacted(seller.id)
        elif category == "act":
            # We make sure to show the seller only the activities that are for today.
            console_instances = campaign.activity_set.filter(
                activity_type="C", seller=seller, status="P", datetime__lte=datetime.now()
            ).order_by("datetime", "id")

        count = console_instances.count()
        if count == 0 or offset - 1 >= count:
            messages.success(request, _("You've reached the end of this list"))
            return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
        elif activity_id:
            try:
                console_instance = console_instances.get(pk=activity_id)
            except Activity.DoesNotExist:
                messages.error(request, _("An error has occurred with activity number {}".format(activity_id)))
                return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
        elif offset - 1 > 0:
            console_instance = console_instances[int(offset) - 1]
        else:
            console_instance = console_instances[0]

        contact = console_instance.contact
        times_contacted = contact.activity_set.filter(activity_type="C", status="C", campaign=campaign).count()
        all_activities = Activity.objects.filter(contact=contact).order_by("-datetime", "id")
        if category == "act":
            # If what we're watching is an activity, let's please not show it here
            all_activities = all_activities.exclude(pk=console_instance.id)
        all_subscriptions = Subscription.objects.filter(contact=contact).order_by("-active", "id")
        url = request.META["PATH_INFO"]
        addresses = Address.objects.filter(contact=contact).order_by("address_1")

        pending_activities_count = seller.total_pending_activities_count()
        upcoming_activity = seller.upcoming_activity()

        other_campaigns = ContactCampaignStatus.objects.filter(contact=contact).exclude(campaign=campaign)

        return render(
            request,
            "seller_console.html",
            {
                "campaign": campaign,
                "times_contacted": times_contacted,
                "category": category,
                "position": offset + 1,
                "offset": offset,
                "seller": seller,
                "contact": contact,
                "count": count,
                "addresses": addresses,
                "call_date": call_datetime,
                "all_activities": all_activities,
                "all_subscriptions": all_subscriptions,
                "console_instance": console_instance,
                "console_instances": console_instances,
                "url": url,
                "pending_activities_count": pending_activities_count,
                "upcoming_activity": upcoming_activity,
                "resolution_reasons": CAMPAIGN_RESOLUTION_REASONS_CHOICES,
                "other_campaigns": other_campaigns,
            },
        )


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
def send_promo(request, contact_id):
    """
    Shows a form that the sellers can use to send promotions to the contact.
    """
    url = request.GET.get("url")
    offset = request.GET.get("offset", 0)
    contact = Contact.objects.get(pk=contact_id)
    result = request.POST.get("result")
    contact_addresses = Address.objects.filter(contact=contact)
    offerable_products = Product.objects.filter(offerable=True)
    start_date = date.today()

    if request.GET.get("act", None):
        activity = Activity.objects.get(pk=request.GET.get("act"))
        campaign = activity.campaign
        ccs = ContactCampaignStatus.objects.get(contact=contact, campaign=campaign)
    elif request.GET.get("new", None):
        ccs = ContactCampaignStatus.objects.get(pk=request.GET["new"])
        campaign = ccs.campaign

    seller = ccs.seller

    if campaign:
        end_date = add_business_days(date.today(), campaign.days)
    else:
        end_date = add_business_days(date.today(), 5)

    form = NewPromoForm(
        initial={
            "name": contact.name,
            "phone": contact.phone,
            "mobile": contact.mobile,
            "email": contact.email,
            "default_address": contact_addresses,
            "start_date": start_date,
            "end_date": end_date,
            "copies": 1,
        }
    )
    form.fields["default_address"].queryset = contact_addresses
    address_form = NewAddressForm(initial={"address_type": "physical"})

    if result == _("Cancel"):
        if offset:
            return HttpResponseRedirect("{}?offset={}".format(url, offset))
        else:
            return HttpResponseRedirect(url)
    elif result == _("Send"):
        form = NewPromoForm(request.POST)
        if form.is_valid():
            # First we need to save all the new contact data if necessary
            name = form.cleaned_data["name"]
            if contact.name != name:
                contact.name = name
            phone = form.cleaned_data["phone"]
            if contact.phone != phone:
                contact.phone = phone
            mobile = form.cleaned_data["mobile"]
            if contact.mobile != mobile:
                contact.mobile = mobile
            notes = form.cleaned_data["notes"]
            if contact.notes != notes:
                contact.notes = notes
            contact.save()
            # After this we will create the subscription
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            subscription = Subscription.objects.create(
                contact=contact,
                type="P",
                start_date=start_date,
                end_date=end_date,
                campaign=campaign,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("check"):
                    product_id = key.split("-")[1]
                    product = Product.objects.get(pk=product_id)
                    address_id = request.POST.get("address-{}".format(product_id))
                    address = Address.objects.get(pk=address_id)
                    copies = request.POST.get("copies-{}".format(product_id))
                    label_message = request.POST.get("message-{}".format(product_id))
                    special_instructions = request.POST.get("instruction-{}".format(product_id))
                    subscription.add_product(
                        product=product,
                        address=address,
                        copies=copies,
                        message=label_message,
                        instructions=special_instructions,
                        seller_id=seller.id,
                    )

            if request.GET.get("act", None):
                # the instance is somehow an activity and we needed to send a promo again, or has been scheduled
                activity.status = "C"  # completed activity
                activity.save()
                ccs.campaign_resolution = "SP"
                ccs.status = 2  # Contacted this person
                ccs.save()
            elif request.GET.get("new", None):
                ccs.status = 2  # contacted this person
                ccs.campaign_resolution = "SP"  # Sent promo to this c c ustomer
                ccs.save()

            # Afterwards we need to make an activity to ask the customer how it went.
            # The activity will show up in the menu after the datetime has passed.
            Activity.objects.create(
                contact=contact,
                campaign=campaign,
                direction="O",
                datetime=end_date + timedelta(1),
                activity_type="C",
                status="P",
                seller=seller,
            )

            return HttpResponseRedirect("{}?offset={}".format(url, offset))

    return render(
        request,
        "seller_console_start_promo.html",
        {
            "contact": contact,
            "form": form,
            "address_form": address_form,
            "offerable_products": offerable_products,
            "contact_addresses": contact_addresses,
        },
    )


@staff_member_required
def new_subscription(request, contact_id):
    """
    Makes a new subscription for the selected contact. If you pass a subscription id on a get parameter, it will
    attempt to change that subscription for a new one.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.GET.get("upgrade_subscription", None):
        subscription_id = request.GET.get("upgrade_subscription")
        form_subscription = get_object_or_404(Subscription, pk=subscription_id)
        if form_subscription.contact != contact:
            return HttpResponseServerError(_("Wrong data"))
        upgrade_subscription, edit_subscription = True, False
    elif request.GET.get("edit_subscription", None):
        subscription_id = request.GET.get("edit_subscription")
        form_subscription = get_object_or_404(Subscription, pk=subscription_id)
        if form_subscription.contact != contact:
            return HttpResponseServerError(_("Wrong data"))
        edit_subscription, upgrade_subscription = True, False
    else:
        form_subscription, upgrade_subscription, edit_subscription = None, False, False

    result = request.POST.get("result")
    contact_addresses = Address.objects.filter(contact=contact)
    offerable_products = Product.objects.filter(offerable=True)
    other_active_normal_subscriptions = Subscription.objects.filter(contact=contact, active=True, type="N")

    if request.GET.get("act", None):
        activity = Activity.objects.get(pk=request.GET["act"])
        campaign = activity.campaign
        ccs = ContactCampaignStatus.objects.get(contact=contact, campaign=campaign)
        user_seller_id = ccs.seller.id
    elif request.GET.get("new", None):
        ccs = ContactCampaignStatus.objects.get(pk=request.GET["new"])
        campaign = ccs.campaign
        user_seller_id = ccs.seller.id
    elif request.user.seller_set.exists():
        user_seller_id = request.user.seller_set.first().id
    else:
        user_seller_id = None

    if form_subscription:
        # If there's an old subscription, get their billing_data if necessary
        start_date_in_form = date.today() if upgrade_subscription else form_subscription.start_date
        initial_dict = {
            "contact_id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "mobile": contact.mobile,
            "email": contact.email,
            "id_document": contact.id_document,
            "default_address": contact_addresses,
            "start_date": start_date_in_form,
            "end_date": form_subscription.end_date,
            "copies": 1,
            "payment_type": form_subscription.payment_type,
            "billing_address": form_subscription.billing_address,
            "billing_name": form_subscription.billing_name,
            "billing_id_document": form_subscription.billing_id_doc,
            "billing_rut": form_subscription.rut,
            "billing_phone": form_subscription.billing_phone,
            "billing_email": form_subscription.billing_email,
            "frequency": form_subscription.frequency,
            "send_bill_copy_by_email": form_subscription.send_bill_copy_by_email,
        }
        form = NewSubscriptionForm(initial=initial_dict)
        form.fields["start_date"].widget.attrs["readonly"] = True
    else:
        form = NewSubscriptionForm(
            initial={
                "contact_id": contact.id,
                "name": contact.name,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "email": contact.email,
                "id_document": contact.id_document,
                "default_address": contact_addresses,
                "start_date": date.today(),
                "copies": 1,
                "send_bill_copy_by_email": True,
            }
        )

    form.fields["billing_address"].queryset = contact_addresses
    form.fields["default_address"].queryset = contact_addresses
    address_form = NewAddressForm(initial={"address_type": "physical"})

    if result == _("Cancel"):
        return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    elif result == _("Send"):
        url = request.GET.get("url", None)
        offset = request.GET.get("offset", None)
        form = NewSubscriptionForm(request.POST)
        if form.is_valid():
            # First we need to save all the new contact data if necessary
            name = form.cleaned_data["name"]
            if contact.name != name:
                contact.name = name
            phone = form.cleaned_data["phone"]
            if contact.phone != phone:
                contact.phone = phone
            mobile = form.cleaned_data["mobile"]
            if contact.mobile != mobile:
                contact.mobile = mobile
            id_document = form.cleaned_data["id_document"]
            if contact.id_document != id_document:
                contact.id_document = id_document
            email = form.cleaned_data["email"]
            if contact.email != email:
                contact.email = email
            contact.save()

            gigantes_name = form.cleaned_data["gigantes_name"]
            gigantes_id = form.cleaned_data["gigantes_id"]
            if gigantes_id:
                gigantes_contact = Contact.objects.get(pk=gigantes_id)
            elif gigantes_name:
                gigantes_contact = Contact.objects.create(name=gigantes_name)
            else:
                gigantes_contact = None

            if upgrade_subscription:
                # We will end the old subscription here.
                form_subscription.end_date = form.cleaned_data["start_date"]
                form_subscription.active = False
                form_subscription.inactivity_reason = 3  # Upgraded
                form_subscription.unsubscription_type = 4  # Upgraded
                form_subscription.save()

            if edit_subscription:
                # this means we are editing the subscription, and we don't need to create a new one
                subscription = form_subscription
                # We're not going to change start_date
                subscription.payment_type = form.cleaned_data["payment_type"]
                subscription.billing_address = form.cleaned_data["billing_address"]
                subscription.billing_name = form.cleaned_data["billing_name"]
                subscription.billing_id_doc = form.cleaned_data["billing_id_document"]
                subscription.rut = form.cleaned_data["billing_rut"]
                subscription.billing_phone = form.cleaned_data["billing_phone"]
                subscription.billing_email = form.cleaned_data["billing_email"]
                subscription.frequency = form.cleaned_data["frequency"]
                subscription.end_date = form.cleaned_data["end_date"]
                subscription.send_bill_copy_by_email = form.cleaned_data["send_bill_copy_by_email"]
                subscription.save()
            else:
                subscription = Subscription.objects.create(
                    contact=contact,
                    type="N",
                    start_date=form.cleaned_data["start_date"],
                    next_billing=form.cleaned_data["start_date"],
                    payment_type=form.cleaned_data["payment_type"],
                    billing_address=form.cleaned_data["billing_address"],
                    billing_name=form.cleaned_data["billing_name"],
                    billing_id_doc=form.cleaned_data["billing_id_document"],
                    rut=form.cleaned_data["billing_rut"],
                    billing_phone=form.cleaned_data["billing_phone"],
                    billing_email=form.cleaned_data["billing_email"],
                    frequency=form.cleaned_data["frequency"],
                    end_date=form.cleaned_data["end_date"],
                    send_bill_copy_by_email=form.cleaned_data["send_bill_copy_by_email"],
                )
            if upgrade_subscription:
                # Then, the amount that was not paid in the period but was not used due to closing the
                # old subscription will be added as a discount.
                subscription.balance = form_subscription.amount_to_pay_in_period()
                subscription.updated_from = form_subscription

            # We need to decide what we do with the status of the subscription, for now it will be normal
            subscription.status = "OK"
            subscription.save()

            # After this, we set all the products we sold
            new_products_list = []
            for key, value in list(request.POST.items()):
                if key.startswith("check"):
                    product_id = key.split("-")[1]
                    product = Product.objects.get(pk=product_id)
                    new_products_list.append(product)
                    address_id = request.POST.get("address-{}".format(product_id))
                    address = Address.objects.get(pk=address_id)
                    copies = request.POST.get("copies-{}".format(product_id))
                    message = request.POST.get("message-{}".format(product_id))
                    instructions = request.POST.get("instructions-{}".format(product_id))
                    seller_id = user_seller_id  # We'll reset seller_id every time to whatever the user seller is
                    # This is to make sure we don't overwrite the original seller for this subscription.
                    if not SubscriptionProduct.objects.filter(subscription=subscription, product=product).exists():
                        # First we're going to check if this is an upgrade and the previous product existed and had a
                        # seller. If it hadn't then the seller will still be None
                        if (
                            form_subscription
                            and SubscriptionProduct.objects.filter(
                                subscription=form_subscription, product=product
                            ).exists()
                        ):
                            seller = (
                                SubscriptionProduct.objects.filter(subscription=form_subscription, product=product)
                                .first()
                                .seller
                            )
                            if seller:
                                seller_id = seller.id
                            else:
                                seller_id = None
                        # For each product, if it is a product that this subscription didn't have, then we'll add it.
                        sp = subscription.add_product(
                            product=product,
                            address=address,
                            copies=copies,
                            message=message,
                            instructions=instructions,
                            seller_id=seller_id,
                        )
                        if product.slug == "gigantes" and gigantes_contact:
                            sp.label_contact = gigantes_contact
                            sp.save()
                    elif (
                        request.GET.get("edit_subscription", None)
                        and SubscriptionProduct.objects.filter(subscription=subscription, product=product).exists()
                    ):
                        sp = SubscriptionProduct.objects.get(subscription=subscription, product=product)
                        sp.address = address
                        sp.copies = copies
                        sp.label_message = message
                        sp.special_instructions = instructions
                        sp.save()

            for subscriptionproduct in SubscriptionProduct.objects.filter(subscription=subscription):
                if subscriptionproduct.product not in new_products_list:
                    subscription.remove_product(subscriptionproduct.product)

            if request.GET.get("new", None):
                # This means this is a direct sale
                ccs.campaign_resolution = "S2"  # this is a success with direct sale
                ccs.status = 4  # Ended with contact
                ccs.save()
                # We also need to register the activity as just started
                activity_notes = "{}\n{}".format(
                    _("Success with direct sale on {}").format(datetime.now().strftime("%Y-%m-%d %H:%M")),
                    form.cleaned_data["register_activity"],
                )
                Activity.objects.create(
                    activity_type="C",
                    seller=ccs.seller,
                    contact=contact,
                    status="C",
                    direction="O",
                    datetime=datetime.now(),
                    campaign=ccs.campaign,
                    notes=activity_notes,
                )
                subscription.campaign = ccs.campaign
                subscription.save()
                redirect_to = url
                if offset:
                    redirect_to += f"?offset={offset}"
            elif request.GET.get("act", None):
                # This means this is a sale from an activity
                activity.status = "C"
                activity_notes = "{}\n{}".format(
                    _("Success with promotion on {}").format(datetime.now().strftime("%Y-%m-%d %H:%M")),
                    form.cleaned_data["register_activity"],
                )
                if activity.notes:
                    activity.notes = activity.notes + "\n" + activity_notes
                else:
                    activity.notes = activity_notes
                activity.save()
                ccs = ContactCampaignStatus.objects.get(campaign=campaign, contact=contact)
                ccs.campaign_resolution = "S1"  # success after a promo
                ccs.status = 4  # Ended with contact
                ccs.save()
                subscription.campaign = campaign
                subscription.save()
                redirect_to = url
                if offset:
                    redirect_to += f"?offset={offset}"
            else:
                redirect_to = reverse("contact_detail", args=[contact.id])

            # if needed, redirect_to default_newsletters_dialog:
            if contact.offer_default_newsletters_condition():
                redirect_to = "%s?next_page=%s" % (
                    reverse("default_newsletters_dialog", kwargs={"contact_id": contact.id}),
                    redirect_to,
                )

            return HttpResponseRedirect(redirect_to)

    return render(
        request,
        "new_subscription.html",
        {
            "contact": contact,
            "upgrade_subscription": upgrade_subscription,
            "edit_subscription": edit_subscription,
            "form_subscription": form_subscription,
            "form": form,
            "address_form": address_form,
            "offerable_products": offerable_products,
            "contact_addresses": contact_addresses,
            "other_active_normal_subscriptions": other_active_normal_subscriptions,
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
            except:
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
            except Exception as e:
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
    seller_list = []
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

def release_seller_contacts_by_campaign(request, seller_id, campaign_id=None):
    seller_obj = get_object_or_404(Seller, pk=seller_id)
    active_campaigns = seller_obj.get_unfinished_campaigns()
    if campaign_id:
        campaign_obj = get_object_or_404(Campaign, pk=campaign_id)
        seller_obj.contactcampaignstatus_set.filter(status__lt=4, campaign=campaign_obj).update(seller=None)
        messages.success(request, f"Los contactos de {seller_obj} fueron liberados de la campaña {campaign_obj.name}")
        return HttpResponseRedirect(reverse("release_seller_contacts"))
    else:
        for campaign in active_campaigns:
            campaign.contacts_not_worked = campaign.contactcampaignstatus_set.filter(status__lt=4, seller=seller_obj).count()
        return render(request, "release_seller_contacts_by_campaign.html", {"active_campaigns": active_campaigns, "seller": seller_obj})


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
    issues_queryset = Issue.objects.all().order_by(
        "-date", "subscription_product__product", "-subscription_product__route__number", "-id"
    )
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
                    issue.contact.name,
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
    return render(request, "new_issue.html", {"contact": contact, "form": form, "category_name": category_name})


@login_required
def new_scheduled_task_total_pause(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST:
        form = NewPauseScheduledTaskForm(request.POST)
        if form.is_valid():
            date1 = form.cleaned_data.get("date_1")
            date2 = form.cleaned_data.get("date_2")
            days = (date2 - date1).days
            subscription = form.cleaned_data.get("subscription")
            subscription.next_billing = subscription.next_billing + timedelta(days)
            subscription.save()
            start_task = ScheduledTask.objects.create(
                contact=contact,
                subscription=subscription,
                execution_date=date1,
                category="PD",  # Deactivation
            )
            ScheduledTask.objects.create(
                contact=contact,
                subscription=subscription,
                execution_date=date2,
                category="PA",  # Activation
                ends=start_task,
            )
            Activity.objects.create(
                datetime=datetime.now(),
                contact=contact,
                notes=_("Scheduled task for pause"),
                activity_type=form.cleaned_data["activity_type"],
                status="C",  # completed
                direction="I",
            )
            if request.POST.get("apply_now", None):
                run_start_of_total_pause(start_task)
                messages.success(request, _("Total pause has been executed."))
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = NewPauseScheduledTaskForm(initial={"activity_type": "C"})
    form.fields["subscription"].queryset = contact.subscriptions.filter(active=True)
    return render(
        request,
        "new_scheduled_task_total_pause.html",
        {"contact": contact, "form": form},
    )


@login_required
def new_scheduled_task_address_change(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST:
        form = NewAddressChangeScheduledTaskForm(request.POST)
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
            date1 = form.cleaned_data.get("date_1")
            scheduled_task = ScheduledTask.objects.create(
                contact=contact,
                execution_date=date1,
                category="AC",
                address=address,
                special_instructions=form.cleaned_data.get("new_special_instructions"),
                label_message=form.cleaned_data.get("new_label_message"),
            )
            Activity.objects.create(
                datetime=datetime.now(),
                contact=contact,
                notes=_("Scheduled task for address change"),
                activity_type=form.cleaned_data["activity_type"],
                status="C",  # completed
                direction="I",
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key[2:]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    scheduled_task.subscription_products.add(subscription_product)
            if request.POST.get("apply_now", None):
                run_address_change(scheduled_task)
                messages.success(request, _("Address change has been executed."))
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = NewAddressChangeScheduledTaskForm(initial={"new_address_type": "physical", "activity_type": "C"})
    form.fields["contact_address"].queryset = contact.addresses.all()
    return render(
        request,
        "new_scheduled_task_address_change.html",
        {
            "contact": contact,
            "form": form,
            "subscriptions": contact.subscriptions.filter(active=True),
        },
    )


@staff_member_required
def new_scheduled_task_partial_pause(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST:
        form = PartialPauseTaskForm(request.POST)
        if form.is_valid():
            date1 = form.cleaned_data.get("date_1")
            date2 = form.cleaned_data.get("date_2")
            start_task = ScheduledTask.objects.create(
                contact=contact,
                execution_date=date1,
                category="PS",  # Deactivation
            )
            end_task = ScheduledTask.objects.create(
                contact=contact,
                execution_date=date2,
                category="PE",  # Activation
                ends=start_task,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key[2:]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    start_task.subscription_products.add(subscription_product)
                    end_task.subscription_products.add(subscription_product)
            Activity.objects.create(
                datetime=datetime.now(),
                contact=contact,
                notes=_("Scheduled task for pause"),
                activity_type=form.cleaned_data["activity_type"],
                status="C",  # completed
                direction="I",
            )
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = PartialPauseTaskForm(initial={"activity_type": "C"})
    return render(
        request,
        "new_scheduled_task_partial_pause.html",
        {
            "contact": contact,
            "form": form,
            "subscriptions": contact.subscriptions.filter(active=True),
        },
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


@login_required
def contact_list(request):
    """
    Shows a very simple contact list.
    """
    page = request.GET.get("p")
    contact_queryset = (
        Contact.objects.all().prefetch_related("subscriptions", "activity_set").select_related().order_by("-id")
    )
    contact_filter = ContactFilter(request.GET, queryset=contact_queryset)
    paginator = Paginator(contact_filter.qs, 50)
    if request.GET.get("export"):
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
        for contact in contact_filter.qs.all():
            active_products, address_1, state, city = "", "", "", ""
            for index, sp in enumerate(contact.get_active_subscriptionproducts()):
                if index > 0:
                    active_products += ", "
                active_products += sp.product.name
            first_subscription = contact.get_first_active_subscription()
            if first_subscription:
                address = first_subscription.get_full_address_by_priority()
                if address:
                    address_1, state, city = address.address_1, address.state, address.city
            writer.writerow(
                [
                    contact.id,
                    contact.name,
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
    try:
        contacts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        contacts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        contacts = paginator.page(paginator.num_pages)
    return render(
        request,
        "contact_list.html",
        {
            "paginator": paginator,
            "contacts": contacts,
            "page": page,
            "total_pages": paginator.num_pages,
            "filter": contact_filter,
            "count": contact_filter.qs.count(),
        },
    )


@login_required
def contact_detail(request, contact_id):
    """
    Shows all important information on a contact.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    addresses = contact.addresses.all()
    activities = contact.activity_set.all().order_by("-id")[:3]
    active_subscriptions = contact.subscriptions.filter(active=True).exclude(status="AP")
    paused_subscriptions = contact.subscriptions.filter(status="PA")
    subscriptions = active_subscriptions | paused_subscriptions
    subscriptions = subscriptions.order_by("-end_date", "-start_date")
    issues = contact.issue_set.all().order_by("-id")[:3]
    newsletters = contact.get_newsletters()
    last_paid_invoice = contact.get_last_paid_invoice()
    inactive_subscriptions = (
        contact.subscriptions.filter(active=False, start_date__lt=date.today())
        .exclude(status__in=("AP", "ER"))
        .order_by("-end_date", "-start_date")
    )
    future_subscriptions = (
        contact.subscriptions.filter(active=False, start_date__gte=date.today())
        .exclude(status__in=("AP", "ER"))
        .order_by("-start_date")
    )
    all_activities = contact.activity_set.all().order_by("-datetime", "id")
    all_issues = contact.issue_set.all().order_by("-date", "id")
    all_scheduled_tasks = contact.scheduledtask_set.all().order_by("-creation_date", "id")
    all_campaigns = contact.contactcampaignstatus_set.all().order_by("-date_created", "id")
    awaiting_payment_subscriptions = contact.subscriptions.filter(status="AP")
    subscriptions_with_error = contact.subscriptions.filter(status="ER")

    return render(
        request,
        "contact_detail.html",
        {
            "contact": contact,
            "addresses": addresses,
            "activities": activities,
            "subscriptions": subscriptions,
            "newsletters": newsletters,
            "issues": issues,
            "inactive_subscriptions": inactive_subscriptions,
            "awaiting_payment_subscriptions": awaiting_payment_subscriptions,
            "paused_subscriptions": paused_subscriptions,
            "subscriptions_with_error": subscriptions_with_error,
            "future_subscriptions": future_subscriptions,
            "last_paid_invoice": last_paid_invoice,
            "all_activities": all_activities,
            "all_issues": all_issues,
            "all_scheduled_tasks": all_scheduled_tasks,
            "all_campaigns": all_campaigns,
        },
    )


def api_new_address(request, contact_id):
    # Convertir en api para llamar a todas las direcciones
    """
    To be called by ajax methods. Creates a new address and responds with the created address on a JSON.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    data = {}
    if request.method == "POST" and request.META.get('HTTP_X_REQUESTED_WITH') == "XMLHttpRequest":
        form = SugerenciaGeorefForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            if getattr(settings, "GEOREF_SERVICES", None):
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
        _("Work phone"),
    ]
    writer.writerow(header)
    for contact in dcf.get_contacts():
        row = [
            contact.id,
            contact.name,
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
def edit_contact(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    form = ContactAdminForm(instance=contact)
    all_newsletters = Product.objects.filter(type="N", active=True)
    contact_newsletters = contact.get_newsletter_products()
    if request.POST:
        form = ContactAdminForm(request.POST, instance=contact)
        if form.is_valid():
            try:
                form.save()
            except Exception as e:
                messages.error(request, "Error: {}".format(e))
            else:
                messages.success(request, _("Contact saved successfully"))
                return HttpResponseRedirect(reverse("edit_contact", args=[contact_id]))
    return render(
        request,
        "create_contact.html",
        {
            "form": form,
            "contact": contact,
            "all_newsletters": all_newsletters,
            "contact_newsletters": contact_newsletters,
        },
    )


@require_POST
@staff_member_required
def edit_newsletters(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.POST:
        all_newsletters = Product.objects.filter(type="N", active=True)
        for newsletter in all_newsletters:
            if request.POST.get(str(newsletter.id)):
                if not contact.has_newsletter(newsletter.id):
                    contact.add_newsletter(newsletter.id)
            else:
                if contact.has_newsletter(newsletter.id):
                    contact.remove_newsletter(newsletter.id)
        messages.success(request, _("Newsletters edited successfully"))
        return HttpResponseRedirect(reverse("edit_contact", args=[contact_id]))


@staff_member_required
def scheduled_activities(request):
    user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        seller = None
    activity_queryset = seller.total_pending_activities()
    activity_filter = ScheduledActivityFilter(request.GET, activity_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(activity_filter.qs, 100)
    try:
        activities = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        activities = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        activities = paginator.page(paginator.num_pages)
    return render(
        request,
        "scheduled_activities.html",
        {
            "filter": activity_filter,
            "activities": activities,
            "seller": seller,
            "page": page_number,
            "total_pages": paginator.num_pages,
            "count": activity_filter.qs.count(),
            "now": datetime.now(),
        },
    )


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
                    issue.contact.name,
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
                    contact.name,
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
def book_unsubscription(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    if subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=subscription.contact.name,
                end_date=subscription.end_date,
            )
            messages.success(request, success_text)
            subscription.unsubscription_type = 1  # Complete unsubscription
            subscription.unsubscription_date = date.today()
            subscription.unsubscription_manager = request.user
            subscription.unsubscription_products.add(*subscription.products.all())
            subscription.save()
            return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))
    else:
        if subscription.is_obsolete():
            messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=subscription)
    return render(
        request,
        "book_unsubscription.html",
        {
            "subscription": subscription,
            "form": form,
        },
    )


@staff_member_required
def partial_unsubscription(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    if old_subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status=old_subscription.status,
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
                card_id=old_subscription.card_id,
                customer_id=old_subscription.customer_id,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key.split("-")[1]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    old_subscription.unsubscription_products.add(subscription_product.product)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if sp.route:
                        new_sp.route = sp.route
                    if sp.order:
                        new_sp.order = sp.order
                    new_sp.save()

            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=old_subscription.contact.name,
                end_date=old_subscription.end_date,
            )
            messages.success(request, success_text)

            old_subscription.unsubscription_type = 2  # Partial unsubscription
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    else:
        messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=old_subscription)
    return render(
        request,
        "book_partial_unsubscription.html",
        {
            "subscription": old_subscription,
            "form": form,
        },
    )


@staff_member_required
def product_change(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    if old_subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
        id__in=old_subscription.products.values_list("id")
    )
    new_products_ids_list = []
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status=old_subscription.status,
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
                card_id=old_subscription.card_id,
                customer_id=old_subscription.customer_id,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key.split("-")[1]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    old_subscription.unsubscription_products.add(subscription_product.product)
                if key.startswith("activateproduct"):
                    product_id = key.split("-")[1]
                    new_products_ids_list.append(product_id)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if sp.route:
                        new_sp.route = sp.route
                    if sp.order:
                        new_sp.order = sp.order
                    new_sp.save()
            # after this, we need to add the new products, that will have to be reviewed by an agent
            for product_id in new_products_ids_list:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    new_subscription.add_product(
                        product=product,
                        address=None,
                    )
            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=old_subscription.contact.name,
                end_date=old_subscription.end_date,
            )
            messages.success(request, success_text)
            old_subscription.unsubscription_type = 3  # Partial unsubscription
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            return HttpResponseRedirect(
                "{}?edit_subscription={}".format(
                    reverse("new_subscription", args=[old_subscription.contact.id]), new_subscription.id
                )
            )
    else:
        messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=old_subscription)
    return render(
        request,
        "book_product_change.html",
        {
            "offerable_products": offerable_products,
            "subscription": old_subscription,
            "form": form,
        },
    )


@login_required
def book_additional_product(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    if request.POST.get("url", None):
        from_seller_console = True
    if old_subscription.frequency != 1:
        messages.error(request, "La periodicidad de la suscripción debe ser mensual")
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact_id]))
    offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
        id__in=old_subscription.products.values_list("id")
    )
    new_products_ids_list = []
    if request.POST:
        form = AdditionalProductForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status="OK",
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
                card_id=old_subscription.card_id,
                customer_id=old_subscription.customer_id,
            )
            for key, value in list(request.POST.items()):
                # These are the new products
                if key.startswith("activateproduct"):
                    product_id = key.split("-")[1]
                    new_products_ids_list.append(product_id)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if sp.route:
                        new_sp.route = sp.route
                    if sp.order:
                        new_sp.order = sp.order
                    new_sp.save()
            # after this, we need to add the new products, that will have to be reviewed by an agent
            for product_id in new_products_ids_list:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    if old_subscription.contact.address_set.exists():
                        default_address = old_Subscription.contact.address_set.first()
                    else:
                        default_address = None
                    new_subscription.add_product(
                        product=product,
                        address=default_address,
                    )
            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy("New product(s) booked for {end_date}", end_date=old_subscription.end_date)
            messages.success(request, success_text)
            old_subscription.inactivity_reason = 3  # Upgrade
            old_subscription.unsubscription_type = 4  # Upgrade
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            new_sub_url = reverse("new_subscription", args=[old_subscription.contact.id])
            return HttpResponseRedirect(
                f"{new_sub_url}?edit_subscription={new_subscription.id}"
            )
    else:
        if old_subscription.end_date:
            messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = AdditionalProductForm(instance=old_subscription)
    return render(
        request,
        "book_additional_product.html",
        {
            "from_seller_console": from_seller_console,
            "offerable_products": offerable_products,
            "subscription": old_subscription,
            "form": form,
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
def unsubscription_statistics(request):
    unsubscriptions_queryset = Subscription.objects.filter(end_date__isnull=False, unsubscription_products__type="S")
    unsubscriptions_filter = UnsubscribedSubscriptionsByEndDateFilter(request.GET, queryset=unsubscriptions_queryset)

    executed_unsubscriptions_requested = (
        unsubscriptions_filter.qs.filter(end_date__lte=date.today(), unsubscription_requested=True)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    executed_unsubscriptions_not_requested = (
        unsubscriptions_filter.qs.filter(end_date__lte=date.today(), unsubscription_requested=False)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    programmed_unsubscriptions_requested = (
        unsubscriptions_filter.qs.filter(end_date__gt=date.today(), unsubscription_requested=True)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    programmed_unsubscriptions_not_requested = (
        unsubscriptions_filter.qs.filter(end_date__gt=date.today(), unsubscription_requested=False)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    total_unsubscriptions_requested = programmed_unsubscriptions_requested | executed_unsubscriptions_requested
    total_unsubscriptions_not_requested = (
        programmed_unsubscriptions_not_requested | executed_unsubscriptions_not_requested
    )

    individual_products_dict = collections.OrderedDict()
    choices = dict(settings.UNSUBSCRIPTION_REASON_CHOICES)
    for product_obj in Product.objects.filter(type="S", offerable=True).order_by("billing_priority"):
        individual_products_dict[product_obj.name] = (
            unsubscriptions_filter.qs.filter(unsubscription_products=product_obj, unsubscription_reason__isnull=False)
            .values("unsubscription_reason")
            .annotate(total=Count("unsubscription_reason"))
        )
    for individual_product in list(individual_products_dict.values()):
        # This dictionary will have unsubscription_reason as the index to be shown, this is not ideal for sure
        for item in individual_product:
            # Probably very bad solution to convert choices to displays, someone help me with a better way!
            item["unsubscription_reason"] = choices.get(item["unsubscription_reason"], None)

    total_unsubscriptions_by_reason = (
        unsubscriptions_filter.qs.filter(unsubscription_reason__isnull=False)
        .values("unsubscription_reason")
        .annotate(total=Count("unsubscription_reason"))
    )
    for item in total_unsubscriptions_by_reason:
        # Probably very bad solution to convert choices to displays, someone help me with a better way!
        item["unsubscription_reason"] = choices.get(item["unsubscription_reason"], None)

    total_requested_unsubscriptions_count = unsubscriptions_filter.qs.filter(unsubscription_requested=True).count()
    total_not_requested_unsubscriptions_count = unsubscriptions_filter.qs.filter(
        unsubscription_requested=False
    ).count()
    total_unsubscriptions_count = unsubscriptions_filter.qs.count()

    return render(
        request,
        "unsubscription_statistics.html",
        {
            "filter": unsubscriptions_filter,
            "queryset": unsubscriptions_filter.qs,
            "executed_unsubscriptions_requested": executed_unsubscriptions_requested,
            "executed_unsubscriptions_not_requested": executed_unsubscriptions_not_requested,
            "programmed_unsubscriptions_requested": programmed_unsubscriptions_requested,
            "programmed_unsubscriptions_not_requested": programmed_unsubscriptions_not_requested,
            "total_unsubscriptions_requested": total_unsubscriptions_requested,
            "total_unsubscriptions_not_requested": total_unsubscriptions_not_requested,
            "individual_products_dict": individual_products_dict,
            "total_unsubscriptions_by_reason": total_unsubscriptions_by_reason,
            "total_requested_unsubscriptions_count": total_requested_unsubscriptions_count,
            "total_not_requested_unsubscriptions_count": total_not_requested_unsubscriptions_count,
            "total_unsubscriptions_count": total_unsubscriptions_count,
        },
    )


@staff_member_required
def seller_console_special_routes(request, route_id):
    if not getattr(settings, "SPECIAL_ROUTES_FOR_SELLERS_LIST", None):
        messages.error(request, _("This function is not available."))
        return HttpResponseRedirect("/")
    if int(route_id) not in settings.SPECIAL_ROUTES_FOR_SELLERS_LIST:
        messages.error(request, _("This is not a special route."))
        return HttpResponseRedirect("/")
    route = get_object_or_404(Route, pk=route_id)

    user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        messages.error(request, _("User has no seller selected. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))
    except Seller.MultipleObjectsReturned:
        messages.error(request, _("This seller is set in more than one user. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))

    subprods = SubscriptionProduct.objects.filter(seller=seller, route=route, subscription__active=True).order_by(
        "subscription__contact__id"
    )
    if subprods.count() == 0:
        messages.error(request, _("There are no contacts in that route for this seller."))
        return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
    return render(
        request,
        "seller_console_special_routes.html",
        {
            "seller": seller,
            "subprods": subprods,
            "route": route,
        },
    )


@staff_member_required
def scheduled_task_filter(request):
    """
    Shows a very basic list of Scheduled Tasks.
    """
    st_queryset = ScheduledTask.objects.all().order_by("-creation_date", "-execution_date", "-id")
    st_filter = ScheduledTaskFilter(request.GET, queryset=st_queryset)
    page_number = request.GET.get("p")
    paginator = Paginator(st_filter.qs, 100)
    if request.GET.get("export"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="scheduled_tasks_export.csv"'
        writer = unicodecsv.writer(response)
        header = [
            _("Contact ID"),
            _("Contact name"),
            _("Category"),
            _("Creation date"),
            _("Execution date"),
            _("Completed"),
        ]
        writer.writerow(header)
        for st in st_filter.qs.all():
            writer.writerow(
                [
                    st.contact.id,
                    st.contact.name,
                    st.get_category_display(),
                    st.creation_date,
                    st.execution_date,
                    st.completed,
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
        "scheduled_task_filter.html",
        {"page": page, "paginator": paginator, "st_filter": st_filter, "count": st_filter.qs.count()},
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
    return render(
        request,
        "history_extended.html",
        {
            "contact": contact,
            "contact_history_dict": contact_history_dict,
            "subscriptions_history_dict": subscriptions_history_dict,
            "issues_history_dict": issues_history_dict,
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
        writer.writerow([
            c.id,
            c.name,
            c.email,
            c.phone,
            c.mobile
        ])
    return response
        
