# coding=utf-8
from django.utils.translation import ugettext_lazy as _

SCHEDULED_TASK_CATEGORIES = (
    ('AC', _('Address change')),
    ('PD', _('Start of pause')),
    ('PA', _('End of pause')),
    ('PS', _('Start of partial pause')),
    ('PE', _('End of partial pause')),
)


ISSUE_CATEGORIES = (
    ('L', _('Logistics')),
    ('I', _('Invoicing')),
    ('M', _('Collections')),
    ('C', _('Contents')),
    ('W', _('Web')),
    ('S', _('Service')),
    ('O', _('Community')),
)

ISSUE_SUBCATEGORIES = (
    # Logistics
    ('L01', _('Did not arrive')),
    ('L02', _('Arrived late')),
    ('L03', _('Arrived wet')),
    ('L04', _('Changed delivery place')),
    ('L05', _('Not delivered')),
    ('L06', _('Delivered to a wrong place')),
    ('L07', _('Wrong label')),
    ('L08', _('Wrong invoice delivered')),
    ('L10', _('Paused route')),
    ('L11', _('Invoice wasn\'t delivered')),
    ('L99', _('Uncategorized logistics issue')),
    # Invoicing
    ('I01', _('Product doesn\'t belong')),
    ('I02', _('Price issue')),
    ('I03', _('Payment type issue')),
    ('I04', _('Subscription not being billed')),
    ('I05', _('Payment type change')),
    ('I06', _('Collection issue')),
    ('I07', _('Collection issue (inactive subscription)')),
    ('I08', _('Credit card expiration')),
    ('I09', _('Debt issue')),
    ('I99', _('Uncategorized invoicing issue')),
    # Contents
    ('C01', _('Suggestions')),
    ('C02', _('Complaints')),
    ('C03', _('Corrections')),
    ('C04', _('Requests')),
    ('C05', _('Contact journalist')),
    ('C06', _('Forward content')),
    # Web
    ('W01', _('Access (sign-in)')),
    ('W02', _('Registry (sign-up)')),
    ('W03', _('Website not available')),
    ('W04', _('Settings issue')),
    ('W05', _('Articles limit reached')),
    ('W06', _('Not using service')),
    # Service
    ('S01', _('Promotion request')),
    ('S02', _('Register new subscription')),
    ('S03', _('End subscription')),
    ('S04', _('Schedule subscription pause')),
    ('S05', _('Schedule address change')),
    ('S06', _('Vacation (Resorts)')),
    ('S07', _('Newsletters')),
    ('S08', _('Complaints on service')),
    ('S09', _('Payment types')),
    ('S10', _('Errors in data')),
    ('S11', _('Special cases')),
    ('S12', _('Schedule task')),
    ('S12', _('Change in subscription')),
    # Community
    ('O01', _('Community Benefits')),
    ('O02', _('Community Events')),
    ('O03', _('Café')),
    ('O04', _('Media-lab')),
    ('O05', _('Shop')),
    ('O06', _('Community Suggestions')),
    ('O07', _('Community Complaints')),
    ('O08', _('Community Requests')),
    ('O09', _('Polls/Surveys')),
    # Uncategorized
    ('N/A', _('No sub-category')),
)

ISSUE_ANSWERS = (
    ('I1', _('Collected')),
    ('L1', _('Delivered again')),
    ('L2', _('Not delivered')),
    ('L3', _('Can\'t be delivered that way')),
    ('L4', _('Delivered late')),
    ('L5', _('Problems to be delivered')),
    ('L6', _('Delivered in a specific way')),
)
