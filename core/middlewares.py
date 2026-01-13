import ipaddress
from http import HTTPStatus

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class HealthCheckMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.META["PATH_INFO"] == "/ping":
            return JsonResponse({"response": "pong!"}, status=HTTPStatus.OK)


class TrustedProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._is_trusted_proxy(request):
            request.META.pop("HTTP_X_FORWARDED_FOR", None)
            request.META.pop("HTTP_X_FORWARDED_HOST", None)
            request.META.pop("HTTP_X_FORWARDED_PROTO", None)

        return self.get_response(request)

    @staticmethod
    def _is_trusted_proxy(request) -> bool:
        remote = request.META.get("REMOTE_ADDR")
        if not remote:
            return False

        trusted_nets = getattr(settings, "TRUSTED_PROXY_NETS", None) or []
        if not trusted_nets:
            return False

        try:
            address = ipaddress.ip_address(remote)
        except ValueError:
            return False

        return any(address in net for net in trusted_nets)
