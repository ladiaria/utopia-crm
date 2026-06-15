from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Max, Min
from django.http import QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import View

from core.mixins import BreadcrumbsMixin
from support.filters import IssueFilter
from support.models import Issue, IssueStatus


class BulkReassignIssueStatusView(BreadcrumbsMixin, UserPassesTestMixin, View):
    """
    Bulk reassign the status of several issues at once, coming from the issue
    list (`list_issues`).

    Two selection modes, both resolved server-side (the client never decides the
    final set of affected issues):

    - ``ids``: an explicit list of issue ids checked in the list.
    - ``filter``: the whole queryset matching the original filter. The original
      filter querystring is replayed through ``IssueFilter``, exactly like the
      CSV export does, so "the whole filter" always matches what the user saw.

    The flow has two steps. The first POST (without ``confirmed``) renders a
    confirmation screen showing how many issues will change and the origin ->
    destination breakdown. The second POST (``confirmed=1``) applies the change
    inside a transaction and logs each modification.

    Access is restricted to superusers and members of the ``Admins`` group.
    """

    template_name = "bulk_reassign_issue_status_confirm.html"

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Admins").exists()

    def breadcrumbs(self):
        return [
            {"url": reverse("home"), "label": _("Home")},
            {"url": reverse("list_issues"), "label": _("Issues")},
            {"label": _("Bulk reassign status")},
        ]

    def get_filtered_queryset(self, filter_querystring):
        """Rebuild the filtered queryset from the original filter querystring."""
        data = QueryDict(filter_querystring)
        return IssueFilter(data, queryset=Issue.objects.all()).qs

    def get_target_queryset(self, mode, ids, filter_querystring):
        if mode == "filter":
            return self.get_filtered_queryset(filter_querystring)
        return Issue.objects.filter(id__in=ids)

    def list_url_with_filter(self, filter_querystring):
        base = reverse("list_issues")
        return f"{base}?{filter_querystring}" if filter_querystring else base

    def filter_is_narrow_enough(self, filter_querystring):
        """Whole-filter mode requires both a status and a subcategory selected."""
        data = QueryDict(filter_querystring)
        return bool(data.get("status")) and bool(data.get("sub_category"))

    def post(self, request, *args, **kwargs):
        mode = request.POST.get("mode", "ids")
        filter_querystring = request.POST.get("filter_querystring", "")
        ids = request.POST.getlist("issue_ids")
        new_status_id = request.POST.get("new_status")

        # Validate destination status against the DB (never trust the POST).
        new_status = IssueStatus.objects.filter(pk=new_status_id).first()
        if not new_status:
            messages.error(request, _("You must select a valid destination status."))
            return redirect(self.list_url_with_filter(filter_querystring))

        # Guardrail for the whole-filter mode: require both a status and a
        # subcategory in the filter so nobody can reassign every single issue at
        # once. Enforced here too (not only in the UI) so it can't be bypassed.
        if mode == "filter" and not self.filter_is_narrow_enough(filter_querystring):
            messages.error(
                request,
                _(
                    "To reassign the whole filter you must select at least a status and a "
                    "subcategory in the filter."
                ),
            )
            return redirect(self.list_url_with_filter(filter_querystring))

        queryset = self.get_target_queryset(mode, ids, filter_querystring)

        if mode == "ids" and not ids:
            messages.warning(request, _("No issues were selected."))
            return redirect(self.list_url_with_filter(filter_querystring))

        if not queryset.exists():
            messages.warning(request, _("No issues matched the selection."))
            return redirect(self.list_url_with_filter(filter_querystring))

        # Step 1: show the confirmation screen.
        if not request.POST.get("confirmed"):
            origin_breakdown = (
                queryset.values("status__name").annotate(total=Count("id")).order_by("-total")
            )
            date_range = queryset.aggregate(oldest=Min("date"), newest=Max("date"))
            context = {
                "count": queryset.count(),
                "new_status": new_status,
                "origin_breakdown": origin_breakdown,
                "oldest_date": date_range["oldest"],
                "newest_date": date_range["newest"],
                "mode": mode,
                "filter_querystring": filter_querystring,
                "issue_ids": ids,
                "new_status_id": new_status.pk,
                "list_url": self.list_url_with_filter(filter_querystring),
                "breadcrumbs": self.breadcrumbs(),
            }
            return render(request, self.template_name, context)

        # Step 2: apply the change.
        affected = self.apply_changes(request, queryset, new_status)
        messages.success(
            request,
            _("Status changed to '{status}' for {count} issue(s).").format(
                status=new_status.name, count=affected
            ),
        )
        return redirect(self.list_url_with_filter(filter_querystring))

    def apply_changes(self, request, queryset, new_status):
        issue_content_type = ContentType.objects.get_for_model(Issue)
        affected = 0

        with transaction.atomic():
            # Lock and iterate; apply_status_change derives next_action_date /
            # closing_date per issue, so we save each instance individually.
            # Lock only the Issue rows (of="self"); status/contact are nullable
            # FKs and a plain FOR UPDATE over their outer joins is unsupported.
            locked = queryset.select_related("status", "contact").select_for_update(of=("self",))
            for issue in locked:
                old_status_name = issue.status.name if issue.status else "-"
                changed_fields = issue.apply_status_change(new_status)
                issue.save(update_fields=changed_fields)
                affected += 1

                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=issue_content_type.pk,
                    object_id=issue.pk,
                    object_repr=str(issue),
                    action_flag=CHANGE,
                    change_message=_(
                        "Bulk status reassign by {user}: '{old}' -> '{new}'"
                    ).format(user=request.user.username, old=old_status_name, new=new_status.name),
                )

        return affected


bulk_reassign_issue_status = BulkReassignIssueStatusView.as_view()
