from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "dashboard"
urlpatterns = [
    path('', views.home, name="home"),
    path('alerts/', views.alerts, name="alerts"),
    path('reports/daily', views.daily_reports, name="daily_reports"),
    path('reports/monthly', views.monthly_reports, name="monthly_reports"),
    path('reports/overview', views.overview_reports, name='reports_overview'),

    path('viewmodel', views.DashboardJson.as_view(), name="viewmodel"),

    path('chlorine-level', TemplateView.as_view(template_name='fl_dashboard/dashboard/reports/chlorine-level.html')),

    path('pulses/flow', views.FlowPulsesHistory.as_view(), name="flow_pulses_history"),

    path('detected-anomalies', views.detected_anomalies, name="detected-anomalies-report"),

    path('pulses/pressure', TemplateView.as_view(template_name='fl_dashboard/dashboard/pressure_pulses_history.html'),
         name="pressure_pulses_history"),

    path('meters', TemplateView.as_view(template_name='fl_dashboard/dashboard/meters_list.html'),
         name="meters_list"),
    path('pressure-transmitters', TemplateView.as_view(template_name='fl_dashboard/dashboard/pressure_transmitters.html'),
         name="pressure_transmitters_list"),
    path('pressure-readings', TemplateView.as_view(template_name='fl_dashboard/dashboard/pressure_readings.html'),
         name="pressure_readings"),
    path('consumption/bulk', TemplateView.as_view(template_name='fl_dashboard/dashboard/bulk_consumption.html'),
         name="bulk_consumption"),
    path('consumption/detailed', TemplateView.as_view(template_name='fl_dashboard/dashboard/detailed_consumption.html'),
         name="detailed_consumption"),
]
