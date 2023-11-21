from django.contrib import admin
from django.urls import path, include, re_path
from main import views
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
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
router.register(r'seasons', views.SeasonsViewSet)
router.register(r'tournaments', views.TournamentsViewSet)
router.register(r'schedule', views.ScheduleViewSet)
router.register(r'users_devices', views.UserDeviceViewSet, basename='users_devices', )


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/matches/<int:match_id>/players/', views.MatchPlayersViewSet.as_view({'get': 'list'})),
    path('api/v1/matches/<int:match_id>/teams/', views.MatchTeamsViewSet.as_view({'get': 'list'})),
    path('api/v1/get_players/<str:clan_tag>/', views.GetClanMembers.as_view()),
    path('api/v1/get_player_logo/<str:region>/<str:realm>/<str:character_id>/', views.GetMemberLogo.as_view()),
    path('api/v1/get_league_by_mmr/', views.get_league_by_mmr, name='get_league_by_mmr'),
    path('api/v1/set_staff_true/', views.user_staff_status_true, name='set_staff_true'),
    path('api/v1/set_staff_false/', views.user_staff_status_false, name='set_staff_false'),
    path('api/v1/manager/team/', views.get_team_and_related_data, name='get_team_and_related_data'),
    path('get_current_tournaments', views.get_current_tournaments, name='get_current_tournaments'),
    path('api/v1/is_auth/', views.is_authenticated),
    path('api/v1/status/', views.is_manager_or_staff),
    path('api/v1/auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.authtoken')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)