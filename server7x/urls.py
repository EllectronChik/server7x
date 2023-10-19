from django.contrib import admin
from django.urls import path, include, re_path
from main import views
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
router.register(r'ask_for_staff', views.AskForStaffViewSet, basename='ask_for_staff')
router.register(r'teams', views.TeamsViewSet, basename='teams')
router.register(r'players', views.PlayersViewSet, basename='players')
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
    path('api/v1/manager/team/', views.get_team_and_related_data, name='get_team_and_related_data'),
    path('api/v1/is_auth/', views.is_authenticated),
    path('api/v1/status/', views.is_manager_or_staff),
    path('api/v1/auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.authtoken')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)