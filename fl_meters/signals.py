import datetime as dt
import logging
import pytz

from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Meter, MeterToken, Pulse, QuarterHourlyZoneConsumption, DailyZoneConsumption, \
    MonthlyZoneConsumption, YearlyZoneConsumption, OnHold, Zone, PressurePulse, DailyAvgZonePressure, \
    MonthlyAvgZonePressure, YearlyAvgZonePressure, HourlyAvgZonePressure, TransmissionLine, DailyTSMInflow, \
    MonthlyTSMInflow, QuarterHourlyTSMInflow, YearlyTSMInflow, YearlyTSMLossRecord, MonthlyTSMLossRecord,\
    DailyTSMLossRecord, ChlorineSensorPulse, DailyAvgChlorineLevel, HourlyAvgChlorineLevel, MonthlyAvgChlorineLevel,\
    YearlyAvgChlorineLevel
from .scripts import end_of_mnf_period_handler
from .tools import is_midnight, ries_between, consumption_between_two_pulses, get_sisters_of_pulse, \
    get_last_sisters_of_zone, datetime_ticks

lg = logging.getLogger(__name__)

@receiver(post_save, sender=Meter)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        MeterToken.objects.create(user=instance)


@receiver(post_save, sender=Pulse)
def on_flow_meter_pulse(sender, instance=None, created=False, **kwargs):
    instance: Pulse
    if created:
        try:
            from .custom_signal_handlers import ignore_meter
            if instance.meter_id in ignore_meter:
                lg.info(f"ignoring analysis of pulse ID:{instance.id} from meter ID:{instance.meter_id}")
                return
        except Exception:
            pass

        pulse_time = (instance.time.astimezone(pytz.utc)).replace(second=0, microsecond=0)

        # this pulse is coming from a meter installed on a transmission line
        if instance.meter.tsm_input_id or instance.meter.tsm_output_id:
            lg.info(f"starting transmission line analysis of pulse ID:{instance.id} from meter ID:{instance.meter_id}")
            # check if pulse was awaited for
            on_hold_entries = [on_hold for on_hold in OnHold.objects.all() if on_hold.is_awaiting(instance)]

            already_processed = set()
            for on_hold in on_hold_entries:

                if on_hold.ready_on == 1:
                    late_pulse = pulse_time != on_hold.time
                elif on_hold.ready_on == 2:
                    late_pulse = pulse_time.day == on_hold.time.day

                    if not pulse_time.day == on_hold.time.day and not pulse_time.day == on_hold.time.day + 1:
                        raise Exception(f"A pulse was captured by an OnHold entry that isn't relevant. {on_hold!r} {instance!r}")
                else:
                    raise Exception(f"A TSM OnHold entry has a bad ready_on value. {on_hold!r}")

                if late_pulse:
                    on_hold.past_pulses_arrived += 1
                else:
                    on_hold.current_pulses_arrived += 1
                    already_processed.add(on_hold.transmission_line_id)  # only ignore tsm if pulse is current

                on_hold.save()

                if on_hold.missing_pulses() == 0:
                    if on_hold.ready_on == 1:
                        time = pulse_time if not late_pulse else pulse_time + dt.timedelta(minutes=15)
                        lg.info(f"Inflow Record @({time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) for tsm ({on_hold.transmission_line}) is being created on arrival of pulse ({instance!r})")
                        create_inflow_record(time, on_hold.transmission_line)
                    else:
                        # here, pulse_time will only ever be a kickoff time or a closure time
                        loss_day = get_offset_time(pulse_time).date()
                        lg.info(f"Loss Record @({loss_day.strftime(settings.VERBOSE_DATE_FORMAT)}) for tsm ({on_hold.transmission_line}) is being created on arrival of pulse ({instance!r})")
                        create_loss_record(loss_day, on_hold.transmission_line)

                    on_hold.delete()

            for transmission_line in (instance.meter.tsm_input, instance.meter.tsm_output):
                if transmission_line is None:
                    continue

                # Create a LossRecord for that day
                if is_midnight(pulse_time) and transmission_line.id not in already_processed:
                    if Meter.objects.filter(tsm_input=transmission_line).exists():
                        OnHold.objects.create(
                            transmission_line=transmission_line, ready_on=2,
                            time=pulse_time-dt.timedelta(days=1), current_pulses_arrived=1,
                            past_pulses_arrived=Pulse.objects.filter(
                                Q(meter__tsm_input=transmission_line) | Q(meter__tsm_output=transmission_line),
                                time=pulse_time - dt.timedelta(hours=23, minutes=45)).count())

                # Create InflowRecords using output meters' pulses
                if instance.meter.tsm_output_id == transmission_line.id:  # if is_output
                    on_hold = OnHold.objects.create(
                        transmission_line=transmission_line, ready_on=1, time=pulse_time, current_pulses_arrived=1,
                        past_pulses_arrived=Pulse.objects.filter(
                            meter__tsm_output=transmission_line, time=pulse_time - dt.timedelta(minutes=15)).count())

                    if not on_hold.missing_pulses():
                        lg.info(f"Inflow Record @({pulse_time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) for tsm ({on_hold.transmission_line}) is being created on arrival of pulse ({instance!r})")
                        create_inflow_record(pulse_time, transmission_line)
                        on_hold.delete()

        # this pulse is coming from a meter installed on a zone border
        else:
            lg.info(f"starting zonal analysis of pulse ID:{instance.id} from meter ID:{instance.meter_id}")
            for zone in [instance.meter.input_for, instance.meter.output_for]:
                if zone is None:
                    lg.debug(f"skipping empty zone")
                    continue

                current_sisters = get_sisters_of_pulse(instance, zone)

                if current_sisters is None:
                    # Not all sisters have arrived yet.
                    lg.debug(f"skipping pulse because not all sisters have arrived yet")
                    continue

                previous_sisters = get_last_sisters_of_zone(zone)
                if previous_sisters is None:
                    # previous_sisters will be None when no base pulses exist to calculate delta meter reading from
                    lg.debug(f"skipping pulse because no base sisters exist")
                    continue

                # Find the consumption of the zone, between the previous and current period
                get_inputs = lambda pulse, zone_id: pulse.meter.input_for_id == zone_id
                get_outputs = lambda pulse, zone_id: pulse.meter.output_for_id == zone_id
                previous_sisters_inputs = list(filter(lambda pulse: get_inputs(pulse, zone.id), previous_sisters))
                current_sisters_inputs = list(filter(lambda pulse: get_inputs(pulse, zone.id), current_sisters))
                previous_sisters_outputs = list(filter(lambda pulse: get_outputs(pulse, zone.id), previous_sisters))
                current_sisters_outputs = list(filter(lambda pulse: get_outputs(pulse, zone.id), current_sisters))
                input_sum = 0
                output_sum = 0
                for previous_pulse, current_pulse in zip(previous_sisters_inputs, current_sisters_inputs):
                    input_sum += consumption_between_two_pulses(previous_pulse, current_pulse, current_pulse.meter.meter_model.digits)
                for previous_pulse, current_pulse in zip(previous_sisters_outputs, current_sisters_outputs):
                    output_sum += consumption_between_two_pulses(previous_pulse, current_pulse, current_pulse.meter.meter_model.digits)
                period_consumption = input_sum - output_sum

                # Update analytics tables. Fill if gap is detected
                current_time = current_sisters[0].time
                previous_time = previous_sisters[0].time

                ticks_between = datetime_ticks(previous_time, current_time, 'minutes')[1:]  # exclude the tick of previous_time
                if len(ticks_between) > 1:
                    logging.info(f"Gap detected, between {previous_time.strftime(settings.VERBOSE_DATETIME_FORMAT)} - "
                                 f"{current_time.strftime(settings.VERBOSE_DATETIME_FORMAT)}. Attempting to fill gap...")
                    if (current_time - previous_time) > dt.timedelta(days=2):
                        logging.debug(f"Gap is too large. Reseting...")

                        rie = previous_time
                        offset_date = (rie-dt.timedelta(minutes=settings.RIE)).date()

                        logging.debug(f"resetting at time: {rie.strftime(settings.VERBOSE_DATETIME_FORMAT)}")

                        consumption_per_rie = 0

                        QuarterHourlyZoneConsumption.objects.create(zone_id=zone, datetime=rie, consumption=consumption_per_rie)

                        daily_record, daily_record_created = DailyZoneConsumption.objects.get_or_create(
                            zone_id_id=zone.id, date=offset_date, defaults={'consumption': consumption_per_rie})
                        if not daily_record_created:
                            daily_record.consumption += consumption_per_rie
                            daily_record.save()

                        monthly_record, monthly_record_created = MonthlyZoneConsumption.objects.get_or_create(
                            zone_id_id=zone.id, date=offset_date.replace(day=1), defaults={'consumption': consumption_per_rie})
                        if not monthly_record_created:
                            monthly_record.consumption += consumption_per_rie
                            monthly_record.save()

                        yearly_record, yearly_record_created = YearlyZoneConsumption.objects.get_or_create(
                            zone_id_id=zone.id, year=offset_date.year, defaults={'consumption': consumption_per_rie})
                        if not yearly_record_created:
                            yearly_record.consumption += consumption_per_rie
                            yearly_record.save()

                        logging.warning(f"Large Gap Reseting Complete")

                        continue

                consumption_per_rie = period_consumption / len(ticks_between)

                for rie in ticks_between:
                    offset_date = (rie-dt.timedelta(minutes=settings.RIE)).date()

                    QuarterHourlyZoneConsumption.objects.create(
                        zone_id=zone, datetime=rie, consumption=consumption_per_rie)

                    daily_record, daily_record_created = DailyZoneConsumption.objects.get_or_create(
                        zone_id_id=zone.id, date=offset_date, defaults={'consumption': consumption_per_rie})
                    if not daily_record_created:
                        daily_record.consumption += consumption_per_rie
                        daily_record.save()

                    monthly_record, monthly_record_created = MonthlyZoneConsumption.objects.get_or_create(
                        zone_id_id=zone.id, date=offset_date.replace(day=1), defaults={'consumption': consumption_per_rie})
                    if not monthly_record_created:
                        monthly_record.consumption += consumption_per_rie
                        monthly_record.save()

                    yearly_record, yearly_record_created = YearlyZoneConsumption.objects.get_or_create(
                        zone_id_id=zone.id, year=offset_date.year, defaults={'consumption': consumption_per_rie})
                    if not yearly_record_created:
                        yearly_record.consumption += consumption_per_rie
                        yearly_record.save()

        # run celery task to detect anomalies each for previous day
        if instance.time.hour == 0 and instance.time.minute > 15:
            from fl_meters.tasks import label_anomalies
            day = (instance.time - dt.timedelta(days=1)).date().isoformat()
            label_anomalies(day)

@receiver(post_save, sender=PressurePulse)
def on_pressure_transmitter_pulse(sender, instance=None, created=False, **kwargs):
    if created:
        for association in instance.transmitter.associations.all():
            if association.use_for_azp:
                update_pressure_analytics(association.zone, instance, association.azp_factor)
        from .custom_signal_handlers import on_pressure_sensor
        on_pressure_sensor(instance)

@receiver(post_save, sender=ChlorineSensorPulse)
def on_chlorine_sensor_pulse(sender, instance=None, created=False, **kwargs):
    if created:
        update_chlorine_levels_analytics(instance)


def update_analytics(zone, *, period_start=None, period_end=None):
    if period_start is None or period_end is None:
        raise Exception("Period start and end times must be supplied.")

    consumption = zone.calculate_delta_consumption(period_start, period_end)

    QuarterHourlyZoneConsumption.objects.create(
        zone_id_id=zone.id,
        consumption=consumption,
        datetime=period_end
    )

    # if a past pulse is missing, consumption will be None and the only analytics entry that will
    # be created is a QuarterHourly record with a consumption of null.
    if consumption is None:
        return

    offset_day = period_start.date()

    # now update other accumulative ZATs
    daily_record, daily_record_created = DailyZoneConsumption.objects.get_or_create(
        zone_id_id=zone.id,
        date=offset_day,
        defaults={
            'zone_id_id': zone.id,
            'date': offset_day,
            'consumption': consumption
        })
    if not daily_record_created:
        daily_record.consumption += consumption
        daily_record.save()

    monthly_record, monthly_record_created = MonthlyZoneConsumption.objects.get_or_create(
        zone_id_id=zone.id,
        date=offset_day.replace(day=1),
        defaults={
            'zone_id_id': zone.id,
            'date': offset_day.replace(day=1),
            'consumption': consumption
        })
    if not monthly_record_created:
        monthly_record.consumption += consumption
        monthly_record.save()
    logging.getLogger(__name__).info(f"Monthly Record:{monthly_record_created}")

    yearly_record, yearly_record_created = YearlyZoneConsumption.objects.get_or_create(
        zone_id_id=zone.id,
        year=offset_day.year,
        defaults={
           'zone_id_id': zone.id,
           'year': offset_day.year,
           'consumption': consumption
       })
    if not yearly_record_created:
        yearly_record.consumption += consumption
        yearly_record.save()

    lg.info(
        f"Consumption Records Updated: For Zone ({zone}) Updated Successfully. "
        f"QH @({period_end.strftime(settings.VERBOSE_DATETIME_FORMAT)}) CREATED VALUE({consumption}) "
        f"Daily @({daily_record.date.strftime(settings.VERBOSE_DATE_FORMAT)}) {'CREATED' if daily_record_created else 'UPDATED'} VALUE({daily_record.consumption}) "
        f"Monthly  @({monthly_record.date.strftime(settings.VERBOSE_DATE_FORMAT)}) {'CREATED' if monthly_record_created else 'UPDATED'} VALUE({monthly_record.consumption}) "
        f"Yearly @({yearly_record.year}) {'CREATED' if yearly_record_created else 'UPDATED'} VALUE({yearly_record.consumption})"
    )

    if period_end.time() == dt.time(0, 0, 0):  # Calculate Losses at end of day # Rie
        previous_day = period_end.date() - dt.timedelta(days=1)
        mnf_start = dt.datetime.combine(previous_day, settings.MNF_START).replace(tzinfo=pytz.utc)
        mnf_end = dt.datetime.combine(previous_day, settings.MNF_END).replace(tzinfo=pytz.utc)
        end_of_mnf_period_handler(mnf_start, mnf_end, zone)



def update_pressure_analytics(zone, pulse, azp_factor):
    offset_time = (pulse.time.astimezone(pytz.utc)) - dt.timedelta(minutes=15)
    offset_date = offset_time.date()
    start_of_hour = offset_time.replace(minute=0, second=0, microsecond=0)
    pulse_reading = pulse.cleaned_reading() * azp_factor

    hourly_record, just_created = HourlyAvgZonePressure.objects.get_or_create(
        time=start_of_hour, zone=zone, defaults={'zone': zone, 'time': start_of_hour, 'azp': pulse_reading})
    if not just_created:
        period_start_time = offset_time.replace(minute=15)
        period_end_time = period_start_time + dt.timedelta(minutes=45)
        weight = PressurePulse.objects.filter(time__gte=period_start_time, time__lte=period_end_time).count() - 1  # exclude current pulse
        hourly_record.azp = weighted_average(hourly_record.azp, weight, pulse_reading)
        hourly_record.save()

    daily_record, just_created = DailyAvgZonePressure.objects.get_or_create(
        date=offset_date, zone=zone, defaults={'zone': zone, 'date': offset_date, 'weight': 1, 'azp': pulse_reading})
    if not just_created:
        daily_record.azp = weighted_average(daily_record.azp, daily_record.weight, pulse_reading)
        daily_record.weight += 1
        daily_record.save()

    monthly_record, just_created = MonthlyAvgZonePressure.objects.get_or_create(
        date=offset_date.replace(day=1), zone=zone,
        defaults={'zone': zone, 'date': offset_date.replace(day=1), 'weight': 1, 'azp': pulse_reading})
    if not just_created:
        monthly_record.azp = weighted_average(monthly_record.azp, monthly_record.weight, pulse_reading)
        monthly_record.weight += 1
        monthly_record.save()

    yearly_record, just_created = YearlyAvgZonePressure.objects.get_or_create(
        year=offset_date.year, zone=zone,
        defaults={'zone': zone, 'year': offset_date.year, 'weight': 1, 'azp': pulse_reading})
    if not just_created:
        yearly_record.azp = weighted_average(yearly_record.azp, yearly_record.weight, pulse.cleaned_reading())
        yearly_record.weight += 1
        yearly_record.save()

def update_chlorine_levels_analytics(pulse: ChlorineSensorPulse):
    offset_time = (pulse.time.astimezone(pytz.utc)) - dt.timedelta(minutes=15)
    offset_date = offset_time.date()
    start_of_hour = offset_time.replace(minute=0, second=0, microsecond=0)
    pulse_reading = pulse.cleaned_reading()

    hourly_record, just_created = HourlyAvgChlorineLevel.objects.get_or_create(
        time=start_of_hour, sensor=pulse.sensor, defaults={'level': pulse_reading})
    if not just_created:
        period_start_time = offset_time.replace(minute=15)
        period_end_time = period_start_time + dt.timedelta(minutes=45)
        weight = ChlorineSensorPulse.objects.filter(time__gte=period_start_time, time__lte=period_end_time).count() - 1  # exclude current pulse
        hourly_record.level = weighted_average(hourly_record.level, weight, pulse_reading)
        hourly_record.save()

    daily_record, just_created = DailyAvgChlorineLevel.objects.get_or_create(
        date=offset_date, sensor=pulse.sensor, defaults={'weight': 1, 'level': pulse_reading})
    if not just_created:
        daily_record.level = weighted_average(daily_record.level, daily_record.weight, pulse_reading)
        daily_record.weight += 1
        daily_record.save()

    monthly_record, just_created = MonthlyAvgChlorineLevel.objects.get_or_create(
        date=offset_date.replace(day=1), sensor=pulse.sensor, defaults={'weight': 1, 'level': pulse_reading})
    if not just_created:
        monthly_record.level = weighted_average(monthly_record.level, monthly_record.weight, pulse_reading)
        monthly_record.weight += 1
        monthly_record.save()

    yearly_record, just_created = YearlyAvgChlorineLevel.objects.get_or_create(
        year=offset_date.year, sensor=pulse.sensor, defaults={'weight': 1, 'level': pulse_reading})
    if not just_created:
        yearly_record.level = weighted_average(yearly_record.level, yearly_record.weight, pulse_reading)
        yearly_record.weight += 1
        yearly_record.save()


def weighted_average(current_avg, weight, new_value):
    return (current_avg * weight + new_value) / (weight + 1)

def django_orm_adapted_weekday(date):
    return (date.weekday() + 1) % 7 + 1

def get_offset_time(time: dt.datetime):
    return time - dt.timedelta(minutes=15)

def create_inflow_record(time: dt.datetime, transmission_line: TransmissionLine) -> None:
    """ Create inflow records for the time period that ends with `time` """

    consumption = transmission_line.calculate_inflow_between(get_offset_time(time), time)

    if consumption is None:
        raise ValueError("Missing Pulses")

    QuarterHourlyTSMInflow.objects.create(transmission_line=transmission_line, datetime=time, consumption=consumption)

    offset_day = get_offset_time(time).date()

    daily_record, created = DailyTSMInflow.objects.get_or_create(
        date=offset_day, transmission_line=transmission_line, defaults={'consumption': consumption})
    if not created:
        daily_record.consumption += consumption
        daily_record.save()

    monthly_record, created = MonthlyTSMInflow.objects.get_or_create(
        date=offset_day.replace(day=1), transmission_line=transmission_line, defaults={'consumption': consumption})
    if not created:
        monthly_record.consumption += consumption
        monthly_record.save()

    yearly_record, created = YearlyTSMInflow.objects.get_or_create(
        year=offset_day.year, transmission_line=transmission_line, defaults={'consumption': consumption})
    if not created:
        yearly_record.consumption += consumption
        yearly_record.save()


def create_loss_record(day: dt.date, transmission_line: TransmissionLine):
    loss = transmission_line.calculate_loss_of(day)

    if loss is None:
        raise ValueError("Missing Pulses")

    if loss <= transmission_line.volume:
        loss = 0
    else:
        loss -= transmission_line.volume

    daily_record, created = DailyTSMLossRecord.objects.get_or_create(
        date=day, transmission_line=transmission_line, defaults={'loss': loss})
    if not created:
        daily_record.loss += loss
        daily_record.save()

    monthly_record, created = MonthlyTSMLossRecord.objects.get_or_create(
        date=day.replace(day=1), transmission_line=transmission_line, defaults={'loss': loss})
    if not created:
        monthly_record.loss += loss
        monthly_record.save()

    yearly_record, created = YearlyTSMLossRecord.objects.get_or_create(
        year=day.year, transmission_line=transmission_line, defaults={'loss': loss})
    if not created:
        yearly_record.loss += loss
        yearly_record.save()



