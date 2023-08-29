import datetime as dt

import pytz
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class TimestampField(serializers.Field):
    default_error_messages = {
        'invalid': _('Timestamp has wrong format. Expected number, received: {format}.'),
        'overflow': _('Datetime value out of range.'),
        'error': _('Error processing timestamp value.'),
    }

    def to_representation(self, datetime_obj):
        return datetime_obj.timestamp()

    def to_internal_value(self, unix_timestamp):
        try:
            dt.datetime.fromtimestamp(unix_timestamp)
        except TypeError:
            self.fail('invalid', format=type(unix_timestamp).__name__)
        except OverflowError:
            self.fail('overflow')
        except:
            self.fail('error')
        return dt.datetime.fromtimestamp(unix_timestamp).replace(tzinfo=pytz.utc)
