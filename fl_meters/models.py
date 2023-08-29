import binascii
import datetime as dt
import os
from decimal import Decimal

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse
from pytz import utc

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now, localtime
from django.utils.translation import ugettext_lazy as _
from django_google_maps import fields as map_fields
from rest_framework.authtoken.models import Token as DrfToken

from .tools import next_meter_key, next_alert_key, next_transmitter_key, is_start_of_hour, is_end_of_hour, \
    sum_pulses_consumption, consumption_between_two_pulses, next_transmission_line_key, next_chlorine_sensor_key, \
    next_tank_level_sensor_key

OPERATIONAL_STATUS = [
    (2, 'Stopped'),
    (3, 'Running'),
    (4, 'Faulty'),
    (9, 'N/A'),
]

METER_LEAKAGE_STATUS = [
    (2, 'Not Leaking'),
    (3, 'Leaking'),
    (9, 'N/A'),
]

METER_MECHANISM_TYPE = [
    (2, 'Electromagnetic'),
    (3, 'Ultrasonic'),
    (4, 'Positive Displacement'),
    (5, 'Multi-jet'),
    (9, 'N/A'),
]

TRANSMITTER_MECHANISM_TYPE = [
    (2, 'ANDARY 1'),
    (3, 'ANDARY 2'),
    (9, 'N/A'),
]

ALERT_STATUS_CODE = [
    ('LK', 'Leak'),
    ('SK', 'Shock'),
    ('NM', 'Anomaly'),

    ('--', 'Undefined'),
]

CUSTOMER_TYPE = [
    (2, 'Residential'),
    (3, 'Commercial'),
    (4, 'Industrial'),
    (5, 'Tourism'),
    (6, 'Irrigation'),
]

TABLE_TYPE = [
    ('qh', 'QuarterHourly'),
    ('day', 'daily'),
    ('month', 'monthly'),
    ('year', 'yearly'),
]


ANNOTATION_TYPES = (
    (0, "Undefined"),
    (1, "Interpolation"),
    (2, "Anomaly"),
    (3, "Estimation Confidence"),
)
METRIC_TYPES = (
    (0, 'Undefined'),
    (1, 'Meter Flowrate'),
    (2, 'Zone Consumption'),
)


class Location(models.Model):
    address = map_fields.AddressField(max_length=200, null=True)
    geolocation = map_fields.GeoLocationField(max_length=100, null=True)

    description = models.TextField()
    city = models.CharField(max_length=32, default="", blank=True)
    neighbourhood = models.CharField(max_length=48, default="", blank=True)
    bldg_no = models.CharField(max_length=8, default="", blank=True)
    zone = models.ForeignKey(to='Zone', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.description


class Serial(models.Model):
    model_name = models.CharField(max_length=16)
    last_serial_value = models.IntegerField(default=0)
    last_serial_stamp = models.DateField(auto_now=True)

    def __str__(self):
        return self.model_name


class Meter(models.Model):
    key = models.CharField(max_length=10, unique=True, null=True, blank=True)
    installation_date = models.DateTimeField(null=True, blank=False, default=now)  # TODO: Add default time?
    op_status = models.IntegerField(choices=OPERATIONAL_STATUS, default=9)
    leak_status = models.IntegerField(choices=METER_LEAKAGE_STATUS, default=9)
    meter_model = models.ForeignKey(to='MeterModel', on_delete=models.PROTECT)
    reading_factor = models.DecimalField(max_digits=9, decimal_places=2, default=1, blank=True,
                                         help_text='The multiplication factor for each pulse going through this meter.')
    reading_offset = models.DecimalField(max_digits=12, decimal_places=5, default=0, blank=True,
                                         help_text="The offset amount for each pulse going through this meter. Can also be a negative value.")
    location = models.ForeignKey(to=Location, on_delete=models.SET_NULL, null=True, blank=True)
    serial_number = models.CharField(max_length=32, blank=True, default='')

    active = models.BooleanField(null=False, default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    input_for = models.ForeignKey('Zone', models.PROTECT, null=True, blank=True, related_name='input_meters',
                                  help_text="Input of Zone")
    output_for = models.ForeignKey('Zone', models.PROTECT, null=True, blank=True, related_name='output_meters',
                                   help_text="Output of Zone")

    tsm_input = models.OneToOneField('TransmissionLine', models.SET_NULL, null=True, blank=True, related_name='input_meter',
                                     help_text="Input of Transmission Line")
    tsm_output = models.OneToOneField('TransmissionLine', models.SET_NULL, null=True, blank=True, related_name='output_meter',
                                      help_text="Output of Transmission Line")

    is_authenticated = True  # django-specific attribute. enables authentication or something...
    is_pulsar = True  # used in .authentication.IsPulsar

    class Meta:
        verbose_name = "Meter"
        verbose_name_plural = "Meters"

    def get_last_two_pulses(self):
        return Pulse.objects.order_by('-time').filter(meter_id=self.id)[:2]

    def get_pulses_at(self, time1, time2):
        before_pulse = None
        after_pulse = None
        pulses = Pulse.objects.filter(meter_id=self.id, time__in=[time1, time2])
        if len(pulses) > 2:
            raise Exception("More than 2 pulses were found")
        elif len(pulses) < 2:
            after_pulse = pulses[0]
        elif len(pulses) == 2:
            pulses = pulses.order_by('time')
            before_pulse = pulses[0]
            after_pulse = pulses[1]
        return before_pulse, after_pulse

    def get_pulses_between(self, start_period, end_period):
        return Pulse.objects.filter(meter_id=self.id, time__gte=start_period, time__lte=end_period)

    def get_previous_pulse(self):
        last_two = self.get_last_two_pulses()
        return last_two[0]

    def get_current_pulse(self):
        last_two = self.get_last_two_pulses()
        return last_two[1]

    def get_op_status_name(self):
        for pair in OPERATIONAL_STATUS:
            if self.op_status == pair[0]:
                return pair[1]
        return 'No Status Found'

    def set_leakage_status(self, leaking=False, not_leaking=False):
        """Set meter leaking status. Return leakage status after being set."""
        if leaking and not_leaking:
            raise ValueError("Can't be both leaking and not leaking at the same time.")

        if leaking:
            self.leak_status = 3
        elif not_leaking:
            self.leak_status = 2
        else:  # if both arguments are False
            self.leak_status = 9

        return self.leak_status

    def is_leaking(self):
        """Returns if meter is leaking or not. Will return False if its status is "N/A"."""
        return self.leak_status == 3

    def is_active(self):
        return self.active

    def save(self, *args, **kwargs):
        if not self.pk:  # if object doesn't exist in database (newly created)
            self.key = next_meter_key()

        return super().save(*args, **kwargs)

    def clean(self):
        zones = [self.input_for_id, self.output_for_id]
        tsms = [self.tsm_input_id, self.tsm_output_id]
        if not any(zones + tsms):
            raise ValidationError("Meter must be associated with either a zone or a transmission line")
        elif any(zones) and any(tsms):
            raise ValidationError("Meter can't be associated with a zone and a transmission line")
        else:
            if self.input_for_id is not None and self.input_for_id == self.output_for_id:
                raise ValidationError("Can't have same zone as input and output")
            elif self.tsm_input_id is not None and self.tsm_input_id == self.tsm_output_id:
                raise ValidationError("Can't have same transmission line as input and output")

    def __str__(self):
        return self.key


class PressureTransmitter(models.Model):
    key = models.CharField(max_length=10, unique=True, null=True, blank=True)
    installation_date = models.DateTimeField(null=True, blank=False)  # TODO: Add default time?
    op_status = models.IntegerField(choices=OPERATIONAL_STATUS, default=9)
    meter_model = models.ForeignKey(to='TransmitterModel', on_delete=models.PROTECT)
    reading_factor = models.DecimalField(max_digits=9, decimal_places=2, default=1, blank=True,
                                         help_text='The division factor for each pulse going through this transmitter.')
    reading_offset = models.DecimalField(max_digits=12, decimal_places=5, default=0, blank=True,
                                         help_text="The offset amount for each pulse going through this transmitter. Can also be a negative value.")
    location = models.ForeignKey(to=Location, on_delete=models.SET_NULL, null=True, blank=True)
    serial_number = models.CharField(max_length=32, blank=True, default='')
    zones = models.ManyToManyField(to='Zone', through='ZoneHasPressureTransmitter')

    active = models.BooleanField(null=False, default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    is_authenticated = True  # django-specific attribute. enables authentication or something...

    class Meta:
        verbose_name = "Transmitter"
        verbose_name_plural = "Transmitters"

    def get_last_two_pulses(self):
        return PressurePulse.objects.order_by('-time').filter(transmitter_id=self.id)[:2]

    def get_last_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[0]
        except Exception:
            return None

    def get_current_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[1]
        except Exception:
            return None

    def get_op_status_name(self):
        for pair in OPERATIONAL_STATUS:
            # compare self.op_status with each operational status' value:
            if self.op_status == pair[0]:
                return pair[1]
        return 'N/A'

    def is_active(self):
        return self.active

    def save(self, *args, **kwargs):
        if not self.pk:  # if object doesn't exist in database (i.e. newly created)
            self.key = next_transmitter_key()

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key


class AnalyticsQueue(models.Model):
    zone = models.ForeignKey(to='Zone', on_delete=models.CASCADE)
    datetime = models.DateTimeField()
    table_type = models.CharField(max_length=5, choices=TABLE_TYPE)
    ready_on = models.IntegerField(default=1)
    arrived = models.IntegerField(default=0)

    def missing_pulses(self):
        return self.ready_on - self.arrived


class OnHold(models.Model):
    zone = models.ForeignKey('Zone', models.CASCADE, null=True)
    transmission_line = models.ForeignKey('TransmissionLine', models.CASCADE, null=True)
    time = models.DateTimeField()
    ready_on = models.IntegerField()
    current_pulses_arrived = models.IntegerField()
    past_pulses_arrived = models.IntegerField()

    def clean(self):
        if self.zone_id is None and self.transmission_line_id is None:
            raise ValidationError("OnHold can't have no zone, or transmission line associated with it")
        elif self.zone_id is not None and self.transmission_line_id is not None:
            raise ValidationError("OnHold can't be associated with a zone and a transmission line")

    def is_awaiting(self, pulse):
        if self.transmission_line_id is not None:
            if not self.transmission_line.has(pulse.meter):
                return False

            if self.ready_on == 1:
                return pulse.time == self.time - dt.timedelta(minutes=15)

            elif self.ready_on == 2:
                return pulse.is_kickoff(self.time) or pulse.is_closure(self.time)

        if self.zone_id is not None:
            # check if pulse can be related in anyway to self.zone
            if self.zone_id not in (pulse.meter.input_for_id, pulse.meter.output_for_id):
                return False

            # if on_hold entry is waiting on a previous pulse, check if this is it
            if self.ready_on != self.past_pulses_arrived:
                if pulse.time + dt.timedelta(minutes=15) == self.time:
                    return True

            # check if on_hold entry is waiting for this pulse as a current pulse
            return pulse.time == self.time

        raise Exception("OnHold entry has no zone nor a transmission_line associated with it")

    def missing_pulses(self):
        return (self.ready_on - self.current_pulses_arrived) + (self.ready_on - self.past_pulses_arrived)

    @property
    def for_zone(self):
        return self.zone_id is not None

    @property
    def for_tsm(self):
        return self.transmission_line_id is not None

    @staticmethod
    def tsm_loss(tsm, time):
        return OnHold.objects.filter(transmission_line=tsm, time=time, ready_on=2)

    @staticmethod
    def tsm_inflow(tsm, time):
        return OnHold.objects.filter(transmission_line=tsm, time=time, ready_on=1)

    def __str__(self):
        time = self.time.strftime(settings.TIME_FORMAT)

        if self.for_zone:
            return f"{self.zone.name} @ {time} ({self.missing_pulses()*-1})"

        typ = 'Loss' if self.ready_on == 2 else 'Inflow' if self.ready_on == 1 else 'UNKNOWN TYPE'
        return f"{typ} of {self.transmission_line.key} @ {time} ({self.missing_pulses()*-1})"

    def __repr__(self):
        typ = f'zone({self.zone_id})' if self.for_zone else f'tsm({self.transmission_line_id})'

        return f"OnHold id({self.id}) time({self.time.strftime(settings.LOG_TIME_FORMAT)}) {typ}" \
               f"readyon({self.ready_on}) curr({self.current_pulses_arrived}) past({self.past_pulses_arrived})"


class Pulse(models.Model):
    meter = models.ForeignKey(to=Meter, on_delete=models.PROTECT)
    time = models.DateTimeField(null=False, blank=False)
    reading = models.CharField(max_length=16, null=False, default="", blank=False)
    normalized_reading = models.DecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    anomaly = models.BooleanField(null=True, blank=True)

    def at_day_end(self, margin_of_error=5):
        """:param margin_of_error: Tolerance in minutes. Default is 5 minutes"""
        return (self.time.hour == 23 and is_end_of_hour(self.time, margin_of_error)) or \
               (self.time.hour == 0 and is_start_of_hour(self.time, margin_of_error))

    def cleaned_reading(self):
        return self.meter.reading_offset + (Decimal(self.reading) * self.meter.reading_factor)

    def display_reading(self):
        if self.normalized_reading is not None:
            return self.normalized_reading
        elif self.reading is not None:
            return round(self.cleaned_reading(), 3) if self.meter_id is not None else self.reading
        return "N/A"

    def is_kickoff(self, datetime=None):
        if datetime is None:
            return self.time.minute == 15 and self.time.hour == 0
        return datetime.replace(minute=15, hour=0, second=0, microsecond=0) == self.time.replace(second=0, microsecond=0)

    def is_closure(self, datetime=None):
        if datetime is None:
            return self.time.minute == 0 and self.time.hour == 0
        dawn_of_next_day = (datetime + dt.timedelta(days=1)).replace(minute=0, hour=0, second=0, microsecond=0)
        return dawn_of_next_day == self.time.replace(second=0, microsecond=0)

    def __str__(self):
        return self.time.strftime(settings.DATETIME_FORMAT) + " - " + self.meter.key + " - " + self.reading

    def __repr__(self):
        return f"Pulse({self.id}) mtr({self.meter}) time({self.time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) reading({self.reading})"

    def save(self, **kwargs):
        self.normalized_reading = self.cleaned_reading()
        super().save(**kwargs)


class PressurePulse(models.Model):
    transmitter = models.ForeignKey(to=PressureTransmitter, on_delete=models.PROTECT)
    time = models.DateTimeField(null=False, blank=False)
    reading = models.CharField(max_length=17, null=False, default="", blank=False)
    normalized_reading = models.DecimalField(max_digits=13, decimal_places=3, null=True, blank=True)

    def display_reading(self):
        if self.normalized_reading is not None:
            return self.normalized_reading
        elif self.reading is not None:
            return round(self.cleaned_reading(), 3) if self.transmitter is not None else self.reading
        return "N/A"

    def cleaned_reading(self):
        return Decimal(self.reading) * self.transmitter.reading_factor + self.transmitter.reading_offset

    def save(self, **kwargs):
        self.normalized_reading = self.cleaned_reading()
        super().save(**kwargs)

    def __str__(self):
        return f"Transmitter ID:{self.transmitter_id} - ({self.reading})"


class Alert(models.Model):
    key = models.CharField(max_length=16, unique=True, default=next_alert_key)
    zone = models.ForeignKey(to='Zone', on_delete=models.DO_NOTHING, null=True, blank=True)
    loss_amount = models.DecimalField(decimal_places=3, max_digits=10)
    datetime = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=3, choices=ALERT_STATUS_CODE, default='--')

    def save(self, *args, **kwargs):
        if not self.pk:  # if object doesn't exist in database (newly created)
            self.key = next_alert_key()

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key

    def get_absolute_url(self):
        return reverse('dashboard:alerts')


class Notification(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    arrived_on = models.DateTimeField(auto_now_add=True)


class Customer(models.Model):
    meter = models.OneToOneField(to=Meter, on_delete=models.PROTECT, related_name='customer')
    name = models.CharField(max_length=48)
    customer_type = models.IntegerField(choices=CUSTOMER_TYPE)
    phone_number = models.CharField(max_length=14, default="", blank=True)
    email = models.CharField(max_length=32, default="", blank=True)

    def __str__(self):
        return self.name


class Zone(models.Model):
    name = models.CharField(max_length=48)
    color = models.CharField(max_length=9, blank=True, default="#ff0000")
    n1 = models.DecimalField(max_digits=6, decimal_places=3, default=1)
    estimated_legitimate_night_use = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    burst_threshold = models.DecimalField(max_digits=6, decimal_places=3, default=0)

    def calculate_delta_consumption(self, start_period, end_period):
        """
        Subtracts the last pulse's reading from the first pulse's reading and returns the value.
        Does not take into consideration that pulses may have cycled through a digits overflow cycle more than 1 time.
        Returns 0 if a critical pulse is missing.

        :param start_period: inclusive
        :param end_period: inclusive
        """
        input_sum = 0
        output_sum = 0
        input_meters = self.input_meters.all()
        output_meters = self.output_meters.all()

        for meter in input_meters:
            start_pulse, end_pulse = meter.get_pulses_at(start_period, end_period)
            if start_pulse is None or end_pulse is None:
                return None
            input_sum += consumption_between_two_pulses(start_pulse, end_pulse, meter.meter_model.digits)

        for meter in output_meters:
            start_pulse, end_pulse = meter.get_pulses_at(start_period, end_period)
            if start_pulse is None or end_pulse is None:
                return None
            output_sum += consumption_between_two_pulses(start_pulse, end_pulse, meter.meter_model.digits)

        return input_sum - output_sum

    def calculate_sigma_consumption(self, start_period, end_period):
        """
        Sums up all the pulses between the periods specified.
        :param start_period: inclusive
        :param end_period: inclusive
        """
        input_sum = 0
        output_sum = 0
        input_meters = self.input_meters.all()
        output_meters = self.output_meters.all()

        for meter in input_meters:
            pulses = meter.get_pulses_between(start_period, end_period)
            input_sum += sum_pulses_consumption(pulses, meter.meter_model.digits)

        for meter in output_meters:
            pulses = meter.get_pulses_between(start_period, end_period)
            output_sum += sum_pulses_consumption(pulses, meter.meter_model.digits)

        return input_sum - output_sum

    def get_flow_pulses_between(self, from_time, to_time):
        Pulse.objects.filter(meter__input_for=self, meter__output_for=self, time__gte=from_time, time__lte=to_time)

    def ready_to_calculate(self):
        last_quarter_hour = timezone.now() - dt.timedelta(minutes=15)
        zone_meters = self.input_meters.all().union(self.output_meters.all())

        for meter in zone_meters:
            current_pulse = meter.get_previous_pulse()
            if current_pulse is not None and current_pulse.time < last_quarter_hour:
                # return False if ANY of the meters' last pulse was older than a quarter hour ago
                return False

        return True

    @property
    def meters(self):
        return list(self.input_meters.union(self.output_meters.all()))

    @property
    def meters_length(self):
        return self.input_meters.count() + self.output_meters.count()

    def len_active_meters(self):
        return self.input_meters.count() + self.output_meters.count()

    def __str__(self):
        return self.name


class ZoneHasPressureTransmitter(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='transmitter_associations')
    transmitter = models.ForeignKey(to=PressureTransmitter, on_delete=models.CASCADE, related_name='associations')
    azp_factor = models.DecimalField(max_digits=12, decimal_places=6, default=1, blank=True)
    use_for_azp = models.BooleanField(default=True, blank=True)


class ZoneCoordinate(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='coords')
    latitude = models.DecimalField(max_digits=8, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"lat: {self.latitude} - lng: {self.longitude}"


class MeterModel(models.Model):
    manufacturer = models.CharField(max_length=48)
    model_number = models.CharField(max_length=24)
    bulk_meter = models.BooleanField(default=True)
    digits = models.IntegerField(help_text="Number of digits on meter. Decimal digits should not be included.")
    type = models.IntegerField(choices=METER_MECHANISM_TYPE, default=2)

    def __str__(self):
        return self.manufacturer + " - " + self.model_number


class TransmitterModel(models.Model):
    manufacturer = models.CharField(max_length=48)
    model_number = models.CharField(max_length=24)
    type = models.IntegerField(choices=TRANSMITTER_MECHANISM_TYPE, default=9)

    def __str__(self):
        return self.manufacturer + " - " + self.model_number


class DeviceModel(models.Model):
    manufacturer = models.CharField(max_length=48)
    model_number = models.CharField(max_length=24)
    description = models.CharField(max_length=100)

    def __str__(self):
        return self.manufacturer + " - " + self.model_number


class ChlorineSensor(models.Model):
    key = models.CharField(max_length=11, unique=True, null=True, blank=True)
    installation_date = models.DateTimeField(null=True, blank=False)
    model = models.ForeignKey(to=DeviceModel, on_delete=models.PROTECT)
    reading_factor = models.DecimalField(max_digits=9, decimal_places=2, default=1, blank=True,
                                         help_text='The division factor for each pulse going through this sensor.')
    reading_offset = models.DecimalField(max_digits=12, decimal_places=5, default=0, blank=True,
                                         help_text="The offset amount for each pulse going through this sensor. Can also be a negative value.")
    location = models.ForeignKey(to=Location, on_delete=models.SET_NULL, null=True, blank=True)

    active = models.BooleanField(null=False, default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    is_authenticated = True  # django-specific attribute. enables authentication or something...

    class Meta:
        verbose_name = "Chlorine Sensor"
        verbose_name_plural = "Chlorine Sensors"

    def get_last_two_pulses(self):
        return ChlorineSensorPulse.objects.order_by('-time').filter(sensor_id=self.id)[:2]

    def get_last_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[0]
        except Exception:
            return None

    def get_current_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[1]
        except Exception:
            return None

    def save(self, *args, **kwargs):
        if not self.pk:  # if object doesn't exist in database (i.e. newly created)
            self.key = next_chlorine_sensor_key()

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key


class ChlorineSensorPulse(models.Model):
    sensor = models.ForeignKey(to=ChlorineSensor, on_delete=models.PROTECT)
    time = models.DateTimeField()
    reading = models.DecimalField(max_digits=16, decimal_places=3)
    normalized_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)

    def display_reading(self):
        if self.normalized_reading is not None:
            return self.normalized_reading
        elif self.reading is not None:
            return round(self.cleaned_reading(), 3) if self.sensor is not None else self.reading
        return "N/A"

    def cleaned_reading(self):
        return Decimal(self.reading) * self.sensor.reading_factor + self.sensor.reading_offset

    def save(self, **kwargs):
        self.normalized_reading = self.cleaned_reading()
        super().save(**kwargs)

    def __str__(self):
        return f"Sensor ID:{self.sensor_id} - ({self.reading})"


class Tank(models.Model):
    name = models.CharField(max_length=50)
    location = models.ForeignKey(to=Location, on_delete=models.SET_NULL, null=True, blank=True)
    volume = models.DecimalField(max_digits=13, decimal_places=3, default=0)

    def __str__(self):
        return self.name


class TankLevelSensor(models.Model):
    tank = models.ForeignKey(to=Tank, on_delete=models.PROTECT)
    key = models.CharField(max_length=13, unique=True, null=True, blank=True)
    name = models.CharField(max_length=50, blank=True, default="", help_text="If not provided, the Key will be used instead.")
    installation_date = models.DateTimeField(null=True, blank=True)
    model = models.ForeignKey(to=DeviceModel, on_delete=models.PROTECT)
    reading_factor = models.DecimalField(max_digits=9, decimal_places=2, default=1, blank=True,
                                         help_text='The division factor for each pulse going through this sensor.')
    reading_offset = models.DecimalField(max_digits=12, decimal_places=5, default=0, blank=True,
                                         help_text="The offset amount for each pulse going through this sensor. Can also be a negative value.")
    active = models.BooleanField(null=False, default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    is_authenticated = True  # django-specific attribute. enables authentication or something...

    class Meta:
        verbose_name = "Tank Level Sensor"
        verbose_name_plural = "Tank Level Sensors"

    def get_last_two_pulses(self):
        return TankLevelSensorPulse.objects.order_by('-time').filter(sensor_id=self.id)[:2]

    def get_last_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[0]
        except Exception:
            return None

    def get_current_pulse(self):
        last_two = self.get_last_two_pulses()
        try:
            return last_two[1]
        except Exception:
            return None

    def save(self, *args, **kwargs):
        if not self.pk:  # if object doesn't exist in database (i.e. newly created)
            self.key = next_tank_level_sensor_key()

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name if self.name else self.key


class TankLevelSensorPulse(models.Model):
    sensor = models.ForeignKey(to=TankLevelSensor, on_delete=models.PROTECT)
    time = models.DateTimeField()
    reading = models.DecimalField(max_digits=16, decimal_places=3)
    normalized_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)

    def display_reading(self):
        if self.normalized_reading is not None:
            return self.normalized_reading
        elif self.reading is not None:
            return round(self.cleaned_reading(), 3) if self.sensor is not None else self.reading
        return "N/A"

    def cleaned_reading(self):
        return Decimal(self.reading) * self.sensor.reading_factor + self.sensor.reading_offset

    def save(self, **kwargs):
        self.normalized_reading = self.cleaned_reading()
        super().save(**kwargs)

    def __str__(self):
        return f"Sensor ID:{self.sensor_id} - ({self.reading})"

@python_2_unicode_compatible
class MeterToken(models.Model):
    """
    The default authorization token model.
    """
    key = models.CharField(_("Key"), max_length=40, primary_key=True)
    user = models.OneToOneField(
        Meter, related_name='auth_token',
        on_delete=models.CASCADE, verbose_name=_("Meter")
    )

    created = models.DateTimeField(_("Created"), auto_now_add=True)

    class Meta:
        # Work around for a bug in Django:
        # https://code.djangoproject.com/ticket/19422
        #
        # Also see corresponding ticket:
        # https://github.com/encode/django-rest-framework/issues/705
        abstract = 'rest_framework.authtoken' not in settings.INSTALLED_APPS
        verbose_name = _("Token")
        verbose_name_plural = _("Tokens")

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(MeterToken, self).save(*args, **kwargs)

    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()

    def __str__(self):
        return self.key


class LossRecord(models.Model):
    date = models.DateField()
    amount = models.DecimalField(max_digits=13, decimal_places=3)
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='loss_records')

    def __str__(self):
        return self.zone.name + " - " + self.date.strftime("%Y %b. %d")


class TransmissionLine(models.Model):
    key = models.CharField(max_length=9, unique=True, blank=True)
    start_location = models.OneToOneField(to=Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    end_location = models.OneToOneField(to=Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    volume = models.DecimalField(max_digits=12, decimal_places=3, default=0, blank=True)

    def calculate_loss_of(self, day: dt.date):
        """
        Delta (input pulses) - Delta (output pulses)
        Does not take into consideration that pulses may have cycled through a digits overflow cycle more than 1 time.
        Returns 0 if a critical pulse is missing.
        """

        start_period = dt.datetime.combine(day, dt.time(minute=15, tzinfo=utc))
        end_period = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min.replace(tzinfo=utc))

        start_pulse, end_pulse = self.input_meter.get_pulses_at(start_period, end_period)
        if start_pulse is None or end_pulse is None:
            return None
        input_sum = consumption_between_two_pulses(start_pulse, end_pulse, self.input_meter.meter_model.digits)

        start_pulse, end_pulse = self.output_meter.get_pulses_at(start_period, end_period)
        if start_pulse is None or end_pulse is None:
            return None
        output_sum = consumption_between_two_pulses(start_pulse, end_pulse, self.output_meter.meter_model.digits)

        return input_sum - output_sum

    def calculate_inflow_between(self, start_period, end_period):
        """
        Subtracts the last pulse's reading from the first pulse's reading and returns the value.
        Does not take into consideration that pulses may have cycled through a digits overflow cycle more than 1 time.
        Returns 0 if a critical pulse is missing.

        :param start_period: inclusive
        :param end_period: inclusive
        """

        start_pulse, end_pulse = self.output_meter.get_pulses_at(start_period, end_period)
        if start_pulse is None or end_pulse is None:
            return None

        return consumption_between_two_pulses(start_pulse, end_pulse, self.output_meter.meter_model.digits)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.key = next_transmission_line_key()
        super().save(*args, **kwargs)

    def len_active_meters(self):
        # OPTIMIZE
        return len(list(filter(bool, (self.input_meter.exists(), self.output_meter.exists()))))

    def has(self, meter):
        return self.id in (meter.tsm_input_id, meter.tsm_output_id)

    def __str__(self):
        return self.key


class TankLevelTransmitter(models.Model):
    key = models.CharField(max_length=9, unique=True, blank=True)
    reading = models.DecimalField(max_digits=13, decimal_places=5)
    reading_factor = models.DecimalField(max_digits=9, decimal_places=4, default=1, blank=True)
    reading_offset = models.DecimalField(max_digits=13, decimal_places=5, default=0, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.key = next_transmission_line_key()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.key


# Zone Consumption
class QuarterHourlyZoneConsumption(models.Model):
    zone_id = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING, related_name='qh_consumption_set')
    datetime = models.DateTimeField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.datetime.strftime("%Y-%m-%d %H:%M") + " (" + self.zone_id.name + ")"

class DailyZoneConsumption(models.Model):
    zone_id = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING, related_name='daily_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)
    p_dawn = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_noon = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_afternoon = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_evening = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_nighttime = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)

    def __str__(self):
        return self.date.strftime("%Y %b. %d") + " (" + self.zone_id.name + ")"

class MonthlyZoneConsumption(models.Model):
    zone_id = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING, related_name='monthly_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)
    billed_consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)
    p_week1 = models.DecimalField(max_digits=13, decimal_places=6, default=0, blank=True)
    p_week2 = models.DecimalField(max_digits=13, decimal_places=6, default=0, blank=True)
    p_week3 = models.DecimalField(max_digits=13, decimal_places=6, default=0, blank=True)
    p_week4 = models.DecimalField(max_digits=13, decimal_places=6, default=0, blank=True)

    def __str__(self):
        return self.date.strftime("%B, %Y") + " (" + self.zone_id.name + ")"

class YearlyZoneConsumption(models.Model):
    zone_id = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING, related_name='yearly_consumption_set')
    year = models.IntegerField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)
    p_quarter1 = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_quarter2 = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_quarter3 = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)
    p_quarter4 = models.DecimalField(max_digits=13, decimal_places=3, default=0, blank=True)

    def __str__(self):
        return str(self.year) + " (" + self.zone_id.name + ")"

class DailyZoneLoss(models.Model):
    zone = models.ForeignKey(Zone, models.CASCADE, related_name='daily_losses', null=True)  # TODO: remove nullable before final makemigrations
    date = models.DateField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%Y %b. %d") + " (" + self.zone.__str__() + ")"

class MonthlyZoneLoss(models.Model):
    zone = models.ForeignKey(Zone, models.CASCADE, related_name='monthly_losses', null=True)  # TODO: remove nullable before final makemigrations
    date = models.DateField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%B, %Y") + " (" + self.zone.__str__() + ")"

class YearlyZoneLoss(models.Model):
    zone = models.ForeignKey(Zone, models.CASCADE, related_name='yearly_losses', null=True)  # TODO: remove nullable before final makemigrations
    year = models.IntegerField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return str(self.year) + " (" + self.zone.__str__() + ")"


# Zone Pressure
class HourlyAvgZonePressure(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING)
    time = models.DateTimeField()
    azp = models.DecimalField(max_digits=10, decimal_places=5)

class DailyAvgZonePressure(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING)
    date = models.DateField()
    azp = models.DecimalField(max_digits=10, decimal_places=5)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.date.strftime('%Y %b. %d')} ({self.zone.name})"

class MonthlyAvgZonePressure(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING)
    date = models.DateField()
    azp = models.DecimalField(max_digits=10, decimal_places=5)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.date.strftime('%B %Y')} ({self.zone.name})"

class YearlyAvgZonePressure(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.DO_NOTHING)
    year = models.PositiveSmallIntegerField()
    azp = models.DecimalField(max_digits=10, decimal_places=5)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.year} ({self.zone.name})"


# Transmission Line Consumption
class QuarterHourlyTSMInflow(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='qh_consumption_set')
    datetime = models.DateTimeField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.datetime.strftime("%Y-%m-%d %H:%M") + " (" + self.transmission_line.key + ")"

class DailyTSMInflow(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='daily_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%Y %b. %d") + " (" + self.transmission_line.key.name + ")"

class MonthlyTSMInflow(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='monthly_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)
    billed_consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%B, %Y") + " (" + self.transmission_line.key + ")"

class YearlyTSMInflow(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='yearly_consumption_set')
    year = models.IntegerField()
    consumption = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return str(self.year) + " (" + self.transmission_line.key + ")"

class DailyTSMLossRecord(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='daily_losses')
    date = models.DateField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%Y %b. %d") + " (" + self.transmission_line.key + ")"

class MonthlyTSMLossRecord(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='monthly_losses')
    date = models.DateField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return self.date.strftime("%B, %Y") + " (" + self.transmission_line.key + ")"

class YearlyTSMLossRecord(models.Model):
    transmission_line = models.ForeignKey(TransmissionLine, models.CASCADE, related_name='yearly_losses')
    year = models.IntegerField()
    loss = models.DecimalField(max_digits=13, decimal_places=3, null=True)

    def __str__(self):
        return str(self.year) + " (" + self.transmission_line.key + ")"


# Chlorine Levels
class HourlyAvgChlorineLevel(models.Model):
    sensor = models.ForeignKey(to=ChlorineSensor, on_delete=models.PROTECT)
    time = models.DateTimeField()
    level = models.DecimalField(max_digits=13, decimal_places=3)

    def __str__(self):
        return f"{self.time.strftime(settings.DATETIME_FORMAT)} ({self.sensor.key}) : {self.level}"

class DailyAvgChlorineLevel(models.Model):
    sensor = models.ForeignKey(to=ChlorineSensor, on_delete=models.PROTECT)
    date = models.DateField()
    level = models.DecimalField(max_digits=13, decimal_places=3)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.date.strftime(settings.DATE_FORMAT)} ({self.sensor.key}) : {self.level}"

class MonthlyAvgChlorineLevel(models.Model):
    sensor = models.ForeignKey(to=ChlorineSensor, on_delete=models.PROTECT)
    date = models.DateField()
    level = models.DecimalField(max_digits=13, decimal_places=3)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.date.strftime('%B %Y')} ({self.sensor.key}) : {self.level}"

class YearlyAvgChlorineLevel(models.Model):
    sensor = models.ForeignKey(to=ChlorineSensor, on_delete=models.PROTECT)
    year = models.PositiveSmallIntegerField()
    level = models.DecimalField(max_digits=13, decimal_places=3)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.year} ({self.sensor.key}) : {self.level}"

class TankLevel(models.Model):
    datetime = models.DateTimeField(primary_key=True)
    tank = models.ForeignKey(Tank, models.CASCADE)
    level = models.DecimalField(decimal_places=3, max_digits=13)

    def __str__(self):
        return f"{self.tank} | ({self.datetime.strftime(settings.DATETIME_FORMAT)})"

# deprecated:
class HourlyAvgConsumption(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='hourly_averages')
    hour_of_day = models.PositiveSmallIntegerField()
    amount = models.DecimalField(decimal_places=3, max_digits=10, null=True)
    weight = models.PositiveSmallIntegerField()

class DailyAvgConsumption(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='daily_averages')
    day_of_week = models.PositiveSmallIntegerField()
    amount = models.DecimalField(decimal_places=3, max_digits=10, null=True)
    weight = models.PositiveSmallIntegerField()

class MonthlyAvgConsumption(models.Model):
    zone = models.ForeignKey(to=Zone, on_delete=models.CASCADE, related_name='monthly_averages')
    month_of_year = models.PositiveSmallIntegerField()
    amount = models.DecimalField(decimal_places=3, max_digits=10, null=True)
    weight = models.PositiveSmallIntegerField()

