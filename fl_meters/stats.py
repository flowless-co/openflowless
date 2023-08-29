import datetime as dt
from decimal import Decimal
from typing import Dict, Union, List

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum

from fl_meters.models import QuarterHourlyTSMInflow, DailyTSMInflow, MonthlyTSMInflow, YearlyTSMInflow, \
    TransmissionLine, Zone, QuarterHourlyZoneConsumption, DailyZoneConsumption, MonthlyZoneConsumption, \
    YearlyZoneConsumption, \
    DailyTSMLossRecord, MonthlyTSMLossRecord, YearlyTSMLossRecord, DailyZoneLoss, MonthlyZoneLoss, YearlyZoneLoss, \
    ChlorineSensor, ChlorineSensorPulse, HourlyAvgChlorineLevel, DailyAvgChlorineLevel, MonthlyAvgChlorineLevel, \
    YearlyAvgChlorineLevel
from fl_meters.tools import datetime_ticks, round_down_to_ri

# == Transmission Line-based ==

def inflow_per_transmission_line(since: dt.datetime, until: dt.datetime, aggregator_string) -> Dict[str, Decimal]:
    # TOTEST: since and until are allowed to be equal
    # TOTEST: passing "wrong" datetime mid-month is allowed and is correctly fixed. same thing for other intervals

    def dry_tool(model, since, until, filter_field):
        return_dict = {
            # 'tsm.key': 'inflow value'
        }

        filters = {
            filter_field + '__gte': since,
            filter_field + '__lte': until,
        }
        for tsm in TransmissionLine.objects.all():
            return_dict[tsm.key] = model.objects.filter(transmission_line=tsm, **filters).aggregate(Sum('consumption'))['consumption__sum']

        return return_dict

    if aggregator_string == 'minutes':
        return dry_tool(QuarterHourlyTSMInflow, since, until, 'datetime')
    elif aggregator_string == 'days':
        return dry_tool(DailyTSMInflow, since.date(), until.date(), 'date')
    elif aggregator_string == 'months':
        return dry_tool(MonthlyTSMInflow, since.date().replace(day=1), until.date().replace(day=1), 'date')
    elif aggregator_string == 'yearly':
        return dry_tool(YearlyTSMInflow, since.year, until.year, 'year')
    else:
        raise ValueError("Bad Resolution Value")


def loss_per_transmission_line(since: dt.date, until: dt.date, aggregator_string) -> Dict[str, Decimal]:
    # TOTEST: since and until are allowed to be equal
    # TOTEST: passing "wrong" datetime mid-month is allowed and is correctly fixed. same thing for other intervals

    def dry_tool(model, since, until, filter_field):
        return_dict = {
            # 'tsm.key': 'inflow value'
        }

        filters = {
            filter_field + '__gte': since,
            filter_field + '__lte': until
        }

        for tsm in TransmissionLine.objects.all():
            return_dict[tsm.key] = model.objects.filter(transmission_line=tsm, **filters).aggregate(Sum('loss'))['loss__sum']

        return return_dict

    if aggregator_string == 'days' or aggregator_string == 'minutes':
        return dry_tool(DailyTSMLossRecord, since, until, 'date')
    elif aggregator_string == 'months':
        return dry_tool(MonthlyTSMLossRecord, since.replace(day=1), until.replace(day=1), 'date')
    elif aggregator_string == 'yearly':
        return dry_tool(YearlyTSMLossRecord, since.year, until.year, 'year')
    else:
        raise ValueError("Bad Resolution Value")


# == Zone-based ==

def consumption_per_zone(since: dt.datetime, until: dt.datetime, resolution) -> Dict[str, Decimal]:

    def dry_tool(model, since, until, filter_field):
        return_dict = {}
        filters = {
            filter_field + '__gte': since,
            filter_field + '__lte': until
        }
        for zone in Zone.objects.all():
            return_dict[zone.name] = model.objects.filter(zone_id=zone, **filters).aggregate(Sum('consumption'))['consumption__sum']

        return return_dict

    if resolution == 'minutes':
        return dry_tool(QuarterHourlyZoneConsumption, since, until, 'datetime')
    elif resolution == 'days':
        return dry_tool(DailyZoneConsumption, since.date(), until.date(), 'date')
    elif resolution == 'months':
        return dry_tool(MonthlyZoneConsumption, since.date().replace(day=1), until.date().replace(day=1), 'date')
    elif resolution == 'yearly':
        return dry_tool(YearlyZoneConsumption, since.year, until.year, 'year')
    else:
        raise ValueError("Bad Resolution Value")


def loss_per_zone(since: dt.datetime, until: dt.datetime, aggregator_string):
    def dry_tool(model, since, until, filter_field):
        return_dict = {
            # 'tsm.key': 'inflow value'
        }

        filters = {
            filter_field + '__gte': since,
            filter_field + '__lte': until
        }

        for zone in Zone.objects.all():
            return_dict[zone.name] = model.objects.filter(zone=zone, **filters).aggregate(Sum('loss'))['loss__sum']

        return return_dict

    if aggregator_string == 'days' or aggregator_string == 'minutes':
        return dry_tool(DailyZoneLoss, since, until, 'date')
    elif aggregator_string == 'months':
        return dry_tool(MonthlyZoneLoss, since.replace(day=1), until.replace(day=1), 'date')
    elif aggregator_string == 'yearly':
        return dry_tool(YearlyZoneLoss, since.year, until.year, 'year')
    else:
        raise ValueError("Bad Resolution Value")


# == Narrated ==

def narrated_input(since: dt.datetime, until, aggregation_period) -> Dict[dt.datetime, Decimal]:
    return_dict = {
        # 'date': 'value',
    }

    since = round_down_to_ri(since)

    for time_point in datetime_ticks(since, until, aggregation_period):
        aggregated_inflow_per_tsm = inflow_per_transmission_line(time_point, time_point, aggregation_period)
        return_dict[time_point] = sum(v or 0 for v in aggregated_inflow_per_tsm.values())

    return return_dict


def narrated_consumption(since: dt.datetime, until, aggregation_period) -> Dict[dt.datetime, Decimal]:
    return_dict = {
        # 'date': 'value',
    }

    since = round_down_to_ri(since)

    for time_point in datetime_ticks(since, until, aggregation_period):
        aggregated_consumption_per_zone = consumption_per_zone(time_point, time_point, aggregation_period)
        return_dict[time_point] = sum(v or 0 for v in aggregated_consumption_per_zone.values())

    return return_dict


def narrated_chlorine_level(since: dt.datetime, until, sensors: Union[List[int], str, int], aggregation_period) -> Dict[dt.datetime, Decimal]:
    is_single = isinstance(sensors, int)

    return_dict = {
        # 'date': 'value',
    }

    def dry_tool(time, aggregation_period, sensor_filter):

        if aggregation_period == 'minutes':
            model, date, attr = ChlorineSensorPulse, time, 'normalized_reading'
        elif aggregation_period == 'hours':
            model, date, attr = HourlyAvgChlorineLevel, time, 'level'
        elif aggregation_period == 'days':
            model, date, attr = DailyAvgChlorineLevel, time.date(), 'level'
        elif aggregation_period == 'months':
            model, date, attr = MonthlyAvgChlorineLevel, time.date().replace(day=1), 'level'
        elif aggregation_period == 'years':
            model, date, attr = YearlyAvgChlorineLevel, time.year, 'level'
        else:
            raise ValueError("Bad Aggregation Period")

        try:
            return model.objects.filter(time=time, **sensor_filter).aggregate(Sum(attr))[f'{attr}__sum']
        except:
            return None

    since = round_down_to_ri(since)

    for time_point in datetime_ticks(since, until, aggregation_period):
        if is_single:
            return_dict[time_point] = dry_tool(time_point, aggregation_period, {'sensor_id': sensors})
        else:
            if isinstance(sensors, str):
                if sensors != '__all__':
                    raise ValueError("Parameter `sensors` can only accept a list of number, or the value `__all__`")

                return_dict[time_point] = dry_tool(time_point, aggregation_period, {})

                # if aggregation_period == 'minutes':
                #     return_dict[time_point] = ChlorineSensorPulse.objects.filter(time=time_point).aggregate(Sum('normalized_reading'))['normalized_reading__sum']
                # elif aggregation_period == 'hours':
                #     return_dict[time_point] = HourlyAvgChlorineLevel.objects.filter(time=time_point).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'days':
                #     return_dict[time_point] = DailyAvgChlorineLevel.objects.filter(date=time_point.date()).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'months':
                #     return_dict[time_point] = MonthlyAvgChlorineLevel.objects.filter(date=time_point.date().replace(day=1)).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'years':
                #     return_dict[time_point] = YearlyAvgChlorineLevel.objects.filter(year=time_point.year).aggregate(Sum('level'))['level__sum']
                # else:
                #     raise ValueError("Bad Aggregation Period")

            elif isinstance(sensors, list):
                return_dict[time_point] = dry_tool(time_point, aggregation_period, {'sensor_id__in': sensors})

                # if aggregation_period == 'minutes':
                #     return_dict[time_point] = ChlorineSensorPulse.objects.filter(sensor_id__in=sensors, time=time_point).aggregate(Sum('normalized_reading'))['normalized_reading__sum']
                # elif aggregation_period == 'hours':
                #     return_dict[time_point] = HourlyAvgChlorineLevel.objects.filter(sensor_id__in=sensors, time=time_point).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'days':
                #     return_dict[time_point] = DailyAvgChlorineLevel.objects.filter(sensor_id__in=sensors, date=time_point.date()).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'months':
                #     return_dict[time_point] = MonthlyAvgChlorineLevel.objects.filter(sensor_id__in=sensors, date=time_point.date().replace(day=1)).aggregate(Sum('level'))['level__sum']
                # elif aggregation_period == 'years':
                #     return_dict[time_point] = YearlyAvgChlorineLevel.objects.filter(sensor_id__in=sensors, year=time_point.year).aggregate(Sum('level'))['level__sum']
                # else:
                #     raise ValueError("Bad Aggregation Period")
            else:
                raise ValueError("Parameter `sensors` can only accept a list of number, or the value `__all__`")

    return return_dict

