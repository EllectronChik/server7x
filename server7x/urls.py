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
router.register(r'regions', views.RegionsViewSet, basename='regions')
router.register(r'matches', views.MatchesViewSet, basename='matches')
router.register(r'races', views.RaceViewSet)
router.register(r'leagues', views.LeagueViewSet)
router.register(r'seasons', views.SeasonsViewSet)
router.register(r'tournaments', views.TournamentsViewSet)
router.register(r'schedule', views.ScheduleViewSet)
router.register(r'users_devices', views.UserDeviceViewSet,
                basename='users_devices')
router.register(r'tournament_registration',
                views.TournamentRegistrationsViewSet, basename='tournament_registration')
router.register(r'player_to_tournament',
                views.PlayerToTournamentViewSet, basename='player_to_tournament')
router.register(r'groupStages', views.groupStageViewSet,
                basename='groupStages')


urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/matches/<int:match_id>/players/',
         views.MatchPlayersViewSet.as_view({'get': 'list'})),
    path('api/v1/matches/<int:match_id>/teams/',
         views.MatchTeamsViewSet.as_view({'get': 'list'})),
    path('api/v1/get_players/<str:clan_tag>/', views.GetClanMembers.as_view()),
    path('api/v1/get_player_logo/<str:region>/<str:realm>/<str:character_id>/',
         views.GetMemberLogo.as_view()),
    path('api/v1/get_league_by_mmr/',
         views.get_league_by_mmr, name='get_league_by_mmr'),
    path('api/v1/set_staff_true/',
         views.user_staff_status_true, name='set_staff_true'),
    path('api/v1/set_staff_false/',
         views.user_staff_status_false, name='set_staff_false'),
    path('api/v1/manager/team/', views.get_team_and_related_data,
         name='get_team_and_related_data'),
    path('api/v1/get_current_tournaments/',
         views.get_current_tournaments, name='get_current_tournaments'),
    path('api/v1/get_current_season/',
         views.get_current_season, name='get_current_season'),
    path('api/v1/get_last_season/', views.get_last_season, name='get_last_season'),
    path('api/v1/get_last_season_number/',
         views.get_last_season_number, name='get_last_season_number'),
    path('api/v1/player_to_tournament/<int:pk>/', views.PlayerToTournamentViewSet.as_view(
        {'delete': 'destroy'}), name='delete_player_to_tournament'),
    path('api/v1/getPlayerToCurrentTournament/',
         views.getPlayerToCurrentTournament, name='getPlayerToCurrentTournament'),
    path('api/v1/registredToCurrentSeasonTeams/',
         views.registredToCurrentSeasonTeams, name='registredToCurrentSeasonTeams'),
    path('api/v1/groupsToCurrentSeason/',
         views.groupsToCurrentSeason, name='groupsToCurrentSeason'),
    path('api/v1/postTeamToGroup/', views.postTeamToGroup, name='postTeamToGroup'),
    path('api/v1/deleteTeamFromGroup/',
         views.deleteTeamFromGroup, name='deleteTeamFromGroup'),
    path('api/v1/getToursToCurrentSeason/',
         views.getToursToCurrentSeason, name='getToursToCurrentSeason'),
    path('api/v1/deleteTournamentsToCurrentSeason/',
         views.deleteTournamentsToCurrentSeason, name='deleteTournamentsToCurrentSeason'),
    path('api/v1/setTimeSuggestion/',
         views.setTimeSuggestion, name='setTimeSuggestion'),
    path('api/v1/acceptTimeSuggestion/',
         views.acceptTimeSuggestion, name='acceptTimeSuggestion'),
    path('api/v1/getToursByManager/',
         views.getToursByManager, name='getToursByManager'),
    path('api/v1/randomizeGroups/', views.randomizeGroups, name='randomizeGroups'),
    path('api/v1/getPlayersByTeam/',
         views.get_players_by_teams, name='getPlayersByTeam'),
    path('api/v1/getSeasonData/<int:season>/',
         views.get_season_by_number, name='get_season_data'),
    path('api/v1/getTeamData/<int:team_id>/',
         views.get_team_by_id, name='get_team_data'),
    path('api/v1/getPlayerData/<int:player_id>/',
         views.get_player_by_id, name='get_player_data'),
    path('api/v1/getTournamentData/<int:tournament_id>/',
         views.get_tournament_by_id, name='get_tournament_data'),
    path('api/v1/is_auth/', views.is_authenticated),
    path('api/v1/status/', views.is_manager_or_staff),
    path('api/v1/auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.authtoken')),
]

if settings.DEBUG:
    urlpatterns.append(path('admin/', admin.site.urls)),
    urlpatterns.append(path('silk/', include('silk.urls', namespace='silk'))),
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
