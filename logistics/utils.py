# coding=utf-8
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from support.models import Issue, IssueSubcategory, IssueStatus


def create_issue_for_special_route(subscription, route_number, user=None, custom_notes=None):
    """
    Creates an Issue when a subscription product is changed to a special route (50-55).

    Args:
        subscription: The Subscription object
        route_number: The route number that was assigned
        user: The user who made the change (optional, will be set as manager)
        custom_notes: Custom notes for the issue (optional, uses automatic message if not provided)

    Returns:
        Issue object if created, None otherwise
    """
    # Only create issue for special routes (50-55 inclusive)
    if route_number not in range(50, 56):
        return None

    try:
        # Get the subcategory from settings
        subcategory_slug = getattr(settings, 'ISSUE_SUBCATEGORY_NOT_DELIVERED', 'not-delivered')
        subcategory = IssueSubcategory.objects.get(slug=subcategory_slug)
    except IssueSubcategory.DoesNotExist:
        # If subcategory doesn't exist, we can't create the issue
        return None

    try:
        # Get the status from settings
        status_slug = getattr(settings, 'ISSUE_STATUS_UNASSIGNED', 'unassigned')
        status = IssueStatus.objects.get(slug=status_slug)
    except IssueStatus.DoesNotExist:
        # If status doesn't exist, we can't create the issue
        return None

    # Use custom notes if provided, otherwise use automatic message
    if custom_notes and custom_notes.strip():
        notes = custom_notes.strip()
    else:
        notes = _("Generated automatically for change of route to special route (route {})").format(route_number)

    # Create the issue
    issue = Issue.objects.create(
        contact=subscription.contact,
        subscription=subscription,
        category="L",  # Logistics category
        sub_category=subcategory,
        status=status,
        manager=user,
        assigned_to=None,  # Not assigned to anyone
        notes=notes,
    )

    return issue
