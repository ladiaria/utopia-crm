import calendar
from datetime import date, datetime, timedelta
from time import localtime
from django.utils.translation import ugettext_lazy as _


def add_business_days(from_date, add_days):
    """
    This is just used to add business days to a function. Should be moved to util.
    """
    business_days_to_add = add_days
    current_date = from_date
    while business_days_to_add > 0:
        current_date += timedelta(days=1)
        weekday = current_date.weekday()
        if weekday >= 5:  # sunday = 6
            continue
        business_days_to_add -= 1
    return current_date


def next_weekday_with_isoweekday(d, isoweekday):
    """
    Returns the next day selecting a date
    Uses Isoweekday (Mon: 1, Sun: 7)
    """
    days_ahead = isoweekday - d.isoweekday()
    if days_ahead <= 1:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


def next_business_day(today=None, today_hour=None):
    """
    Returns the next business day INCLUDING SATURDAYS, keeping in mind that for our company the day starts at 5 am.
    If necessary, today_hour can be removed.
    """
    today = today or date.today()
    today_hour = today_hour or localtime().tm_hour
    if today_hour > 5:  # days start at 5 am
        # Then if it's more than 5 am, we check for today's isoweekday
        iso = today.isoweekday()
        # For us, Saturday is also a business day, if necessary, we can change this to say iso in (5, 6) so it takes
        # both Friday and Saturday
        if iso == 6:
            # If it's Saturday, then next business day is going to be Monday
            dif = 2
        else:
            dif = 1
        return today + timedelta(days=dif)
    return today


def first_saturday_on_month(today_date=None):
    """
    Returns the first Saturday on the current month.
    """
    today_date = today_date or date.today()
    first_day_of_month = date(today_date.year, today_date.month, 1)
    month_range = calendar.monthrange(today_date.year, today_date.month)
    delta = (calendar.SATURDAY - month_range[0]) % 7
    return first_day_of_month + timedelta(delta)


def next_month():
    return date(
        date.today().year + 1 if date.today().month == 12 else
        date.today().year, int(date.today().strftime("%m")) % 12 + 1, 1)


def get_default_start_date():
    return date.today() + timedelta(days=1)


def get_default_next_billing():
    return date.today() + timedelta(days=1)


def format_date(d):
    if d == date.today():
        return _('Today')
    elif d == date.today() - timedelta(1):
        return _('Yesterday')
    else:
        if d.isoweekday() == 1:
            return _('Mon') + d.strftime('%d-%m')
        else:
            return d.strftime('%d')


def add_month(d, n=1):
    """
    Add n+1 months to date then subtract 1 day. To get eom, last day of target month.
    """
    q, r = divmod(d.month + n, 12)
    eom = date(d.year + q, r + 1, 1) - timedelta(days=1)
    if d.month != (d + timedelta(days=1)).month or d.day >= eom.day:
        return eom
    return eom.replace(day=d.day)


def diff_month(newer, older):
    return (newer.year - older.year) * 12 + newer.month - older.month
