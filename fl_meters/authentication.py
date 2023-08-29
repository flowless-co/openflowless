from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.permissions import IsAdminUser, BasePermission
from .models import MeterToken

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class MeterTokenAuthentication(TokenAuthentication):
    model = MeterToken


class IsPulsar(BasePermission):
    """
    Allows access only to Pulsars.
    """

    def has_permission(self, request, view):
        """
        Return `True` if object is a `Pulsar` object. `False` otherwise.
        """
        try:
            request.user.is_pulsar
            return True
        except Exception:
            return False


class IsPulsarOrReadOnly(BasePermission):
    """
    Allows access to Pulsar devices or to Admin Users.
    """

    def has_permission(self, request, view):
        safe = False
        try:
            safe = request.user.is_pulsar
        except Exception:
            safe = bool(request.method in SAFE_METHODS)

        return safe
