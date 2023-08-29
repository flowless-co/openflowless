import datetime

from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers

from .fields import TimestampField
from .models import Meter, Pulse, PressurePulse, ChlorineSensorPulse


class PulseField(serializers.Field):
    def to_representation(self, value):
        return PulseSerializer(value).data

    def to_internal_value(self, data):
        return PulseSerializer(data=data)


class MeterSerializer(serializers.ModelSerializer):
    pulses = serializers.ListSerializer(
            child=PulseField(),
            allow_empty=True,
            allow_null=True
    )

    class Meta:
        model = Meter
        fields = (
            'description',
            'model_number',
            'latitude',
            'longitude',
            'area_name',
            'installation_date',
            'op_status',
            'pulses'
        )


class PulseSerializer(serializers.ModelSerializer):
    time = serializers.DateTimeField(default=datetime.datetime.now, required=False)
    meter_id = serializers.IntegerField(required=True)
    reading = serializers.CharField(max_length=16, required=True)

    class Meta:
        model = Pulse
        fields = ('id', 'meter_id', 'reading', 'time')
        read_only_fields = ('time',)

class TimestampedPulseSerializer(serializers.ModelSerializer):
    time = TimestampField(required=True)
    meter_id = serializers.IntegerField(required=True)
    reading = serializers.CharField(max_length=16, required=True)

    class Meta:
        model = Pulse
        fields = ('id', 'meter_id', 'reading', 'time')
        read_only_fields = ('time',)


class TimestampedPressurePulseSerializer(serializers.ModelSerializer):
    time = TimestampField(required=True)
    transmitter_id = serializers.IntegerField(required=True)
    reading = serializers.CharField(max_length=16, required=True)

    class Meta:
        model = PressurePulse
        fields = ('id', 'transmitter_id', 'reading', 'time')
        read_only_fields = ('time',)


class PressurePulseSerializer(serializers.ModelSerializer):
    time = serializers.DateTimeField(default=datetime.datetime.now, required=False)
    transmitter_id = serializers.IntegerField(required=True)
    reading = serializers.CharField(max_length=16, required=True)

    class Meta:
        model = PressurePulse
        fields = ('id', 'transmitter_id', 'reading', 'time')
        read_only_fields = ('time',)


class ChlorineSensorPulseSerializer(serializers.ModelSerializer):
    time = TimestampField(required=True)

    class Meta:
        model = ChlorineSensorPulse
        fields = ('sensor', 'reading', 'time')


class SinceUntilSerializer(serializers.Serializer):
    since = serializers.DateTimeField()
    until = serializers.DateTimeField()


class DatesToStrings(DjangoJSONEncoder):
    def _encode(self, obj):
        if isinstance(obj, dict):
            def transform_date(o):
                return self._encode(o.isoformat() if isinstance(o, datetime.datetime) else o)
            return {transform_date(k): transform_date(v) for k, v in obj.items()}
        else:
            return obj

    def encode(self, obj):
        return super(DatesToStrings, self).encode(self._encode(obj))
