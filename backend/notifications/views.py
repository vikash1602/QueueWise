from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        unread_only = request.query_params.get("unread") == "1"
        if unread_only:
            qs = qs.filter(is_read=False)
        return Response(
            {
                "unread_count": Notification.objects.filter(
                    user=request.user, is_read=False
                ).count(),
                "results": [
                    {
                        "id": n.id,
                        "type": n.type,
                        "title": n.title,
                        "body": n.body,
                        "payload": n.payload,
                        "is_read": n.is_read,
                        "created_at": n.created_at,
                    }
                    for n in qs[:50]
                ],
            }
        )


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"id": notification.id, "is_read": True})


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"marked_read": updated})
