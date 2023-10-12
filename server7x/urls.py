"""server7x URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from main import views
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
router.register(r'ask_for_staff', views.AskForStaffViewSet, basename='ask_for_staff')
router.register(r'teams', views.TeamsViewSet)
router.register(r'players', views.PlayersViewSet)
router.register(r'managers', views.ManagersViewSet)
router.register(r'manager_contacts', views.ManagerContactsViewSet)
router.register(r'team_resources', views.TeamResourcesViewSet)
router.register(r'stages', views.StagesViewSet)
router.register(r'regions', views.RegionsViewSet, basename='regions')
router.register(r'matches', views.MatchesViewSet, basename='matches')
router.register(r'races', views.RaceViewSet)
router.register(r'leagues', views.LeagueViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/matches/<int:match_id>/players/', views.MatchPlayersViewSet.as_view({'get': 'list'})),
    path('api/v1/matches/<int:match_id>/teams/', views.MatchTeamsViewSet.as_view({'get': 'list'})),
    path('api/v1/get_players/<str:clan_tag>/', views.GetClanMembers.as_view()),
    path('api/v1/get_player_logo/<str:region>/<str:realm>/<str:character_id>/', views.GetMemberLogo.as_view()),
    path('api/v1/is_auth/', views.is_authenticated),
    path('api/v1/status/', views.is_manager_or_staff),
    path('api/v1/auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.authtoken')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)