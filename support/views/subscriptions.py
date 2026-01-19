import collections
import json
from datetime import date, datetime, timedelta

import pandas as pd
from dateutil.relativedelta import relativedelta
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.text import format_lazy
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.generic import CreateView, FormView, ListView
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
    RetentionDiscountForm,
    FreeSubscriptionForm,
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
        return {
            "contact": contact,
            "name": contact.name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "mobile": contact.mobile,
            "email": contact.email,
            "id_document": contact.id_document,
            "id_document_type": contact.id_document_type,
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

            # Create an Activity to store unsubscription information for potential reactivation
            unsubscription_data = {
                "type": "unsubscription",
                "subscription_id": subscription.id,
                "end_date": subscription.end_date.isoformat(),
                "unsubscription_reason": subscription.unsubscription_reason,
                "unsubscription_channel": subscription.unsubscription_channel,
                "unsubscription_addendum": subscription.unsubscription_addendum,
                "unsubscription_type": subscription.unsubscription_type,
                "unsubscription_date": subscription.unsubscription_date.isoformat(),
                "unsubscription_manager_id": request.user.id,
                "unsubscription_manager_name": request.user.get_full_name() or request.user.username,
                "unsubscription_products": [p.id for p in subscription.unsubscription_products.all()],
            }

            # Create human-readable notes
            products_list = ", ".join([p.name for p in subscription.unsubscription_products.all()])
            readable_notes = _(
                "Complete unsubscription booked for {end_date}.\n"
                "Reason: {reason}\n"
                "Products: {products}\n"
                "Manager: {manager}"
            ).format(
                end_date=subscription.end_date.isoformat(),
                reason=subscription.get_unsubscription_reason_display() or "-",
                products=products_list,
                manager=request.user.get_full_name() or request.user.username
            )

            Activity.objects.create(
                contact=subscription.contact,
                activity_type="N",  # Internal - system-generated activity
                datetime=datetime.now(),
                status="C",
                direction="O",
                created_by=request.user,
                notes=readable_notes,
                metadata=unsubscription_data,
            )

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
def reactivate_subscription(request, subscription_id):
    """
    Reactivate a subscription that was disabled using book_unsubscription.
    This only works for complete unsubscriptions (unsubscription_type=1).
    Partial unsubscriptions and product changes create new subscriptions, so they cannot be reactivated.

    Business Rules:
    - Can only reactivate within 30 days of unsubscription_date
    - If next_billing is in the past, it will be adjusted to today + 1 day
    """
    subscription = get_object_or_404(Subscription, pk=subscription_id)

    # Validate that this subscription can be reactivated
    if not subscription.end_date:
        messages.error(request, _("This subscription is not unsubscribed and cannot be reactivated"))
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))

    if subscription.unsubscription_type != 1:
        messages.error(
            request,
            _(
                "Only complete unsubscriptions can be reactivated. "
                "Partial unsubscriptions and product changes create new subscriptions."
            )
        )
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))

    # Validate 30-day limit from unsubscription_date
    if subscription.unsubscription_date:
        days_since_unsubscription = (date.today() - subscription.unsubscription_date).days
        if days_since_unsubscription > 30:
            messages.error(
                request,
                _(
                    "This subscription cannot be reactivated because more than 30 days have passed "
                    "since the unsubscription date ({unsubscription_date}). "
                    "Reactivation is only allowed within 30 days of unsubscription."
                ).format(unsubscription_date=subscription.unsubscription_date.strftime("%Y-%m-%d"))
            )
            return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))

    # Find the unsubscription activity to retrieve stored data
    # First try to find activity with metadata field (new approach)
    unsubscription_activity = None
    stored_data = None

    activities_with_metadata = Activity.objects.filter(
        contact=subscription.contact,
        metadata__type="unsubscription",
        metadata__subscription_id=subscription.id
    ).order_by("-datetime")

    if activities_with_metadata.exists():
        unsubscription_activity = activities_with_metadata.first()
        stored_data = unsubscription_activity.metadata
    else:
        # Fallback: try old format with notes (for backward compatibility)
        for activity in Activity.objects.filter(
            contact=subscription.contact,
            notes__startswith="UNSUBSCRIPTION_DATA:"
        ).order_by("-datetime"):
            try:
                notes_data = activity.notes.replace("UNSUBSCRIPTION_DATA:", "", 1)
                data = json.loads(notes_data)
                if (
                    data.get("end_date") == subscription.end_date.isoformat()
                    and data.get("unsubscription_type") == subscription.unsubscription_type
                ):
                    unsubscription_activity = activity
                    stored_data = data
                    break
            except (json.JSONDecodeError, AttributeError):
                continue

    if request.POST:
        # If no activity was found, create one now for registry purposes (failproof)
        if not unsubscription_activity:
            # Create fallback unsubscription data from current subscription state
            fallback_data = {
                "type": "unsubscription",
                "subscription_id": subscription.id,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                "unsubscription_reason": subscription.unsubscription_reason,
                "unsubscription_channel": subscription.unsubscription_channel,
                "unsubscription_addendum": subscription.unsubscription_addendum,
                "unsubscription_type": subscription.unsubscription_type,
                "unsubscription_date": (
                    subscription.unsubscription_date.isoformat() if subscription.unsubscription_date else None
                ),
                "unsubscription_manager_id": (
                    subscription.unsubscription_manager.id if subscription.unsubscription_manager else None
                ),
                "unsubscription_manager_name": (
                    subscription.unsubscription_manager.get_full_name()
                    or subscription.unsubscription_manager.username
                ) if subscription.unsubscription_manager else "Unknown",
                "unsubscription_products": [p.id for p in subscription.unsubscription_products.all()],
                "created_at_reactivation": True,  # Flag to indicate this was created during reactivation
            }

            products_list = ", ".join([p.name for p in subscription.unsubscription_products.all()])
            fallback_notes = _(
                "Unsubscription data (created during reactivation for registry):\n"
                "End date: {end_date}\n"
                "Reason: {reason}\n"
                "Products: {products}\n"
                "Manager: {manager}"
            ).format(
                end_date=subscription.end_date.isoformat() if subscription.end_date else "-",
                reason=subscription.get_unsubscription_reason_display() or "-",
                products=products_list or "-",
                manager=fallback_data["unsubscription_manager_name"]
            )

            unsubscription_activity = Activity.objects.create(
                contact=subscription.contact,
                activity_type="N",  # Internal - system-generated activity
                datetime=datetime.now(),
                status="C",
                direction="O",
                created_by=request.user,
                notes=fallback_notes,
                metadata=fallback_data,
            )
            stored_data = fallback_data

        # Perform the reactivation
        subscription.end_date = None
        subscription.unsubscription_reason = None
        subscription.unsubscription_channel = None
        subscription.unsubscription_addendum = None
        subscription.unsubscription_type = None
        subscription.unsubscription_date = None
        subscription.unsubscription_manager = None
        subscription.unsubscription_products.clear()

        # Adjust next_billing if it's in the past to prevent unwanted invoices
        if subscription.next_billing and subscription.next_billing < date.today():
            subscription.next_billing = date.today() + timedelta(days=1)

        subscription.save()

        # Create an Activity to log the reactivation
        reactivation_notes = _("Subscription reactivated by {user} on {date}").format(
            user=request.user.get_full_name() or request.user.username,
            date=date.today().isoformat()
        )
        if unsubscription_activity:
            reactivation_notes += (
                f"\n{_('Original unsubscription data stored in Activity')} "
                f"#{unsubscription_activity.id}"
            )

        reactivation_metadata = {
            "type": "reactivation",
            "subscription_id": subscription.id,
            "reactivation_date": date.today().isoformat(),
            "reactivated_by_id": request.user.id,
            "reactivated_by_name": request.user.get_full_name() or request.user.username,
            "unsubscription_activity_id": unsubscription_activity.id if unsubscription_activity else None,
        }

        Activity.objects.create(
            contact=subscription.contact,
            activity_type="N",  # Internal - system-generated activity
            datetime=datetime.now(),
            status="C",
            direction="O",
            created_by=request.user,
            notes=reactivation_notes,
            metadata=reactivation_metadata,
        )

        success_text = format_lazy(
            "Subscription for {name} has been reactivated",
            name=subscription.contact.get_full_name(),
        )
        messages.success(request, success_text)
        return HttpResponseRedirect(reverse("contact_detail", args=[subscription.contact.id]))

    # GET request - show confirmation page
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[subscription.contact.id]),
        },
        {"label": _("Reactivate subscription"), "url": ""},
    ]

    # Get display values for reason and channel from subscription object
    # These are needed because stored_data contains integer values, not display labels
    reason_display = subscription.get_unsubscription_reason_display() if subscription.unsubscription_reason else None
    channel_display = subscription.get_unsubscription_channel_display() if subscription.unsubscription_channel else None

    # stored_data is already set from the activity lookup above
    return render(
        request,
        "reactivate_subscription.html",
        {
            "subscription": subscription,
            "stored_data": stored_data,
            "unsubscription_activity": unsubscription_activity,
            "breadcrumbs": breadcrumbs,
            "reason_display": reason_display,
            "channel_display": channel_display,
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
                    new_sp.original_datetime = sp.original_datetime
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
                    new_sp.original_datetime = sp.original_datetime
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
            old_subscription.inactivity_reason = Subscription.InactivityReasonChoices.ADDED_PRODUCTS
            old_subscription.unsubscription_type = Subscription.UnsubscriptionTypeChoices.ADDED_PRODUCTS
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


@staff_member_required
def add_retention_discount(request, subscription_id):
    """
    View for adding retention discounts to a subscription.
    Creates a new subscription with retention discount products starting on a specified date.
    Sets the old subscription's unsubscription type and reason to RETENTION.

    This view allows:
    - Adding retention discounts (shows all available except those already applied)
    - Adding new subscription products (optional)
    - Removing existing products (optional)

    Similar to product_change but focused on retention scenarios.
    """
    old_subscription = get_object_or_404(Subscription, pk=subscription_id)

    # Get existing retention discounts to exclude (only show discounts not already applied)
    existing_discount_ids = old_subscription.products.filter(
        type__in=["D", "P", "A"], discount_category="R"
    ).values_list("id", flat=True)

    # Get all available retention products (no target_product filtering)
    retention_products = (
        Product.objects.filter(type__in=["D", "P", "A"], discount_category="R", active=True)
        .exclude(id__in=existing_discount_ids)
    )

    # Get offerable subscription products that the customer doesn't have yet
    offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
        id__in=old_subscription.products.values_list("id")
    )

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {
            "label": old_subscription.contact.get_full_name(),
            "url": reverse("contact_detail", args=[old_subscription.contact.id]),
        },
        {"label": _("Add retention discount"), "url": ""},
    ]

    if request.POST:
        form = RetentionDiscountForm(request.POST, instance=old_subscription)
        if form.is_valid():
            # Validate start date is at least tomorrow
            start_date = form.cleaned_data["start_date"]
            from datetime import timedelta
            tomorrow = date.today() + timedelta(days=1)
            if start_date < tomorrow:
                messages.error(
                    request,
                    _("Start date must be at least tomorrow (%s)") % tomorrow.strftime('%d/%m/%Y'),
                )
                return render(
                    request,
                    "add_retention_discount.html",
                    {
                        "retention_products": retention_products,
                        "subscription": old_subscription,
                        "form": form,
                        "breadcrumbs": breadcrumbs,
                    },
                )

            # Get products to remove (marked for unsubscription)
            products_to_remove = []
            for key in request.POST.keys():
                if key.startswith("sp-"):
                    subscription_product_id = key.split("-")[1]
                    subscription_product = SubscriptionProduct.objects.get(pk=subscription_product_id)
                    products_to_remove.append(subscription_product.product)

            # Get selected retention discount products
            selected_discount_ids = []
            for key in request.POST.keys():
                if key.startswith("retentionproduct-"):
                    product_id = key.split("-")[1]
                    selected_discount_ids.append(product_id)

            # Get new products to add
            new_products_ids_list = []
            for key in request.POST.keys():
                if key.startswith("activateproduct-"):
                    product_id = key.split("-")[1]
                    new_products_ids_list.append(product_id)

            # Validate that at least one action is being taken
            if not selected_discount_ids and not products_to_remove and not new_products_ids_list:
                messages.error(
                    request,
                    _("Please select at least one retention discount, add new products, "
                      "or mark products to remove")
                )
                return render(
                    request,
                    "add_retention_discount.html",
                    {
                        "retention_products": retention_products,
                        "offerable_products": offerable_products,
                        "subscription": old_subscription,
                        "form": form,
                        "breadcrumbs": breadcrumbs,
                    },
                )

            # Validate that at least one subscription product remains
            # Count only subscription products (type "S"), not discounts
            subscription_products = [
                sp.product for sp in old_subscription.subscriptionproduct_set.all()
                if sp.product.type == "S"
            ]
            subscription_products_to_remove = [p for p in products_to_remove if p.type == "S"]

            # Check if we're removing all subscription products without adding new ones
            if len(subscription_products_to_remove) >= len(subscription_products) and not new_products_ids_list:
                messages.error(
                    request,
                    _("You cannot remove all subscription products without adding new ones. "
                      "At least one subscription product must remain (discounts alone are not enough)."),
                )
                return render(
                    request,
                    "add_retention_discount.html",
                    {
                        "retention_products": retention_products,
                        "offerable_products": offerable_products,
                        "subscription": old_subscription,
                        "form": form,
                        "breadcrumbs": breadcrumbs,
                    },
                )

            # Set end date on old subscription
            old_subscription.end_date = form.cleaned_data["start_date"]
            old_subscription.save()

            # Create new subscription with retention discounts
            new_subscription = Subscription.objects.create(
                active=False,
                contact=old_subscription.contact,
                start_date=form.cleaned_data["start_date"],
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

            # Copy products from old subscription to new subscription, excluding removed ones
            # Also add removed products to unsubscription_products
            for sp in old_subscription.subscriptionproduct_set.all():
                if sp.product in products_to_remove:
                    # Add to unsubscription_products for tracking
                    old_subscription.unsubscription_products.add(sp.product)
                else:
                    # Copy to new subscription
                    new_sp = new_subscription.add_product(
                        product=sp.product,
                        address=sp.address,
                        copies=sp.copies,
                        message=sp.label_message,
                        instructions=sp.special_instructions,
                        seller_id=sp.seller_id,
                    )
                    new_sp.original_datetime = sp.original_datetime
                    if logistics_is_installed():
                        if sp.route:
                            new_sp.route = sp.route
                        if sp.order:
                            new_sp.order = sp.order
                    new_sp.save()

            # Get seller for new products
            seller_id = request.user.seller_set.first().id if request.user.seller_set.exists() else None

            # Add retention discount products
            for product_id in selected_discount_ids:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    new_subscription.add_product(
                        product=product,
                        address=None,  # Discounts don't need addresses
                    )

            # Add new subscription products
            for product_id in new_products_ids_list:
                product = Product.objects.get(pk=product_id)
                if product not in new_subscription.products.all():
                    new_subscription.add_product(
                        product=product,
                        seller_id=seller_id,
                        address=None,
                    )

            # Set old subscription's unsubscription type and reason to RETENTION
            old_subscription.inactivity_reason = Subscription.InactivityReasonChoices.RETENTION
            old_subscription.unsubscription_type = Subscription.UnsubscriptionTypeChoices.RETENTION
            old_subscription.unsubscription_date = date.today()
            old_subscription.unsubscription_manager = request.user
            old_subscription.save()

            success_text = format_lazy(
                "Retention discount(s) added for {name}, starting {start_date}",
                name=old_subscription.contact.get_full_name(),
                start_date=form.cleaned_data["start_date"],
            )
            messages.success(request, success_text)

            # Redirect to edit subscription page to allow address changes for new products
            url = reverse("edit_subscription", args=[new_subscription.contact.id, new_subscription.id])
            url_params = ""
            if request.GET.get("url", None):
                url_params += f"&url={request.GET['url']}"
            if request.GET.get("offset", None):
                url_params += f"&offset={request.GET['offset']}"
            if request.GET.get("new", None):
                url_params += f"&new={request.GET['new']}"
            if request.GET.get("act", None):
                url_params += f"&act={request.GET['act']}"
            if url_params.startswith("&"):
                # Switch the first & for ?
                url_params = "?" + url_params[1:]

            return HttpResponseRedirect(url + url_params)
    else:
        form = RetentionDiscountForm(instance=old_subscription)
        # Set default start date based on old subscription's start date
        # If in the past: use today
        # If in the future: use one day after it
        if old_subscription.start_date < date.today():
            form.initial["start_date"] = date.today() + timedelta(days=1)
        else:
            form.initial["start_date"] = old_subscription.start_date + timedelta(days=1)

    return render(
        request,
        "add_retention_discount.html",
        {
            "retention_products": retention_products,
            "offerable_products": offerable_products,
            "subscription": old_subscription,
            "form": form,
            "breadcrumbs": breadcrumbs,
        },
    )


class SendPromoView(BreadcrumbsMixin, UserPassesTestMixin, FormView):
    """
    Shows a form that the sellers can use to send promotions to the contact.
    """

    template_name = "seller_console_start_promo.html"
    form_class = NewPromoForm

    def test_func(self):
        return self.request.user.is_staff

    def breadcrumbs(self):
        """Return breadcrumbs for navigation."""
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {
                "label": self.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.contact.id]),
            },
            {"label": _("Send promotion"), "url": ""},
        ]

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
            self.ccs = get_object_or_404(ContactCampaignStatus, contact=self.contact, campaign=self.campaign)
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
            "notes": self.contact.notes,
            "start_date": start_date,
            "end_date": end_date,
            "copies": 1,
        }

    def get_form(self, form_class=None):
        """Customize form to set address queryset and pass contact."""
        form = super().get_form(form_class)
        return form

    def get_form_kwargs(self):
        """Pass the contact to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['contact'] = self.contact
        return kwargs

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
        context.update(
            {
                "contact": self.contact,
                "address_form": NewAddressForm(initial={"address_type": "physical"}),
                "offerable_products": self.offerable_products,
                "contact_addresses": self.contact_addresses,
            }
        )
        return context


# Backward compatibility
send_promo = SendPromoView.as_view()


class UpdatePromoView(BreadcrumbsMixin, UserPassesTestMixin, FormView):
    """
    Shows a form that allows updating an existing promotional subscription.
    Similar to SendPromoView but updates instead of creates.
    """

    template_name = "seller_console_start_promo.html"
    form_class = NewPromoForm

    def test_func(self):
        return self.request.user.is_staff

    def breadcrumbs(self):
        """Return breadcrumbs for navigation."""
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {
                "label": self.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.contact.id]),
            },
            {"label": _("Update promotion"), "url": ""},
        ]

    def dispatch(self, request, *args, **kwargs):
        """Initialize view-level variables from URL parameters."""
        self.url = request.GET.get("url")
        self.offset = request.GET.get("offset", 0)

        # Get the subscription to update
        self.subscription = get_object_or_404(Subscription, pk=kwargs['subscription_id'])
        self.contact = self.subscription.contact
        self.contact_addresses = Address.objects.filter(contact=self.contact)
        self.offerable_products = Product.objects.filter(offerable=True, type="S")

        # Get existing subscription products
        self.subscription_products = SubscriptionProduct.objects.filter(subscription=self.subscription).select_related(
            'product', 'address'
        )

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Set initial form data from existing subscription."""
        return {
            "name": self.contact.name,
            "last_name": self.contact.last_name,
            "phone": self.contact.phone,
            "mobile": self.contact.mobile,
            "email": self.contact.email,
            "notes": self.contact.notes,
            "start_date": self.subscription.start_date,
            "end_date": self.subscription.end_date,
            "copies": 1,
        }

    def get_form(self, form_class=None):
        """Customize form to set address queryset and mark checked products."""
        form = super().get_form(form_class)

        # Mark products that are already in the subscription as checked
        form.checked_products = list(self.subscription_products.values_list('product_id', flat=True))

        # Create a method to get bound values for each product
        def bound_product_values(product_id):
            try:
                sp = self.subscription_products.get(product_id=product_id)
                return {
                    'address': sp.address_id,
                    'copies': sp.copies,
                    'message': sp.label_message or '',
                    'instructions': sp.special_instructions or '',
                }
            except SubscriptionProduct.DoesNotExist:
                return {
                    'address': None,
                    'copies': 1,
                    'message': '',
                    'instructions': '',
                }

        form.bound_product_values = bound_product_values

        return form

    def get_form_kwargs(self):
        """Pass the contact to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['contact'] = self.contact
        return kwargs

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
        """Process the form and update subscription."""
        # Update contact data if necessary
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

        # Update subscription dates
        self.subscription.start_date = form.cleaned_data["start_date"]
        self.subscription.end_date = form.cleaned_data["end_date"]
        self.subscription.save()

        # Get currently selected products from POST
        selected_product_ids = set()
        for key in self.request.POST.keys():
            if key.startswith("check-"):
                product_id = int(key.split("-")[1])
                selected_product_ids.add(product_id)

        # Get existing subscription products
        existing_product_ids = set(self.subscription_products.values_list('product_id', flat=True))

        # Remove products that are no longer selected
        products_to_remove = existing_product_ids - selected_product_ids
        if products_to_remove:
            SubscriptionProduct.objects.filter(
                subscription=self.subscription, product_id__in=products_to_remove
            ).delete()

        # Add or update products
        for product_id in selected_product_ids:
            product = Product.objects.get(pk=product_id)
            address_id = self.request.POST.get("address-{}".format(product_id))
            address = Address.objects.get(pk=address_id)
            copies = self.request.POST.get("copies-{}".format(product_id))
            label_message = self.request.POST.get("message-{}".format(product_id))
            special_instructions = self.request.POST.get("instruction-{}".format(product_id))

            # Update existing or create new
            if product_id in existing_product_ids:
                sp = SubscriptionProduct.objects.get(subscription=self.subscription, product_id=product_id)
                sp.address = address
                sp.copies = copies
                sp.label_message = label_message
                sp.special_instructions = special_instructions
                sp.save()
            else:
                # Add new product to subscription
                self.subscription.add_product(
                    product=product,
                    address=address,
                    copies=copies,
                    message=label_message,
                    instructions=special_instructions,
                    seller_id=self.subscription.seller_id if hasattr(self.subscription, 'seller_id') else None,
                )

        messages.success(self.request, _("Promotional subscription updated successfully"))

        if self.url:
            if self.offset:
                return HttpResponseRedirect("{}?offset={}".format(self.url, self.offset))
            else:
                return HttpResponseRedirect(self.url)
        else:
            return HttpResponseRedirect(reverse('contact_detail', args=[self.contact.id]))

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "contact": self.contact,
                "address_form": NewAddressForm(initial={"address_type": "physical"}),
                "offerable_products": self.offerable_products,
                "contact_addresses": self.contact_addresses,
                "subscription": self.subscription,
                "is_update": True,  # Flag to indicate this is an update operation
            }
        )
        return context


# Backward compatibility
update_promo = UpdatePromoView.as_view()


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


class AffiliateSubscriptionCreateView(LoginRequiredMixin, BreadcrumbsMixin, CreateView):
    template_name = "subscriptions/affiliate_subscriptions.html"
    form_class = AffiliateSubscriptionForm

    def breadcrumbs(self):
        return [
            {"label": "Inicio", "url": reverse("home")},
            {"label": "Lista de contactos", "url": reverse("contact_list")},
            {
                "label": self.corporate_subscription.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.corporate_subscription.contact.id]),
            },
            {"label": "Crear suscripción afiliada", "url": ""},
        ]

    def dispatch(self, request, *args, **kwargs):
        self.corporate_subscription = get_object_or_404(Subscription, id=kwargs['subscription_id'])
        self.product = self.corporate_subscription.products.first()

        # Ensure the subscription is corporate
        if self.corporate_subscription.type != "C":
            messages.error(request, "Esta suscripción no es corporativa")
            return HttpResponseRedirect(reverse("contact_detail", args=[self.corporate_subscription.contact.id]))

        # Check the affiliate limit
        current_affiliates = (
            Subscription.objects.filter(parent_subscription=self.corporate_subscription).count() + 1
        )  # Include the parent subscription
        if current_affiliates >= self.corporate_subscription.number_of_subscriptions:
            messages.error(request, "Ya se ha alcanzado el límite de suscripciones afiliadas")
            return HttpResponseRedirect(reverse("contact_detail", args=[self.corporate_subscription.contact.id]))

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Set parent subscription and corporate flag before saving."""
        if form.instance.contact == self.corporate_subscription.contact:
            messages.error(self.request, "El contacto seleccionado no puede ser el mismo que el contacto principal")
            return self.form_invalid(form)
        if form.instance.contact.subscriptions.filter(type="A", active=True).exists():
            messages.error(self.request, "El contacto seleccionado ya tiene una suscripción afiliada activa")
            return self.form_invalid(form)
        form.instance.parent_subscription = self.corporate_subscription
        form.instance.type = "A"  # Affiliate
        response = super().form_valid(form)
        form.instance.add_product(product=self.product, address=None, copies=1, message=None, instructions=None)
        messages.success(self.request, "Suscripción afiliada creada exitosamente")
        return response

    def get_context_data(self, **kwargs):
        """Add subscription details to the template context."""
        context = super().get_context_data(**kwargs)
        current_affiliates = Subscription.objects.filter(parent_subscription=self.corporate_subscription).count() + 1
        affiliate_subscriptions = Subscription.objects.filter(
            parent_subscription=self.corporate_subscription,
            type="A",
            active=True,
        )
        context.update(
            {
                'corporate_subscription': self.corporate_subscription,
                'current_affiliates': current_affiliates,
                'available_slots': self.corporate_subscription.number_of_subscriptions - current_affiliates,
                'affiliate_subscriptions': affiliate_subscriptions,
            }
        )
        return context

    def get_initial(self):
        initial = super().get_initial()
        start_date = now().date()
        end_date = start_date + relativedelta(months=self.product.duration_months)
        initial['start_date'] = start_date.strftime("%Y-%m-%d")
        initial['end_date'] = end_date.strftime("%Y-%m-%d")
        return initial

    def get_success_url(self):
        return reverse("add_affiliate_subscription", args=[self.corporate_subscription.id])


class FreeSubscriptionMixin:
    """
    Mixin for shared functionality between CreateFreeSubscriptionView and UpdateFreeSubscriptionView.
    Handles common logic for free subscription management.
    """

    def test_func(self):
        """Check if user has permission to add free subscriptions."""
        return self.request.user.has_perm('core.can_add_free_subscription')

    def get_form_kwargs(self):
        """Pass the contact to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['contact'] = self.contact
        return kwargs

    def update_contact_data(self, form):
        """Update contact information if changed."""
        changed = False
        for attr in ("name", "last_name", "phone", "mobile", "email", "notes"):
            val = form.cleaned_data.get(attr)
            if getattr(self.contact, attr) != val:
                changed = True
                setattr(self.contact, attr, val)

        if changed:
            try:
                self.contact.save()
            except forms.ValidationError as ve:
                form.add_error(None, ve)
                return False
        return True

    def add_products_to_subscription(self, subscription):
        """Add products to the subscription based on POST data."""
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
                )


class CreateFreeSubscriptionView(FreeSubscriptionMixin, BreadcrumbsMixin, FormView):
    """
    View for managers to create free subscriptions for contacts.
    Requires can_add_free_subscription permission.
    """

    template_name = "free_subscription_form.html"
    form_class = FreeSubscriptionForm

    def dispatch(self, request, *args, **kwargs):
        """Initialize view-level variables from URL parameters."""
        self.contact = get_object_or_404(Contact, pk=kwargs['contact_id'])
        self.contact_addresses = Address.objects.filter(contact=self.contact)
        self.offerable_products = Product.objects.filter(offerable=True, type="S")
        return super().dispatch(request, *args, **kwargs)

    def breadcrumbs(self):
        """Return breadcrumbs for navigation."""
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {
                "label": self.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.contact.id]),
            },
            {"label": _("Create free subscription"), "url": ""},
        ]

    def get_initial(self):
        """Set initial form data."""
        start_date = date.today()
        end_date = add_business_days(date.today(), 5)

        return {
            "name": self.contact.name,
            "last_name": self.contact.last_name,
            "phone": self.contact.phone,
            "mobile": self.contact.mobile,
            "email": self.contact.email,
            "notes": self.contact.notes,
            "start_date": start_date,
            "end_date": end_date,
        }

    def form_valid(self, form):
        """Process the form and create free subscription."""
        # Update contact data if necessary
        if not self.update_contact_data(form):
            return self.form_invalid(form)

        # Create the free subscription
        start_date = form.cleaned_data["start_date"]
        end_date = form.cleaned_data["end_date"]
        free_subscription_requested_by = form.cleaned_data["free_subscription_requested_by"]

        subscription = Subscription.objects.create(
            contact=self.contact,
            type="F",  # Free subscription
            start_date=start_date,
            end_date=end_date,
            free_subscription_requested_by=free_subscription_requested_by,
        )

        # Add products to subscription
        self.add_products_to_subscription(subscription)

        messages.success(
            self.request,
            _("Free subscription created successfully for {contact}").format(contact=self.contact.get_full_name()),
        )

        return HttpResponseRedirect(reverse("contact_detail", args=[self.contact.id]))

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "contact": self.contact,
                "address_form": NewAddressForm(initial={"address_type": "physical"}),
                "offerable_products": self.offerable_products,
                "contact_addresses": self.contact_addresses,
                "is_update": False,
            }
        )
        return context


class UpdateFreeSubscriptionView(FreeSubscriptionMixin, BreadcrumbsMixin, FormView):
    """
    View for managers to update existing free subscriptions.
    Requires can_add_free_subscription permission.
    Uses FormView instead of UpdateView since FreeSubscriptionForm is not a ModelForm.
    """

    template_name = "free_subscription_form.html"
    form_class = FreeSubscriptionForm

    def dispatch(self, request, *args, **kwargs):
        """Initialize view-level variables."""
        self.subscription = get_object_or_404(Subscription, pk=kwargs['subscription_id'])
        self.contact = self.subscription.contact
        self.contact_addresses = Address.objects.filter(contact=self.contact)
        self.offerable_products = Product.objects.filter(offerable=True, type="S")
        return super().dispatch(request, *args, **kwargs)

    def breadcrumbs(self):
        """Return breadcrumbs for navigation."""
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Contact list"), "url": reverse("contact_list")},
            {
                "label": self.contact.get_full_name(),
                "url": reverse("contact_detail", args=[self.contact.id]),
            },
            {"label": _("Update free subscription"), "url": ""},
        ]

    def get_initial(self):
        """Set initial form data from subscription."""
        return {
            "name": self.contact.name,
            "last_name": self.contact.last_name,
            "phone": self.contact.phone,
            "mobile": self.contact.mobile,
            "email": self.contact.email,
            "notes": self.contact.notes,
            "start_date": self.subscription.start_date,
            "end_date": self.subscription.end_date,
            "free_subscription_requested_by": self.subscription.free_subscription_requested_by,
        }

    def form_valid(self, form):
        """Process the form and update subscription."""
        # Update contact data if necessary
        if not self.update_contact_data(form):
            return self.form_invalid(form)

        # Update subscription fields
        self.subscription.start_date = form.cleaned_data["start_date"]
        self.subscription.end_date = form.cleaned_data["end_date"]
        self.subscription.free_subscription_requested_by = form.cleaned_data["free_subscription_requested_by"]
        self.subscription.save()

        messages.success(
            self.request,
            _("Free subscription updated successfully for {contact}").format(contact=self.contact.get_full_name()),
        )

        return HttpResponseRedirect(reverse("contact_detail", args=[self.contact.id]))

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)

        # Get existing subscription products
        existing_products = SubscriptionProduct.objects.filter(subscription=self.subscription)

        context.update(
            {
                "contact": self.contact,
                "address_form": NewAddressForm(initial={"address_type": "physical"}),
                "offerable_products": self.offerable_products,
                "contact_addresses": self.contact_addresses,
                "subscription": self.subscription,
                "existing_products": existing_products,
                "is_update": True,
            }
        )
        return context


# Backward compatibility
create_free_subscription = CreateFreeSubscriptionView.as_view()
update_free_subscription = UpdateFreeSubscriptionView.as_view()
