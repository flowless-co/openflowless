from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r'pulse', views.PulseViewSet)
router.register(r'pressure', views.PressurePulseViewSet)
router.register(r'chlorine', views.ChlorinePulseViewSet)

app_name = "api"
urlpatterns = [
    path('new-meter/', views.ConfigView.as_view()),
    path('meters-summary/', views.MetersSummary.as_view()),
    path('meters-list/', views.MetersList.as_view()),
    path('transmitters-list/', views.PressureTransmittersList.as_view()),
    path('alerts-summary/', views.AlertsSummary.as_view()),
    path('bulk-meters-consumption/', views.BulkMetersConsumption.as_view(), name='bulk-meters-consumption'),
    path('detailed-meters-consumption/', views.DetailedMetersConsumption.as_view(), name='detailed-meters-consumption'),
    path('pressure-readings/', views.PressureReadings.as_view()),
    path('zones/', views.ZonesList.as_view()),
    path('transmission-lines/', views.TransmissionLinesList.as_view()),

    path('daily-reports-data/', views.daily_reports_data),
    path('monthly-reports-data/', views.monthly_reports_data),
    path('consumption-hours-ago/', views.consumption_of_hours_ago, name='consumption-hours-ago'),
    path('recent_qh/', views.recent_qh),

    path('analytics/flow-consumption/', views.flow_consumption_history),
    path('analytics/azp/', views.azp_history),
    path('pulses-history/flow/', views.flow_pulses_history),
    path('pulses-history/pressure/', views.pressure_pulses_history),

    path('unix-time/', views.unix_time),
    path('unix-pulse/', views.UnixStampedPulse.as_view()),
    path('unix-pressure-pulse/', views.UnixStampedPressurePulse.as_view()),

    path('stats/overview', views.overview_report_data),
    path('stats/narrated-pressure-levels-overview-data/', views.narrated_pressure_levels_overview_data),
    path('stats/narrated-chlorine-levels', views.narrated_chlorine_level, name="narrated-chlorine-levels"),

    path('detected-anomalies/', views.detected_anomalies, name="detected-anomalies"),

    path('flow-meter/narrate', views.flow_meter_narrate, name="flow-meter-narrate"),
]


