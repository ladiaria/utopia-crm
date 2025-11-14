import csv
import io

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from core.mixins import BreadcrumbsMixin
from core.models import ContactCampaignStatus
from core.utils import detect_csv_delimiter
from support.forms import BulkDeleteCampaignStatusForm


class BulkDeleteCampaignStatusView(BreadcrumbsMixin, UserPassesTestMixin, FormView):
    """
    View for bulk deleting ContactCampaignStatus records.

    Allows managers to upload a CSV file with contact IDs and select a campaign.
    All ContactCampaignStatus records matching the contact IDs and campaign will be deleted.

    Access: Only users in the 'Managers' group can access this view.
    """

    template_name = 'campaign_management/bulk_delete_campaign_status.html'
    form_class = BulkDeleteCampaignStatusForm
    success_url = reverse_lazy('bulk_delete_campaign_status')

    def test_func(self):
        """Only users in the Managers group can access this view."""
        return self.request.user.groups.filter(name='Managers').exists()

    def breadcrumbs(self):
        return [
            {"url": reverse("home"), "label": _("Home")},
            {"label": _("Bulk Delete Campaign Status"), "url": reverse("bulk_delete_campaign_status")},
        ]

    def get(self, request, *args, **kwargs):
        """Handle GET requests, including CSV template download."""
        if request.GET.get('download_template'):
            return self.download_template()
        return super().get(request, *args, **kwargs)

    def download_template(self):
        """Generate and return a CSV template file."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bulk_delete_campaign_status_template.csv"'

        writer = csv.writer(response)
        writer.writerow(['contact_id'])
        writer.writerow(['123'])
        writer.writerow(['456'])
        writer.writerow(['789'])

        return response

    def form_valid(self, form):
        """Process the form and delete ContactCampaignStatus records."""
        csv_file = form.cleaned_data['csv_file']
        campaign = form.cleaned_data['campaign']

        # Read CSV file
        file_content = io.StringIO(csv_file.read().decode('utf-8'))

        # Detect delimiter automatically
        delimiter = detect_csv_delimiter(file_content)

        # Parse contact IDs from CSV
        contact_ids = []
        csv_reader = csv.DictReader(file_content, delimiter=delimiter)

        # Try to find the contact_id column (case-insensitive)
        for row in csv_reader:
            # Look for common column names
            contact_id = None
            for key in row.keys():
                if key.lower().strip() in ['contact_id', 'id', 'contact id', 'contactid']:
                    try:
                        contact_id = int(row[key].strip())
                        contact_ids.append(contact_id)
                        break
                    except (ValueError, AttributeError):
                        continue

            if contact_id is None:
                messages.warning(
                    self.request,
                    _(
                        "Could not find contact_id column in CSV. Expected column names: "
                        "'contact_id', 'id', 'contact id', or 'contactid'"
                    ),
                )
                return redirect(self.success_url)

        if not contact_ids:
            messages.warning(self.request, _("No valid contact IDs found in the CSV file."))
            return redirect(self.success_url)

        # Delete ContactCampaignStatus records
        with transaction.atomic():
            deleted_count, _unused = ContactCampaignStatus.objects.filter(
                contact_id__in=contact_ids, campaign=campaign
            ).delete()

        # Show success message
        messages.success(
            self.request,
            _(
                "Successfully deleted {count} ContactCampaignStatus record(s) for campaign "
                "'{campaign}' with {total} contact ID(s) from CSV."
            ).format(count=deleted_count, campaign=campaign.name, total=len(contact_ids)),
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        messages.error(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


bulk_delete_campaign_status = BulkDeleteCampaignStatusView.as_view()
