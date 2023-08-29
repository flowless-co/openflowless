from django.contrib import admin

from . import models
from . import forms
from django_google_maps import widgets as map_widgets
from django_google_maps import fields as map_fields

admin.site.register(models.QuarterHourlyZoneConsumption)
admin.site.register(models.DailyZoneConsumption)
admin.site.register(models.MonthlyZoneConsumption)
admin.site.register(models.YearlyZoneConsumption)
admin.site.register(models.DailyZoneLoss)
admin.site.register(models.MonthlyZoneLoss)
admin.site.register(models.YearlyZoneLoss)
admin.site.register(models.OnHold)
admin.site.register(models.DeviceModel)

admin.site.register(models.ChlorineSensor)
admin.site.register(models.ChlorineSensorPulse)
admin.site.register(models.HourlyAvgChlorineLevel)
admin.site.register(models.DailyAvgChlorineLevel)
admin.site.register(models.MonthlyAvgChlorineLevel)
admin.site.register(models.YearlyAvgChlorineLevel)
admin.site.register(models.Notification)

admin.site.register(models.Tank)
admin.site.register(models.TankLevelSensorPulse)
admin.site.register(models.TankLevel)
@admin.register(models.TankLevelSensor)
class TankLevelSensorAdmin(admin.ModelAdmin):
    readonly_fields = ['key', ]

@admin.register(models.TransmissionLine)
class TransmissionLineAdmin(admin.ModelAdmin):
    readonly_fields = ['key']


@admin.register(models.Meter)
class MeterAdmin(admin.ModelAdmin):
    readonly_fields = ['key']
    list_display = ['key', 'location', 'meter_model', 'id', 'active']
    list_filter = ('active', 'meter_model__bulk_meter', 'meter_model__type')
    search_fields = ('key',
                     'location__description',
                     'location__neighbourhood',
                     'location__city',
                     'meter_model__manufacturer',
                     'meter_model__model_number')


@admin.register(models.Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['key', 'zone', 'datetime', 'loss_amount']


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'meter', 'customer_type', 'phone_number', 'email']
    list_filter = ('customer_type',)
    search_fields = ['name', 'meter__key', 'phone_number', 'email']


admin.site.register(models.LossRecord)

@admin.register(models.Pulse)
class PulseAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'meter']
    list_filter = ('time',)


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    formfield_overrides = {
        map_fields.AddressField: {'widget': map_widgets.GoogleMapsAddressWidget(attrs={'data-map-type': 'roadmap'})},
    }
    list_display = ['description', 'city', 'neighbourhood', 'bldg_no']


@admin.register(models.MeterModel)
class MeterModelAdmin(admin.ModelAdmin):
    search_fields = ['manufacturer', 'model_number']
    list_display = ['manufacturer', 'model_number', 'bulk_meter', 'type']
    list_filter = ('bulk_meter', 'type')


admin.site.register(models.Serial)

admin.site.register(models.QuarterHourlyTSMInflow)
admin.site.register(models.DailyTSMInflow)
admin.site.register(models.MonthlyTSMInflow)
admin.site.register(models.YearlyTSMInflow)
admin.site.register(models.DailyTSMLossRecord)
admin.site.register(models.MonthlyTSMLossRecord)
admin.site.register(models.YearlyTSMLossRecord)

class ZoneCoordinatesInline(admin.TabularInline):
    model = models.ZoneCoordinate
    template = 'admin/zone_inline.html'
    extra = 1

class ZonePressureTransmittersInline(admin.TabularInline):
    model = models.ZoneHasPressureTransmitter
    extra = 1
    verbose_name = 'pressure transmitter'
    verbose_name_plural = 'pressure transmitters'

class MetersInputZoneInline(admin.TabularInline):
    verbose_name = 'Input Meter'
    verbose_name_plural = 'Input Meters'
    model = models.Meter
    max_num = 0
    fk_name = 'input_for'
    fields = ('key', )
    readonly_fields = ('key', )

class MetersOutputZoneInline(admin.TabularInline):
    verbose_name = 'Output Meter'
    verbose_name_plural = 'Output Meters'
    model = models.Meter
    max_num = 0
    fk_name = 'output_for'
    fields = ('key', )
    readonly_fields = ('key', )

@admin.register(models.Zone)
class ZoneAdmin(admin.ModelAdmin):
    inlines = [ZoneCoordinatesInline, ZonePressureTransmittersInline, MetersInputZoneInline, MetersOutputZoneInline]
    list_display = ('name',)
    search_fields = ('name',)

    class Media:
        css = {
            "all": ("fl_meters/custom_admin.css",)
        }
        js = ("admin/js/vendor/jquery/jquery.min.js", )


@admin.register(models.PressureTransmitter)
class PressureTransmitterAdmin(admin.ModelAdmin):
    inlines = [ZonePressureTransmittersInline]
    readonly_fields = ['key']
    list_display = ['key', 'location', 'meter_model', 'id', 'active']
    list_filter = ('active', 'meter_model__type')
    search_fields = ('key',
                     'location__description',
                     'location__neighbourhood',
                     'location__city',
                     'meter_model__manufacturer',
                     'meter_model__model_number')


@admin.register(models.PressurePulse)
class PressurePulseAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'transmitter', 'reading']
    list_filter = ('time',)


admin.site.register(models.TransmitterModel)
