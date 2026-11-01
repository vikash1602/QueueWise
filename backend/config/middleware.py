"""API error middleware: keep error responses machine-readable.

Django's debug handler returns the technical-500 page as *plain text* when the
client sends `Accept: application/json` (which our SPA always does), so a
database outage reached the frontend as a non-JSON body and surfaced as a
confusing JSON parse error. For /api/ paths we return a JSON 503 carrying the
original exception type instead — the error stays visible, just parseable.

Old-style process_exception is required here: Django converts view exceptions
to the debug/plain-text response inside the handler itself, before new-style
__call__ middleware could see them.
"""
import json

from django.db import InterfaceError, OperationalError
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class DatabaseErrorJsonMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if not isinstance(exception, (OperationalError, InterfaceError)):
            return None
        if not request.path.startswith("/api/"):
            return None  # non-API paths keep Django's normal behavior
        body = json.dumps(
            {
                "detail": (
                    f"Database connection error ({type(exception).__name__}). The "
                    "service is temporarily unavailable — please try again shortly."
                )
            }
        )
        return HttpResponse(body, status=503, content_type="application/json")
