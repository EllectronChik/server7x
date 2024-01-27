"""
ASGI config for server7x project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from main.consumers import *
from django.urls import re_path, path


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server7x.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(URLRouter([
        path('ws/match/', MatchConsumer.as_asgi()),
        path('ws/tournament_status/', TournamentStatusConsumer.as_asgi()),
        path('ws/tournaments_admin/', AdminConsumer.as_asgi()),
        path('ws/groups/', groupsConsumer.as_asgi()),
    ])),
})

