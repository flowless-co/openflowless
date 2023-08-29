from django.contrib import admin
from . import models
from django_google_maps import widgets as map_widgets
from django_google_maps import fields as map_fields


@admin.register(models.Preferences)
class PreferencesAdmin(admin.ModelAdmin):
    fieldsets = (
        ('General', {
            'fields': ('clientScreenName',)
        }),
        ('Dashboard Map', {
            'fields': ('address', ('geolocation', 'mapZoom'))
        })
    )
    formfield_overrides = {
        map_fields.AddressField: {
            'widget': map_widgets.GoogleMapsAddressWidget(attrs={'data-map-type': 'roadmap'})},
    }
