import csv
import datetime as dt
import itertools
import json
from functools import reduce
from json import JSONEncoder

import pytz
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Avg, F
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now, make_aware, localtime
from django.views.decorators.csrf import csrf_exempt
from flexdict import FlexDict
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from fl_dashboard.tools import clean_since_until_date
from . import stats
from .models import Zone, DailyZoneConsumption, Meter, Pulse, PressurePulse, Alert, Customer, PressureTransmitter, \
    MonthlyZoneConsumption, LossRecord, QuarterHourlyZoneConsumption, TransmissionLine, ChlorineSensorPulse
from .serializers import MeterSerializer, PulseSerializer, PressurePulseSerializer, TimestampedPulseSerializer, \
    DatesToStrings, SinceUntilSerializer, ChlorineSensorPulseSerializer, TimestampedPressurePulseSerializer
from .tools import consumption_between_two_pulses, get_now, datetime_ticks

DATETIME_FORMAT = settings.DATETIME_FORMAT


class MeterViewSet(viewsets.ModelViewSet):
    queryset = Meter.objects.all()
    serializer_class = MeterSerializer


class PulseViewSet(viewsets.ModelViewSet):
    permission_classes = ()
    queryset = Pulse.objects.all()
    serializer_class = PulseSerializer
    http_method_names = ['get', 'post', 'head']


class PressurePulseViewSet(viewsets.ModelViewSet):
    permission_classes = ()
    queryset = PressurePulse.objects.all()
    serializer_class = PressurePulseSerializer
    http_method_names = ['get', 'post', 'head']


class ChlorinePulseViewSet(viewsets.ModelViewSet):
    permission_classes = ()
    queryset = ChlorineSensorPulse.objects.all()
    serializer_class = ChlorineSensorPulseSerializer
    http_method_names = ['get', 'post', 'head']


class ConfigView(APIView):

    def post(self, request, format=None):
        meter = Meter.objects.create()
        data = {'id': meter.id, 'token': meter.key}
        return Response(data=data, status=status.HTTP_200_OK)


# I think this is not used anymore
class MetersSummary(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):

        return_dict = {
            'data': []
        }

        all_meters = Meter.objects.all()

        for meter in all_meters:
            last_two_pulses = meter.get_last_two_pulses()

            status_string = "Good"
            if meter.leak_status == 3:
                status_string = "Leak"

            last_pulse = last_two_pulses[0] if len(last_two_pulses) > 0 else Pulse()
            previous_pulse = last_two_pulses[1] if len(last_two_pulses) > 1 else Pulse()

            return_dict["data"].append({
                "id": meter.id,

                "last_reading": last_pulse.display_reading(),
                "last_time": last_pulse.time.strftime(DATETIME_FORMAT) if last_pulse.time is not None else "N/A",

                "previous_reading": previous_pulse.display_reading(),
                "previous_time": previous_pulse.time.strftime(DATETIME_FORMAT) if previous_pulse.time is not None else "N/A",

                "consumption": 5,
                "average_consumption": 4.333,
                "status_string": status_string
            })

        return Response(return_dict)


class AlertsSummary(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):

        return_dict = {
            'data': []
        }

        # this will also include meters with a N/A status
        all_alerts = Alert.objects.all().select_related('zone')

        for alert in all_alerts:

            return_dict["data"].append({
                "alert_key": alert.key,
                "alert_id": alert.pk,
                "datetime": alert.datetime.strftime(DATETIME_FORMAT),
                "zone_name": alert.zone.name,
                "zone_id": alert.zone_id,
                "loss_amount": alert.loss_amount,
            })

        return Response(return_dict)


class BulkMetersConsumption(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }

        bulk_meters = Meter.objects.filter(meter_model__bulk_meter=True).select_related('meter_model')

        for meter in bulk_meters:
            last_two_pulses = meter.get_last_two_pulses()

            last_pulse = last_two_pulses[0] if len(last_two_pulses) > 0 else None
            previous_pulse = last_two_pulses[1] if len(last_two_pulses) > 1 else None

            if last_pulse is None or previous_pulse is None:
                consumption_value = 'N/A'
            else:
                consumption_value = consumption_between_two_pulses(previous_pulse, last_pulse, meter.meter_model.digits)

            return_dict["data"].append({
                "meter_key": meter.key,

                "last_reading": last_pulse.normalized_reading if last_pulse else "N/A",
                "last_time": last_pulse.time.strftime(DATETIME_FORMAT) if last_pulse is not None else "N/A",

                "previous_reading": previous_pulse.normalized_reading if previous_pulse else "N/A",
                "previous_time": previous_pulse.time.strftime(DATETIME_FORMAT) if previous_pulse else "N/A",

                "consumption": consumption_value,
                "average_consumption": 0,
            })

        return Response(return_dict)


class DetailedMetersConsumption(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        from random import randrange
        return_dict = {
            'data': []
        }

        detailed_meters = Meter.objects.filter(meter_model__bulk_meter=False)

        for meter in detailed_meters:
            last_two_pulses = meter.get_last_two_pulses()

            alerts_number = Alert.objects.filter(meter_id__exact=meter.pk).count()

            last_pulse = last_two_pulses[0] if len(last_two_pulses) > 0 else Pulse()
            previous_pulse = last_two_pulses[1] if len(last_two_pulses) > 1 else Pulse()

            return_dict["data"].append({
                "meter_key": meter.key,
                "customer_name": meter.customer.name,

                "last_reading": last_pulse.display_reading(),
                "last_time": last_pulse.time.strftime(DATETIME_FORMAT) if last_pulse.time is not None else "N/A",

                "previous_reading": previous_pulse.display_reading(),
                "previous_time": previous_pulse.time.strftime(
                    DATETIME_FORMAT) if previous_pulse.time is not None else "N/A",

                "consumption": 0,
                "average_consumption": 0,
                "alerts_no": alerts_number
            })

        return Response(return_dict)


class MetersList(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }
        only_with_coords = self.request.query_params.get('onlyWithCoords', None)

        # Queryset filtering
        detailed_meters = Meter.objects.all().select_related('meter_model', 'customer', 'location')
        if only_with_coords:
            detailed_meters = detailed_meters.filter(location__geolocation__isnull=False)

        for meter in detailed_meters:
            try:
                customer_name = meter.customer.name
            except Customer.DoesNotExist:
                customer_name = ''

            try:
                location = meter.location.description
                latitude, longitude = meter.location.geolocation.lat, meter.location.geolocation.lon
            except AttributeError:
                latitude, longitude, location = ('',)*3

            return_dict["data"].append({
                "meter_id": meter.pk,
                "meter_serial": meter.serial_number,
                "meter_key": meter.key,
                "customer_name": customer_name,

                "manufacturer": meter.meter_model.manufacturer,
                "model_number": meter.meter_model.model_number,
                "is_bulk": "Yes" if meter.meter_model.bulk_meter else "No",
                "op_status": meter.get_op_status_name(),

                "installation_date": meter.installation_date.strftime(DATETIME_FORMAT) if meter.installation_date else "N/A",
                "location": location,
                "lat": latitude if only_with_coords else None,
                "lng": longitude if only_with_coords else None,
            })

        return Response(return_dict)


class PressureTransmittersList(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }
        only_with_coords = self.request.query_params.get('onlyWithCoords', None)

        # Queryset filtering
        transmitters = PressureTransmitter.objects.all().select_related('meter_model', 'location')
        if only_with_coords:
            transmitters = transmitters.filter(location__geolocation__isnull=False)

        for meter in transmitters:

            try:
                location = meter.location.description
                latitude, longitude = meter.location.geolocation.lat, meter.location.geolocation.lon
            except AttributeError:
                latitude, longitude, location = ('',)*3

            return_dict["data"].append({
                "meter_id": meter.pk,
                "meter_serial": meter.serial_number,
                "meter_key": meter.key,

                "manufacturer": meter.meter_model.manufacturer,
                "model_number": meter.meter_model.model_number,
                "op_status": meter.get_op_status_name(),

                "installation_date": meter.installation_date.strftime(DATETIME_FORMAT) if meter.installation_date else "N/A",
                "location": location,
                "lat": latitude if only_with_coords else None,
                "lng": longitude if only_with_coords else None,
            })

        return Response(return_dict)


class PressureReadings(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }

        transmitters = PressureTransmitter.objects.filter()

        for meter in transmitters:
            last_two_pulses = meter.get_last_two_pulses()

            last_pulse = last_two_pulses[0] if len(last_two_pulses) > 0 else Pulse()
            previous_pulse = last_two_pulses[1] if len(last_two_pulses) > 1 else Pulse()

            return_dict["data"].append({
                "meter_key": meter.key,

                "last_reading": last_pulse.display_reading(),
                "last_time": last_pulse.time.strftime(DATETIME_FORMAT) if last_pulse.time is not None else "N/A",

                "previous_reading": previous_pulse.display_reading(),
                "previous_time": previous_pulse.time.strftime(DATETIME_FORMAT) if previous_pulse.time is not None else "N/A"
            })

        return Response(return_dict)


class ZonesList(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }

        # Queryset filtering
        zones = Zone.objects.prefetch_related('coords')

        for zone in zones:
            coords_list = []

            for coord in zone.coords.all():
                coords_list.append({'lat': coord.latitude, 'lng': coord.longitude})

            return_dict["data"].append({
                "id": zone.id,
                "name": zone.name,
                "hex_color": zone.color,
                "coords": coords_list,
            })

        return Response(return_dict)


class TransmissionLinesList(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        return_dict = {
            'data': []
        }

        # Queryset filtering
        for tsm in TransmissionLine.objects.select_related('start_location', 'end_location'):
            return_dict["data"].append({
                "id": tsm.id,
                "key": tsm.key,
                "volume": tsm.volume,
                "coords": {
                    "inlet": {'lat': tsm.start_location.geolocation.lat, 'lng': tsm.start_location.geolocation.lon},
                    "outlet": {'lat': tsm.end_location.geolocation.lat, 'lng': tsm.end_location.geolocation.lon}
                },
            })

        return Response(return_dict)

@csrf_exempt
def dummy_view(request):
    from django.http import HttpResponse
    from django.conf import settings
    import os
    import json

    body = json.loads(request.body)
    reading = body['reading']

    with open(os.path.join(settings.BASE_DIR, 'log.txt'), 'a') as file:
        file.write(str(reading)+'\n')
    return HttpResponse("dummy_view")


def daily_reports_data(request):
    return_dict = FlexDict()
    # {
    #     "zoneStats":
    #     {
    #         zone.pk:
    #         [
    #               {
    #               "consumption": value,
    #               "average": value
    #               },
    #               {},{},{}, {},{},{}
    #         ]
    #     },
    #     "zoneMetaData": {}
    # }

    today = get_now()  # will be in UTC
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    day = int(request.GET.get('day', today.day))

    start_of_day = dt.datetime(year, month, day, tzinfo=pytz.utc)
    start_of_week = start_of_day - dt.timedelta(days=6)
    day_pointer_idx = 0
    for zone in Zone.objects.all():
        # loops through weekdays in descending order starting from the start_of_day.weekday()
        for weekday_idx in map(lambda x: (x+1)%7 + 1, range(start_of_day.weekday()+7, start_of_day.weekday(), -1)):
            try:
                day_record = DailyZoneConsumption.objects.only('consumption').get(zone_id=zone, date__week_day=weekday_idx, date__gte=start_of_week, date__lte=start_of_day)
            except DailyZoneConsumption.DoesNotExist:
                day_record = DailyZoneConsumption(consumption=0)
            return_dict["zoneStats"][zone.pk][day_pointer_idx]['consumption'] = day_record.consumption

            avg_record = DailyZoneConsumption.objects.filter(zone_id=zone, date__year=year, date__month=month, date__week_day=weekday_idx).aggregate(Avg('consumption'))
            return_dict["zoneStats"][zone.pk][day_pointer_idx]['average'] = avg_record['consumption__avg'] if avg_record['consumption__avg'] is not None else 0

            day_pointer_idx += 1

        day_pointer_idx = 0  # reset for other zones
        return_dict["zoneMetaData"][zone.pk]['name'] = zone.name

    return JsonResponse(return_dict)


def monthly_reports_data(request):
    return_dict = {
        "zoneStats": {},
        "zoneMetaData": {}
    }

    today = now()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    start_of_month = make_aware(dt.datetime(year, month, 1))
    end_of_month = make_aware(dt.datetime(year, month+1, 1) - dt.timedelta(days=1))

    for zone in Zone.objects.all():
        try:
            month_consumption_record = MonthlyZoneConsumption.objects.get(zone_id=zone, date__exact=start_of_month)
            return_dict["zoneStats"].update({zone.pk: {'consumption': month_consumption_record.consumption}})

            try:
                month_leak_records = LossRecord.objects.filter(zone=zone, date__gte=start_of_month, date__lt=end_of_month)
                month_leak = reduce(lambda acc, day_loss_record: day_loss_record.amount + acc, month_leak_records, 0)
                return_dict["zoneStats"][zone.pk].update({'leak': month_leak})
            except LossRecord.DoesNotExist:
                return_dict["zoneStats"][zone.pk].update({'leak': 0})

        except MonthlyZoneConsumption.DoesNotExist:
            return_dict["zoneStats"].update({zone.pk: {'consumption': 0}})
            return_dict["zoneStats"][zone.pk].update({'leak': 0})

        return_dict["zoneMetaData"].update({
            zone.pk: {"name": zone.name}
        })

    return JsonResponse(return_dict)


def consumption_of_hours_ago(request):
    hours_ago = int(request.GET.get('hours', 24))

    return_dict = FlexDict()
    return_dict["labels"] = []
    return_dict["values"] = []

    just = localtime().replace(minute=0, second=0, microsecond=0, tzinfo=pytz.utc)
    start_of_12h_ago = just - dt.timedelta(hours=hours_ago)
    qh_consumptions = QuarterHourlyZoneConsumption.objects.filter(datetime__gte=start_of_12h_ago)

    try:
        from fl_dashboard.customization import dashboard_stats
        if dashboard_stats['include_zones'] != '__all__':
            qh_consumptions = qh_consumptions.filter(zone_id_id__in=dashboard_stats['include_zones'])
    except Exception:
        pass

    for hours_ago in range(hours_ago, -1, -1):
        effective_period_start = (just - dt.timedelta(hours=hours_ago)).replace(minute=15)
        effective_period_end = effective_period_start + dt.timedelta(minutes=45)
        hour_cons = qh_consumptions.filter(datetime__gte=effective_period_start, datetime__lte=effective_period_end).aggregate(Sum('consumption'))
        try:
            hour_cons = round(hour_cons['consumption__sum'], 2)
        except:
            hour_cons = 0

        return_dict["labels"].append(effective_period_start.strftime(settings.HOURS_FORMAT))
        return_dict["values"].append(hour_cons)

    s = list(zip(return_dict['labels'], return_dict['values']))

    return JsonResponse(return_dict)


def flow_consumption_history(request):
    return HttpResponseBadRequest()


def azp_history(request):
    return HttpResponseBadRequest()


def generic_filtered_json_response(request, get_json_response):
    if request.method == 'GET':
        until = request.GET.get('until', None)
        since = request.GET.get('since', None)
        try:
            since, until = clean_since_until_date(since, until)
        except:
            return HttpResponseBadRequest("Invalid date parameter(s). Send date values in ISO 8601 format")

        if since > until:
            return HttpResponseBadRequest("Time period is reversed. `Since` is after `Until`")
        elif (until - since) >= dt.timedelta(days=31):
            return HttpResponseBadRequest("Time period can't be greater than 31 days")

        try:
            response = get_json_response(since, until)
        except Exception as e:
            response = {}
        return JsonResponse(response)

    return HttpResponseBadRequest()

@csrf_exempt
def overview_report_data(request):
    today = dt.datetime.combine(localtime().date(), dt.time.min).replace(tzinfo=pytz.utc)
    thirty_days_ago = today - dt.timedelta(days=30)

    res = 'months'

    from fl_dashboard.customization import overview_report
    response_dict = {
        'pies': {},
        'narrated_charts': {}
    }
    if 'network_input_today' in overview_report['pies']:
        response_dict['pies']['transmission_inflow'] = stats.inflow_per_transmission_line(thirty_days_ago, today, res)
        response_dict['pies']['transmission_loss'] = stats.loss_per_transmission_line(thirty_days_ago, today, res)
    if 'zone_consumption_today' in overview_report['pies']:
        response_dict['pies']['zone_consumption'] = stats.consumption_per_zone(thirty_days_ago, today, res)
        response_dict['pies']['zone_loss'] = stats.loss_per_zone(thirty_days_ago, today, res)
    if 'narrated_network_input' in overview_report['narration_charts']:
        response_dict['narrated_charts']['narrated_network_input'] = stats.narrated_input(thirty_days_ago, today, res)
    if 'narrated_zone_consumption' in overview_report['narration_charts']:
        response_dict['narrated_charts']['narrated_zone_consumption'] = stats.narrated_consumption(thirty_days_ago, today, 'days')

    return JsonResponse(json.dumps(response_dict, cls=DatesToStrings), safe=False)


def narrated_pressure_levels_overview_data(request):
    today = dt.datetime.combine(localtime().date(), dt.time.min).replace(tzinfo=pytz.utc)
    thirty_days_ago = today - dt.timedelta(days=30)

    response_dict = {
        'xAxisLabels': [],
        'datasets': [
            # {
            #     'label': '',
            #     'data': []
            # }
        ]
    }

    past_thirty_days = datetime_ticks(thirty_days_ago, today, 'days')
    for day in past_thirty_days:
        response_dict['xAxisLabels'].append(str(day))

    for pressure_sensor in PressureTransmitter.objects.all():
        dataset = {
            'label': pressure_sensor.key,
            'data': []
        }
        for day in past_thirty_days:
            start_of_day = dt.datetime.combine(day, dt.time.min)
            end_of_day = start_of_day + dt.timedelta(days=1)
            dataset['data'].append(PressurePulse.objects.filter(time__gte=start_of_day, time__lte=end_of_day, transmitter=pressure_sensor).aggregate(Avg('normalized_reading'))['normalized_reading__avg'])
        response_dict['datasets'].append(dataset)

    return JsonResponse(json.dumps(response_dict, cls=DatesToStrings), safe=False)

@csrf_exempt
def overview_stats(request):
    post = json.loads(request.body)

    su = SinceUntilSerializer(data=post)
    su.is_valid()

    since_last_24h = su.validated_data['since']
    until_last_24h = su.validated_data['until']
    res = post['res']

    since_this_day = since_last_24h.replace(hour=0, minute=0, second=0, microsecond=0)
    until_this_day = until_last_24h.replace(hour=23, minute=59, second=59, microsecond=0)

    from fl_dashboard.customization import overview_report
    response_dict = {
        'pies': {},
        'narrated_charts': {}
    }
    if 'network_input_today' in overview_report['pies']:
        response_dict['pies']['transmission_inflow'] = stats.inflow_per_transmission_line(since_this_day, until_this_day, res)
        response_dict['pies']['transmission_loss'] = stats.loss_per_transmission_line(since_this_day, until_this_day, res)
    if 'zone_consumption_today' in overview_report['pies']:
        response_dict['pies']['zone_consumption'] = stats.consumption_per_zone(since_this_day, until_this_day, res)
        response_dict['pies']['zone_loss'] = stats.loss_per_zone(since_this_day, until_this_day, res)
    if 'narrated_network_input' in overview_report['narration_charts']:
        response_dict['narrated_charts']['narrated_network_input'] = stats.narrated_input(since_last_24h, until_last_24h, res)
    if 'narrated_zone_consumption' in overview_report['narration_charts']:
        response_dict['narrated_charts']['narrated_zone_consumption'] = stats.narrated_consumption(since_last_24h, until_last_24h, res)

    return JsonResponse(json.dumps(response_dict, cls=DatesToStrings), safe=False)

@csrf_exempt
def narrated_chlorine_level(request):
    post = json.loads(request.body)
    su = SinceUntilSerializer(data=post)
    su.is_valid()
    since = su.validated_data['since']
    until = su.validated_data['until']
    aggregation_period = post['res']
    sensors = post['sensors']
    return JsonResponse(json.dumps(stats.narrated_chlorine_level(since, until, sensors, aggregation_period), cls=DatesToStrings), safe=False)


def flow_pulses_history(request):
    def get_json_response(since, until):
        server_timezone = localtime().tzinfo
        since = since.replace(tzinfo=server_timezone)
        until = until.replace(tzinfo=server_timezone)
        pulses = Pulse.objects.filter(time__gte=since, time__lte=until)\
            .select_related('meter', 'meter__input_for', 'meter__output_for')\
            .only('id', 'reading', 'time', 'meter_id', 'meter__key', 'meter__input_for__name', 'meter__output_for__name')

        def transform_pulse_to_response(entry: Pulse):
            return {
                'id': entry.id,
                'reading': entry.display_reading(),
                'raw_reading': entry.reading,
                'time': entry.time.strftime(DATETIME_FORMAT),
                'timestamp': entry.time.timestamp(),
                'meter_id': entry.meter_id,
                'meter_key': entry.meter.key,
                'input_zone_name': entry.meter.input_for.name if entry.meter.input_for else None,
                'output_zone_name': entry.meter.output_for.name if entry.meter.output_for else None,
            }

        return {'data': list(map(transform_pulse_to_response, pulses))}

    return generic_filtered_json_response(request, get_json_response)


def pressure_pulses_history(request):
    def get_json_response(since, until):
        pulses = PressurePulse.objects.filter(time__gte=since, time__lte=until)\
            .select_related('transmitter').only('id', 'reading', 'time', 'transmitter_id', 'transmitter__key')

        def pulse_to_json(entry: PressurePulse):
            return {
                'id': entry.id,
                'raw_reading': entry.reading,
                'reading': entry.display_reading(),
                'time': entry.time.strftime(DATETIME_FORMAT),
                'transmitter_id': entry.transmitter_id,
                'transmitter_key': entry.transmitter.key,
            }

        return {'data': list(map(pulse_to_json, pulses))}

    return generic_filtered_json_response(request, get_json_response)


def unix_time(request):
    import time
    return HttpResponse(time.time())


class UnixStampedPulse(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        pulse = TimestampedPulseSerializer(data=request.data)
        if pulse.is_valid():
            pulse.save()
            return Response(pulse.validated_data)
        return Response(pulse.errors, status=400)

class UnixStampedPressurePulse(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        pulse = TimestampedPressurePulseSerializer(data=request.data)
        if pulse.is_valid():
            pulse.save()
            return Response(pulse.validated_data)
        return Response(pulse.errors, status=400)


def recent_qh(request):
    just_now = localtime().replace(minute=0, second=0, microsecond=0, tzinfo=pytz.utc)
    before_36_hours = just_now - dt.timedelta(hours=36)

    response = HttpResponse()
    response['Content-Type'] = 'text/plain; charset=utf-8'
    response['Content-Disposition'] = 'inline'
    writer = csv.writer(response)

    writer.writerow(['id', 'datetime', 'consumption', 'zone_id'])

    for record in QuarterHourlyZoneConsumption.objects.filter(datetime__gte=before_36_hours, datetime__lte=just_now):
        writer.writerow([record.id, record.datetime, record.consumption, record.zone_id_id])

    return response


def flow_meter_narrate(request):
    since = request.GET.get('from')
    until = request.GET.get('to')
    if not all((since, until)):
        return HttpResponseBadRequest("Invalid query parameters. Must include `from` and `to` parameters.")

    try:
        since = parse_datetime(since)
        until = parse_datetime(until)
        if not all((since, until)):
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("Invalid time parameters format. Valid format is YYYY-MM-DD HH:MM[+00:00]")

    meters = request.GET.getlist('meters[]')
    exclude_meters = request.GET.getlist('exclude-meters[]')
    if meters and exclude_meters:
        return HttpResponseBadRequest("Request must include either `meters` or `exclude_meters` parameter, but not both.")


    resolution = request.GET.get('resolution')
    if not resolution:
        def guess_resolution(since, until):
            return 'hours'

        resolution = guess_resolution(since, until)

    # TODO: Replace with a flowrate table instead of this crap
    pulses_qs = QuarterHourlyZoneConsumption.objects.filter(datetime__range=(since, until)).order_by('datetime')

    if exclude_meters:
        pulses_qs = pulses_qs.exclude(meter_id__in=list(map(int, exclude_meters)))
    elif meters:
        pulses_qs = pulses_qs.filter(zone_id__input_meters__in=list(map(int, meters)))

    def time_resolution(datetime: dt.datetime, resolution):
        if resolution == 'hours':
            resolution = "%Y-%m-%dT%H:00"
        elif resolution == 'days':
            resolution = "%Y-%m-%dT00:00"
        elif resolution == 'months':
            resolution = "%Y-%m-01T00:00"
        elif resolution == 'years':
            resolution = "%Y-01-01T00:00"

        return datetime.strftime(resolution)

    if resolution == 'minutes':
        return_list = pulses_qs.values('time', reading=F('normalized_reading'))
    else:
        pulse_chunks = itertools.groupby(pulses_qs, lambda pulse: time_resolution(pulse.datetime - dt.timedelta(minutes=15), resolution))
        return_list = []
        for resolution_group, pulses in pulse_chunks:
            return_list.append({
                'time': resolution_group,
                'reading': sum([pulse.consumption for pulse in pulses])
            })

    return JsonResponse(json.dumps(return_list, cls=DatesToStrings), safe=False)


def detected_anomalies(request):
    import pandas as pd
    from adtk.detector import PersistAD, SeasonalAD

    from adtk.visualization import plot
    import matplotlib.pyplot as plt

    since = request.GET.get('since')
    until = request.GET.get('until')
    meters_ids = list(map(int, request.GET.getlist('metersIds[]')))

    since = parse_datetime(since)
    org_since = since
    since = since - dt.timedelta(days=14)
    until = parse_datetime(until)

    flow_readings = list(Pulse.objects.filter(time__gte=since, time__lte=until).order_by('time'))

    return_dict = {
        'timestamps': list(map(lambda val: val.isoformat(), datetime_ticks(org_since, until, 'minutes'))),
        'metersData': {meter_id: dict() for meter_id in meters_ids}
    }

    for meter_id in meters_ids:
        meter_pulses = list(filter(lambda pulse: pulse.meter_id == meter_id, flow_readings))

        if len(meter_pulses) == 0:
            continue

        pulses_df = pd.DataFrame(
            zip(
                [pulse.time for pulse in meter_pulses],
                [float(pulse.normalized_reading) for pulse in meter_pulses],
            ),
            columns=['time', 'reading']
        )
        pulses_df = pulses_df.set_index('time')
        pulses_df_resampler = pulses_df.resample('15min')
        pulses_df = pulses_df_resampler.interpolate()
        pulses_df['reading'] = pulses_df['reading'].diff().map(lambda x: round(x, 3))

        persist_ad = PersistAD()
        seasonal_ad = SeasonalAD()
        anomalies = persist_ad.fit_detect(pulses_df)

        return_dict['metersData'][meter_id] = {
            'flow': [],
            'anomalies': [],
        }

        for flow_series, anomaly_series in zip(pulses_df.iterrows(), anomalies.iterrows()):
            if flow_series[0] < org_since:
                continue

            flow_value = flow_series[1][0]
            is_anomaly = anomaly_series[1][0] is True

            if not is_anomaly:
                try:
                    pulse_lookup = filter(lambda p: p.time == flow_series[0], meter_pulses)
                    found_pulse = next(pulse_lookup)
                    is_anomaly = found_pulse.anomaly
                except StopIteration:
                    pass

            return_dict['metersData'][meter_id]['flow'].append(None if pd.isnull(flow_value) else flow_value)
            return_dict['metersData'][meter_id]['anomalies'].append(is_anomaly)

    return JsonResponse(return_dict)

