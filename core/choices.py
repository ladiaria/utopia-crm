# coding=utf-8
from django.utils.translation import ugettext_lazy as _

ADDRESS_TYPE_CHOICES = (
    ('digital', _('Digital')),
    ('physical', _('Physical'))
)

EDUCATION_CHOICES = (
    (1, _('Primary')),
    (2, _('Incomplete secondary')),
    (3, _('Complete secondary')),
    (4, _('Incomplete university')),
    (5, _('Complete university')),
    (6, _('Postgraduate')),
    (100, _('Doesn\'t want to inform')),
)

INACTIVITY_REASONS = (
    (1, _('Normal end')),
    (2, _('Paused')),
    (3, _('Upgraded')),
    (9, _('Lost the route')),
    (10, _('We don\'t reach this address')),
    (11, _('Bad addition to the database')),
    (12, _('Duplicated address')),
    (13, _('Debtor')),
    (15, _('Vacations')),
    (16, _('Debtor, automatic unsubscription')),
    (99, _('N/A')),
)

FREQUENCY_CHOICES = (
    (1, _('Monthly')),
    (3, _('Quarterly')),
    (6, _('Biannual')),
    (12, _('Annual'))
)


SUBSCRIPTION_TYPE_CHOICES = (
    ('P', _('Promotion')),
    ('N', _('Normal')),
    ('F', _('Gift')),
    ('S', _('Staff')),
)

SUBSCRIPTION_STATUS_CHOICES = (
    ('AP', _('Awaiting payment')),
    ('NC', _('Not consolidated')),
    ('OK', _('Normal')),
    ('PA', _('Paused')),
    ('DE', _('End because of debt')),
    ('NE', _('Normal end')),
)

GENDERS = (
    ('M', _('Male')),
    ('F', _('Female')),
    ('O', _('Other')),
)

VARIABLE_TYPES = (
    ('impresion', _('Impression')),
    ('impresion_fs', _('Imperssion Weekend')),
)

PRIORITY_CHOICES = (
    (1, _('Highest')),
    (2, _('High')),
    (3, _('Normal')),
    (4, _('Low')),
    (5, _('Lowest')),
)

PRODUCTHISTORY_CHOICES = (
    ('A', _('Active')),
    ('I', _('Inactive')),
    ('P', _('Paused')),
    ('R', _('Resumed')),
)

ACTIVITY_STATUS_CHOICES = (
    ('P', _('Pending')),
    ('C', _('Completed')),
    ('D', _('Delayed')),
)


ACTIVITY_DIRECTION_CHOICES = (
    ('I', _('In')),
    ('O', _('Out')),
)

CAMPAIGN_RESOLUTION_CHOICES = (
    ('SP', _('Started promotion')),
    ('AS', _('Already a subscriber')),
    ('DN', _('Do not call anymore')),
    ('EP', _('Error in promotion')),
    ('LO', _('Logistics')),
    ('NI', _('Not interested')),
    ('S1', _('Success with promotion')),
    ('S2', _('Success with direct sale')),
)

CAMPAIGN_REJECT_REASONS_CHOICES = (
    ('F', _('Failed delivery')),
    ('E', _('Financial reasons')),
    ('D', _('Error in data')),
    ('N', _('Never signed in for promotion')),
    ('P', _('Did not like the product')),
    ('C', _('Did not like the content')),
    ('R', _('Cannot reach the contact\'s location')),
    ('K', _('Did not know what they signed up for')),
    ('T', _('Does not read/Does not have time')),
    ('Z', _('Dangerous zone')),
    ('A', _('Does not accept call')),
    ('O', _('Accepts call but does not accept offer')),
    ('H', _('Accepts call, will think about it')),
)

CAMPAIGN_RESOLUTION_REASONS_CHOICES = (
    (1, u'Acepta llamada / va a pensarlo'),
    (2, u'Motivos económicos'),
    (3, u'Fuera de zona'),
    (4, u'Le interesa para más adelante'),
    (5, u'Mala experiencia'),
    (6, u'No aplica a la campaña'),
    (7, u'No da motivos'),
    (8, u'No lee / No tiene tiempo'),
    (9, u'No llegó promoción'),
    (10, u'No responde'),
    (11, u'No sabía que se había registrado'),
    (12, u'Número y email incorrectos'),
    (13, u'Ya es suscriptor'),
)

ACTIVITY_TYPES = (
    ('S', _('Campaign start')),
    ('C', _('Call')),
    ('M', _('E-mail')),
    ('L', _('Link hit')),
    ('E', _('Event participation')),
    ('I', _('In-place visit')),
)

PRODUCT_TYPE_CHOICES = (
    ('S', _('Subscription')),
    ('N', _('Newsletter')),
    ('D', _('Discount')),
    ('P', _('Percentage discount')),
    ('O', _('Other')),
)

PRODUCT_WEEKDAYS = (
    (1, _('Monday')),
    (2, _('Tuesday')),
    (3, _('Wednesday')),
    (4, _('Thursday')),
    (5, _('Friday')),
    (6, _('Saturday')),
    (7, _('Sunday')),
    (8, _('All week')),
    (9, _('Weekdays')),
    (10, _('Weekends')),
)


CAMPAIGN_STATUS_CHOICES = (
    (1, _('Not yet contacted')),
    (2, _('Contacted')),
    (3, _('Called, could not contact')),
    (4, _('Ended with contact')),
    (5, _('Ended without contact')),
)

PRICERULE_MODE_CHOICES = (
    (1, _('Replace all')),
    (2, _('Replace one')),
    (3, _('Add new')),
)


DYNAMIC_CONTACT_FILTER_MODES = [
    (1, _('At least one of the products')),
    (2, _('All products')),
    (3, 'Newsletters'),
]

ENVELOPE_CHOICES = (
    (1, _("Paid envelope")),
    (2, _("Free envelope")),
)
