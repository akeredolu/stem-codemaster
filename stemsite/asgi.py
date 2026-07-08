import os

# 1️⃣ Set Django settings module first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stemsite.settings')

# 2️⃣ Import Django ASGI application
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# 3️⃣ Import Channels stuff AFTER settings and Django setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 4️⃣ Import your routing AFTER Django setup
import chat.routing

# 5️⃣ Define the ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,  # use the variable instead of calling get_asgi_application() again
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})

