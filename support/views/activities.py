from datetime import datetime

from django.contrib.auth.models import User
from django.views.generic import CreateView, UpdateView, ListView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.translation import gettext as _
from django.utils import timezone
from core.models import Activity, Contact
from core.mixins import BreadcrumbsMixin
from support.models import Seller
from support.filters import ScheduledActivityFilter
from support.forms import CreateActivityForm


class ScheduledActivitiesView(BreadcrumbsMixin, UserPassesTestMixin, ListView):
    model = Activity
    template_name = "scheduled_activities.html"
    context_object_name = "activities"
    paginate_by = 100
    paginate_orphans = 5
    page_kwarg = 'p'  # Use 'p' instead of default 'page' for pagination parameter

    def breadcrumbs(self):
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Seller console"), "url": reverse("seller_console_list_campaigns")},
            {"label": _("Activities"), "url": reverse("scheduled_activities")},
        ]

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        user = User.objects.get(username=self.request.user.username)
        try:
            self.seller = Seller.objects.get(user=user)
        except Seller.DoesNotExist:
            self.seller = None

        if self.seller:
            queryset = self.seller.total_pending_activities()
        else:
            queryset = Activity.objects.none()

        # Apply filter - now this happens regardless of whether seller exists
        self.activity_filter = ScheduledActivityFilter(self.request.GET, queryset)
        return self.activity_filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the page object from ListView's pagination
        activities = context['object_list']

        # Get the most recent active subscription end date for each contact
        activities_with_subscription_data = []
        for activity in activities:
            if activity.contact:
                # Get the most recent active subscription end date for this contact
                latest_subscription = activity.contact.subscriptions.filter(active=True).order_by('-end_date').first()

                latest_subscription_end_date = latest_subscription.end_date if latest_subscription else None

                # Add the subscription end date to the activity object
                activity.latest_subscription_end_date = latest_subscription_end_date
                activities_with_subscription_data.append(activity)
            else:
                activity.latest_subscription_end_date = None
                activities_with_subscription_data.append(activity)

        # Apply date range filtering for subscription end date if specified
        subscription_end_date_min = self.request.GET.get('subscription_end_date_min')
        subscription_end_date_max = self.request.GET.get('subscription_end_date_max')

        if subscription_end_date_min or subscription_end_date_max:
            filtered_activities = []
            for activity in activities_with_subscription_data:
                # Skip activities without subscription end date if filtering by date
                if activity.latest_subscription_end_date is None:
                    continue

                include_activity = True

                if (
                    subscription_end_date_min
                    and activity.latest_subscription_end_date
                    < datetime.strptime(subscription_end_date_min, '%Y-%m-%d').date()
                ):
                    include_activity = False

                if (
                    subscription_end_date_max
                    and activity.latest_subscription_end_date
                    > datetime.strptime(subscription_end_date_max, '%Y-%m-%d').date()
                ):
                    include_activity = False

                if include_activity:
                    filtered_activities.append(activity)

            activities_with_subscription_data = filtered_activities

        # Check if we need to sort by latest subscription end date
        sort_by = self.request.GET.get('sort_by', 'latest_subscription_end_date')  # Default to ascending order

        # Sort by latest subscription end date
        if sort_by == 'latest_subscription_end_date' or sort_by is None:
            # Sort by latest subscription end date ascending (None values at the end)
            activities_with_subscription_data.sort(
                key=lambda x: (x.latest_subscription_end_date is None, x.latest_subscription_end_date)
            )
        elif sort_by == '-latest_subscription_end_date':
            # Sort by latest subscription end date in descending order (None values at the end)
            activities_with_subscription_data.sort(
                key=lambda x: (x.latest_subscription_end_date is None, x.latest_subscription_end_date), reverse=True
            )

        # Update context
        context.update(
            {
                "filter": self.activity_filter,
                "activities": activities_with_subscription_data,
                "seller": self.seller,
                "count": self.get_queryset().count(),
                "now": datetime.now(),
                "sort_by": sort_by  # Pass the sort parameter to the template
            }
        )

        return context


scheduled_activities = ScheduledActivitiesView.as_view()


class ActivityCreateView(UserPassesTestMixin, BreadcrumbsMixin, CreateView):
    model = Activity
    form_class = CreateActivityForm
    template_name = "activities/create_activity.html"
    success_url = reverse_lazy("contact_list")

    def test_func(self):
        return self.request.user.is_staff

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": self.contact.get_full_name(), "url": reverse("contact_detail", args=[self.contact.id])},
            {"label": _("Register activity"), "url": ""},
        ]

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["contact"].initial = self.contact
        form.fields["datetime"].initial = timezone.now().strftime("%Y-%m-%dT%H:%M")
        form.fields["status"].initial = "C"  # Completed
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Create a mapping of topic_id -> list of response options
        from core.models import ActivityTopic, ActivityResponse
        import json

        topic_responses = {}
        for topic in ActivityTopic.objects.all():
            responses = ActivityResponse.objects.filter(topic=topic).values('id', 'name')
            topic_responses[topic.id] = list(responses)

        # Also include responses without a topic
        responses_without_topic = ActivityResponse.objects.filter(topic__isnull=True).values('id', 'name')
        topic_responses['null'] = list(responses_without_topic)

        context['topic_responses_json'] = json.dumps(topic_responses)
        return context

    def get_success_url(self):
        return reverse_lazy("contact_detail", kwargs={"pk": self.object.contact.id})

    def dispatch(self, request, *args, **kwargs):
        self.contact = get_object_or_404(Contact, pk=kwargs["contact_id"])
        return super().dispatch(request, *args, **kwargs)


class ActivityUpdateView(UserPassesTestMixin, BreadcrumbsMixin, UpdateView):
    model = Activity
    form_class = CreateActivityForm
    template_name = "activities/create_activity.html"
    success_url = reverse_lazy("contact_list")

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": self.contact.get_full_name(), "url": reverse("contact_detail", args=[self.contact.id])},
            {"label": _("Update activity"), "url": ""},
        ]

    def test_func(self):
        return self.request.user.is_staff

    def get_success_url(self):
        return reverse_lazy("contact_detail", kwargs={"pk": self.object.contact.id})

    def dispatch(self, request, *args, **kwargs):
        # We need to see if the contact exists first because it's in the url
        get_object_or_404(Contact, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)
