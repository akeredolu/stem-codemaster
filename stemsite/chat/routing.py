from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Example: ws://127.0.0.1:8000/ws/chat/guest_admin/
    # Example: ws://127.0.0.1:8000/ws/chat/student_admin/
    re_path(r'ws/chat/(?P<room_name>\w+)/$', consumers.ChatConsumer.as_asgi()),
]

