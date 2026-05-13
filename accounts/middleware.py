from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .rate_limit import get_client_ip, record_request_limit, should_skip_rate_limit


class RequestRateLimitMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if should_skip_rate_limit(request):
            return self.get_response(request)

        blocked, _count = record_request_limit(
            namespace="request",
            identifier=get_client_ip(request),
            limit=settings.REQUEST_RATE_LIMIT,
            window_seconds=settings.REQUEST_RATE_WINDOW_SECONDS,
        )
        if blocked:
            response = HttpResponse("Too many requests", status=429)
            response["Retry-After"] = str(settings.REQUEST_RATE_WINDOW_SECONDS)
            return response

        return self.get_response(request)
