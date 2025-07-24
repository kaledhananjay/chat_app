from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    #ssre_path(r"ws/meeting/(?P<room_name>\w+)/$", consumers.MeetingConsumer.as_asgi()),
    re_path(r"ws/meeting/(?P<room_name>[^/]+)/$", consumers.MeetingConsumer.as_asgi()),
    re_path(r"ws/.*", consumers.FallbackConsumer.as_asgi()),  # Catch-all
]

