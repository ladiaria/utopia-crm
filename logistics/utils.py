# coding=utf-8
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from support.models import Issue, IssueSubcategory, IssueStatus


def create_issue_for_special_route(subscription, route_number=None, user=None, custom_notes=None, route_numbers=None):
    """
    Creates an Issue when a subscription product is changed to a special route (50-55).

    Can be called with a single route_number (original behavior) or with a list of
    route_numbers to create a single issue covering multiple route changes.

    Args:
        subscription: The Subscription object
        route_number: A single route number (for backward compatibility)
        user: The user who made the change (optional, will be set as manager)
        custom_notes: Custom notes for the issue (optional, uses automatic message if not provided)
        route_numbers: A list of route numbers to create a single issue for multiple changes

    Returns:
        Issue object if created, None otherwise
    """
    # Build the list of special route numbers to include in the issue
    if route_numbers is not None:
        special_routes = [r for r in route_numbers if r in range(50, 56)]
    elif route_number is not None:
        if route_number not in range(50, 56):
            return None
        special_routes = [route_number]
    else:
        return None

    if not special_routes:
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
        unique_routes = sorted(set(special_routes))
        route_str = ", ".join(str(r) for r in unique_routes)
        if len(unique_routes) == 1:
            notes = _("Generated automatically for change of route to special route (route {})").format(route_str)
        else:
            notes = _("Generated automatically for change of routes to special routes ({})").format(route_str)

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
