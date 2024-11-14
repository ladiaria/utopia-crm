from datetime import datetime

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import CreateView
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
            "paginator": paginator,
        },
    )


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

    def get_success_url(self):
        return reverse_lazy("contact_detail", kwargs={"pk": self.object.contact.id})

    def dispatch(self, request, *args, **kwargs):
        self.contact = get_object_or_404(Contact, pk=kwargs["contact_id"])
        return super().dispatch(request, *args, **kwargs)
