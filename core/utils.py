import requests
from datetime import date, timedelta
from django.conf import settings

dnames = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday')


def addMonth(d, n=1):
    """
    Add n+1 months to date then subtract 1 day. To get eom, last day of target month.
    """
    q, r = divmod(d.month + n, 12)
    eom = date(d.year + q, r + 1, 1) - timedelta(days=1)
    if d.month != (d + timedelta(days=1)).month or d.day >= eom.day:
        return eom
    return eom.replace(day=d.day)


def subscribe_email_to_mailtrain_list(email, mailtrain_list_id):
    print("sending email {} to {}".format(email, mailtrain_list_id))
    url = '{}subscribe/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    print(r)


def delete_email_from_mailtrain_list(email, mailtrain_list_id):
    print("deleting email {} from {}".format(email, mailtrain_list_id))
    url = '{}delete/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    print(r)


def get_emails_from_mailtrain_list(mailtrain_list_id):
    emails = []
    url = '{}subscriptions/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY, 'limit': 30000}
    r = requests.get(url=url, params=params)
    data = r.json()
    for subscription in data['data']['subscriptions']:
        emails.append(subscription['email'])
    return emails
