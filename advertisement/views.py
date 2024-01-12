from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from advertisement.models import Advertiser
from advertisement.filters import AdvertiserFilter


@staff_member_required
def advertiser_list(request):
    """
    Shows a very simple contact list.
    """
    page = request.GET.get("p")
    advertiser_qs = Advertiser.objects.all().order_by("-id")
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
    return render(request, "my_advertisers.html")
