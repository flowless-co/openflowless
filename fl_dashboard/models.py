from django.db import models
from django_google_maps import fields as map_fields


class Preferences(models.Model):
    clientScreenName = models.CharField(max_length=80, default='')
    address = map_fields.AddressField(max_length=200, null=True, verbose_name='Map Center Address')
    geolocation = map_fields.GeoLocationField(max_length=100, null=True, verbose_name='Map Center Coords')
    mapZoom = models.IntegerField(default=15, verbose_name='Map Zoom Level')
