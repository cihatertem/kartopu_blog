import ipaddress
import os
from http import HTTPStatus

from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from core.decorators import log_exceptions


class RejectNullByteMiddleware:
    """
    Rejects requests whose path or query string contains a NUL (0x00) byte.

    Such requests only come from malicious/automated scanners and would
    otherwise reach the DB and raise ``DataError`` (PostgreSQL text fields
    cannot contain NUL bytes). Rejecting them here with a lightweight 400 is
    O(1) and avoids URL resolution, DB and template work.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "\x00" in request.META.get("PATH_INFO", "") or "\x00" in request.META.get(
            "QUERY_STRING", ""
        ):
            return HttpResponseBadRequest()

        return self.get_response(request)


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
    @log_exceptions(
        default=False,
        exception_types=(ValueError,),
        message="Invalid IP address in proxy check",
        include_traceback=True,
    )
    def _is_trusted_proxy(request) -> bool:
        remote = request.META.get("REMOTE_ADDR")
        if not remote:
            return False

        trusted_nets = getattr(settings, "TRUSTED_PROXY_NETS", None) or []
        if not trusted_nets:
            return False

        address = ipaddress.ip_address(remote)
        return any(address in net for net in trusted_nets)


class AdminCSPExcludeMiddleware:
    """
    Removes Content-Security-Policy headers from admin endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_address = os.getenv("ADMIN_ADDRESS", "admin")
        self.admin_prefixes = (
            f"/{self.admin_address}",
            f"/en/{self.admin_address}",
            f"/tr/{self.admin_address}",
        )

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if any(path.startswith(prefix) for prefix in self.admin_prefixes):
            response.headers.pop("Content-Security-Policy", None)
            response.headers.pop("Content-Security-Policy-Report-Only", None)
        return response
