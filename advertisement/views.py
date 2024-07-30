from datetime import datetime

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import DetailView, TemplateView
from django.utils.decorators import method_decorator
from django_filters.views import FilterView
from django.contrib.auth.decorators import permission_required

from advertisement.models import (
    Advertiser,
    AdvertisementSeller,
    AdvertisementActivity,
    Agency,
    AdPurchaseOrder,
    Agent,
)
from advertisement.filters import AdvertiserFilter, AdPurchaseOrderFilter
from advertisement.forms import (
    AdvertisementActivityForm,
    AddAdvertiserForm,
    AddAgencyForm,
    AdPurchaseOrderForm,
    AdFormSet,
    AddAgentForm,
)


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
        return HttpResponseRedirect(reverse("advertiser_list"))
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


@method_decorator(staff_member_required, name='dispatch')
class AdvertiserCreateView(CreateView):
    model = Advertiser
    form_class = AddAdvertiserForm
    template_name = "advertiser_create_update.html"
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
    template_name = "advertiser_create_update.html"
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
    template_name = "agency_create_update.html"
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
    template_name = "agency_create_update.html"
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
class AgentCreateView(CreateView):
    model = Agent
    form_class = AddAgentForm
    template_name = "agent_create_update.html"
    success_url = reverse_lazy("agent_list")
    success_message = _("Agent has been added")

    def dispatch(self, request, *args, **kwargs):
        self.agency_id = kwargs.get("agency_id")
        if self.agency_id:
            self.agency_obj = get_object_or_404(Agency, pk=self.agency_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("agency_detail", kwargs={'pk': self.agency_id})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error"))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agency"] = self.agency_obj
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['agency'] = self.agency_obj
        return initial


@method_decorator(staff_member_required, name='dispatch')
class AdvertisementActivityCreateView(CreateView):
    model = AdvertisementActivity
    form_class = AdvertisementActivityForm
    template_name = "advertisement_activity_create_update.html"
    success_url = reverse_lazy("advertiser_list")
    success_message = _("Activity has been registered")

    def dispatch(self, request, *args, **kwargs):
        self.advertiser_id = kwargs.get("advertiser_id")
        if self.advertiser_id:
            self.advertiser_obj = get_object_or_404(Advertiser, pk=self.advertiser_id)
        if AdvertisementSeller.objects.filter(user=request.user).exists():
            self.seller = AdvertisementSeller.objects.filter(user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("advertiser_detail", kwargs={'pk': self.advertiser_id})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error"))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["advertiser"] = self.advertiser_obj
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['advertiser'] = self.advertiser_obj
        if self.seller:
            initial['seller'] = self.seller
        initial['date'] = datetime.now()
        return initial


@method_decorator(staff_member_required, name='dispatch')
class AdvertisementActivityEditView(UpdateView):
    model = AdvertisementActivity
    form_class = AdvertisementActivityForm
    template_name = "advertisement_activity_create_update.html"
    success_url = reverse_lazy("advertiser_list")
    success_message = _("Activity has been updated")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["advertiser"] = self.object.advertiser
        return context

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        self.success_url = reverse("advertiser_detail", args=[form.instance.advertiser.id])
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There was an error: %(error_message)s") % {"error_message": form.errors})
        return super().form_invalid(form)


@method_decorator(staff_member_required, name='dispatch')
class AdPurchaseOrderCreateView(CreateView):
    model = AdPurchaseOrder
    form_class = AdPurchaseOrderForm
    template_name = "ad_purchase_order_create_update.html"
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


@method_decorator(staff_member_required, name='dispatch')
class AdPurchaseOrderFilterView(FilterView):
    model = AdPurchaseOrder
    template_name = "ad_purchase_order_list.html"
    paginate_by = 50
    filterset_class = AdPurchaseOrderFilter

    def get_queryset(self):
        return AdPurchaseOrder.objects.all().order_by("-date_created")


@method_decorator(staff_member_required, name='dispatch')
class AdPurchaseOrderDetailView(DetailView):
    model = AdPurchaseOrder
    template_name = "ad_purchase_order_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ads"] = self.object.ad_set.all()
        if self.object.bill_to:
            context["bill_to"] = self.object.bill_to
        else:
            context["bill_to"] = self.object.advertiser
        return context


@permission_required("adpurchaseorder.can_set_billed", raise_exception=True)
@staff_member_required
def ad_purchase_order_set_billed(request, agency_id, pk):
    ad_purchase_order = get_object_or_404(AdPurchaseOrder, pk=pk)
    ad_purchase_order.set_billed()
    messages.success(request, _("Purchase order has been marked as billed"))
    return HttpResponseRedirect(reverse("ad_purchase_order_list"))
