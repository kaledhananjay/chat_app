"""
ASGI config for chat_app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_app.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns
)
    ),
})


# from channels.routing import ProtocolTypeRouter, URLRouter
# from django.core.asgi import get_asgi_application
# from chat.routing import websocket_urlpatterns
# from channels.auth import AuthMiddlewareStack
# import chat.routing
# import os

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_app.settings")
# print('XXX chat.routing.websocket_urlpatterns : ', chat.routing.websocket_urlpatterns)
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),  # Handles normal HTTP requests
#     "websocket": AuthMiddlewareStack(  # Handles WebSocket connections
#         URLRouter(chat.routing.websocket_urlpatterns)
#     ),
# })