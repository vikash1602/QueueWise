from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/queue/(?P<entry_id>\d+)/$", consumers.QueueEntryConsumer.as_asgi()),
    re_path(r"ws/org/(?P<org_id>\d+)/queue/$", consumers.OrgQueueConsumer.as_asgi()),
]
