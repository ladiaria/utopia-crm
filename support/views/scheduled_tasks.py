from datetime import timedelta, datetime
import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils import timezone

from core.models import Contact, Activity, SubscriptionProduct, Address
from support.models import ScheduledTask
from support.forms import NewPauseScheduledTaskForm, NewAddressChangeScheduledTaskForm, PartialPauseTaskForm
from support.filters import ScheduledTaskFilter


@staff_member_required
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
                start_task.execute()
                messages.success(request, _("Total pause has been executed."))
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = NewPauseScheduledTaskForm(
            initial={
                "activity_type": "C",
                "date_1": timezone.now().date().strftime("%Y-%m-%d"),
                "date_2": (timezone.now().date() + timedelta(days=1)).strftime("%Y-%m-%d"),
            }
        )
    form.fields["subscription"].queryset = contact.subscriptions.filter(active=True)
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": contact.get_full_name(),
            "url": reverse("contact_detail", args=[contact.id]),
        },
        {"label": _("New total pause"), "url": ""},
    ]
    return render(
        request,
        "new_scheduled_task_total_pause.html",
        {
            "contact": contact,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
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
                scheduled_task.execute()
                messages.success(request, _("Address change has been executed."))
            return HttpResponseRedirect(reverse("contact_detail", args=[contact.id]))
    else:
        form = NewAddressChangeScheduledTaskForm(
            initial={
                "new_address_type": "physical",
                "activity_type": "C",
                "date_1": timezone.now().date().strftime("%Y-%m-%d"),
            }
        )
    form.fields["contact_address"].queryset = contact.addresses.all()
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": contact.get_full_name(),
            "url": reverse("contact_detail", args=[contact.id]),
        },
        {"label": _("New address change"), "url": ""},
    ]
    return render(
        request,
        "new_scheduled_task_address_change.html",
        {
            "contact": contact,
            "form": form,
            "subscriptions": contact.subscriptions.filter(active=True),
            "breadcrumbs": breadcrumbs,
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
        form = PartialPauseTaskForm(
            initial={
                "activity_type": "C",
                "date_1": timezone.now().date().strftime("%Y-%m-%d"),
                "date_2": (timezone.now().date() + timedelta(days=1)).strftime("%Y-%m-%d"),
            }
        )
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": contact.get_full_name(),
            "url": reverse("contact_detail", args=[contact.id]),
        },
        {"label": _("New partial pause"), "url": ""},
    ]
    return render(
        request,
        "new_scheduled_task_partial_pause.html",
        {
            "contact": contact,
            "form": form,
            "subscriptions": contact.subscriptions.filter(active=True),
            "breadcrumbs": breadcrumbs,
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
        writer = csv.writer(response)
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
                    st.contact.get_full_name(),
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
