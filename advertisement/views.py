from datetime import date, datetime

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect
from django.urls import reverse

from advertisement.models import Advertiser, AdvertisementSeller, AdvertisementActivity
from advertisement.filters import AdvertiserFilter
from advertisement.forms import AdvertisementActivityForm, AddAdvertiserForm


@staff_member_required
def advertiser_list(request):
    """Shows a very simple advertiser list."""
    page = request.GET.get("p")
    advertiser_qs = Advertiser.objects.all().order_by("priority", "-id")
    contact_filter = AdvertiserFilter(request.GET, queryset=advertiser_qs)
    paginator = Paginator(contact_filter.qs, 50)
    try:
        advertisers = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        advertisers = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        advertisers = paginator.page(paginator.num_pages)
    return render(
        request,
        "advertiser_list.html",
        {
            "paginator": paginator,
            "advertisers": advertisers,
            "page": page,
            "total_pages": paginator.num_pages,
            "filter": contact_filter,
            "count": contact_filter.qs.count(),
        },
    )


@staff_member_required
def my_advertisers(request):
    if not AdvertisementSeller.objects.filter(user=request.user).exists():
        messages.error(request, _("User has no seller set"))
        return HttpResponseRedirect(reverse("list_advertisers"))
    seller = request.user.advertisementseller
    high = seller.advertiser_main_seller.filter(priority="1")
    mid = seller.advertiser_main_seller.filter(priority="2")
    low = seller.advertiser_main_seller.filter(priority__in=["3", None])
    upcoming_activities = AdvertisementActivity.objects.filter(
        advertiser__main_seller=seller, status="P", date__gte=datetime.now()
    ).order_by("date")
    overdue_activities = AdvertisementActivity.objects.filter(
        advertiser__main_seller=seller, status="P", date__lt=datetime.now()
    ).order_by("date")

    return render(
        request,
        "my_advertisers.html",
        {
            "seller": seller,
            "high": high,
            "mid": mid,
            "low": low,
            "upcoming": upcoming_activities,
            "overdue": overdue_activities,
        },
    )


@staff_member_required
def advertiser_detail(request, advertiser_id):
    advertiser_obj = get_object_or_404(Advertiser, pk=advertiser_id)
    activities = advertiser_obj.advertisementactivity_set.all().order_by("-date")
    return render(request, "advertiser_detail.html", {"advertiser": advertiser_obj, "activities": activities})


@staff_member_required
def add_advertisement_activity(request, advertiser_id):
    advertiser_obj = get_object_or_404(Advertiser, pk=advertiser_id)
    if request.POST:
        print("POST")
        form = AdvertisementActivityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Activity has been registered"))
            return HttpResponseRedirect(reverse("advertiser_detail", args=[advertiser_obj.id]))
    else:
        if AdvertisementSeller.objects.filter(user=request.user).exists():
            seller = AdvertisementSeller.objects.filter(user=request.user)
        form = AdvertisementActivityForm(
            initial={
                "date": datetime.now(),
                "seller": seller,
                "advertiser": advertiser_obj,
            }
        )
    return render(request, "add_advertisement_activity.html", {"advertiser": advertiser_obj, "form": form})

def add_advertiser(request):
    form = AddAdvertiserForm()
    return render(request, "add_edit_advertiser.html", {"form": form})
