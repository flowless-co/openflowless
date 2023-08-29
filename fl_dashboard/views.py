from functools import reduce

from django.contrib.auth.decorators import login_required
from django.db.models import Value as V, Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import utc
from django.views.generic import TemplateView
from rest_framework.response import Response
from django.shortcuts import render
from rest_framework.views import APIView

from fl_meters.models import Zone, LossRecord, Notification
from fl_meters.tools import get_day_opening, get_day_start
from . import models
from .tools import *


@login_required
def home(request):
    context = homepage_stats()
    context.update({
        'alert_notifications': Notification.objects.filter(user=request.user, alert__isnull=False).count()
    })
    return render(request, template_name='fl_dashboard/dashboard/home.html', context=context)

@login_required
def overview_reports(request):
    from .customization import overview_report
    context = {
        'narration_charts': overview_report['narration_charts'],
        'pies': overview_report['pies']
    }
    return render(request, template_name='fl_dashboard/dashboard/reports/overview.html', context=context)

@login_required
def daily_reports(request):
    today = get_day_start(get_now())
    today_consumption = DailyZoneConsumption.objects.filter(date=today).aggregate(Sum('consumption'))['consumption__sum']
    today_consumption = round(today_consumption, 2) if today_consumption is not None else '---'
    today_avg = DailyAvgConsumption.objects.filter(day_of_week=today.weekday()).aggregate(Avg('amount'))['amount__avg']
    today_avg = round(today_avg, 2) if today_avg is not None else '---'

    yesterday = today - dt.timedelta(days=1)
    yesterday_loss = LossRecord.objects.filter(date=yesterday).aggregate(Sum('amount'))['amount__sum']
    if yesterday_loss is None:
        yesterday_loss = '---'
        yesterday_loss_percentage = None
    else:
        yesterday_consumption = DailyZoneConsumption.objects.filter(date=yesterday).aggregate(Sum('consumption'))['consumption__sum']
        try:
            yesterday_loss_percentage = str(round(yesterday_loss / yesterday_consumption, 2) * 100) + "%"
        except:  # catches: yesterday_consumption == 0, or yesterday_consumption == None
            yesterday_loss_percentage = None

    context = {
        'list_of_months': list(range(1, 13)),
        'list_of_days': list(range(32)),
        'this_year': today.year,
        'this_month': today.month,
        'this_day': today.day,
        'today_consumption': today_consumption,
        'today_avg': today_avg,
        'yesterday_loss': yesterday_loss,
        'yesterday_loss_percentage': yesterday_loss_percentage
    }
    return render(request, template_name='fl_dashboard/dashboard/daily_reports.html', context=context)


@login_required
def monthly_reports(request):
    today = get_now()
    from datetime import datetime
    beginning_of_month = datetime(today.year, today.month, 1).replace(tzinfo=utc)

    month_consumption = 1  # prevents division by zero exception in new systems
    month_nrw = 0
    all_zones = Zone.objects.all()
    for zone in all_zones:
        month_record = MonthlyZoneConsumption.objects.filter(zone_id=zone, date=beginning_of_month).first()
        month_consumption += month_record.consumption if month_record is not None else 0
        month_nrw += reduce(
            lambda acc, record: record.amount + acc,
            LossRecord.objects.filter(zone=zone, date__gte=beginning_of_month),
            0)

    context = {
        'month_consumption': round(month_consumption, 2),
        'month_nrw_percentage': round(month_nrw / month_consumption * 100, 2),
        'burst_alerts': "---",
        'year': today.year,
        'month': today.month,
        'list_of_months': list(range(1, 13))
    }
    return render(request, template_name='fl_dashboard/dashboard/monthly_reports.html', context=context)

@login_required
def alerts(request):
    Notification.objects.filter(user=request.user).delete()
    return render(request, template_name='fl_dashboard/dashboard/alerts.html')

def detected_anomalies(request):
    ctx = {
        'meters': Meter.objects.all()
    }
    return render(request, template_name='fl_dashboard/dashboard/detected_anomalies.html', context=ctx)

class FlowPulsesHistory(TemplateView):
    template_name = 'fl_dashboard/dashboard/flow_pulses_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update({
            'meters': Meter.objects.all()
        })
        return context


class DashboardJson(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, format=None):
        prefs, created = models.Preferences.objects.get_or_create(id=1, defaults={'geolocation': '0,0'})

        return Response({
            'mapCenterLat': prefs.geolocation.lat,
            'mapCenterLng': prefs.geolocation.lon,
            'mapZoomLevel': prefs.mapZoom,
            'mapTypeId': 'hybrid',
        })
