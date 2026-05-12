from django.conf import settings
from django.contrib.auth.views import LoginView
from django.http import HttpResponse

from .forms import EmailAuthenticationForm
from .rate_limit import get_client_ip, record_request_limit


class RateLimitedLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "registration/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            email = (request.POST.get("username") or "").strip().lower()
            identifier = f"{get_client_ip(request)}:{email or 'anonymous'}"
            blocked, _count = record_request_limit(
                namespace="login",
                identifier=identifier,
                limit=settings.LOGIN_RATE_LIMIT,
                window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
            )
            if blocked:
                response = HttpResponse("Too many login attempts", status=429)
                response["Retry-After"] = str(settings.LOGIN_RATE_WINDOW_SECONDS)
                return response

        return super().dispatch(request, *args, **kwargs)
