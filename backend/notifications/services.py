from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def create(*, user, type, title, body="", payload=None):
    """Create an in-app notification and (configurably) send an email copy.

    Email uses Django's EMAIL_BACKEND; the default console backend keeps local
    development functional without real credentials.
    """
    notification = Notification.objects.create(
        user=user, type=type, title=title, body=body, payload=payload or {}
    )
    if user.email and getattr(settings, "QUEUEWISE_SEND_EMAIL_NOTIFICATIONS", False):
        send_mail(
            subject=f"QueueWise: {title}",
            message=body or title,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    return notification
