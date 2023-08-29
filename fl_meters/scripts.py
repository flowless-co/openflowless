import logging
from decimal import Decimal
from functools import reduce
import datetime as dt

from django.contrib.auth.models import User
from pytz import utc

from .models import Zone, PressurePulse, Alert, LossRecord, HourlyAvgZonePressure, Notification
from django.conf import settings

lg = logging.getLogger(__name__)

""" LOSS CONSUMPTION ROUTINE """

# Constants
BURST_THRESHOLD = 0.5


def calculate_mnf_leak(zone: Zone, mnf_start, mnf_end):
    mnf_start = mnf_start - dt.timedelta(minutes=settings.RIE)
    mnf_consumption = zone.calculate_delta_consumption(mnf_start, mnf_end)
    if mnf_consumption is None:
        return None
    mnf_length_in_hours = (mnf_end - mnf_start).seconds / 60 / 60
    mnf_flow_rate = mnf_consumption / Decimal(str(mnf_length_in_hours))  # QMNF
    mnf_leak = mnf_flow_rate - zone.estimated_legitimate_night_use  # LDMA

    lg.info(f"1) Calculating MNF Leak: "
            f"mnf_consumption = {mnf_consumption} | mnf_flow_rate = {mnf_flow_rate} | mnf_leak = {mnf_leak}.")

    return mnf_leak

def calculate_fnd_factor(zone, mnf_start: dt.datetime, mnf_end: dt.datetime):
    day_start = dt.datetime.combine(mnf_end.date(), dt.time.min).replace(tzinfo=utc)
    day_end = dt.datetime.combine(day_start.date(), dt.time.max).replace(tzinfo=utc)

    today_hourly_pressure_readings = list(HourlyAvgZonePressure.objects.filter(zone=zone, time__gte=day_start, time__lte=day_end))
    mnf_hourly_pressure_readings = list(HourlyAvgZonePressure.objects.filter(zone=zone, time__gte=mnf_start, time__lte=mnf_end))

    # calculate avg pressure throughout mnf period:
    pmnf = reduce(lambda acc, pulse: pulse.azp + acc, mnf_hourly_pressure_readings, 0)
    mnf_length_in_hours = (mnf_end - mnf_start + dt.timedelta(minutes=settings.RIE)).seconds / 60 / 60
    pmnf = pmnf / Decimal(str(mnf_length_in_hours))

    # calculate FND:
    fnd = sum(map(lambda pressure: Decimal(str(pressure.azp / pmnf)) ** zone.n1, today_hourly_pressure_readings))  # Σ(Pi/PMNF)^N1

    lg.info(f"2) Calculating FND Factor: "
            f"len(today_hourly_pressure_readings) = {len(today_hourly_pressure_readings)} | "
            f"len(mnf_hourly_pressure_readings) = {len(mnf_hourly_pressure_readings)} | "
            f"pmnf = {pmnf} | "
            f"fnd = {fnd}")

    return fnd

def calculate_daily_leak(zone, mnf_start, mnf_end):
    mnf_leak = calculate_mnf_leak(zone, mnf_start, mnf_end)
    if mnf_leak is None:
        return None
    fnd = calculate_fnd_factor(zone, mnf_start, mnf_end)

    lg.info(f"3) Calculating Daily Leak: "
            f"mnf_leak * fnd = {mnf_leak} * {fnd} = {mnf_leak * fnd}")

    return mnf_leak * fnd  # QDMA|daily

def end_of_mnf_period_handler(mnf_start: dt.datetime, mnf_end: dt.datetime, zone: Zone):
    lg.info(f"== Calculating Daily Leak Between {mnf_start.strftime(settings.DATETIME_FORMAT)} - {mnf_end.strftime(settings.DATETIME_FORMAT)} For Zone: {zone} ==")

    loss_amount = calculate_daily_leak(zone, mnf_start, mnf_end)
    if loss_amount is not None:
        if loss_amount > zone.burst_threshold:
            alert = Alert.objects.create(zone=zone, loss_amount=loss_amount-zone.burst_threshold, kind='LK')
            notify_client(alert)
        LossRecord.objects.create(zone=zone, amount=loss_amount, date=mnf_end.date())

def notify_client(alert):
    for user in User.objects.filter(groups__name='Client'):
        Notification.objects.create(user=user, alert=alert)