from django.views.generic import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta, datetime

from support.models import Seller, Issue
from core.models import Address, SubscriptionProduct, Activity, ContactCampaignStatus, Campaign, Subscription
from core.utils import logistics_is_installed
from core.choices import CAMPAIGN_RESOLUTION_REASONS_CHOICES

if logistics_is_installed():
    from logistics.models import Route


@staff_member_required
def seller_console_special_routes(request, route_id):
    if "logistics" in getattr(settings, "DISABLED_APPS", []):
        messages.error(request, _("This function is not available."))
        return HttpResponseRedirect(reverse("main_menu"))
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
def seller_console_list_campaigns(request, seller_id=None):
    """
    List all campaigns on a dashboard style list for sellers to use, so they can see which campaigns they have contacts
    in to call.
    """
    if seller_id:
        # Check that the user is a manager
        if not request.user.is_staff and not request.user.groups.filter(name="Managers").exists():
            messages.error(request, _("You are not authorized to see this page"))
            return HttpResponseRedirect(reverse("main_menu"))
        seller = Seller.objects.get(pk=seller_id)
        user = seller.user
    else:
        user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        messages.error(request, _("User has no seller selected. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))
    except Seller.MultipleObjectsReturned:
        messages.error(request, _("This seller is set in more than one user. Please contact your manager."))
        return HttpResponseRedirect(reverse("main_menu"))

    if logistics_is_installed():
        special_routes = {}
        for route_id in settings.SPECIAL_ROUTES_FOR_SELLERS_LIST:
            route = Route.objects.get(pk=route_id)
            counter = SubscriptionProduct.objects.filter(
                seller=seller, route_id=route_id, subscription__active=True
            ).count()
            if counter:
                special_routes[route_id] = (route.name, counter)

    # We'll make these lists so we can append the sub count to each campaign
    campaigns_with_not_contacted, campaigns_with_activities_to_do = [], []
    issues_never_paid = Issue.objects.filter(
        sub_category__slug=settings.ISSUE_SUBCATEGORY_NEVER_PAID,
        assigned_to=user,
    ).exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)

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

    context = {
        "campaigns_with_not_contacted": campaigns_with_not_contacted,
        "campaigns_with_activities_to_do": campaigns_with_activities_to_do,
        "seller": seller,
        "total_pending_activities": total_pending_activities,
        "upcoming_activity": upcoming_activity,
        "issues_never_paid": issues_never_paid,
    }
    if logistics_is_installed():
        context["special_routes"] = special_routes
    return render(
        request,
        "seller_console_list_campaigns.html",
        context,
    )


class SellerConsoleView(UserPassesTestMixin, TemplateView):
    template_name = 'seller_console.html'

    def test_func(self):
        return self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        """Check for end of list before processing the request"""
        if request.method == 'GET':
            redirect_response = self.check_end_of_list()
            if redirect_response:
                return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def check_end_of_list(self):
        """Check if we've reached the end of the list and return redirect if needed"""
        campaign = self.get_campaign()
        seller = self.get_seller()
        console_instances = self.get_console_instances(campaign, seller)
        count = console_instances.count()

        offset = self.request.GET.get('offset')
        offset = int(offset) if offset else 1

        if count == 0 or offset - 1 >= count:
            messages.success(self.request, _("You've reached the end of this list"))
            return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
        return None

    def get_seller(self):
        """Get seller for current user"""
        return get_object_or_404(Seller, user=self.request.user)

    def get_campaign(self):
        """Get campaign from URL kwargs"""
        return get_object_or_404(Campaign, pk=self.kwargs['campaign_id'])

    def get_console_instances(self, campaign, seller):
        """Get queryset of console instances based on category"""
        category = self.kwargs['category']
        if category == "new":
            return campaign.get_not_contacted(seller.id)
        return campaign.activity_set.filter(
            activity_type="C",
            seller=seller,
            status="P",
            datetime__lte=datetime.now()
        ).order_by("datetime", "id")

    def process_activity_result(self, contact, campaign, seller, result, new_activity_notes):
        """Process activity result and create/update related objects"""
        ccs = ContactCampaignStatus.objects.filter(campaign=campaign, contact=contact).first()

        # Map results to status and campaign_resolution
        result_mapping = {
            _("Schedule"): (2, "SC"),
            "No encontrado, llamar más tarde": (3, "CL"),
            _("Not interested"): (4, "NI"),
            "No volver a llamar": (4, "DN"),
            _("Logistics"): (4, "LO"),
            _("Already a subscriber"): (4, "AS"),
            "Inubicable, retirar de campaña": (5, "UN"),
            _("Error in promotion"): (5, "EP"),
            "Mover a la mañana": (6, None),
            "Mover a la tarde": (7, None),
        }

        if result in result_mapping:
            status, campaign_resolution = result_mapping[result]
            ccs.status = status
            if campaign_resolution:
                ccs.campaign_resolution = campaign_resolution
            if status in (6, 7):  # Morning/Afternoon moves
                ccs.seller = None

        return ccs

    def create_scheduled_activity(self, contact, campaign, seller, call_datetime):
        """Create a scheduled activity"""
        return Activity.objects.create(
            contact=contact,
            activity_type="C",
            datetime=call_datetime,
            campaign=campaign,
            seller=seller,
            notes="{} {}".format(_("Scheduled for"), call_datetime),
        )

    def get_status_action_message(self, status):
        """Get appropriate action message for status"""
        status_messages = {
            2: _("scheduled"),
            3: _("skipped to call later"),
            4: _("marked as not interested"),
            5: _("marked as uncontactable"),
            6: _("moved to morning"),
            7: _("moved to afternoon"),
        }
        return status_messages.get(status, _("updated"))

    def handle_post_request(self):
        """Handle POST request logic"""
        data = self.request.POST
        result = data.get("result")
        offset = data.get("offset")
        campaign = self.get_campaign()
        category = data.get("category")
        instance_id = data.get("instance_id")
        seller = Seller.objects.get(pk=data.get("seller_id"))

        # Process resolution reason
        resolution_reason = (
            int(data.get("campaign_resolution_reason")) if data.get("campaign_resolution_reason") else None
        )
        chosen_resolution_reason = dict(CAMPAIGN_RESOLUTION_REASONS_CHOICES).get(resolution_reason)

        # Build activity notes
        new_activity_notes = self.build_activity_notes(result, chosen_resolution_reason, data.get("notes"))

        # Process based on category
        if category == "act":
            activity = Activity.objects.get(pk=instance_id)
            contact = activity.contact
            activity.notes = new_activity_notes
            activity.status = "C"
            activity.save()
        else:  # category == "new"
            ccs = ContactCampaignStatus.objects.get(pk=instance_id)
            contact = ccs.contact
            Activity.objects.create(
                contact=contact,
                activity_type="C",
                datetime=datetime.now(),
                campaign=campaign,
                seller=seller,
                status="C",
                notes=new_activity_notes,
            )

        # Process the result
        ccs = self.process_activity_result(contact, campaign, seller, result, new_activity_notes)

        # Handle scheduling if needed
        if result == _("Schedule"):
            call_datetime = self.get_call_datetime(data)
            self.create_scheduled_activity(contact, campaign, seller, call_datetime)

        # Save any resolution reason
        if data.get("campaign_resolution_reason"):
            ccs.resolution_reason = data.get("campaign_resolution_reason")
        ccs.save()

        # Show success message
        action = self.get_status_action_message(ccs.status)
        messages.success(self.request, _("Contact {id} {action}".format(id=contact.id, action=action)))

        # Convert offset to int and increment it only for "Call later" result
        try:
            if result == "No encontrado, llamar más tarde":
                offset = int(offset) + 1
        except (TypeError, ValueError):
            offset = 2  # If offset is None or invalid, start at 2 (next item)

        return self.get_redirect_response(category, campaign.id, offset)

    def build_activity_notes(self, result, chosen_resolution_reason, additional_notes):
        """Build complete activity notes string"""
        notes = [result]
        if chosen_resolution_reason:
            notes.append(f"({chosen_resolution_reason})")
        if additional_notes:
            notes.append(additional_notes)
        return "\n".join(notes)

    def get_call_datetime(self, data):
        """Convert date and time strings to datetime object"""
        call_date = datetime.strptime(data.get("call_date"), "%Y-%m-%d")
        call_time = datetime.strptime(data.get("call_time"), "%H:%M").time()
        return datetime.combine(call_date, call_time)

    def get_redirect_response(self, category, campaign_id, offset):
        """Get appropriate redirect response"""
        base_url = reverse("seller_console", args=[category, campaign_id])
        if offset:
            return HttpResponseRedirect(f"{base_url}?offset={offset}")
        return HttpResponseRedirect(base_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        campaign = self.get_campaign()
        seller = self.get_seller()

        category = self.kwargs['category']
        offset = self.request.GET.get('offset')
        activity_id = self.request.GET.get('a')

        offset = int(offset) if offset else 1
        call_datetime = datetime.strftime(date.today() + timedelta(1), "%Y-%m-%d")

        console_instances = self.get_console_instances(campaign, seller)
        count = console_instances.count()

        # Get console instance based on activity_id or offset
        console_instance = self.get_console_instance(
            console_instances=console_instances,
            activity_id=activity_id,
            count=count,
            offset=offset
        )

        contact = console_instance.contact

        context.update({
            'campaign': campaign,
            'times_contacted': contact.activity_set.filter(
                activity_type="C", status="C", campaign=campaign
            ).count(),
            'category': category,
            'position': offset + 1,
            'offset': offset,
            'seller': seller,
            'contact': contact,
            'count': count,
            'addresses': Address.objects.filter(contact=contact).order_by("address_1"),
            'call_date': call_datetime,
            'all_activities': self.get_activities(contact, console_instance, category),
            'all_subscriptions': Subscription.objects.filter(contact=contact).order_by("-active", "id"),
            'console_instance': console_instance,
            'console_instances': console_instances,
            'url': self.request.path,
            'pending_activities_count': seller.total_pending_activities_count(),
            'upcoming_activity': seller.upcoming_activity(),
            'resolution_reasons': CAMPAIGN_RESOLUTION_REASONS_CHOICES,
            'other_campaigns': ContactCampaignStatus.objects.filter(contact=contact).exclude(campaign=campaign),
        })
        return context

    def get_activities(self, contact, console_instance, category):
        activities = Activity.objects.filter(contact=contact).order_by("-datetime", "id")
        if category == "act":
            activities = activities.exclude(pk=console_instance.id)
        return activities

    def get_console_instance(self, *, console_instances, activity_id, count, offset):
        """Get the appropriate console instance based on activity_id or offset.

        Args:
            console_instances: QuerySet of available instances
            activity_id: Optional ID of specific activity to retrieve
            count: Total count of console instances
            offset: Current offset (1-based)
        """
        if activity_id:
            try:
                activity = console_instances.get(pk=activity_id)
                # Check if the contact is still in the campaign
                campaign = activity.campaign
                if not ContactCampaignStatus.objects.filter(
                    campaign=campaign,
                    contact=activity.contact
                ).exists():
                    # Contact is not in campaign anymore, delete the orphaned activity
                    activity.delete()
                    messages.warning(
                        self.request,
                        _("Activity was removed because the contact is no longer in the campaign")
                    )
                    return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
                return activity
            except Activity.DoesNotExist:
                messages.error(
                    self.request,
                    _("An error has occurred with activity number {}".format(activity_id))
                )
                return HttpResponseRedirect(reverse("seller_console_list_campaigns"))

        # Get item by offset (offset is 1-based, but list indexing is 0-based)
        index = offset - 1
        if 0 <= index < count:
            return console_instances[index]
        return console_instances[0]

    def post(self, request, *args, **kwargs):
        return self.handle_post_request()
