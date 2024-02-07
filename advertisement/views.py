from datetime import date, datetime

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import DetailView, TemplateView
from django.utils.decorators import method_decorator
from django_filters.views import FilterView
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from advertisement.models import Advertiser, AdvertisementSeller, AdvertisementActivity, Agency, AdPurchaseOrder, Ad
from advertisement.filters import AdvertiserFilter
from advertisement.forms import (
    AdvertisementActivityForm,
    AddAdvertiserForm,
    AddAgencyForm,
    AdPurchaseOrderForm,
    AdFormSet,
)

from icecream import ic


@method_decorator(staff_member_required, name='dispatch')
class AdvertiserFilterView(FilterView):
    model = Advertiser
    template_name = "advertiser_list.html"
    paginate_by = 50
    filterset_class = AdvertiserFilter

    def get_queryset(self):
        return Advertiser.objects.all().order_by("priority", "-id")


@method_decorator(staff_member_required, name='dispatch')
class AgencyFilterView(FilterView):
    model = Agency
    template_name = "agency_list.html"
    paginate_by = 50
    filterset_class = AdvertiserFilter

    def get_queryset(self):
        return Agency.objects.all().order_by("priority", "-id")


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


@method_decorator(staff_member_required, name='dispatch')
class AdvertiserCreateView(CreateView):
    model = Advertiser
    form_class = AddAdvertiserForm
    template_name = "add_edit_advertiser.html"
    success_url = reverse_lazy("advertiser_list")
    success_message = _("Advertiser has been added")

    def get_success_url(self):
        # Redirect to the detail view of the newly created object
        return reverse_lazy('advertiser_detail', kwargs={'advertiser_id': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error"))
        return super().form_invalid(form)


@method_decorator(staff_member_required, name='dispatch')
class AdvertiserEditView(UpdateView):
    model = Advertiser
    form_class = AddAdvertiserForm
    template_name = "add_edit_advertiser.html"
    success_url = reverse_lazy("advertiser_list")
    success_message = _("Advertiser has been updated")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["advertiser"] = self.object
        if self.object.main_contact:
            context["main_contact"] = self.object.main_contact
        return context

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        self.success_url = reverse("advertiser_detail", args=[form.instance.id])
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error: %(error_message)s") % {"error_message": form.errors})
        return super().form_invalid(form)


@method_decorator(staff_member_required, name='dispatch')
class AdvertiserDetailView(DetailView):
    model = Advertiser
    template_name = "advertiser_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activities"] = self.object.advertisementactivity_set.all().order_by("-date")
        return context


@method_decorator(staff_member_required, name='dispatch')
class AgencyCreateView(CreateView):
    model = Agency
    form_class = AddAgencyForm
    template_name = "add_edit_agency.html"
    success_url = reverse_lazy("agency_list")
    success_message = _("Agency has been added")

    def get_success_url(self):
        # Redirect to the detail view of the newly created object
        return reverse_lazy('agency_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error"))
        return super().form_invalid(form)


@method_decorator(staff_member_required, name='dispatch')
class AgencyEditView(UpdateView):
    model = Agency
    form_class = AddAgencyForm
    template_name = "add_edit_agency.html"
    success_url = reverse_lazy("agency_list")
    success_message = _("Agency has been updated")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agency"] = self.object
        if self.object.main_contact:
            context["main_contact"] = self.object.main_contact
        return context

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        self.success_url = reverse("agency_detail", args=[form.instance.id])
        if self.request.POST.get("contact", None):
            form.cleaned_data["main_contact"] = self.request.POST.get("contact")
            form.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error: %(error_message)s") % {"error_message": form.errors})
        return super().form_invalid(form)


@method_decorator(staff_member_required, name='dispatch')
class AgencyDetailView(DetailView):
    model = Agency
    template_name = "agency_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activities"] = self.object.advertisementactivity_set.all().order_by("-date")
        return context


@method_decorator(staff_member_required, name='dispatch')
class AdFormTemplateView(TemplateView):
    model = Ad
    template_name = "partials/ad_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ad_form"] = AdForm()
        return context


@method_decorator(staff_member_required, name='dispatch')
class AdPurchaseOrderCreateView(CreateView):
    model = AdPurchaseOrder
    form_class = AdPurchaseOrderForm
    template_name = "add_edit_ad_purchase_order.html"
    success_url = reverse_lazy("advertiser_list")
    success_message = _("Purchase Order has been added")

    def dispatch(self, request, *args, **kwargs):
        self.advertiser_id = kwargs.get("advertiser_id")
        if self.advertiser_id:
            self.advertiser = get_object_or_404(Advertiser, pk=self.advertiser_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("advertiser_detail", kwargs={'pk': self.object.advertiser.id})

    def form_valid(self, form):
        context = self.get_context_data()
        ads_formset = context['ads_formset']
        if ads_formset.is_valid():
            self.object = form.save()
            ads_formset.instance = self.object
            ads_formset.save()
            msg = _("Purchase order for %(advertiser)s with a total value of %(price)s has been added") % {
                "advertiser": self.object.advertiser,
                "price": self.object.total_price,
            }
            messages.success(self.request, msg)
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error"))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['ads_formset'] = AdFormSet(self.request.POST)
        else:
            data['ads_formset'] = AdFormSet()
        data['advertiser'] = self.advertiser
        return data

    def get_initial(self):
        initial = super().get_initial()
        initial['advertiser'] = self.advertiser
        return initial
