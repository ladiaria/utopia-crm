import collections
from datetime import date, datetime, timedelta

import pandas as pd
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.text import format_lazy
from django.utils.translation import gettext as _
from django.views.generic import FormView, ListView
from django_filters.views import FilterView
from requests.exceptions import RequestException

from core.mixins import BreadcrumbsMixin
from core.models import (
    Activity,
    Address,
    Campaign,
    Contact,
    ContactCampaignStatus,
    Product,
    Subscription,
    SubscriptionProduct,
)
from core.utils import logistics_is_installed
from core.choices import ACTIVITY_STATUS
from support.filters import (
    SubscriptionEndDateFilter,
    UnsubscribedSubscriptionsByEndDateFilter,
)
from support.forms import (
    AdditionalProductForm,
    NewAddressForm,
    NewPromoForm,
    NewSubscriptionForm,
    UnsubscriptionForm,
    CorporateSubscriptionForm,
    AffiliateSubscriptionForm,
)
from support.location import SugerenciaGeorefForm
from support.models import SalesRecord
from util.dates import add_business_days


class SubscriptionMixin(BreadcrumbsMixin):
    template_name = "new_subscription.html"
    form_class = NewSubscriptionForm

    def breadcrumbs(self):
        return [
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {"label": self.contact.get_full_name(), "url": reverse("contact_detail", args=[self.contact.id])},
            {"label": _("Edit subscription") if hasattr(self, "subscription") else _("Add subscription"), "url": ""},
        ]

    def get_contact(self, contact_id):
        self.contact = get_object_or_404(Contact, pk=contact_id)
        return self.contact

    def get_contact_addresses(self, contact):
        return Address.objects.filter(contact=contact)

    def get_subscription(self, subscription_id):
        self.subscription = get_object_or_404(Subscription, pk=subscription_id) if subscription_id else None
        return self.subscription

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["contact"] = self.get_contact(self.kwargs["contact_id"])
        return kwargs

    def get_initial_data(self):
        contact = self.contact
        contact_addresses = Address.objects.filter(contact=contact)
        return {
            "contact": contact,
            "name": contact.name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "mobile": contact.mobile,
            "email": contact.email,
            "id_document": contact.id_document,
            "id_document_type": contact.id_document_type,
            "default_address": contact_addresses,
            "copies": 1,
        }

    def handle_form_errors(self, form):
        if form.errors:
            for field, error in form.errors.items():
                messages.error(self.request, f"{field}: {error}")

    def save_contact_changes(self, form, contact):
        changed = False
        for attr in ("name", "last_name", "phone", "mobile", "email", "id_document_type", "id_document"):
            val = form.cleaned_data.get(attr)
            if getattr(contact, attr) != val:
                changed = True
                setattr(contact, attr, val)
        if changed:
            try:
                contact.save()
            except (ValidationError, RequestException) as vre:
                form.add_error(None, vre if isinstance(vre, ValidationError) else _("CMS sync error"))
        return changed

    def process_subscription_products(self, request, subscription):
        new_products_list = []
        for key in request.POST.keys():
            if key.startswith("check"):
                product_id = key.split("-")[1]
                product = Product.objects.get(pk=product_id)
                new_products_list.append(product)
                address_id = request.POST.get(f"address-{product_id}")
                address = Address.objects.get(pk=address_id)
                copies = request.POST.get(f"copies-{product_id}")
                message = request.POST.get(f"message-{product_id}")
                instructions = request.POST.get(f"instructions-{product_id}")
                old_address, old_route, old_order = None, None, None
                if not SubscriptionProduct.objects.filter(subscription=subscription, product=product).exists():
                    if (
                        subscription
                        and SubscriptionProduct.objects.filter(subscription=subscription, product=product).exists()
                    ):
                        old_address = (
                            SubscriptionProduct.objects.filter(subscription=subscription, product=product)
                            .first()
                            .address
                        )
                        if old_address == address:
                            old_route = (
                                SubscriptionProduct.objects.filter(subscription=subscription, product=product)
                                .first()
                                .route
                            )
                            old_order = (
                                SubscriptionProduct.objects.filter(subscription=subscription, product=product)
                                .first()
                                .order
                            )
                    subscription.add_product(
                        product=product,
                        address=address,
                        copies=copies,
                        message=message,
                        instructions=instructions,
                        route=old_route,
                        order=old_order,
                    )
                else:
                    sp = SubscriptionProduct.objects.get(subscription=subscription, product=product)
                    if sp.address != address:
                        sp.route, sp.order = None, None
                    sp.address = address
                    sp.copies = copies
                    sp.label_message = message
                    sp.special_instructions = instructions
                    sp.save()
        return new_products_list

    def handle_subscription_status(self, subscription):
        if subscription.start_date > date.today() + timedelta(1):
            subscription.active = False
        subscription.status = "OK"
        subscription.save()

    def handle_subscription_type(self, subscription):
        if subscription.number_of_subscriptions > 1 and subscription.override_price:
            subscription.type = "C"
        else:
            subscription.type = "N"

    def remove_unselected_products(self, subscription, new_products_list):
        for subscriptionproduct in SubscriptionProduct.objects.filter(subscription=subscription):
            if subscriptionproduct.product not in new_products_list:
                subscription.remove_product(subscriptionproduct.product)

    def save_subscription(self, form, subscription, contact):
        self.save_contact_changes(form, contact)
        if not form.errors:
            try:
                subscription = form.save()
            except Exception as exc:
                if settings.DEBUG:
                    print(exc)
                messages.error(
                    self.request,
                    _("The subscription may not have been completely saved or synchronized with the CMS"),
                )
            else:
                new_products_list = self.process_subscription_products(self.request, subscription)
                self.handle_subscription_type(subscription)
                self.handle_subscription_status(subscription)
                self.remove_unselected_products(subscription, new_products_list)
                return subscription

    def capture_variables(self):
        self.url = self.request.GET.get("url", None)
        self.offset = self.request.GET.get("offset", None)
        self.is_new = self.request.GET.get("new", None)
        self.is_activity = self.request.GET.get("act", None)
        self.ccs = None
        self.campaign = None
        self.user_seller_id = None

        if self.subscription:
            if self.subscription.contact != self.contact:
                # TODO: change this to a better approach, it generates bad UX and an error email wo traceback (useless)
                return HttpResponseServerError(_("Wrong data"))
            self.edit_subscription = True
        else:
            self.subscription, self.edit_subscription = None, False

        if self.request.GET.get("act", None):
            self.activity = Activity.objects.get(pk=self.request.GET["act"])
            self.campaign = self.activity.campaign
            try:
                self.ccs = ContactCampaignStatus.objects.get(contact=self.contact, campaign=self.campaign)
            except ContactCampaignStatus.DoesNotExist:
                msg = _(
                    "Activity {} is not in campaign {}. Please report this error!".format(
                        self.activity.id, self.campaign.id
                    )
                )
                messages.error(self.request, msg)
                return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
            self.user_seller_id = self.ccs.seller.id
        elif self.request.GET.get("new", None):
            self.ccs = ContactCampaignStatus.objects.get(pk=self.request.GET["new"])
            self.campaign = self.ccs.campaign
            self.user_seller_id = self.ccs.seller.id
        elif self.request.user.seller_set.exists():
            self.user_seller_id = self.request.user.seller_set.first().id
        else:
            self.user_seller_id = None

    def get_redirect_url_and_sales_record(self, form, subscription, contact, user_seller_id):
        if self.is_new:
            # This means this is a direct sale, we also need to register the activity as just started
            self.ccs.handle_direct_sale(form.cleaned_data["register_activity"], subscription=subscription)
            redirect_to = f"{self.url}?offset={self.offset}"
        elif self.request.GET.get("act", None):
            # This means this is a sale from an activity
            self.activity.mark_as_sale(
                form.cleaned_data["register_activity"], self.campaign, subscription=subscription
            )
            redirect_to = f"{self.url}?offset={self.offset}"
        else:
            if form.cleaned_data.get("register_activity", None):
                Activity.objects.create(
                    contact=contact,
                    activity_type="C",
                    datetime=datetime.now(),
                    campaign=self.campaign,
                    seller_id=self.user_seller_id,
                    status="C",
                    notes=form.cleaned_data["register_activity"],
                )
            redirect_to = reverse("contact_detail", args=[contact.id])
        if not self.edit_subscription:
            sf = SalesRecord.objects.create(
                subscription=subscription,
                seller_id=user_seller_id,
                price=subscription.get_price_for_full_period(),
                campaign=self.campaign,
            )
            sf.add_products()
            if not user_seller_id:
                sf.set_generic_seller()
        self.redirect_to = redirect_to
        return redirect_to

    def get_success_url(self):
        return self.redirect_to

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contact"] = self.contact
        return context


class SubscriptionCreateView(UserPassesTestMixin, SubscriptionMixin, FormView):

    def test_func(self):
        return self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        self.contact = self.get_contact(kwargs['contact_id'])
        self.subscription = None
        self.capture_variables()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.subscription = self.save_subscription(form, self.subscription, self.contact)
        if self.subscription:
            redirect_to = self.get_redirect_url_and_sales_record(
                form, self.subscription, self.contact, self.user_seller_id
            )
            return HttpResponseRedirect(redirect_to)
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "contact": self.contact,
                "edit_subscription": self.edit_subscription,
                "subscription": self.subscription,
                "offerable_products": Product.objects.filter(offerable=True),
                "contact_addresses": Address.objects.filter(contact=self.contact),
                "other_active_normal_subscriptions": Subscription.objects.filter(
                    contact=self.contact, active=True, type="N"
                ),
                "georef_activated": getattr(settings, "GEOREF_SERVICES", False),
                "address_form": SugerenciaGeorefForm(),
            }
        )
        return context


class SubscriptionUpdateView(SubscriptionMixin, FormView):

    def dispatch(self, request, *args, **kwargs):
        self.contact = self.get_contact(kwargs['contact_id'])
        self.subscription = self.get_subscription(kwargs['subscription_id'])
        self.capture_variables()
        if self.subscription and self.subscription.contact != self.contact:
            # TODO: change this to a better approach, it generates bad UX and an error email wo traceback (useless)
            return HttpResponseServerError(_("Wrong data"))
        self.edit_subscription = bool(self.subscription)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial_data = self.get_initial_data()
        if self.subscription:
            initial_data.update(
                {
                    # Add any initial data from the subscription if needed
                }
            )
        return initial_data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.subscription
        return kwargs

    def form_valid(self, form):
        self.subscription = self.save_subscription(form, self.subscription, self.contact)
        if self.subscription:
            redirect_to = self.get_redirect_url_and_sales_record(
                form, self.subscription, self.contact, self.user_seller_id
            )
            return HttpResponseRedirect(redirect_to)
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "contact": self.contact,
                "edit_subscription": self.edit_subscription,
                "subscription": self.subscription,
                "offerable_products": Product.objects.filter(offerable=True),
                "contact_addresses": Address.objects.filter(contact=self.contact),
                "other_active_normal_subscriptions": Subscription.objects.filter(
                    contact=self.contact, active=True, type="N"
                ),
                "georef_activated": getattr(settings, "GEOREF_SERVICES", False),
                "address_form": SugerenciaGeorefForm(),
            }
        )
        return context


@staff_member_required
def unsubscription_statistics(request):
    unsubscriptions_queryset = Subscription.objects.filter(end_date__isnull=False, unsubscription_products__type="S")
    unsubscriptions_filter = UnsubscribedSubscriptionsByEndDateFilter(request.GET, queryset=unsubscriptions_queryset)

    executed_unsubscriptions_requested = (
        unsubscriptions_filter.qs.filter(end_date__lte=date.today())
        .exclude(unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    executed_unsubscriptions_not_requested = (
        unsubscriptions_filter.qs.filter(
            end_date__lte=date.today(), unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON
        )
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    programmed_unsubscriptions_requested = (
        unsubscriptions_filter.qs.filter(end_date__gt=date.today())
        .exclude(unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON)
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    programmed_unsubscriptions_not_requested = (
        unsubscriptions_filter.qs.filter(
            end_date__gt=date.today(), unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON
        )
        .values("unsubscription_products__name")
        .annotate(total=Count("unsubscription_products"))
        .order_by("unsubscription_products__billing_priority", "unsubscription_products__name")
    )

    total_unsubscriptions_requested = programmed_unsubscriptions_requested | executed_unsubscriptions_requested
    total_unsubscriptions_not_requested = (
        programmed_unsubscriptions_not_requested | executed_unsubscriptions_not_requested
    )

    individual_products_dict = collections.OrderedDict()
    choices = dict(settings.UNSUBSCRIPTION_REASON_CHOICES)
    for product_obj in Product.objects.filter(type="S", offerable=True).order_by("billing_priority"):
        individual_products_dict[product_obj.name] = (
            unsubscriptions_filter.qs.filter(unsubscription_products=product_obj, unsubscription_reason__isnull=False)
            .values("unsubscription_reason")
            .annotate(total=Count("unsubscription_reason"))
        )
    for individual_product in list(individual_products_dict.values()):
        # This dictionary will have unsubscription_reason as the index to be shown, this is not ideal for sure
        for item in individual_product:
            # Probably very bad solution to convert choices to displays, someone help me with a better way!
            item["unsubscription_reason"] = choices.get(item["unsubscription_reason"], None)

    total_unsubscriptions_by_reason = (
        unsubscriptions_filter.qs.filter(unsubscription_reason__isnull=False)
        .values("unsubscription_reason")
        .annotate(total=Count("unsubscription_reason"))
    )
    for item in total_unsubscriptions_by_reason:
        # Probably very bad solution to convert choices to displays, someone help me with a better way!
        item["unsubscription_reason"] = choices.get(item["unsubscription_reason"], None)

    total_requested_unsubscriptions_count = unsubscriptions_filter.qs.exclude(
        unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON
    ).count()
    total_not_requested_unsubscriptions_count = unsubscriptions_filter.qs.filter(
        unsubscription_reason=settings.UNSUBSCRIPTION_OVERDUE_REASON
    ).count()
    total_unsubscriptions_count = unsubscriptions_filter.qs.count()

    return render(
        request,
        "unsubscription_statistics.html",
        {
            "filter": unsubscriptions_filter,
            "queryset": unsubscriptions_filter.qs,
            "executed_unsubscriptions_requested": executed_unsubscriptions_requested,
            "executed_unsubscriptions_not_requested": executed_unsubscriptions_not_requested,
            "programmed_unsubscriptions_requested": programmed_unsubscriptions_requested,
            "programmed_unsubscriptions_not_requested": programmed_unsubscriptions_not_requested,
            "total_unsubscriptions_requested": total_unsubscriptions_requested,
            "total_unsubscriptions_not_requested": total_unsubscriptions_not_requested,
            "individual_products_dict": individual_products_dict,
            "total_unsubscriptions_by_reason": total_unsubscriptions_by_reason,
            "total_requested_unsubscriptions_count": total_requested_unsubscriptions_count,
            "total_not_requested_unsubscriptions_count": total_not_requested_unsubscriptions_count,
            "total_unsubscriptions_count": total_unsubscriptions_count,
        },
    )


@staff_member_required
def book_unsubscription(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    if subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=subscription.contact.get_full_name(),
                end_date=subscription.end_date,
            )
            messages.success(request, success_text)
            subscription.unsubscription_type = 1  # Complete unsubscription
            subscription.unsubscription_date = date.today()
            subscription.unsubscription_manager = request.user
            subscription.unsubscription_products.add(*subscription.products.all())
            subscription.save()
            return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))
    else:
        if subscription.is_obsolete():
            messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=subscription)
        if not subscription.end_date:
            form.initial["end_date"] = date.today()

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[subscription.contact.id]),
        },
        {"label": _("Book unsubscription"), "url": ""},
    ]
    return render(
        request,
        "book_unsubscription.html",
        {
            "subscription": subscription,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def partial_unsubscription(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    if old_subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status=old_subscription.status,
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key.split("-")[1]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    old_subscription.unsubscription_products.add(subscription_product.product)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if logistics_is_installed():
                        if sp.route:
                            new_sp.route = sp.route
                        if sp.order:
                            new_sp.order = sp.order
                        new_sp.save()

            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=old_subscription.contact.get_full_name(),
                end_date=old_subscription.end_date,
            )
            messages.success(request, success_text)

            old_subscription.unsubscription_type = 2  # Partial unsubscription
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    else:
        messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=old_subscription)
        if not old_subscription.end_date:
            form.initial["end_date"] = date.today()

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": old_subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[old_subscription.contact.id]),
        },
        {"label": _("Partial unsubscription"), "url": ""},
    ]
    return render(
        request,
        "book_partial_unsubscription.html",
        {
            "subscription": old_subscription,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def product_change(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    if old_subscription.is_obsolete():
        messages.warning(request, _("WARNING: This subscription has already been closed"))
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact.id]))
    offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
        id__in=old_subscription.products.values_list("id")
    )
    new_products_ids_list = []
    if request.POST:
        form = UnsubscriptionForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status=old_subscription.status,
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
            )
            for key, value in list(request.POST.items()):
                if key.startswith("sp"):
                    subscription_product_id = key.split("-")[1]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    old_subscription.unsubscription_products.add(subscription_product.product)
                if key.startswith("activateproduct"):
                    product_id = key.split("-")[1]
                    new_products_ids_list.append(product_id)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if logistics_is_installed():
                        if sp.route:
                            new_sp.route = sp.route
                        if sp.order:
                            new_sp.order = sp.order
                        new_sp.save()
            # after this, we need to add the new products, that will have to be reviewed by an agent
            for product_id in new_products_ids_list:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    new_subscription.add_product(
                        product=product,
                        address=None,
                    )
            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy(
                "Unsubscription for {name} booked for {end_date}",
                name=old_subscription.contact.get_full_name(),
                end_date=old_subscription.end_date,
            )
            messages.success(request, success_text)
            old_subscription.unsubscription_type = 3  # Partial unsubscription
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            return HttpResponseRedirect(
                reverse("edit_subscription", args=[new_subscription.contact.id, new_subscription.id])
            )
    else:
        messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = UnsubscriptionForm(instance=old_subscription)
        if not old_subscription.end_date:
            form.initial["end_date"] = date.today()

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": old_subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[old_subscription.contact.id]),
        },
        {"label": _("Book product change"), "url": ""},
    ]
    return render(
        request,
        "book_product_change.html",
        {
            "offerable_products": offerable_products,
            "subscription": old_subscription,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def book_additional_product(request, subscription_id):
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)
    from_seller_console = "url" in request.GET
    if old_subscription.frequency != 1:
        messages.error(request, "La periodicidad de la suscripción debe ser mensual")
        return HttpResponseRedirect(reverse("contact_detail", args=[old_subscription.contact_id]))
    offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
        id__in=old_subscription.products.values_list("id")
    )
    new_products_ids_list = []
    if request.POST:
        seller_id = request.user.seller_set.first().id if request.user.seller_set.exists() else None
        campaign = request.GET.get("campaign", None)
        campaign_obj = Campaign.objects.get(pk=campaign) if campaign else None
        form = AdditionalProductForm(request.POST, instance=old_subscription)
        if form.is_valid():
            form.save()
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["end_date"],
                payment_type=old_subscription.payment_type,
                type=old_subscription.type,
                status="OK",
                billing_name=old_subscription.billing_name,
                billing_id_doc=old_subscription.billing_id_doc,
                rut=old_subscription.rut,
                billing_phone=old_subscription.billing_phone,
                send_bill_copy_by_email=old_subscription.send_bill_copy_by_email,
                billing_address=old_subscription.billing_address,
                billing_email=old_subscription.billing_email,
                next_billing=old_subscription.next_billing,
                frequency=old_subscription.frequency,
                updated_from=old_subscription,
            )
            for key, value in list(request.POST.items()):
                # These are the new products
                if key.startswith("activateproduct"):
                    product_id = key.split("-")[1]
                    new_products_ids_list.append(product_id)

            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product not in old_subscription.unsubscription_products.all():
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    if logistics_is_installed():
                        if sp.route:
                            new_sp.route = sp.route
                        if sp.order:
                            new_sp.order = sp.order
                        new_sp.save()
            # after this, we need to add the new products, that will have to be reviewed by an agent
            new_products_list = []
            for product_id in new_products_ids_list:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    if old_subscription.contact.address_set.exists():
                        default_address = old_subscription.contact.address_set.first()
                    else:
                        default_address = None
                    new_subscription.add_product(
                        product=product,
                        address=default_address,
                        seller_id=seller_id,
                    )
                    new_products_list.append(product)
            # If there was a seller we have to add a new SalesRecord.
            # We will add the difference in price between the old and the new subscription, when it's a partial sale.
            sf = SalesRecord.objects.create(
                subscription=new_subscription,
                seller=seller_id,
                price=new_subscription.get_price_for_full_period() - old_subscription.get_price_for_full_period(),
                sale_type=SalesRecord.TYPES.PARTIAL,
                campaign=campaign_obj,
            )
            sf.products.add(*new_products_list)
            if not seller_id:
                sf.set_generic_seller()
            # After that, we'll set the unsubscription date to this new subscription
            success_text = format_lazy("New product(s) booked for {end_date}", end_date=old_subscription.end_date)
            messages.success(request, success_text)
            old_subscription.inactivity_reason = 3  # Upgrade
            old_subscription.unsubscription_type = 4  # Upgrade
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()
            edit_subscription_url = reverse(
                "edit_subscription", args=[new_subscription.contact.id, new_subscription.id]
            )
            return HttpResponseRedirect(edit_subscription_url)
    else:
        if old_subscription.end_date:
            messages.warning(request, _("WARNING: This subscription already has an end date"))
        form = AdditionalProductForm(instance=old_subscription)
        if not old_subscription.end_date:
            form.initial["end_date"] = date.today()

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": old_subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[old_subscription.contact.id]),
        },
        {"label": _("Book additional product"), "url": ""},
    ]
    return render(
        request,
        "book_additional_product.html",
        {
            "from_seller_console": from_seller_console,
            "offerable_products": offerable_products,
            "subscription": old_subscription,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


class SendPromoView(UserPassesTestMixin, FormView):
    """
    Shows a form that the sellers can use to send promotions to the contact.
    """
    template_name = "seller_console_start_promo.html"
    form_class = NewPromoForm

    def test_func(self):
        return self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        """Initialize view-level variables from URL parameters."""
        self.url = request.GET.get("url")
        self.act = request.GET.get("act")
        self.new = request.GET.get("new")
        self.offset = request.GET.get("offset", 0)

        if not (self.act or self.new):
            return HttpResponseNotFound()

        self.contact = get_object_or_404(Contact, pk=kwargs['contact_id'])
        self.contact_addresses = Address.objects.filter(contact=self.contact)
        self.offerable_products = Product.objects.filter(offerable=True, type="S")

        # Get campaign and seller info
        if self.act:
            self.activity = get_object_or_404(Activity, pk=self.act)
            self.campaign = self.activity.campaign
            self.ccs = get_object_or_404(
                ContactCampaignStatus, contact=self.contact, campaign=self.campaign
            )
        elif self.new:
            self.ccs = get_object_or_404(ContactCampaignStatus, pk=self.new)
            self.campaign = self.ccs.campaign
            self.activity = None

        self.seller = self.ccs.seller

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Set initial form data."""
        start_date = date.today()

        if self.campaign:
            end_date = add_business_days(date.today(), self.campaign.days)
        else:
            end_date = add_business_days(date.today(), 5)

        return {
            "name": self.contact.name,
            "last_name": self.contact.last_name,
            "phone": self.contact.phone,
            "mobile": self.contact.mobile,
            "email": self.contact.email,
            "default_address": self.contact_addresses,
            "start_date": start_date,
            "end_date": end_date,
            "copies": 1,
        }

    def get_form(self, form_class=None):
        """Customize form to set address queryset."""
        form = super().get_form(form_class)
        form.fields["default_address"].queryset = self.contact_addresses
        return form

    def post(self, request, *args, **kwargs):
        """Handle Cancel button separately from form submission."""
        result = request.POST.get("result")

        if result == _("Cancel"):
            if self.offset:
                return HttpResponseRedirect("{}?offset={}".format(self.url, self.offset))
            else:
                return HttpResponseRedirect(self.url)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Process the form and create subscription."""
        # First we need to save all the new contact data if necessary
        changed = False
        for attr in ("name", "phone", "mobile", "email", "notes"):
            val = form.cleaned_data.get(attr)
            if getattr(self.contact, attr) != val:
                changed = True
                setattr(self.contact, attr, val)

        if changed:
            try:
                self.contact.save()
            except forms.ValidationError as ve:
                form.add_error(None, ve)
                return self.form_invalid(form)

        # Create the subscription
        start_date = form.cleaned_data["start_date"]
        end_date = form.cleaned_data["end_date"]
        subscription = Subscription.objects.create(
            contact=self.contact,
            type="P",
            start_date=start_date,
            end_date=end_date,
            campaign=self.campaign,
        )

        # Add products to subscription
        for key, value in list(self.request.POST.items()):
            if key.startswith("check"):
                product_id = key.split("-")[1]
                product = Product.objects.get(pk=product_id)
                address_id = self.request.POST.get("address-{}".format(product_id))
                address = Address.objects.get(pk=address_id)
                copies = self.request.POST.get("copies-{}".format(product_id))
                label_message = self.request.POST.get("message-{}".format(product_id))
                special_instructions = self.request.POST.get("instruction-{}".format(product_id))
                subscription.add_product(
                    product=product,
                    address=address,
                    copies=copies,
                    message=label_message,
                    instructions=special_instructions,
                    seller_id=self.seller.id,
                )

        # Update activity and campaign status
        if self.request.GET.get("act", None):
            # the instance is somehow an activity and we needed to send a promo again, or has been scheduled
            self.activity.status = ACTIVITY_STATUS.COMPLETED  # completed activity
            self.activity.save()
            self.ccs.campaign_resolution = "SP"
            self.ccs.status = 2  # Contacted this person
            self.ccs.save()
        elif self.request.GET.get("new", None):
            self.ccs.status = 2  # contacted this person
            self.ccs.campaign_resolution = "SP"  # Sent promo to this customer
            self.ccs.save()

        # Create follow-up activity
        Activity.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            direction="O",
            datetime=end_date + timedelta(1),
            activity_type="C",
            status="P",
            seller=self.seller,
        )

        return HttpResponseRedirect("{}?offset={}".format(self.url, self.offset))

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context.update({
            "contact": self.contact,
            "address_form": NewAddressForm(initial={"address_type": "physical"}),
            "offerable_products": self.offerable_products,
            "contact_addresses": self.contact_addresses,
        })
        return context


# Backward compatibility
send_promo = SendPromoView.as_view()


class SubscriptionEndDateListView(UserPassesTestMixin, FilterView, ListView):
    model = Subscription
    template_name = 'subscriptions/subscription_end_date_list.html'
    context_object_name = 'subscriptions'
    filterset_class = SubscriptionEndDateFilter
    paginate_by = 10
    page_kwarg = 'p'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        # Apply the filterset to the queryset
        queryset = super().get_queryset().filter(active=True)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs.order_by('end_date')

    def get(self, request, *args, **kwargs):
        if request.GET.get("export"):
            return self.export_to_csv()
        return super().get(request, *args, **kwargs)

    def export_to_csv(self):
        queryset = self.get_queryset().select_related('contact').prefetch_related('products')
        if settings.DEBUG:
            print(f"DEBUG: export_to_csv: Exporting {queryset.count()} subscriptions to CSV")

        data = []
        for subscription in queryset:
            data.append(
                {
                    'Contact ID': subscription.contact.id,
                    'Contact Name': subscription.contact.get_full_name(),
                    'Email': subscription.contact.email,
                    'Phone': subscription.contact.phone,
                    'End Date': subscription.end_date,
                    'Products': ', '.join([p.name for p in subscription.products.all()]),
                }
            )

        df = pd.DataFrame(data)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="subscription_end_dates.csv"'

        df.to_csv(path_or_buf=response, index=False, encoding='utf-8')

        return response


class CorporateSubscriptionCreateView(SubscriptionMixin, FormView):
    form_class = CorporateSubscriptionForm

    # TODO: Add a template for this view that allows to select products and addresses.
    # It should also allow to select the start and end dates and the amount of subscriptions to create.

    def dispatch(self, request, *args, **kwargs):
        self.contact = self.get_contact(kwargs['contact_id'])
        self.subscription = None
        self.capture_variables()
        return super().dispatch(request, *args, **kwargs)


class AffiliateSubscriptionView(FormView):
    template_name = 'subscriptions/affiliate_subscription.html'
    form_class = AffiliateSubscriptionForm

    def get_success_url(self):
        return reverse_lazy(
            'affiliate_subscription', kwargs={'corporate_subscription_id': self.kwargs['corporate_subscription_id']}
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['main_subscription_id'] = self.kwargs['main_subscription_id']
        return kwargs

    def form_valid(self, form):
        main_subscription = get_object_or_404(Subscription, id=self.kwargs['main_subscription_id'])
        contact = form.cleaned_data['contact']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        bulk_subscription = Subscription.objects.create(
            contact=contact,
            start_date=start_date,
            end_date=end_date,
            payment_type=main_subscription.payment_type,
            type='C',  # Complementary
            status=main_subscription.status,
        )

        main_sp = SubscriptionProduct.objects.get(subscription=main_subscription)
        SubscriptionProduct.objects.create(subscription=bulk_subscription, product=main_sp.product, copies=1)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        corporate_subscription = get_object_or_404(Subscription, id=self.kwargs['corporate_subscription_id'])
        context['corporate_subscription'] = corporate_subscription
        context['affiliate_subscriptions'] = (
            Subscription.objects.filter(
                type='C', payment_type=corporate_subscription.payment_type, status=corporate_subscription.status
            )
            .select_related('contact')
            .order_by('start_date')
        )
        return context
