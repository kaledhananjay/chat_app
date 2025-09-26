from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/meeting/(?P<room_name>[^/]+)/$", consumers.MeetingConsumer.as_asgi()),
    re_path("ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
    re_path(r"ws/.*", consumers.FallbackConsumer.as_asgi()),  # Catch-all
]

