from django.contrib import admin
from django.urls import include, path, reverse_lazy
from rest_framework import routers
from django.views.generic.base import RedirectView

import fl_meters.urls as fl_meters_urls

router = routers.DefaultRouter()
router.registry.extend(fl_meters_urls.router.registry)

# Customize Admin panel titles
admin.site.site_header = "Flowless Administration"
admin.site.site_title = "Flowless Admin"
admin.site.index_title = "Admin Panel"
admin.site.site_url = reverse_lazy('dashboard:home')

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('api/', include(router.urls)),       # DRF API endpoints
    path('api/', include('fl_meters.urls')),  # Custom API endpoints
    path('dashboard/', include('fl_dashboard.urls'), name='index'),
    path('', include('fl_dashboard.auth_urls'), name='auth'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=True))
]
