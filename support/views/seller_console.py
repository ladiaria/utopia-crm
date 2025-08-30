from django.views.generic import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta, datetime

from support.models import Seller, Issue, SellerConsoleAction
from core.models import Address, SubscriptionProduct, Activity, ContactCampaignStatus, Campaign, Subscription, Contact
from core.utils import logistics_is_installed
from core.choices import ACTIVITY_STATUS, CAMPAIGN_RESOLUTION_REASONS_CHOICES, CAMPAIGN_STATUS

if logistics_is_installed():
    from logistics.models import Route


@staff_member_required
def seller_console_special_routes(request, route_id):
    # issue t935: Only show subscriptions started in the last 45 days (today included).
    if "logistics" in getattr(settings, "DISABLED_APPS", []):
        messages.error(request, _("This function is not available."))
        return HttpResponseRedirect(reverse("home"))
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
        return HttpResponseRedirect(reverse("home"))
    except Seller.MultipleObjectsReturned:
        messages.error(request, _("This seller is set in more than one user. Please contact your manager."))
        return HttpResponseRedirect(reverse("home"))

    # Only include products of subscriptions started in the last 45 days (today included).
    # i.e. start_date must be >= (today - 45 days), so anything older is excluded.
    subprods = SubscriptionProduct.objects.filter(
            seller=seller,
            route=route,
            subscription__active=True,
            subscription__start_date__lte=datetime.now() - timedelta(45)
        ).order_by("subscription__contact__id")
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
            return HttpResponseRedirect(reverse("home"))
        seller = Seller.objects.get(pk=seller_id)
        user = seller.user
    else:
        user = User.objects.get(username=request.user.username)
    try:
        seller = Seller.objects.get(user=user)
    except Seller.DoesNotExist:
        messages.error(request, _("User has no seller selected. Please contact your manager."))
        return HttpResponseRedirect(reverse("home"))
    except Seller.MultipleObjectsReturned:
        messages.error(request, _("This seller is set in more than one user. Please contact your manager."))
        return HttpResponseRedirect(reverse("home"))

    if logistics_is_installed():
        special_routes = {}
        for route_id in getattr(settings, "SPECIAL_ROUTES_FOR_SELLERS_LIST", []):
            route = Route.objects.get(pk=route_id)
            # Only include subscriptions started in the last 45 days (today included).
            # i.e. start_date must be >= (today - 45 days), so anything older is excluded.
            counter = SubscriptionProduct.objects.filter(
                seller=seller, route_id=route_id, subscription__active=True,
                subscription__start_date__gte=datetime.now() - timedelta(days=45),
            ).count()
            if counter:
                special_routes[route_id] = (route.name, counter)

    # We'll make these lists so we can append the sub count to each campaign
    campaigns_with_not_contacted_list, campaigns_with_activities_list = [], []
    if getattr(settings, "ISSUE_SUBCATEGORY_NEVER_PAID", None) and getattr(
        settings, "ISSUE_STATUS_FINISHED_LIST", None
    ):
        # issue t935: Only show issues with subscriptions that are less than one month old
        # Consider creating a setting for this if other apps need to use a different time frame
        issues_never_paid = Issue.objects.filter(
            sub_category__slug=getattr(settings, "ISSUE_SUBCATEGORY_NEVER_PAID", ""),
            assigned_to=user,
            # Only include subscriptions started in the last 45 days (today included).
            # i.e. start_date must be >= (today - 45 days), so anything older is excluded.
            subscription__start_date__gte=datetime.now() - timedelta(days=45),
        ).exclude(status__slug__in=getattr(settings, "ISSUE_STATUS_FINISHED_LIST", []))
    else:
        issues_never_paid = []

    not_contacted_campaigns = seller.get_campaigns_by_status([1, 3])
    campaigns_with_activities = seller.get_campaigns_with_activities()
    for campaign in not_contacted_campaigns:
        campaign.count = campaign.get_not_contacted_count(seller.id)
        campaign.successful = campaign.get_successful_count(seller.id)
        campaigns_with_not_contacted_list.append(campaign)
    for campaign in campaigns_with_activities:
        campaign.pending = campaign.activity_set.filter(
            seller=seller,
            status="P",
            activity_type="C",
            datetime__lte=timezone.now(),
        ).count()
        campaign.successful = campaign.get_successful_count(seller.id)
        if campaign.pending:
            campaigns_with_activities_list.append(campaign)
    upcoming_activity = seller.upcoming_activity()
    total_pending_activities = seller.total_pending_activities_count()

    context = {
        "campaigns_with_not_contacted": campaigns_with_not_contacted_list,
        "campaigns_with_activities_to_do": campaigns_with_activities_list,
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


class SellerConsoleView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'seller_console.html'

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, *args, **kwargs):
        """Handle GET requests and check for end of list"""
        redirect_url = self.check_end_of_list()
        if redirect_url:
            messages.success(request, _("You've reached the end of this list"))
            # Ensure redirect_url is a string
            return HttpResponseRedirect(str(redirect_url))

        return super().get(request, *args, **kwargs)

    def check_end_of_list(self):
        """Check if we've reached the end of the list and return redirect if needed"""
        campaign = self.get_campaign()
        seller = self.get_seller()
        console_instances = self.get_console_instances(campaign, seller)
        count = console_instances.count()

        try:
            offset = self.request.GET.get('offset')
            offset = int(offset) if offset else 1
            # Additional check to ensure offset is positive
            if offset < 1:
                messages.warning(self.request, _("Invalid offset value. Using first item."))
                return str(self.request.path)  # Convert to string
        except ValueError:
            messages.warning(self.request, _("Invalid offset value. Using first item."))
            return str(self.request.path)  # Convert to string

        if count == 0 or offset - 1 >= count:
            return str(reverse("seller_console_list_campaigns"))  # Convert to string
        return None

    def get_seller(self):
        """Get seller for current user"""
        return get_object_or_404(Seller, user=self.request.user)

    def get_campaign(self):
        """Get campaign from URL kwargs"""
        return get_object_or_404(Campaign, pk=self.kwargs['campaign_id'])

    def get_seller_console_action(self, result_slug, required=True):
        """Get SellerConsoleAction by slug with unified error handling

        Args:
            result_slug (str): The action slug to lookup
            required (bool): If True, raises error and returns None. If False, shows warning and continues.

        Returns:
            SellerConsoleAction or None
        """
        try:
            return SellerConsoleAction.objects.get(slug=result_slug, is_active=True)
        except SellerConsoleAction.DoesNotExist:
            if required:
                messages.error(self.request, _("Invalid action: {action}").format(action=result_slug))
                return None
            else:
                messages.warning(self.request, _("Invalid action slug: {action}").format(action=result_slug))
                return None

    def process_activity_result(self, contact, campaign, seller, seller_console_action, notes):
        """Process activity result and create/update related objects"""
        try:
            ccs = ContactCampaignStatus.objects.filter(campaign=campaign, contact=contact).first()
            if not ccs:
                messages.error(self.request, _("Contact is no longer in this campaign"))
                return None

            # Update the last console action
            ccs.last_console_action = seller_console_action

            # Use the campaign_status from the action if it's set
            if seller_console_action.campaign_status:
                ccs.status = seller_console_action.campaign_status

                # Handle special cases for morning/afternoon moves
                if seller_console_action.campaign_status in (
                    CAMPAIGN_STATUS.SWITCH_TO_MORNING,
                    CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON,
                ):
                    ccs.seller = None

            return ccs
        except Exception as e:
            messages.error(self.request, str(e))
            return None

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

    def get_contact_from_instance_id(self, instance_id, category):
        if category == "act":
            try:
                activity = Activity.objects.get(pk=instance_id)
                return activity.contact
            except Activity.DoesNotExist:
                messages.error(self.request, _("Activity not found"))
                return None
        else:
            try:
                ccs = ContactCampaignStatus.objects.get(pk=instance_id)
                return ccs.contact
            except ContactCampaignStatus.DoesNotExist:
                messages.error(
                    self.request,
                    _("The contact is no longer in this campaign, instance number: {}".format(instance_id)),
                )
                return None

    def register_new_activity(self, instance_id, category, campaign, seller, notes, result):
        contact = self.get_contact_from_instance_id(instance_id, category)
        if not contact:
            return None

        # Get action - not required, can continue with None if missing
        seller_console_action = self.get_seller_console_action(result, required=False)
        # If the ACTION_TYPE was DECLINED, we won't create a new activity
        if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.DECLINED:
            return
        # If we're using the setting to keep contacts in campaigns indefinitely, we'll need to set the datetime
        # to a future date, otherwise we'll use the current date and set this as closed. Anyways we'll mark the
        # current activity as closed and create a new one with the future datetime.
        if getattr(settings, "KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY", False):
            Activity.objects.create(
                contact=contact,
                activity_type="C",  # Call
                datetime=datetime.now() + timedelta(days=getattr(settings, "SELLER_CONSOLE_CALL_LATER_DAYS", 7)),
                campaign=campaign,
                seller=seller,
                status="P",  # Pending
                seller_console_action=seller_console_action,
                notes="",
            )
        if category == "new":
            # If this is the first time we're seeing this contact, we'll create an activity for it
            Activity.objects.create(
                contact=contact,
                activity_type="C",  # Call
                datetime=datetime.now(),
                campaign=campaign,
                seller=seller,
                status="C",  # Completed
                notes=notes,
                seller_console_action=seller_console_action,
            )

    def handle_post_request(self):
        """Handle POST request logic"""
        data = self.request.POST
        result = data.get("result")
        offset = data.get("offset")
        campaign = self.get_campaign()
        category = data.get("category")
        instance_id = data.get("instance_id")
        notes = data.get("notes")
        reason = data.get("campaign_resolution_reason")

        if not instance_id:
            messages.error(self.request, _("Missing console instance in POST data"))
            return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))
        contact = self.get_contact_from_instance_id(instance_id, category)
        if not contact:
            messages.error(self.request, _("Contact not found"))
            return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))
        try:
            seller = Seller.objects.get(pk=data.get("seller_id"))
        except Seller.DoesNotExist:
            messages.error(self.request, _("Invalid seller ID"))
            return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))

        seller_console_action = self.get_seller_console_action(result, required=True)
        if not seller_console_action:
            return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))

        # Process based on category
        if category == "act":
            try:
                activity = Activity.objects.get(pk=instance_id)
            except Activity.DoesNotExist:
                messages.error(self.request, _("Activity not found"))
                return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))
            activity.notes = data.get("notes")
            activity.status = ACTIVITY_STATUS.COMPLETED
            activity.datetime = datetime.now()  # Set the datetime to the current time
            activity.save()
            if getattr(settings, "KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY", False):
                # This is only here so that we can register a new activity if the setting is enabled
                self.register_new_activity(instance_id, category, campaign, seller, notes, result)
        else:  # category == "new"
            self.register_new_activity(instance_id, category, campaign, seller, notes, result)

        # Process the result
        ccs = self.process_activity_result(contact, campaign, seller, seller_console_action, notes)
        if not ccs:
            return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))

        # Handle scheduling if needed
        if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.SCHEDULED:
            call_datetime = self.get_call_datetime(data)
            self.create_scheduled_activity(contact, campaign, seller, call_datetime)

        # Save any resolution reason
        if reason:
            ccs.resolution_reason = reason
        ccs.save()

        # Show success message
        messages.success(self.request, _("Contact {id} has been updated".format(id=contact.id)))

        # Convert offset to int and increment it only for "Call later" result
        try:
            if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.CALL_LATER:
                offset = int(offset) + 1
        except (TypeError, ValueError):
            offset = 2  # If offset is None or invalid, start at 2 (next item)

        return self.get_redirect_response(category, campaign.id, offset)

    def get_call_datetime(self, data):
        """Convert date and time strings to datetime object"""
        try:
            call_date = datetime.strptime(data.get("call_date"), "%Y-%m-%d")
            call_time = datetime.strptime(data.get("call_time"), "%H:%M").time()
            return datetime.combine(call_date, call_time)
        except (ValueError, TypeError):
            messages.error(self.request, _("Invalid date or time format"))
            raise

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
            console_instances=console_instances, activity_id=activity_id, count=count, offset=offset
        )

        # If no valid console instance is found, redirect to campaigns list
        if not console_instance:
            messages.warning(self.request, _("No valid contacts found in this campaign"))
            return {'redirect': reverse("seller_console_list_campaigns")}

        contact = console_instance.contact

        # Get phone duplicate information
        phone_duplicates_info = self.get_phone_duplicates_info(contact)

        context.update(
            {
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
                'phone_duplicates_count': phone_duplicates_info['count'],
                'phone_duplicates': phone_duplicates_info['contacts'],
            }
        )
        return context

    def get_phone_duplicates_info(self, contact):
        """
        Get information about other contacts with the same phone number.
        
        Args:
            contact (Contact): The current contact to check for duplicates
            
        Returns:
            dict: Dictionary with 'count' (int) and 'contacts' (QuerySet) keys
        """
        from django.db.models import Q
        
        # Build query to find contacts with matching phone or mobile numbers
        phone_query = Q()
        
        # Check if contact has a phone number and add to query
        if contact.phone and str(contact.phone).strip():
            phone_query |= Q(phone=contact.phone) | Q(mobile=contact.phone)
            
        # Check if contact has a mobile number and add to query
        if contact.mobile and str(contact.mobile).strip():
            phone_query |= Q(phone=contact.mobile) | Q(mobile=contact.mobile)
        
        # If no phone numbers to check, return empty result
        if not phone_query:
            return {'count': 0, 'contacts': Contact.objects.none()}
        
        # Find other contacts with matching phone numbers (exclude current contact)
        duplicate_contacts = Contact.objects.filter(phone_query).exclude(id=contact.id).select_related(
            'subtype', 'institution'
        ).order_by('name', 'last_name')
        
        count = duplicate_contacts.count()
        
        return {
            'count': count,
            'contacts': duplicate_contacts
        }

    def get_activities(self, contact, console_instance, category):
        activities = Activity.objects.filter(contact=contact).order_by("-datetime", "id")
        if category == "act":
            activities = activities.exclude(pk=console_instance.id)
        return activities

    def get_console_instance(self, *, console_instances, activity_id, count, offset):
        """
        Retrieve a single console instance based on an activity ID or offset.

        Args:
            console_instances (QuerySet): The queryset of available console instances.
            activity_id (int): Optional. The ID of a specific activity to retrieve.
            count (int): The total number of console instances.
            offset (int): The current offset (1-based index) for navigating instances.

        Returns:
            Model or None: A single console instance (e.g., Activity) or None if no valid instance is found.

        Notes:
            - If activity_id is provided, it attempts to fetch the activity with that ID.
            - If no activity_id is provided, it uses the offset to determine the instance.
            - Includes checks to ensure data integrity (e.g., contact is still part of the campaign).
            - Used mainly to show the seller the current contact to call.
        """
        if activity_id:
            try:
                activity = console_instances.get(pk=activity_id)
                # Check if the contact is still in the campaign
                campaign = activity.campaign
                if not ContactCampaignStatus.objects.filter(campaign=campaign, contact=activity.contact).exists():
                    # Contact is not in campaign anymore, delete the orphaned activity
                    activity.delete()
                    messages.warning(
                        self.request, _("Activity was removed because the contact is no longer in the campaign")
                    )
                    return None
                return activity
            except Activity.DoesNotExist:
                messages.error(self.request, _("An error has occurred with activity number {}".format(activity_id)))
                return None

        # Get item by offset (offset is 1-based, but list indexing is 0-based)
        index = offset - 1
        if 0 <= index < count:
            return console_instances[index]
        return console_instances[0]

    def get_console_instances(self, campaign, seller):
        """
        Retrieve a queryset of console instances based on the campaign and seller.

        Args:
            campaign (Campaign): The campaign instance to filter console instances.
            seller (Seller): The seller instance associated with the current user.

        Returns:
            QuerySet: A queryset of console instances matching the given criteria.

        Notes:
            - If the category is "new", it retrieves contacts not yet contacted by the seller.
            - Otherwise, it filters activities with type "C" (e.g., calls) and specific statuses.
            - Used mainly to show the seller the list of contacts to call.
            - It's also used to check if the list is empty and redirect to the list of campaigns if it is.
        """
        category = self.kwargs['category']
        if category == "new":
            return campaign.get_not_contacted(seller.id)
        if getattr(settings, "ALLOW_ACCESSING_FUTURE_ACTIVITIES_IN_SELLER_CONSOLE", False):
            return campaign.activity_set.filter(activity_type="C", seller=seller, status="P").order_by(
                "datetime", "id"
            )
        return campaign.activity_set.filter(
            activity_type="C", seller=seller, status="P", datetime__lte=datetime.now()
        ).order_by("datetime", "id")

    def post(self, request, *args, **kwargs):
        return self.handle_post_request()

    def render_to_response(self, context, **response_kwargs):
        """Override render_to_response to handle redirects from get_context_data"""
        if context.get('redirect'):
            return HttpResponseRedirect(context['redirect'])
        return super().render_to_response(context, **response_kwargs)
