# coding=utf-8
"""
The email takeover queue as a screen: where the requests operators file get resolved.

Access is gated by ``core.can_takeover_email``. That permission is the whole point of the queue --
approving a request can delete a web account, so it is deliberately not something the operator who
filed it can do.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView

from core.email_takeover_queue import (
    RESOLVED,
    UNREACHABLE,
    approve_takeover,
    enqueue_takeover,
    preview_takeover,
    reject_takeover,
    takeover_queue_enabled,
)
from core.mixins import BreadcrumbsMixin
from core.models import Contact, EmailTakeoverRequest


class TakeoverOnDemandForm(forms.Form):
    """Start a takeover without an operator having filed it -- the manual case."""

    contact = forms.IntegerField(label=_("Contact ID"), min_value=1)
    email = forms.EmailField(label=_("Email to take over"))

    def clean_contact(self):
        contact_id = self.cleaned_data["contact"]
        try:
            return Contact.objects.get(pk=contact_id)
        except Contact.DoesNotExist:
            raise forms.ValidationError(_("There is no contact with id %(id)s") % {"id": contact_id})


class EmailTakeoverQueueView(LoginRequiredMixin, PermissionRequiredMixin, BreadcrumbsMixin, ListView):
    """Pending requests with the preview the CMS gave when each was filed, plus recent history."""

    permission_required = "core.can_takeover_email"
    model = EmailTakeoverRequest
    template_name = "email_takeovers/queue.html"
    context_object_name = "pending_requests"

    def breadcrumbs(self):
        return [
            {"url": reverse("home"), "label": _("Home")},
            {"label": _("Email takeovers"), "url": ""},
        ]

    def get_queryset(self):
        return (
            EmailTakeoverRequest.objects.filter(status=EmailTakeoverRequest.PENDING)
            .select_related("contact", "requested_by")
            .order_by("created_at")  # oldest first: the person has been waiting the longest
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resolved_requests"] = (
            EmailTakeoverRequest.objects.exclude(status=EmailTakeoverRequest.PENDING)
            .select_related("contact", "resolved_by")[:25]
        )
        context["on_demand_form"] = TakeoverOnDemandForm()
        context["takeover_enabled"] = takeover_queue_enabled()
        return context


class EmailTakeoverResolveView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """
    Approve or reject one request. POST only -- nothing here is safe to trigger with a link.

    Approving re-asks the CMS instead of trusting the stored preview, so a request that became
    unsafe since it was filed is refused now rather than executed on stale information.
    """

    permission_required = "core.can_takeover_email"

    def post(self, request, pk, *args, **kwargs):
        takeover_request = get_object_or_404(EmailTakeoverRequest, pk=pk)
        note = request.POST.get("resolution_note", "").strip()

        if request.POST.get("action") == "approve":
            outcome, msg = approve_takeover(takeover_request, user=request.user, note=note)
        else:
            outcome, msg = reject_takeover(takeover_request, user=request.user, note=note)

        if outcome == RESOLVED:
            messages.success(request, msg)
        elif outcome == UNREACHABLE:
            messages.warning(request, msg)
        else:
            messages.error(request, msg)
        return redirect("email_takeover_queue")

    def get(self, request, *args, **kwargs):
        return redirect("email_takeover_queue")


class EmailTakeoverOnDemandView(LoginRequiredMixin, PermissionRequiredMixin, BreadcrumbsMixin, FormView):
    """
    Takeover for a contact nobody filed a request for: the reviewer previews it, then executes.

    Executing files the request and approves it in one go, so a manual takeover leaves the same
    audit trail as one that came through the queue -- who asked, who approved, and the preview it
    was decided on.
    """

    permission_required = "core.can_takeover_email"
    form_class = TakeoverOnDemandForm
    template_name = "email_takeovers/on_demand.html"

    def breadcrumbs(self):
        return [
            {"url": reverse("home"), "label": _("Home")},
            {"label": _("Email takeovers"), "url": reverse("email_takeover_queue")},
            {"label": _("On demand"), "url": ""},
        ]

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("contact"):
            initial["contact"] = self.request.GET["contact"]
        return initial

    def form_valid(self, form):
        contact, email = form.cleaned_data["contact"], form.cleaned_data["email"]

        if not takeover_queue_enabled():
            messages.error(self.request, _("Email takeovers are disabled."))
            return self.form_invalid(form)

        preview = preview_takeover(contact.id, email)
        if preview in ("TIMEOUT", "ERROR") or not isinstance(preview, dict):
            messages.warning(self.request, _("The web did not answer. Try again."))
            return self.form_invalid(form)

        if preview.get("retval") != 1:
            messages.error(self.request, preview.get("msg") or _("The web refused the takeover."))
            return self.form_invalid(form)

        if self.request.POST.get("action") != "execute":
            # First pass: show what would happen and let them decide.
            return self.render_to_response(
                self.get_context_data(form=form, preview=preview.get("detail") or {}, contact=contact, email=email)
            )

        takeover_request = enqueue_takeover(
            contact,
            email,
            preview.get("detail"),
            origin=EmailTakeoverRequest.ORIGIN_OTHER,
            requested_by=self.request.user,
        )
        if not takeover_request:
            messages.error(self.request, _("The request could not be filed."))
            return self.form_invalid(form)

        outcome, msg = approve_takeover(takeover_request, user=self.request.user)
        if outcome == RESOLVED:
            messages.success(self.request, msg)
            return redirect("contact_detail", takeover_request.contact_id)
        messages.error(self.request, msg)
        return self.form_invalid(form)
