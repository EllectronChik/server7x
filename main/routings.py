from main.consumers import *
from django.urls import path

websocket_routes = [
        path('ws/match/', MatchConsumer.as_asgi()),
        path('ws/tournament_status/', TournamentStatusConsumer.as_asgi()),
        path('ws/tournaments_admin/', AdminConsumer.as_asgi()),
        path('ws/groups/', groupsConsumer.as_asgi()),
        path('ws/information/', InfoConsumer.as_asgi()),
    ]