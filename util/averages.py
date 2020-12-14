from math import ceil
from datetime import date, datetime, timedelta
from subprocess import Popen, PIPE
try:
    import simplejson as json
except ImportError:
    import json

from django.conf import settings

def lastweek_homes_avg():
    """ Returns the average of homes we reached last week """
    # find last week monday
    # iter over tail checking dates
    lastweek_monday = date.today() - timedelta(
        6 + date.today().isoweekday() % 7)
    homes = [0] * 7
    for line in Popen(('tail', '-12', settings.DOMICILIOS_LOG),
            stdout=PIPE).communicate()[0].splitlines():
        line_data = json.loads(line)
        line_day = datetime.strptime(line_data[0], "%Y%m%d").date()
        if line_day < lastweek_monday:
            continue # not last week yet
        elif line_day < lastweek_monday + timedelta(5):
            print line_day
            homes = [sum(x) for x in zip(homes, line_data[1])] # in last week
        else:
            break # after last week
    # transform the sum in the average
    homes = [x / 5.0 for x in homes]
    # update the sum factors
    for i in range(1,7,2):
        homes[i] = int(ceil(
            homes[i] + homes[i + 1] * settings.DOMICILIOS_EXTRA / 100))
    # update total and return
    homes[0] = homes[1] + homes[3] + homes[5]
    return homes
