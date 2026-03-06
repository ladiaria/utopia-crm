# coding=utf-8
from django.db.models import TextChoices, IntegerChoices
from django.conf import settings
from django.utils.translation import gettext_lazy as _


ADDRESS_TYPE_CHOICES = (("digital", _("Digital")), ("physical", _("Physical")))

EDUCATION_CHOICES = (
    (1, _("Primary")),
    (2, _("Incomplete secondary")),
    (3, _("Complete secondary")),
    (4, _("Incomplete university")),
    (5, _("Complete university")),
    (6, _("Postgraduate")),
    (100, _("Doesn't want to inform")),
)

FREQUENCY_CHOICES = ((1, _("Monthly")), (3, _("Quarterly")), (6, _("Biannual")), (12, _("Annual")))

PRODUCT_BILLING_FREQUENCY_CHOICES = (
    (30, _("Monthly")),
    (90, _("Quarterly")),
    (365, _("Annual")),
    (730, _("Biannual")),
    (0, _("One-shot")),
)

PRODUCT_RENEWAL_TYPE_CHOICES = (
    ("N", _("New")),
    ("A", _("Automatic")),
    ("R", _("Renewal")),
)

SUBSCRIPTION_TYPE_CHOICES = (
    ("P", _("Promotion")),
    ("N", _("Normal")),
    ("F", _("Gift")),
    ("S", _("Staff")),
    ("C", _("Corporate")),
    ("A", _("Affiliate")),
)

SUBSCRIPTION_STATUS_CHOICES = (
    ("AP", _("Awaiting payment")),
    ("NC", _("Not consolidated")),
    ("OK", _("Normal")),
    ("PA", _("Paused")),
    ("DE", _("End because of debt")),
    ("NE", _("Normal end")),
    ("ER", _("Error")),
)

GENDERS = (
    ("M", _("Male")),
    ("F", _("Female")),
    ("O", _("Other")),
)

VARIABLE_TYPES = (
    ("impresion", _("Impression")),
    ("impresion_fs", _("Imperssion Weekend")),
)

PRIORITY_CHOICES = (
    (1, _("Highest")),
    (2, _("High")),
    (3, _("Normal")),
    (4, _("Low")),
    (5, _("Lowest")),
)

PRODUCTHISTORY_CHOICES = (
    ("A", _("Active")),
    ("I", _("Inactive")),
    ("P", _("Paused")),
    ("R", _("Resumed")),
)


class ACTIVITY_STATUS(TextChoices):
    PENDING = "P", _("Pending")
    COMPLETED = "C", _("Completed")
    DELAYED = "D", _("Delayed")
    EXPIRED = "E", _("Expired")


# Legacy tuple for backward compatibility - will be removed eventually
ACTIVITY_STATUS_CHOICES = (
    ("P", _("Pending")),
    ("C", _("Completed")),
    ("D", _("Delayed")),
    ("E", _("Expired")),
)

ACTIVITY_DIRECTION_CHOICES = (
    ("I", _("In")),
    ("O", _("Out")),
    ("N", _("Internal")),
    ("R", _("Renewal")),
)


class CAMPAIGN_STATUS(IntegerChoices):
    NOT_YET_CONTACTED = 1, _("Not yet contacted")
    CONTACTED = 2, _("Contacted")
    CALLED_COULD_NOT_CONTACT = 3, _("Called, could not contact")
    ENDED_WITH_CONTACT = 4, _("Ended with contact")
    ENDED_WITHOUT_CONTACT = 5, _("Ended without contact")
    SWITCH_TO_MORNING = 6, _("Switch to morning")
    SWITCH_TO_AFTERNOON = 7, _("Switch to afternoon/evening")


CAMPAIGN_RESOLUTION_CHOICES = (
    ("SP", _("Started promotion")),
    ("AS", _("Already a subscriber")),
    ("DN", _("Do not call anymore")),
    ("EP", _("Error in promotion")),
    ("LO", _("Logistics")),
    ("NI", _("Not interested")),
    ("S1", _("Success with promotion")),
    ("S2", _("Success with direct sale")),
    ("SC", _("Scheduled")),
    ("CL", _("Call later")),
    ("NF", _("Not found")),
    ("UN", _("Cannot find contact")),
    ("CW", _("Close without contact")),
)

CAMPAIGN_RESOLUTION_REASONS_CHOICES = getattr(settings, "CAMPAIGN_RESOLUTION_REASONS_CHOICES", ())

DEFAULT_ACTIVITY_TYPES = (
    ("S", _("Campaign start")),
    ("C", _("Call")),
    ("M", _("E-mail")),
    ("L", _("Link hit")),
    ("W", _("WhatsApp message or other apps")),
    ("E", _("Event participation")),
    ("I", _("In-place visit")),
)


def get_activity_types():
    """
    Returns activity types with 'Internal' (N) always included as a required system type.

    The 'Internal' type is used for system-generated activities (unsubscriptions,
    reactivations, etc.) and must always be available regardless of custom activity types.
    """
    # Internal activity type - required by the system for automated activities
    internal_type = ("N", _("Internal"))

    # Get custom types or use defaults
    custom_types = getattr(settings, "CUSTOM_ACTIVITY_TYPES", DEFAULT_ACTIVITY_TYPES)

    # Always ensure Internal type is included
    if internal_type not in custom_types:
        return custom_types + (internal_type,)
    return custom_types


PRODUCT_WEEKDAYS = (
    (1, _("Monday")),
    (2, _("Tuesday")),
    (3, _("Wednesday")),
    (4, _("Thursday")),
    (5, _("Friday")),
    (6, _("Saturday")),
    (7, _("Sunday")),
    (8, _("All week")),
    (9, _("Weekdays")),
    (10, _("Weekends")),
)

PRODUCT_EDITION_FREQUENCY = (
    (1, _("Daily")),
    (2, _("Weekly")),
    (3, _("Monthly")),
    (4, _("One-shot")),
    (5, _("Others")),
)

PRICERULE_MODE_CHOICES = (
    (1, _("Replace all")),
    (2, _("Replace one")),
    (3, _("Add new")),
)

PRICERULE_WILDCARD_MODE_CHOICES = (("pool_and_any", _("Pool AND Any")), ("pool_or_any", _("Pool OR Any")))

PRICERULE_AMOUNT_TO_PICK_CONDITION_CHOICES = (("eq", _("Equal than")), ("gt", _("Greater than")))

DYNAMIC_CONTACT_FILTER_MODES = [
    (1, _("At least one of the products")),
    (2, _("All products")),
    (3, "Newsletters"),
]

ENVELOPE_CHOICES = (
    (1, _("Paid envelope")),
    (2, _("Free envelope")),
)

DEBTOR_CONCACTS_CHOICES = (
    (1, _("Exclude debtors")),
    (2, _("Only debtors")),
)

DISCOUNT_VALUE_MODE_CHOICES = (
    (1, _("Integer")),
    (2, _("Percentage")),
)

DISCOUNT_PRODUCT_MODE_CHOICES = (
    (1, _("Find at least one product")),
    (2, _("Find all products")),
)

EMAIL_REPLACEMENT_STATUS_CHOICES = (
    ("suggested", _("Suggested")),
    ("requested", _("Requested")),
    ("approved", _("Approved")),
    ("rejected", _("Rejected")),
)

EMAIL_BOUNCE_ACTION_INVALID = 1
EMAIL_BOUNCE_ACTION_MAXREACH = 2
EMAIL_BOUNCE_ACTIONLOG_CHOICES = (
    (EMAIL_BOUNCE_ACTION_INVALID, _("invalid email")),
    (EMAIL_BOUNCE_ACTION_MAXREACH, _("max bounce reached")),
)


class FreeSubscriptionRequestedBy(TextChoices):
    HR = "HR", _("Human resources")
    ADVERTISEMENT = "AD", _("Advertisement")
    MANAGEMENT = "MA", _("Management")
    NEWSROOM = "JD", _("Newsroom")
    PROMOTION = "PR", _("Promotion")
