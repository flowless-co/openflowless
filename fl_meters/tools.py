import datetime as dt
from enum import Enum
from typing import List, Optional

import pytz
from django.utils.timezone import localtime
from pytz import utc
from django.conf import settings


class EnumLeakageStatus:
    @staticmethod
    def value(name):
        from .models import METER_LEAKAGE_STATUS
        for status in METER_LEAKAGE_STATUS:
            if status[1].lower() == name.lower():
                return status[0]

    @staticmethod
    def name(value):
        from .models import METER_LEAKAGE_STATUS
        for status in METER_LEAKAGE_STATUS:
            if status[0] == value:
                return status[1]


class LeakageStatus(Enum):
    NOT_LEAKING = 2
    LEAKING = 3
    NA = 9


class AlertStatusCode(Enum):
    LEAK = 2
    SHOCK = 3
    UNDEFINED = 25

def ries_between(before: dt.datetime, after: dt.datetime):
    """
    Finds how many Ries exist between two datetimes, excluding them.\n
    *Example: between 2:00 and 3:00, assuming a 15 minute Rie, the return value will be 3.*
    """
    return int((after - before).total_seconds() // (60 * settings.RIE) - 1)


def datetime_ticks(since, until, aggregation_period, rie=15) -> List[dt.datetime]:
    if since > until:
        raise ValueError("Until is after Since")

    if aggregation_period == 'minutes':
        delta = int((until - since).total_seconds()) // (60 * rie) + 1  # Rie
        return [since + dt.timedelta(minutes=i*rie) for i in range(delta)]  # Rie
    if aggregation_period == 'hours':
        delta = int((until - since).total_seconds()) // 3600 + 1  # Rie
        return [since + dt.timedelta(hours=i*rie) for i in range(delta)]  # Rie
    if aggregation_period == 'days':
        delta = (until - since).days + 1
        return [since + dt.timedelta(days=i) for i in range(delta)]
    if aggregation_period == 'months':
        delta = (until - since).days // 30 + 1
        return [since + dt.timedelta(days=i) for i in range(delta)]
    if aggregation_period == 'years':
        delta = (until - since).days // (12 * 30) + 1
        return [since + dt.timedelta(days=i) for i in range(delta)]
    raise ValueError("Bad Resolution Value")


def round_down_to_ri(time: dt.datetime):
    ri_minute = (time.minute // 15) * 15
    return time.replace(minute=ri_minute, second=0, microsecond=0)

def slide_to_start_of_aggregation_period(time: dt.datetime, aggregation_period):
    if aggregation_period == 'minutes':
        rie = 15
        return time.replace(minute=(time.minute // rie) * rie, second=0, microsecond=0)
    if aggregation_period == 'hours':
        time.replace(minute=0, second=0, microsecond=0)
    if aggregation_period == 'days':
        time.replace(hour=0, minute=0, second=0, microsecond=0)
    if aggregation_period == 'months':
        time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if aggregation_period == 'years':
        time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError("Bad Aggregation Period Value")


def _next_meter_serial():
    """ Returns the serial number for meters to be used next.
    It also automatically increments the serial record in the database. """

    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="Meter")

    if db_record.last_serial_stamp.year < dt.datetime.now().year:
        # if a new serial year is upon us, reset serial to 1 and save record.
        db_record.last_serial_value = 1
        serial_value = 1
    else:
        db_record.last_serial_value += 1
        serial_value = db_record.last_serial_value

    db_record.save()
    return serial_value


def _next_transmitter_serial():
    """ Returns the serial number for transmitters to be used next.
    It also automatically increments the serial record in the database. """

    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="Transmitter")

    # if last serial was in the previous year:
    if db_record.last_serial_stamp.year < dt.datetime.now().year:
        # reset serial to 1
        db_record.last_serial_value = 1
        serial_value = 1
    else:
        db_record.last_serial_value += 1
        serial_value = db_record.last_serial_value

    db_record.save()
    return serial_value


def _next_chlorine_sensor_serial():
    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="ChlorineSensor")

    db_record.last_serial_value += 1
    serial_value = db_record.last_serial_value

    db_record.save()
    return serial_value


def _next_alert_serial():
    """ Returns the serial number for alerts to be used next.
    It also automatically increments the serial record in the database. """

    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="Alert")

    if db_record.last_serial_stamp.day < dt.datetime.now().day:
        # if a new serial year is upon us, reset serial to 1 and save record.
        db_record.last_serial_value = 1
        serial_value = 1
    else:
        db_record.last_serial_value += 1
        serial_value = db_record.last_serial_value

    db_record.save()
    return serial_value


def _next_transmission_line_serial():
    """ Returns the serial number for transmission line to be used next.
    It also automatically increments the serial record in the database. """

    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="TransmissionLine")

    db_record.last_serial_value += 1
    serial_value = db_record.last_serial_value

    db_record.save()
    return serial_value


def next_meter_key():
    """ Returns the formatted meter_key ready to be used in a meter object """
    serial_number = str(_next_meter_serial()).rjust(4, "0")
    this_year = dt.datetime.now().strftime("%y")
    return f"MTR-{this_year}{serial_number}"


def next_transmitter_key():
    """ Returns the formatted transmitter_key ready to be used in a transmitter object """
    serial_number = str(_next_transmitter_serial()).rjust(4, "0")
    this_year = dt.datetime.now().strftime("%y")
    return f"PTM-{this_year}{serial_number}"


def next_chlorine_sensor_key():
    """ Returns the formatted chlorine_sensor_key ready to be used in a ChlorineSensor object """
    serial_number = str(_next_transmission_line_serial()).rjust(1, "0")
    return f"CHL-SSR-{serial_number}"

def next_alert_key():
    """ Returns the formatted alert_key ready to be used in an alert object """
    serial_number = str(_next_alert_serial()).rjust(3, "0")
    short_date = dt.datetime.now().strftime("%y%m%d")
    return f"ALERT-{short_date}-{serial_number}"


def next_transmission_line_key():
    """ Returns the formatted key ready to be used in a transmission_line object """
    serial_number = str(_next_transmission_line_serial()).rjust(1, "0")
    return f"TSM-{serial_number}"


def next_tank_level_sensor_key():
    from .models import Serial
    db_record, created = Serial.objects.get_or_create(model_name="TankLevelSensor")
    db_record.last_serial_value += 1
    serial_number = str(db_record.last_serial_value).rjust(1, "0")
    db_record.save()
    return f"TKLVL-{serial_number}"


def is_end_of_hour(time, margin_of_error=5):
    """:param margin_of_error: Tolerance in minutes. Default is 5 minutes"""
    return 60 - margin_of_error <= time.minute <= 59


def is_start_of_hour(time, margin_of_error=5):
    """:param margin_of_error: Tolerance in minutes. Default is 5 minutes"""
    return 0 <= time.minute <= margin_of_error


def is_midnight(time: dt.datetime):
    return time.hour == 0 and time.minute == 0


""" FLOW METERS PULSES CALCULATORS """

def consumption_between_two_pulses_legacy(before_pulse, after_pulse, meter_digits):
    if before_pulse is not None and after_pulse is not None:
        before_reading = before_pulse.cleaned_reading()
        if after_pulse.cleaned_reading() < before_reading / 2:
            # if current reading happened after a meter digits overflow reset, compensate for that.
            # the division by 2 is to leave room for back-flow TODO: implement back flow logic
            after_reading = 10 ** meter_digits + after_pulse.cleaned_reading()
        else:
            after_reading = after_pulse.cleaned_reading()

        return after_reading - before_reading
    raise Exception("Neither of the pulses can be None.")

def consumption_between_two_pulses(before_pulse, after_pulse, meter_digits):
    if before_pulse is None or after_pulse is None:
        raise Exception("Neither of the pulses can be None.")

    if int(after_pulse.reading) < int(after_pulse.reading)/2:
        after_reading = 10 ** meter_digits + int(after_pulse.reading)
    else:
        after_reading = after_pulse.cleaned_reading()

    return after_reading - before_pulse.cleaned_reading()

def sum_pulses_consumption(pulses, meter_digits):
    consumption_sum = 0
    last_pulse = None
    for pulse in pulses:
        if last_pulse is None:
            last_pulse = pulse
            continue
        consumption_sum += consumption_between_two_pulses(last_pulse, pulse, meter_digits)
    return consumption_sum

def get_offset_time(datetime: dt.datetime):
    """ Offset time is used to get the "effective" day of a pulse's time. """
    return datetime - dt.timedelta(minutes=settings.RIE)

def get_day_opening(datetime: dt.datetime):
    """ Day opening time is the time at which a pulse is considered the first pulse of that day. """
    return get_offset_time(datetime).replace(hour=0, minute=settings.RIE, second=0, microsecond=0, tzinfo=utc)

def get_day_close(datetime: dt.datetime):
    """ Day close time is the time at which a pulse is considered the last pulse of that day. """
    return get_day_opening(datetime).replace(minute=0, tzinfo=utc) + dt.timedelta(days=1)

def get_month_opening(datetime: dt.datetime):
    """ Day opening time is the time at which a pulse is considered the first pulse of that month. """
    return get_day_opening(datetime).replace(day=1)

def get_day_start(datetime: dt.datetime, offset=True):
    """ Day start time is the first moment of a day. """
    if offset:
        datetime = get_offset_time(datetime)
    return datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=utc)

def get_month_start(datetime: dt.datetime, offset=True):
    """ Month start time is the first moment of a month. """
    return get_day_start(datetime, offset).replace(day=1)

def get_now():
    return localtime().replace(tzinfo=pytz.utc)


def get_pulses_of_each_meter_in_zone_at_timestamp(zone, time):
    """ For a specific zone, get each meter's pulse at the specified time. """
    #pulses = []
    #for meter in zone.meters:
    #	pulses.append(Pulse.objects.filter(meter=meter, time=time).first())
    #return pulses
    from fl_meters.models import Pulse
    return list(map(lambda meter: Pulse.objects.filter(meter=meter, time=time).first(), zone.meters))

def get_sisters_of_pulse(pulse, zone):
    """ Returns all sisters of a pulse in a zone, or None if at least one sister is missing. """
    potential_sisters = get_pulses_of_each_meter_in_zone_at_timestamp(zone, pulse.time)

    if len(list(filter(None, potential_sisters))) != zone.meters_length:
        return None

    return potential_sisters

def get_last_sisters_of_zone(zone, start_from: dt.datetime=None):
    """ Returns the last available group of sisters for a zone. If start_from == None,
    it skips the last group of sisters and finds the one before that.

    :param start_from: The time point from which to start looking for a group of sisters (excluded) """

    """
    EXPLANATION SCENARIO:
        |> Oldest Pulse (layer 5) 
        |       |> Newest Pulse (layer 1)
        x   x x x : pulses of meter 1
        x   x   x : pulses of meter 2
        x x   x x : pulses of meter 3
        All these meters are associated with the same zone. The X's are pulses, and blanks are missing pulses.
    EXPECTED BEHAVIOUR:
        Calling this function with start_from == None, should return the pulses in (layer 5).
    EXPLANATION:
        Going through the pulses of these meters (skipping the newest layer), will keep failing since they are
        never a complete group of 3 sisters. It will eventually return the newest available group of 3 sisters,
        which are the ones found in layer 5.  
    """
    from fl_meters.models import Pulse

    filters = {'time__lt': start_from} if start_from else {}
    skip = 0 if start_from else 1

    last_pulse_of_each_meter = list(map(lambda meter: Pulse.objects.filter(meter=meter, **filters).order_by('-time')[skip:].first(), zone.meters))
    if len(list(filter(None, last_pulse_of_each_meter))) == 0:
        return None
    last_pulse_of_each_meter.sort(key=lambda pulse: pulse.time)
    oldest_pulse = last_pulse_of_each_meter[0]
    if not all([pulse.time == oldest_pulse.time for pulse in last_pulse_of_each_meter]):

        last_pulse_of_each_meter = get_sisters_of_pulse(oldest_pulse, zone)

        if last_pulse_of_each_meter is None:
            return get_last_sisters_of_zone(zone, start_from=oldest_pulse.time)

    return last_pulse_of_each_meter
