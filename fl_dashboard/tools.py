import datetime as dt
from typing import List, Tuple

from django.conf import settings
from django.db.models import Sum, Avg, DateField, DateTimeField

import pytz

from fl_meters.models import Pulse, Meter, Alert, DailyZoneConsumption, MonthlyZoneConsumption, DailyAvgConsumption, \
    MonthlyAvgConsumption, Zone
from fl_meters.tools import get_day_opening, get_month_opening, get_day_start, get_month_start, get_now


def homepage_stats():
    context = {
        'received_signals_percentage': get_received_signals_percentage()
    }
    context.update(get_consumption_stats_context())

    return context


def get_consumption_stats_context():
    today_start = get_day_start(get_now())
    yesterday_opening = today_start - dt.timedelta(days=1)
    this_month_start = get_month_start(get_now())

    today_consumption = DailyZoneConsumption.objects.filter(date=today_start)
    yesterday_consumption = DailyZoneConsumption.objects.filter(date=yesterday_opening)
    month_consumption = MonthlyZoneConsumption.objects.filter(date=this_month_start)

    try:
        from fl_dashboard.customization import dashboard_stats
        if dashboard_stats['include_zones'] != '__all__':
            n_zones = len(dashboard_stats['include_zones'])
            today_consumption = today_consumption.filter(zone_id_id__in=dashboard_stats['include_zones'])
            yesterday_consumption = yesterday_consumption.filter(zone_id_id__in=dashboard_stats['include_zones'])
            month_consumption = month_consumption.filter(zone_id_id__in=dashboard_stats['include_zones'])
        else:
            n_zones = Zone.objects.count()
    except Exception:
        n_zones = Zone.objects.count()

    today_consumption = today_consumption.aggregate(Sum('consumption'))
    yesterday_consumption = yesterday_consumption.aggregate(Sum('consumption'))
    month_consumption = month_consumption.aggregate(Sum('consumption'))

    # TODO: Clean up this crap:
    try:
        today_consumption = round(today_consumption['consumption__sum'], 2)
    except:
        today_consumption = '---'

    try:
        yesterday_consumption = round(yesterday_consumption['consumption__sum'], 2)
    except:
        yesterday_consumption = '---'

    try:
        month_consumption = round(month_consumption['consumption__sum'], 2)
    except:
        month_consumption = '---'

    return {
        'today_consumption': today_consumption,
        'yesterday_consumption': yesterday_consumption,
        'month_consumption': month_consumption,
        'daily_avg_consumption': '---',
        'monthly_avg_consumption': '---',
        'n_zones': n_zones
    }


def get_received_signals_percentage():
    last_hour = get_now() - dt.timedelta(hours=1)
    pulses_in_last_hour = 0

    all_meters = Meter.objects.all()

    for meter in all_meters:
        try:
            last_pulse = meter.get_previous_pulse()
            if last_pulse.time >= last_hour:
                pulses_in_last_hour += 1
        except IndexError:
            pass

    if not all_meters:
        ratio = 0
    else:
        ratio = pulses_in_last_hour / len(all_meters)

    return str(round(ratio * 100, 2)) + "%"


def clean_since_until_date(since, until) -> Tuple[dt.datetime, dt.datetime]:
    if not all(x is not None for x in (since, until)):
        raise ValueError("since, or until can't be None")
    since = dt.datetime.combine(DateTimeField().to_python(since), dt.time.min).replace(tzinfo=pytz.utc)
    until = dt.datetime.combine(DateTimeField().to_python(until), dt.time.max).replace(tzinfo=pytz.utc)
    return since, until

def clean_since_until_datetime(since, until) -> Tuple[dt.datetime, dt.datetime]:
    if not all(x is not None for x in (since, until)):
        raise ValueError("since, or until can't be None")
    since = DateTimeField().to_python(since).replace(tzinfo=pytz.utc)
    until = DateTimeField().to_python(until).replace(tzinfo=pytz.utc)
    return since, until
