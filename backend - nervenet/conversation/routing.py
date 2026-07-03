from django.urls import re_path
from conversation.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r"^api/ws/chat$", ChatConsumer.as_asgi()),
]
