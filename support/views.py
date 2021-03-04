# coding=utf-8
import csv
from datetime import date, timedelta, datetime

from django import forms
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.http import (
    HttpResponseServerError,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from core.filters import ContactFilter
from core.forms import AddressForm
from core.models import (
    Contact,
    Subscription,
    Campaign,
    Address,
    Product,
    Subtype,
    Activity,
    SubscriptionProduct,
    ContactCampaignStatus,
    SubscriptionNewsletter,
)

from .forms import *
from .models import Seller, ScheduledTask
from core.utils import calc_price_from_products, process_products
from util.dates import add_business_days


now = datetime.now()


def csv_sreader(src):
    """(Magic) CSV String Reader"""

    # Auto-detect the dialect
    dialect = csv.Sniffer().sniff(src, delimiters=",;")
    return csv.reader(src.splitlines(), dialect=dialect)


@login_required
def import_contacts(request):
    """
    Imports contacts from a CSV file.
    Csv must consist of a header, and then:
    name, phone, email, mobile, work_phone, notes, address, address_2, city, state

    TODO: Pandas this
    """
    if request.POST and request.FILES:
        new_contacts_list = []
        old_contacts_list = []
        errors_list = []
        tag_list = []
        campaign_id = request.POST.get("campaign", None)
        subtype_id = request.POST.get("subtype", None)
        tags = request.POST.get("tags", None)
        if tags:
            tags = tags.split(",")
            for tag in tags:
                tag_list.append(tag.strip())
        # check files for every possible match
        try:
            reader = csv_sreader(request.FILES["file"].read())
            # consume header
            reader.next()
        except csv.Error:
            return HttpResponse(_("No delimiters found in csv file. Please check the delimiters for csv files."))

        for row in reader:
            try:
                name = row[0]
                phone = row[1] or None
                email = row[2] or None
                mobile = row[3] or None
                work_phone = row[4] or None
                notes = row[5].strip() or None
                address = row[6] or None
                address_2 = row[7] or None
                city = row[8] or None
                state = row[9].strip() or None
            except IndexError:
                return HttpResponse(
                    _("The column count is wrong, please check that the header has at least 10 columns")
                )
            cpx = Q()
            # We're going to look for all the fields with possible coincidences
            if email:
                cpx = cpx | Q(email=email)
            if phone:
                cpx = cpx | Q(work_phone=phone) | Q(mobile=phone) | Q(phone=phone)
            if mobile:
                cpx = cpx | Q(work_phone=mobile) | Q(mobile=mobile) | Q(phone=mobile)
            if work_phone:
                cpx = cpx | Q(work_phone=work_phone) | Q(mobile=work_phone) | Q(phone=work_phone)
            matches = Contact.objects.filter(cpx)
            if matches.count() > 0:
                # if we get more than one match, alert the user
                for c in matches:
                    if c not in old_contacts_list:
                        old_contacts_list.append(c)
            else:
                try:
                    new_contact = Contact.objects.create(
                        name=name,
                        phone=phone,
                        email=email,
                        work_phone=work_phone,
                        mobile=mobile,
                        notes=notes
                    )
                    # Build the address if necessary
                    if address:
                        Address.objects.create(
                            contact=new_contact,
                            address_1=address_1,
                            address_2=address_2,
                            city=city,
                            state=state,
                            type="physical",
                            email=email,
                        )
                    new_contacts_list.append(new_contact)
                    if tag_list:
                        for tag in tag_list:
                            new_contact.tags.add(tag)
                    if campaign_id:
                        new_contact.add_to_campaign(campaign_id)
                except Exception as e:
                    errors_list.append("%s - %s" % (name, e.message))
        return render(
            request, "import_subscribers.html", {
                "new_contacts_list": new_contacts_list,
                "old_contacts_list": old_contacts_list,
                "errors_list": errors_list,
                "subtype_id": subtype_id,
                "campaign_id": campaign_id,
                "tag_list": tag_list,
            },
        )

    elif request.POST and (request.POST.get("hidden_campaign_id") or request.POST.get("hidden_tag_list")):
        campaign_id = request.POST.get("hidden_campaign_id", None)
        tag_list = request.POST.get("hidden_tag_list", None)
        errors_in_changes = []
        changed_list = []
        try:
            for name, value in request.POST.items():
                if name.startswith("move") and value == "M":
                    contact = Contact.objects.get(pk=name.replace("move-", ""))
                    contact.add_to_campaign(campaign_id)
                    for tag in eval(tag_list):
                        contact.tags.add(tag)
                    changed_list.append(contact)
                elif name.startswith("move") and value == "C":
                    contact = Contact.objects.get(pk=name.replace("move-", ""))
                    contact.add_to_campaign(campaign_id)
                    changed_list.append(contact)
                elif name.startswith("move") and value == "T":
                    contact = Contact.objects.get(pk=name.replace("move-", ""))
                    for tag in eval(tag_list):
                        contact.tags.add(tag)
                    changed_list.append(contact)
        except Exception as e:
            errors_in_changes.append(u"{} - {}".format(contact.id, e.message))
        return render(
            request, "import_subscribers.html", {
                "changed_list": changed_list,
                "errors_in_changes": errors_in_changes,
            }
        )
    else:
        return render(request, "import_subscribers.html")


@login_required
def seller_console_list_campaigns(request):
    """
    List all campaigns on a dashboard style list for sellers to use, so they can see which campaigns they have contacts
    in to call.
    """
    user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        return HttpResponse(_("User has no seller selected."))
    except Seller.MultipleObjectsReturned as e:
        return HttpResponse(e.message)

    # We'll make these lists so we can append the sub count to each campaign
    campaigns_with_not_contacted, campaigns_with_activities_to_do = [], []

    not_contacted_campaigns = seller.get_campaigns_by_status([1])
    all_campaigns = seller.get_unfinished_campaigns()
    for campaign in not_contacted_campaigns:
        campaign.count = campaign.get_not_contacted_count(seller.id)
        campaigns_with_not_contacted.append(campaign)
    for campaign in all_campaigns:
        campaign.pending = campaign.get_activities_by_seller(seller, "P", "C", date.today()).count()
        campaign.delayed = campaign.get_activities_by_seller(seller, "D", "C", date.today()).count()
        if campaign.pending or campaign.delayed:
            campaigns_with_activities_to_do.append(campaign)
    return render(
        request,
        "seller_console_list_campaigns.html",
        {
            "campaigns_with_not_contacted": campaigns_with_not_contacted,
            "campaigns_with_activities_to_do": campaigns_with_activities_to_do,
            "seller": seller,
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
        position = int(offset) + 1 if offset else 0
        url = request.POST.get("url")
        campaign = get_object_or_404(Campaign, pk=request.POST.get("campaign_id"))
        instance_type = request.POST.get("instance_type")
        instance_id = request.POST.get("instance_id")
        seller_id = request.POST.get("seller_id")
        seller = Seller.objects.get(pk=seller_id)
        if instance_type == "act":
            instance = Activity.objects.get(pk=instance_id)
            activity = instance
            contact = instance.contact
            campaign_status = ContactCampaignStatus.objects.get(
                campaign=campaign, contact=contact
            )
        elif instance_type == "new":
            instance = ContactCampaignStatus.objects.get(pk=instance_id)
            campaign_status = instance
            contact = instance.contact
            activity = Activity.objects.create(
                contact=contact, activity_type="C", datetime=datetime.now(), campaign=campaign, seller=seller
            )

        # We save the notes before doing anything else to the subscription
        if activity.notes != request.POST.get("notes"):
            activity.notes = request.POST.get("notes")
            activity.save()

        if result == _("Schedule"):
            # Schedule customers
            activity.status = "C"  # The current activity has to be completed, since we called the person.
            activity.campaign_resolution = "SC"
            campaign_status.campaign_resolution = "SC"
            campaign_status.status = 2
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

        elif result == _("Not interested"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "NI"
            campaign_status.status = 4

        elif result == _("Cannot find contact"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "UN"
            campaign_status.status = 5

        elif result == _("Error in promotion"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "EP"
            campaign_status.status = 4

        elif result == _("Do not call anymore"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "DN"
            campaign_status.status = 4

        elif result == _("Logistics"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "LO"
            campaign_status.status = 4

        elif result == _("Already a subscriber"):
            activity.status = "C"  # The activity was completed
            campaign_status.campaign_resolution = "AS"
            campaign_status.status = 4

        if campaign_status.campaign_resolution:
            campaign_status.campaign_reject_reason = request.POST.get(
                "campaign_reject_reason", None
            )
            campaign_status.save()

        if activity:
            activity.save()

        if result == _("Sell"):
            activity.status = 'C'
            activity.save()
            return HttpResponseRedirect(
                reverse("start_paid_subscription", args=[contact.id]) +
                "?url={}&offset={}&instance={}&instance_type={}".format(url, position, instance.id, instance_type)
            )

        elif result == _("Send promo"):
            activity.status = 'C'
            activity.save()
            return HttpResponseRedirect(
                reverse("send_promo", args=[contact.id]) +
                "?url={}&offset={}&instance={}&instance_type={}".format(url, position, instance.id, instance_type)
            )
        else:
            return HttpResponseRedirect(
                reverse("seller_console", args=[instance_type, campaign.id]) +
                "?offset={}".format(offset)
                if offset
                else None
            )

    else:
        """
        This is if the user has not selected any option.
        """
        user = User.objects.get(username=request.user.username)
        try:
            seller = Seller.objects.get(user=user)
        except Seller.DoesNotExist:
            return HttpResponse(_("User has no seller selected."))

        if request.GET.get("offset"):
            offset = request.GET.get("offset")
        else:
            offset = request.POST.get("offset")
        offset = int(offset) - 1 if (offset and int(offset) > 0) else 0

        campaign = Campaign.objects.get(pk=campaign_id)

        call_datetime = datetime.strftime(date.today() + timedelta(1), "%Y-%m-%d")

        if category == "new":
            console_instances = campaign.get_not_contacted(seller.id)
        elif category == "act":
            # We make sure to show the seller only the activities that are for today.
            pending = campaign.get_activities_by_seller(seller, "P", None, date.today())
            delayed = campaign.get_activities_by_seller(seller, "D", None, date.today())
            console_instances = pending | delayed
        count = console_instances.count()
        if count == 0:
            return HttpResponse(_("No more records."))
        if offset:
            if offset >= count:
                return HttpResponse("Error")
            console_instance = console_instances[int(offset)]
        else:
            console_instance = console_instances[0]

        contact = console_instance.contact
        times_contacted = contact.activity_set.filter(
            activity_type="C", status="C", campaign=campaign
        ).count()
        all_activities = Activity.objects.filter(contact=contact)
        if category == "act":
            # If what we're watching is an activity, let's please not show it here
            all_activities = all_activities.exclude(pk=console_instance.id)
        all_subscriptions = Subscription.objects.filter(contact=contact)
        url = request.META["PATH_INFO"]
        addresses = Address.objects.filter(contact=contact).order_by("address_1")

        return render(
            request,
            "seller_console.html",
            {
                "campaign": campaign,
                "times_contacted": times_contacted,
                # 'count': count,
                # 'activities_list': activities_list,
                "console_instances": console_instances,
                "category": category,
                "position": offset + 1,
                "offset": offset,
                "seller": seller,
                "contact": contact,
                "url": url,
                "addresses": addresses,
                "call_date": call_datetime,
                "all_activities": all_activities,
                "all_subscriptions": all_subscriptions,
                "console_instance": console_instance,
                "url": url,
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
    instance_type = request.GET.get("instance_type", None)
    instance_id = request.GET.get("instance", None)
    result = request.POST.get("result")
    contact = Contact.objects.get(pk=contact_id)
    instance = None
    contact_addresses = Address.objects.filter(contact=contact)
    offerable_products = Product.objects.filter(bundle_product=False, type="S")

    if instance_type and instance_type == "new" and instance_id:
        instance = ContactCampaignStatus.objects.get(pk=instance_id)
    elif instance_type and instance_type == "act" and instance_id:
        instance = Activity.objects.get(pk=instance_id)
    else:
        instance = None

    campaign = instance.campaign
    start_date = date.today()
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
            return HttpResponseRedirect(url + "?offset=%d" % int(offset))
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
            for key, value in request.POST.items():
                if key.startswith("check"):
                    product_id = key.split("-")[1]
                    product = Product.objects.get(pk=product_id)
                    address_id = request.POST.get("address-{}".format(product_id))
                    address = Address.objects.get(pk=address_id)
                    copies = request.POST.get("copies-{}".format(product_id))
                    subscription.add_product(product, address, copies)
            if instance_type == "new":
                # The instance is a contact campaign status
                instance.status = 2  # contacted the customer
                instance.campaign_resolution = (
                    "SP"  # we sent the promo to this customer
                )
                instance.save()

            elif instance_type == "act":
                # the instance is somehow an activity and we needed to send a promo again
                instance.status = "C"  # completed activity
                instance.campaign_resolution = "SP"  # success with promo
                instance.save()

            # Afterwards we need to make an activity to ask the customer how it went.
            # The activity will show up in the menu after the datetime has passed.
            Activity.objects.create(
                contact=contact,
                campaign=campaign,
                direction="O",
                datetime=end_date,
                activity_type="C",
                status="P",
            )

            return HttpResponseRedirect(url + "?offset=%d" % int(offset))

    return render(
        request,
        "seller_console_start_promo.html",
        {
            "contact": contact,
            "instance_type": instance_type,
            "instance": instance,
            "form": form,
            "address_form": address_form,
            "offerable_products": offerable_products,
            "contact_addresses": contact_addresses,
        },
    )


@login_required
def start_paid_subscription(request, contact_id):
    """
    Shows a form that the sellers can use to sell products to the contact.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    url = request.GET.get("url")
    offset = request.GET.get("offset", 0)
    instance_type = request.GET.get("instance_type", None)
    instance_id = request.GET.get("instance", None)
    result = request.POST.get("result")
    contact_addresses = Address.objects.filter(contact=contact)
    offerable_products = Product.objects.filter(bundle_product=False, type="S")
    other_active_normal_subscriptions = Subscription.objects.filter(contact=contact, active=True, type="N")

    if instance_type and instance_type == "new" and instance_id:
        instance = ContactCampaignStatus.objects.get(pk=instance_id)
    elif instance_type and instance_type == "act" and instance_id:
        instance = Activity.objects.get(pk=instance_id)
    else:
        instance = None

    campaign = instance.campaign if instance else None
    start_date = date.today()

    form = NewSubscriptionForm(
        initial={
            "name": contact.name,
            "phone": contact.phone,
            "mobile": contact.mobile,
            "email": contact.email,
            "id_document": contact.id_document,
            "default_address": contact_addresses,
            "start_date": start_date,
            "copies": 1,
        }
    )
    form.fields["billing_address"].queryset = contact_addresses
    form.fields["default_address"].queryset = contact_addresses
    address_form = NewAddressForm(initial={"address_type": "physical"})

    if result == _("Cancel"):
        if offset:
            return HttpResponseRedirect(url + "?offset=%d" % int(offset))
        else:
            return HttpResponseRedirect(url)
    elif result == _("Send"):
        form = NewSubscriptionForm(request.POST)
        replace_subscription = request.POST.get("replace_this_subscription", None)
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
            id_document = form.cleaned_data["id_document"]
            if contact.id_document != id_document:
                contact.id_document = id_document
            contact.save()
            # After this we will create the subscription
            subscription = Subscription.objects.create(
                contact=contact,
                type="N",
                campaign=campaign,
                start_date=form.cleaned_data["start_date"],
                next_billing=form.cleaned_data["start_date"],
                payment_type=form.cleaned_data["payment_type"],
                billing_address=form.cleaned_data['billing_address'],
                billing_name=form.cleaned_data['billing_name'],
                billing_id_doc=form.cleaned_data['billing_id_document'],
                rut=form.cleaned_data['billing_rut'],
                billing_phone=form.cleaned_data['billing_phone'],
                billing_email=form.cleaned_data['billing_email'],
            )

            if replace_subscription:
                replace_subscription = Subscription.objects.get(pk=replace_subscription)
                replace_subscription.end_date = start_date
                replace_subscription.active = False
                replace_subscription.save()
                subscription.balance = replace_subscription.amount_already_paid_in_period()

            # We need to decide what we do with the status of the subscription, for now it will be normal
            subscription.status = "OK"
            subscription.save()

            # After this, we set all the products we sold
            for key, value in request.POST.items():
                if key.startswith("check"):
                    product_id = key.split("-")[1]
                    product = Product.objects.get(pk=product_id)
                    address_id = request.POST.get("address-{}".format(product_id))
                    address = Address.objects.get(pk=address_id)
                    copies = request.POST.get("copies-{}".format(product_id))
                    subscription.add_product(product, address, copies)

            if instance_type == "new":
                # The instance is a contact campaign status so this is a direct sale without activity
                instance.status = 4  # contacted the customer and ended the promo
                instance.campaign_resolution = "S2"  # this is a success with direct sale
                instance.save()
            elif instance_type == "act":
                # the instance is an activity we need to mark this as the end of the campaign
                instance.status = "C"  # completed activity
                instance.save()
                # after this, we'll look for the ContactCampaignStatus that has this campaign, and close it
                ccs = ContactCampaignStatus.objects.get(contact=contact, campaign=instance.campaign)
                ccs.status = 4  # contacted the customer and ended the promo
                ccs.campaign_resolution = "S1"  # success after a promo
                ccs.save()
            if url:
                return HttpResponseRedirect(url + "?offset=%d" % int(offset))
            else:
                return HttpResponseRedirect("/admin/core/contact/{}/".format(contact.id))

    return render(
        request,
        "seller_console_start_subscription.html",
        {
            "contact": contact,
            "instance_type": instance_type,
            "instance": instance,
            "form": form,
            "address_form": address_form,
            "offerable_products": offerable_products,
            "contact_addresses": contact_addresses,
            "other_active_normal_subscriptions": other_active_normal_subscriptions,
        },
    )


def new_subscription(request, contact_id):
    """
    Makes a new subscription for the selected contact. If you pass a subscription id on a get parameter, it will
    attempt to change that subscription for a new one.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    if request.GET.get('upgrade_subscription', None):
        subscription_id = request.GET.get('upgrade_subscription')
        form_subscription = get_object_or_404(Subscription, pk=subscription_id)
        if form_subscription.contact != contact:
            return HttpResponseServerError(_('Wrong data'))
        upgrade_subscription, edit_subscription = True, False
    elif request.GET.get('edit_subscription', None):
        subscription_id = request.GET.get('edit_subscription')
        form_subscription = get_object_or_404(Subscription, pk=subscription_id)
        if form_subscription.contact != contact:
            return HttpResponseServerError(_('Wrong data'))
        edit_subscription, upgrade_subscription = True, False
    else:
        form_subscription, upgrade_subscription, edit_subscription = None, False, False

    result = request.POST.get("result")
    contact_addresses = Address.objects.filter(contact=contact)
    offerable_products = Product.objects.filter(bundle_product=False, type="S")
    other_active_normal_subscriptions = Subscription.objects.filter(contact=contact, active=True, type="N")

    if form_subscription:
        # If there's an old subscription, get their billing_data if necessary
        form = NewSubscriptionForm(
            initial={
                "name": contact.name,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "email": contact.email,
                "id_document": contact.id_document,
                "default_address": contact_addresses,
                "start_date": date.today(),
                "copies": 1,
                "billing_address": form_subscription.billing_address,
                "billing_name": form_subscription.billing_name,
                "billing_id_document": form_subscription.billing_id_doc,
                "billing_rut": form_subscription.rut,
                "billing_phone": form_subscription.billing_phone,
                "billing_email": form_subscription.billing_email,
            }
        )
    else:
        form = NewSubscriptionForm(
            initial={
                "name": contact.name,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "email": contact.email,
                "id_document": contact.id_document,
                "default_address": contact_addresses,
                "start_date": date.today(),
                "copies": 1,
            }
        )

    form.fields["billing_address"].queryset = contact_addresses
    form.fields["default_address"].queryset = contact_addresses
    address_form = NewAddressForm(initial={"address_type": "physical"})

    if result == _("Cancel"):
        return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    elif result == _("Send"):
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
            notes = form.cleaned_data["notes"]
            if contact.notes != notes:
                contact.notes = notes
            id_document = form.cleaned_data["id_document"]
            if contact.id_document != id_document:
                contact.id_document = id_document
            contact.save()

            if upgrade_subscription:
                # We will end the old subscription here.
                form_subscription.end_date = form.cleaned_data["start_date"]
                form_subscription.active = False
                form_subscription.save()

            if edit_subscription:
                # this means we are editing the subscription, and we don't need to create a new one
                subscription = form_subscription
                subscription.start_date = form.cleaned_data["start_date"]
                subscription.payment_type = form.cleaned_data["payment_type"]
                subscription.billing_address = form.cleaned_data['billing_address']
                subscription.billing_name = form.cleaned_data['billing_name']
                subscription.billing_id_doc = form.cleaned_data['billing_id_document']
                subscription.rut = form.cleaned_data['billing_rut']
                subscription.billing_phone = form.cleaned_data['billing_phone']
                subscription.billing_email = form.cleaned_data['billing_email']
                subscription.save()

            else:
                subscription = Subscription.objects.create(
                    contact=contact,
                    type="N",
                    start_date=form.cleaned_data["start_date"],
                    next_billing=form.cleaned_data["start_date"],
                    payment_type=form.cleaned_data["payment_type"],
                    billing_address=form.cleaned_data['billing_address'],
                    billing_name=form.cleaned_data['billing_name'],
                    billing_id_doc=form.cleaned_data['billing_id_document'],
                    rut=form.cleaned_data['billing_rut'],
                    billing_phone=form.cleaned_data['billing_phone'],
                    billing_email=form.cleaned_data['billing_email'],
                )
            if upgrade_subscription:
                # Then, the amount that was already paid in the period but was not used due to closing the
                # old subscription will be added as a discount.
                subscription.balance = form_subscription.amount_already_paid_in_period()

            # We need to decide what we do with the status of the subscription, for now it will be normal
            subscription.status = "OK"
            subscription.save()

            # After this, we set all the products we sold
            new_products_list = []
            for key, value in request.POST.items():
                if key.startswith("check"):
                    product_id = key.split("-")[1]
                    product = Product.objects.get(pk=product_id)
                    new_products_list.append(product)
                    if not SubscriptionProduct.objects.filter(subscription=subscription, product=product).exists():
                        # For each product, if it is a product that this subscription didn't have, then we'll add it.
                        address_id = request.POST.get("address-{}".format(product_id))
                        address = Address.objects.get(pk=address_id)
                        copies = request.POST.get("copies-{}".format(product_id))
                        subscription.add_product(product, address, copies)
            for subscriptionproduct in SubscriptionProduct.objects.filter(subscription=subscription):
                if subscriptionproduct.product not in new_products_list:
                    subscription.remove_product(subscriptionproduct.product)
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))

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
def assign_campaigns(request):
    """
    Allows a supervisor to add contacts to campaigns, using tags or a csv file.
    """
    campaigns = Campaign.objects.filter(active=True)
    if request.POST and request.FILES:
        response = []
        campaign = request.POST.get("campaign")
        try:
            reader = csv_sreader(request.FILES["file"].read())
            for row in reader:
                try:
                    contact = Contact.objects.get(pk=row[0])
                    contact.add_to_campaign(campaign)
                    response.append(contact.add_to_campaign(campaign))
                except Exception as e:
                    response.append(e.message)
            return render(
                request,
                "assign_campaigns.html",
                {
                    "response": response,
                },
            )
        except csv.Error:
            return HttpResponse(
                u"Error: No se encuentran delimitadores en el archivo "
                u"ingresado, deben usarse ',' (comas) <br/><a href="
                u"'.'>Volver</a>"
            )
        except Exception as e:
            return HttpResponse(u"Error: %s" % e.message)
    elif request.POST and request.POST.get("tags"):
        response = []
        campaign = request.POST.get("campaign")
        tags = request.POST.get("tags")
        tag_list = tags.split(",")
        contacts = Contact.objects.filter(tags__name__in=tag_list)
        for contact in contacts:
            try:
                response.append(contact.add_to_campaign(campaign))
            except Exception as e:
                response.append(e.message)
        return render(
            request,
            "assign_campaigns.html",
            {
                "response": response,
            },
        )
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
    campaigns = Campaign.objects.filter(
        contactcampaignstatus__contact__seller=None
    ).distinct()
    campaign_list = []
    for campaign in campaigns:
        count = ContactCampaignStatus.objects.filter(
            campaign=campaign, contact__seller=None
        ).count()
        campaign.count = count
        campaign_list.append(campaign)
    return render(
        request, "distribute_campaigns.html", {"campaign_list": campaign_list}
    )


@login_required
def assign_seller(request, campaign_id):
    """
    Shows a list of sellers to assign contacts to.
    """
    campaign = Campaign.objects.get(pk=campaign_id)
    campaign.count = Contact.objects.filter(
        contactcampaignstatus__campaign=campaign, seller=None
    ).count()
    message = ""

    if request.POST:
        seller_list = []
        for name, value in request.POST.items():
            if name.startswith("seller"):
                seller_list.append([name.replace("seller-", ""), value or 0])
        total = 0
        for seller, amount in seller_list:
            total += int(amount)
        if total > campaign.count:
            return HttpResponse(u"Cantidad de clientes superior a la que hay.")
        for seller, amount in seller_list:
            if amount:
                for contact in Contact.objects.filter(
                    seller=None, contactcampaignstatus__campaign=campaign
                )[:amount]:
                    contact.seller = Seller.objects.get(pk=seller)
                    try:
                        contact.save()
                    except Exception as e:
                        return HttpResponse(e.message)
        return HttpResponseRedirect(reverse("assign_sellers", args=campaign_id))

    sellers = Seller.objects.filter(internal=True)
    seller_list = []
    for seller in sellers:
        seller.contacts = Contact.objects.filter(
            seller=seller, contactcampaignstatus__campaign=campaign
        ).count()
        seller_list.append(seller)
    if message:
        # Refresh value if some subs were distributed
        campaign.count = Contact.objects.filter(
            contactcampaignstatus__campaign=campaign, seller=None
        ).count()
    return render(
        request,
        "assign_sellers.html",
        {"seller_list": seller_list, "campaign": campaign, "message": message},
    )


@login_required
def edit_products(request, subscription_id):
    """
    Allows editing products in a subscription.
    """
    products = Product.objects.filter(type="S").exclude(bundle_product=True)
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
    page_number = request.GET.get("p")
    issues = Issue.objects.all().order_by("-id")
    paginator = Paginator(issues, 100)
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
        {
            "page": page,
            "paginator": paginator,
        },
    )


@login_required
def select_contact_for_issue(request, issue_type):
    """
    Asks for a contact id before creating an issue.
    """
    form = SelectContactForIssue(
        request.POST or None, initial={"issue_type": issue_type}
    )
    if request.POST:
        if form.is_valid():
            issue_type = form.cleaned_data["issue_type"]
            contact_id = form.cleaned_data["contact_id"]
            if issue_type.startswith("S"):
                return HttpResponseRedirect(
                    reverse("new_issue", args=[contact_id, "S", issue_type])
                )
            elif issue_type.startswith("L"):
                return HttpResponseRedirect(
                    reverse("new_issue", args=[contact_id, "L"])
                )

    return render(request, "select_contact_for_issue.html", {"form": form})


@login_required
def new_issue(request, contact_id, category="L", subcategory=""):
    """
    Creates an issue of a selected category and subcategory.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    if category == "L" and subcategory == "":
        # Logistics issue
        if request.POST:
            form = LogisticsIssueStartForm(request.POST)
            if form.is_valid():
                Issue.objects.create(
                    contact=form.cleaned_data["contact"],
                    category="L",
                    subcategory=form.cleaned_data["subcategory"],
                    notes=form.cleaned_data["notes"],
                    copies=form.cleaned_data["copies"],
                    subscription=form.cleaned_data["subscription"],
                    subscription_product=form.cleaned_data["subscription_product"],
                    product=form.cleaned_data["product"],
                    inside=False,
                    manager=request.user,
                    status="P",
                )
                return HttpResponseRedirect(
                    "/admin/core/contact/{}/".format(form.cleaned_data["contact"].id)
                )
                # TODO: Reverse to admin
        else:
            form = LogisticsIssueStartForm(
                initial={"contact": contact, "category": "L"}
            )
            form.fields["subscription"].queryset = contact.subscriptions.filter(
                active=True
            )
            form.fields[
                "subscription_product"
            ].queryset = SubscriptionProduct.objects.filter(
                subscription__contact=contact, subscription__active=True
            )
        return render(
            request, "new_logistics_issue.html", {"contact": contact, "form": form}
        )

    elif category == "S" and subcategory == "S04":
        # Services / pause issue
        if request.POST:
            form = NewPauseScheduledTaskForm(request.POST)
            if form.is_valid():
                # first we have to create an issue that will have this task
                date1 = form.cleaned_data.get("date_1")
                date2 = form.cleaned_data.get("date_2")
                subscription = form.cleaned_data.get("subscription")
                new_issue = Issue.objects.create(
                    contact=contact,
                    category=category,
                    subcategory=subcategory,
                    date=date.today(),
                    manager=request.user,
                    status="P",
                    next_action_date=date1,
                )
                # Then we create the deactivation and activation events
                ScheduledTask.objects.create(
                    issue=new_issue,
                    contact=contact,
                    subscription=subscription,
                    execution_date=date1,
                    category="PD",
                )
                ScheduledTask.objects.create(
                    issue=new_issue,
                    contact=contact,
                    subscription=subscription,
                    execution_date=date2,
                    category="PA",
                )
                return HttpResponseRedirect(
                    "/admin/core/contact/{}/".format(contact.id)
                )
        else:
            form = NewPauseScheduledTaskForm()
        form.fields["subscription"].queryset = contact.subscriptions.filter(active=True)
        return render(
            request,
            "new_scheduled_task_issue.html",
            {"contact": contact, "form": form, "subcategory": subcategory},
        )

    elif category == "S" and subcategory == "S05":
        # Services / address change issue
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
                # First we create the issue that will contain the scheduled task
                new_issue = Issue.objects.create(
                    contact=contact,
                    category=category,
                    subcategory=subcategory,
                    date=date.today(),
                    manager=request.user,
                    status="P",
                    next_action_date=date1,
                )
                # after this, we will create this scheduled task
                scheduled_task = ScheduledTask.objects.create(
                    issue=new_issue,
                    contact=contact,
                    execution_date=date1,
                    category="AC",
                    address=address,
                )
                for key, value in request.POST.items():
                    if key.startswith("sp"):
                        subscription_product_id = key[2:]
                        subscription_product = SubscriptionProduct.objects.get(
                            pk=subscription_product_id
                        )
                        scheduled_task.subscription_products.add(subscription_product)
                return HttpResponseRedirect(
                    "/admin/core/contact/{}/".format(contact.id)
                )
        else:
            form = NewAddressChangeScheduledTaskForm(
                initial={"new_address_type": "physical"}
            )
        subscription_products = [
            s
            for s in SubscriptionProduct.objects.filter(
                subscription__contact=contact, subscription__active=True
            )
        ]
        form.fields["contact_address"].queryset = contact.addresses.all()
        return render(
            request,
            "new_scheduled_task_issue.html",
            {
                "contact": contact,
                "form": form,
                "subscription_products": subscription_products,
                "subcategory": subcategory,
            },
        )


@login_required
def view_issue(request, issue_id):
    """
    Shows a logistics type issue.
    """
    issue = get_object_or_404(Issue, pk=issue_id)
    if request.POST:
        form = LogisticsIssueChangeForm(request.POST, instance=issue)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse("view_issue", args=(issue_id,)))
    else:
        form = LogisticsIssueChangeForm(instance=issue)
    return render(
        request,
        "view_issue.html",
        {
            "form": form,
            "issue": issue,
        },
    )


@login_required
def contact_list(request):
    """
    Shows a very simple contact list.
    """
    page = request.GET.get("p")
    contact_queryset = (
        Contact.objects.all()
        .prefetch_related("subscriptions", "activity_set")
        .select_related()
        .order_by("-id")
    )
    contact_filter = ContactFilter(request.GET, queryset=contact_queryset)
    paginator = Paginator(contact_filter.qs, 50)
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
    subscriptions = contact.subscriptions.filter(active=True)
    issues = contact.issue_set.all().order_by("-id")[:3]
    newsletters = contact.get_newsletters()
    last_paid_invoice = contact.get_last_paid_invoice()
    inactive_subscriptions = contact.subscriptions.filter(active=False)
    all_activities = contact.activity_set.all().order_by('-datetime')
    all_issues = contact.issue_set.all().order_by('-date')
    all_scheduled_tasks = contact.scheduledtask_set.all().order_by('-creation_date')

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
            "last_paid_invoice": last_paid_invoice,
            "all_activities": all_activities,
            "all_issues": all_issues,
            "all_scheduled_tasks": all_scheduled_tasks,
        },
    )


def api_new_address(request, contact_id):
    """
    To be called by ajax methods. Creates a new address and responds with the created address on a JSON.
    """
    contact = get_object_or_404(Contact, pk=contact_id)
    data = {}
    if request.method == "POST" and request.is_ajax():
        form = NewAddressForm(request.POST)
        if form.is_valid():
            address = Address.objects.create(
                contact=contact,
                address_1=form.cleaned_data["address_1"],
                address_2=form.cleaned_data["address_2"],
                city=form.cleaned_data["address_city"],
                state=form.cleaned_data["address_state"],
                address_type=form.cleaned_data["address_type"],
                notes=form.cleaned_data["address_notes"],
            )
            data = {
                address.id: "{} {} {}".format(
                    address.address_1, address.city, address.state
                )
            }
            return JsonResponse(data)
    else:
        return HttpResponseNotFound()


@csrf_exempt
def api_dynamic_prices(request):
    """
    Uses price rules to calculate products and prices depending on the products that have been selected on one of the
    views to add new products to a subscription.
    """
    if request.method == "POST" and request.is_ajax():
        frequency, product_copies = 1, {}
        for key, value in request.POST.items():
            if key == "frequency":
                frequency = value
            else:
                product_copies[key] = value
        product_copies = process_products(product_copies)
        price = calc_price_from_products(product_copies, frequency)
        return JsonResponse({"price": price})
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
                    subscription_newsletters = subscription_newsletters.filter(
                        product=newsletter
                    )
                subscription_newsletters = subscription_newsletters.filter(
                    contact__email__isnull=False
                )
                count = subscription_newsletters.count()
                email_sample = subscription_newsletters.values("contact__email")[:50]
            else:
                if mode == 1:  # At least one of the products
                    subscriptions = Subscription.objects.all()
                elif mode == 2:  # All products must match
                    subscriptions = Subscription.objects.annotate(
                        count=Count("products")
                    ).filter(active=True, count=products.count())
                for product in products:
                    subscriptions = subscriptions.filter(products=product)
                if allow_promotions:
                    subscriptions = subscriptions.filter(contact__allow_promotions=True)
                if allow_polls:
                    subscriptions = subscriptions.filter(contact__allow_polls=True)
                # Finally we remove the ones who don't have emails
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
            if request.POST.get("confirm", None):
                dcf.description = description
                dcf.allow_promotions = allow_promotions
                dcf.allow_polls = allow_polls
                dcf.mode = mode
                dcf.mailtrain_id = mailtrain_id
                dcf.autosync = autosync
                dcf.products = products
                dcf.newsletters = newsletters
                dcf.save()
                return HttpResponseRedirect(
                    reverse("dynamic_contact_filter_edit", args=[dcf.id])
                )

            # After getting the data, process it to find out how many records there are for the filter
            if mode == 3:
                subscription_newsletters = SubscriptionNewsletter.objects.all()
                for newsletter in newsletters:
                    subscription_newsletters = subscription_newsletters.filter(
                        product=newsletter
                    )
                subscription_newsletters = subscription_newsletters.filter(
                    contact__email__isnull=False
                )
                count = subscription_newsletters.count()
                email_sample = subscription_newsletters.values("contact__email")[:50]
            else:
                if mode == 1:  # At least one of the products
                    subscriptions = Subscription.objects.all()
                elif mode == 2:  # All products must match
                    subscriptions = Subscription.objects.annotate(
                        count=Count("products")
                    ).filter(active=True, count=products.count())
                for product in products:
                    subscriptions = subscriptions.filter(products=product)
                if allow_promotions:
                    subscriptions = subscriptions.filter(contact__allow_promotions=True)
                if allow_polls:
                    subscriptions = subscriptions.filter(contact__allow_polls=True)
                # Finally we remove the ones who don't have emails
                subscriptions = subscriptions.filter(contact__email__isnull=False)
                count = subscriptions.count()
                email_sample = subscriptions.values("contact__email")[:50]

            return render(
                request,
                "dynamic_contact_filter_details.html",
                {
                    "email_sample": email_sample,
                    "dcf": dcf,
                    "form": form,
                    "confirm": True,
                    "count": count,
                },
            )

    return render(
        request, "dynamic_contact_filter_details.html", {"dcf": dcf, "form": form}
    )


@login_required
def export_dcf_emails(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dcf_list_{}.csv"'.format(
        dcf.id
    )

    writer = csv.writer(response)
    for email in dcf.get_emails():
        writer.writerow([email])

    return response


@login_required
def sync_with_mailtrain(request, dcf_id):
    dcf = get_object_or_404(DynamicContactFilter, pk=dcf_id)
    dcf.sync_with_mailtrain_list()
    if dcf.mailtrain_id is None:
        return HttpResponse(_("Error: This filter has no mailtrain id"))
    try:
        dcf.sync_with_mailtrain_list()
    except Exception as e:
        return HttpResponse(_("Error: {}".format(e.message)))
    else:
        return HttpResponseRedirect(
            reverse("dynamic_contact_filter_edit", args=[dcf.id])
        )
