"""
ASGI config for server7x project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
import main.routings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server7x.settings')

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(URLRouter(main.routings.websocket_routes)),
})

