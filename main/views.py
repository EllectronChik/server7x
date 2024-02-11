import configparser
import requests

from main.models import *
from main.serializers import *
from main.utils import leagueFrames, get_league, form_character_data, get_avatar
from rest_framework import status, viewsets, exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from djoser.utils import logout_user
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, F

from .permissions import *
from .utils import distribute_teams_to_groups, image_compressor, get_season_data

config = configparser.ConfigParser()
config.read('.ini')


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = '_limit'
    max_page_size = 100


class TeamsViewSet(viewsets.ModelViewSet):
    serializer_class = TeamsSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = Team.objects.all()
        tag = self.request.query_params.get('tag')
        if tag is not None:
            queryset = queryset.filter(tag=tag)
        return queryset

    def perform_create(self, serializer):
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        logo = serializer.validated_data.get('logo')
        if logo:
            image_file = image_compressor(
                logo, serializer.validated_data['tag'])
            serializer.validated_data['logo'] = image_file
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        logo = serializer.validated_data.get('logo')
        if logo:
            image_file = image_compressor(
                logo, Team.objects.get(id=serializer.instance.id).tag)
            serializer.validated_data['logo'] = image_file
        serializer.save(user=self.request.user)


class PlayersViewSet(viewsets.ModelViewSet):
    serializer_class = PlayersSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = Player.objects.all()
        team = self.request.query_params.get('team')

        if team is not None:
            queryset = queryset.filter(team=team)
        return queryset

    def perform_create(self, serializer):
        if serializer.validated_data['league'] is None:
            league_frames = leagueFrames()
            if serializer.validated_data['region'] == 1:
                region = 'US'
            elif serializer.validated_data['region'] == 2:
                region = 'EU'
            elif serializer.validated_data['region'] == 3:
                region = 'KR'

            league = get_league(
                serializer.validated_data['mmr'], league_frames, region)
            serializer.validated_data['league'] = league

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class ManagersViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.all()
    serializer_class = ManagersSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)

        serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = Manager.objects.all()
        user = self.request.query_params.get('user')

        if user is not None:
            queryset = queryset.filter(user=user)
        return queryset


class ManagerContactsViewSet(viewsets.ModelViewSet):
    queryset = ManagerContact.objects.all()
    serializer_class = ManagerContactsSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class TeamResourcesViewSet(viewsets.ModelViewSet):
    queryset = TeamResource.objects.all()
    serializer_class = TeamResourcesSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = TeamResource.objects.all()
        team = self.request.query_params.get('team')

        if team is not None:
            queryset = queryset.filter(team=team)
        return queryset


class SeasonsViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonsSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def get_object_or_404(self):
        number = self.kwargs.get('pk')
        try:
            return Season.objects.get(number=number)
        except Season.DoesNotExist:
            return Response({"error": "Season not found"}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object_or_404()
        if (request.data.get('is_finished')):
            highest_stage = Tournament.objects.filter(season=instance, group__isnull=True).order_by(
                '-stage').values_list('stage', flat=True).distinct()[0]
            if (highest_stage == 999):
                highest_stage = Tournament.objects.filter(season=instance, group__isnull=True).order_by(
                    '-stage').values_list('stage', flat=True).distinct()[1]
            tournament = Tournament.objects.get(
                season=instance, group__isnull=True, stage=highest_stage)
            instance.winner = tournament.winner if tournament.winner else None
        serializer = self.get_serializer(
            instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def perform_create(self, serializer):
        try:
            season = Season.objects.get(is_finished=False)
            if season:
                raise exceptions.PermissionDenied("Season is already created")
        except Season.DoesNotExist:
            serializer.save()


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class TournamentsViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all()
    serializer_class = TournamentsSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        tournament = Tournament.objects.filter(
            season=Season.objects.get(is_finished=False),
            stage=serializer.validated_data['stage'],
            team_one=serializer.validated_data['team_one'],
            team_two=serializer.validated_data['team_two'],
            match_start_time=serializer.validated_data['match_start_time']).first()
        if (serializer.validated_data['team_one'] == serializer.validated_data['team_two']):
            raise exceptions.ValidationError("Teams can't be equal")
        if tournament:
            raise exceptions.PermissionDenied("Tournament is already created")
        if 'group' in serializer.validated_data:
            try:
                tournament = Tournament.objects.get(
                    season=Season.objects.get(is_finished=False),
                    stage=serializer.validated_data['stage'],
                    group=serializer.validated_data['group'],
                    team_one=serializer.validated_data['team_one'],
                    match_start_time=serializer.validated_data['match_start_time'],
                )
                if tournament and serializer.validated_data['team_one']:
                    tournament.team_two = serializer.validated_data['team_two']
                    tournament.save()
            except Tournament.DoesNotExist:
                try:
                    tournament = Tournament.objects.get(
                        season=Season.objects.get(is_finished=False),
                        stage=serializer.validated_data['stage'],
                        group=serializer.validated_data['group'],
                        team_two=serializer.validated_data['team_two'],
                        match_start_time=serializer.validated_data['match_start_time'],
                    )
                    if tournament and serializer.validated_data['team_two']:
                        tournament.team_one = serializer.validated_data['team_one']
                        tournament.save()
                except Tournament.DoesNotExist:
                    try:
                        tournament = Tournament.objects.get(
                            season=Season.objects.get(is_finished=False),
                            stage=serializer.validated_data['stage'],
                            team_one=serializer.validated_data['team_one'],
                            team_two=serializer.validated_data['team_two'],
                            match_start_time=serializer.validated_data['match_start_time'],
                        )
                        if tournament and serializer.validated_data['group']:
                            tournament.group = serializer.validated_data['group']
                            tournament.save()
                    except Tournament.DoesNotExist:
                        try:
                            tournament = Tournament.objects.get(
                                season=Season.objects.get(is_finished=False),
                                stage=serializer.validated_data['stage'],
                                group=serializer.validated_data['group'],
                                team_two=serializer.validated_data['team_two'],
                                team_one=serializer.validated_data['team_one'],
                            )
                            if tournament and serializer.validated_data['match_start_time']:
                                tournament.match_start_time = serializer.validated_data[
                                    'match_start_time']
                                tournament.save()
                        except Tournament.DoesNotExist:
                            try:
                                tournament = Tournament.objects.get(
                                    season=Season.objects.get(
                                        is_finished=False),
                                    group=serializer.validated_data['group'],
                                    team_one=serializer.validated_data['team_one'],
                                    team_two=serializer.validated_data['team_two'],
                                    match_start_time=serializer.validated_data['match_start_time'],
                                )
                                if tournament and serializer.validated_data['stage']:
                                    tournament.stage = serializer.validated_data['stage']

                                    tournament.save()
                            except Tournament.DoesNotExist:
                                serializer.save()
        else:
            serializer.save()


class RegionsViewSet(viewsets.ModelViewSet):
    serializer_class = RegionsSerializer
    permission_classes = (isAdminOrReadOnly, )

    def get_queryset(self):
        name = self.request.query_params.get('name')
        if name is not None:
            return Region.objects.filter(name=name)
        return Region.objects.all().order_by('name')


class TournamentRegistrationsViewSet(viewsets.ModelViewSet):
    queryset = TournamentRegistration.objects.all()
    serializer_class = TournamentRegistrationSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class MatchesViewSet(viewsets.ModelViewSet):
    serializer_class = MatchesSerializer
    permission_classes = (canEditMatchField,)
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = Match.objects.all()
        player_one = self.request.query_params.get('player_one')
        player_two = self.request.query_params.get('player_two')
        if player_one is not None:
            queryset = queryset.filter(player_one=player_one)
        if player_two is not None:
            queryset = queryset.filter(player_two=player_two)

        return queryset

    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class MatchPlayersViewSet(viewsets.ViewSet):
    def list(self, request, match_id):
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            return Response({"error": "Match not found"}, status=404)

        players = match.get_players()
        serializer = PlayersSerializer(players, many=True)
        return Response(serializer.data)


class MatchTeamsViewSet(viewsets.ViewSet):
    def list(self, request, match_id):
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            return Response({"error": "Match not found"}, status=404)

        teams = match.get_teams()
        serializer = TeamsSerializer(teams, many=True)
        return Response(serializer.data)


class RaceViewSet(viewsets.ModelViewSet):
    queryset = Race.objects.all()
    serializer_class = RaceSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class UserDeviceViewSet(viewsets.ModelViewSet):
    queryset = UserDevice.objects.all()
    serializer_class = UserDevicesSerializer
    permission_classes = (permissions.IsAdminUser |
                          permissions.IsAuthenticated, )
    pagination_class = CustomPageNumberPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user_devices = queryset.filter(user=self.request.user)
        device_values = user_devices.values_list('device', flat=True)
        return Response(list(device_values))

    def patch(self, request, *args, **kwargs):
        if request.data.get('action') not in ['increase', 'decrease']:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_device = UserDevice.objects.get(user=self.request.user.id)
        except UserDevice.DoesNotExist:
            user_device = UserDevice.objects.create(
                user=self.request.user, device=0)

        current_device_value = user_device.device

        if request.data.get('action') == 'increase':
            new_device_value = current_device_value + 1
        elif request.data.get('action') == 'decrease':
            new_device_value = current_device_value - 1
        else:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        user_device.device = new_device_value
        user_device.save()

        if new_device_value == 0:
            logout_user(self.request)

        return Response({"device": new_device_value}, status=status.HTTP_200_OK)


class PlayerToTournamentViewSet(viewsets.ModelViewSet):
    queryset = PlayerToTournament.objects.all()
    serializer_class = PlayerToTournamentSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def destroy(self, request, *args, **kwargs):
        player_id = self.kwargs.get('pk')
        user = request.user
        if user.is_anonymous:
            return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            player_to_tournament = PlayerToTournament.objects.get(
                player=player, user=user)
            player_to_tournament.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PlayerToTournament.DoesNotExist:
            try:
                player_to_tournament = PlayerToTournament.objects.get(
                    player=player)
                if player_to_tournament:
                    return Response({"error": "You are not owner of this player"}, status=status.HTTP_403_FORBIDDEN)
            except PlayerToTournament.DoesNotExist:
                return Response({"error": "Player does not registered"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "Player does not registered"}, status=status.HTTP_404_NOT_FOUND)

    def get_queryset(self):
        user = self.request.query_params.get('user')
        season = self.request.query_params.get('season')
        try:
            if user:
                return PlayerToTournament.objects.filter(user=user)
            if season:
                return PlayerToTournament.objects.filter(Season=season)
        except ValueError:
            return PlayerToTournament.objects.all()
        if user and season:
            return PlayerToTournament.objects.filter(user=user, Season=season)
        return PlayerToTournament.objects.all()


class GetClanMembers(APIView):
    def get(self, request, clan_tag):
        try:
            character_data = form_character_data(clan_tag)
            if character_data[1] == status.HTTP_200_OK:
                return Response(character_data[0], status=status.HTTP_200_OK)
            else:
                raise Exception(f"Error {character_data[1]}")
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetMemberLogo(APIView):
    def get(self, request, region, realm, character_id):
        try:
            avatar = get_avatar(region, realm, character_id)
            if avatar is not None:
                return Response(avatar, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Character not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            error_code = e.response.status_code
            return Response({"error": str(e)}, status=error_code)


class groupStageViewSet(viewsets.ModelViewSet):
    queryset = GroupStage.objects.all()
    serializer_class = groupStageSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        season = self.request.query_params.get('season')
        try:
            int(season)
        except:
            return GroupStage.objects.all()
        season = Season.objects.get(number=season)
        if season:
            return GroupStage.objects.filter(season=season)
        return GroupStage.objects.all()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def is_authenticated(request):
    return Response(status=status.HTTP_200_OK, data={"is_authenticated": request.user.is_authenticated})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def is_manager_or_staff(request):
    user = request.user
    is_manager = Manager.objects.filter(user=user).exists()
    return Response(status=status.HTTP_200_OK, data={
        "is_staff": request.user.is_staff,
        "is_manager": is_manager})


@api_view(['GET'])
def get_team_and_related_data(request):
    user_id = request.query_params.get('user', None)
    if user_id is None:
        return Response({"error": "User ID is required in query parameter"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        manager = Manager.objects.get(user=user_id)
    except:
        return Response({"error": "Manager not found"}, status=status.HTTP_404_NOT_FOUND)

    team = manager.team
    players = Player.objects.filter(team=team)
    team_resources = TeamResource.objects.filter(team=team)

    team_id = team.id
    team_name = team.name
    team_tag = team.tag
    team_logo_url = team.logo.url
    team_region_name = team.region.name
    team_region_flag = team.region.flag_url.url
    try:
        season = Season.objects.get(is_finished=False)
    except:
        season = None
    is_reg_to_current_season = TournamentRegistration.objects.filter(
        user=user_id, team=team, season=season).exists()

    team_data = {
        "team_id": team_id,
        "team_name": team_name,
        "team_tag": team_tag,
        "team_logo_url": team_logo_url,
        "team_region_name": team_region_name,
        "team_region_flag": team_region_flag,
        "players": [{"id": player.id,
                     "username": player.username,
                     "avatar": player.avatar,
                     "mmr": player.mmr,
                     "league": player.league_id,
                     "race": player.race_id,
                     "wins": player.wins,
                     "total_games": player.total_games,
                     "team": player.team_id,
                     "user": player.user_id,
                     "region": player.region} for player in players],
        "team_resources": list(team_resources.values()),
        "is_reg_to_current_season": is_reg_to_current_season
    }

    return Response(team_data)


@api_view(['GET'])
def get_league_by_mmr(request):
    mmr = request.query_params.get('mmr', None)
    region = request.query_params.get('region', None)
    league_frames = leagueFrames()

    if mmr is None:
        return Response({"error": "MMR is required in query parameter"}, status=status.HTTP_400_BAD_REQUEST)
    if region is None:
        return Response({"error": "Region is required in query parameter"}, status=status.HTTP_400_BAD_REQUEST)
    if mmr == 'NaN':
        return Response({"league": 0}, status=status.HTTP_200_OK)
    try:
        resp = get_league(mmr, league_frames, region)
        return Response({"league": resp}, status=status.HTTP_200_OK)
    except:
        return Response({"error": "Something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([permissions.IsAdminUser])
def user_staff_status_true(request):
    try:
        user = User.objects.get(username=request.data.get('username'))
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    if user.is_staff:
        return Response({"error": "User is already staff"}, status=status.HTTP_400_BAD_REQUEST)

    user.is_staff = True
    user.save()

    return Response({"message": "User staff status updated"}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([permissions.IsAdminUser])
def user_staff_status_false(request):
    try:
        user = User.objects.get(username=request.data.get('username'))
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    if not user.is_staff:
        return Response({"error": "User is already not staff"}, status=status.HTTP_400_BAD_REQUEST)

    user.is_staff = False
    user.save()

    return Response({"message": "User staff status updated"}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_current_tournaments(request):
    tournaments = Tournament.objects.filter(match_start_time__lte=timezone.now(
    ), is_finished=False).order_by('match_start_time')
    serializer = TournamentsSerializer(tournaments, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_current_season(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    if season.start_datetime < timezone.now():
        season.can_register = False
        season.save()
    serializer = SeasonsSerializer(season)
    return Response(serializer.data)


@api_view(['GET'])
def get_last_season(request):
    seasons = Season.objects.last()
    serializer = SeasonsSerializer(seasons)
    return Response(serializer.data)


@api_view(['GET'])
def get_last_season_number(request):
    try:
        season = Season.objects.last()
        season_number = season.number
    except:
        return Response({"error": "Seasons have not yet been held"}, status=status.HTTP_404_NOT_FOUND)
    return Response(season_number)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def randomizeGroups(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "Season not found"}, status=status.HTTP_404_NOT_FOUND)
    group_cnt = request.data.get('groupCnt')
    if group_cnt is None:
        return Response({"error": "groupCnt is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        group_cnt = int(group_cnt)
    except:
        return Response({"error": "groupCnt must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
    if int(group_cnt) <= 0:
        return Response({"error": "groupCnt must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)

    tournamentRegistrations = TournamentRegistration.objects.filter(
        season=season)
    distr = distribute_teams_to_groups(
        list(tournamentRegistrations), group_cnt)
    if distr['status'] != 201:
        return Response({"error": distr["error"]}, status=distr['status'])
    groupStages = GroupStage.objects.filter(season=season)

    responseData = []
    for groupStage in groupStages:
        groupInfo = {
            'id': groupStage.id,
            'groupMark': groupStage.groupMark,
            'teams': [TeamsSerializer(team).data for team in groupStage.teams.all()]
        }
        responseData.append(groupInfo)

    return Response(responseData)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getPlayerToCurrentTournament(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    user = request.user
    if season:
        playerToTournaments = PlayerToTournament.objects.filter(
            Season=season, user=user)
        serializer = PlayerToTournamentSerializer(
            playerToTournaments, many=True)
        return Response(serializer.data)
    return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def registredToCurrentSeasonTeams(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    tournamentRegistrations = TournamentRegistration.objects.filter(
        season=season)
    responseData = []
    for tournamentRegistration in tournamentRegistrations:
        team_id = tournamentRegistration.team.id
        team = Team.objects.get(id=team_id)
        teamData = TeamsSerializer(team).data
        responseData.append(teamData)
    return Response(responseData)


@api_view(['GET'])
def groupsToCurrentSeason(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    groupStages = GroupStage.objects.filter(season=season)
    responseData = []
    for groupStage in groupStages:
        groupInfo = {
            'id': groupStage.id,
            'groupMark': groupStage.groupMark,
            'teams': [TeamsSerializer(team).data for team in groupStage.teams.all()]
        }
        responseData.append(groupInfo)
    return Response(responseData)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def postTeamToGroup(request):
    groupStageMark = request.data.get('groupStageMark')
    teamId = request.data.get('teamId')
    if groupStageMark is None and teamId is None:
        return Response({"error": "groupStageMark and teamId are required"}, status=status.HTTP_400_BAD_REQUEST)
    if groupStageMark is None:
        return Response({"error": "groupStageMark is required"}, status=status.HTTP_400_BAD_REQUEST)
    if teamId is None:
        return Response({"error": "teamId is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        team = TournamentRegistration.objects.get(
            team_id=teamId, season__is_finished=False)
    except TournamentRegistration.DoesNotExist:
        return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)
    season = Season.objects.get(is_finished=False)
    try:
        groupStage = GroupStage.objects.get(
            season=season, groupMark=groupStageMark)
    except GroupStage.DoesNotExist:
        groupStage = GroupStage.objects.create(
            season=season, groupMark=groupStageMark)

    try:
        otherGroup = GroupStage.objects.exclude(
            id=groupStage.id).get(season=season, teams=team.team)
        otherGroup.teams.remove(team.team)
        otherGroup.save()
        if otherGroup.teams.count() == 0:
            otherGroup.delete()
    except GroupStage.DoesNotExist:
        pass
    groupStage.teams.add(team.team)
    groupStage.save()
    groupStageData = groupStageSerializer(groupStage).data
    return Response(groupStageData)


@api_view(['DELETE'])
@permission_classes([permissions.IsAdminUser])
def deleteTeamFromGroup(request):
    teamId = request.data.get('teamId')
    if teamId is None:
        return Response({"error": "teamId is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        team = Team.objects.get(id=teamId)
    except Team.DoesNotExist:
        return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)
    season = Season.objects.get(is_finished=False)
    groupStage = GroupStage.objects.get(season=season, teams=team)
    groupStage.teams.remove(team)
    groupStage.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def getToursToCurrentSeason(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    matches = Tournament.objects.filter(season=season)
    responseData = []
    for match in matches:
        responseData.append(TournamentsSerializer(match).data)
    return Response(responseData)


@api_view(['DELETE'])
@permission_classes([permissions.IsAdminUser])
def deleteTournamentsToCurrentSeason(request):
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    matches = Tournament.objects.filter(season=season)
    for match in matches:
        match.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getToursByManager(request):
    user = request.user
    season = Season.objects.get(is_finished=False)
    if user.is_anonymous:
        return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        manager = Manager.objects.get(user=user)
    except Manager.DoesNotExist:
        return Response({"error": "Manager not found"}, status=status.HTTP_404_NOT_FOUND)
    team = manager.team
    tournaments = Tournament.objects.filter(
        Q(team_one=team) | Q(team_two=team), season=season)
    if tournaments.count() == 0:
        return Response([])
    tournaments = tournaments.order_by('match_start_time')
    responseData = []
    for tournament in tournaments:
        if tournament.asked_team is not None:
            if tournament.asked_team.id != team.id:
                timeSuggested = tournament.ask_for_other_time
            else:
                timeSuggested = None
        else:
            timeSuggested = None
        opponent = tournament.team_two if tournament.team_one == team else tournament.team_one
        team_in_tour_num = 1 if tournament.team_one == team else 2
        opponent_data = TeamsSerializer(opponent).data
        opp_players_to_tournament = PlayerToTournament.objects.filter(
            user=opponent.user, Season=season)
        opp_players_to_tournament_data = []
        for player in opp_players_to_tournament:
            opp_players_to_tournament_data.append({
                'id': player.player.id,
                'username': player.player.username
            })
        opponent_data['players'] = opp_players_to_tournament_data
        if (not tournament.is_finished):
            responseData.append({
                'id': tournament.id,
                'startTime': tournament.match_start_time,
                'timeSuggested': timeSuggested,
                'opponent': opponent_data,
                'isFinished': tournament.is_finished,
                'teamInTournament': team_in_tour_num
            })
        else:
            matches = Match.objects.filter(tournament=tournament)
            matches_data = MatchesSerializer(matches, many=True).data
            responseData.append({
                'id': tournament.id,
                'startTime': tournament.match_start_time,
                'timeSuggested': timeSuggested,
                'opponent': opponent_data,
                'isFinished': tournament.is_finished,
                'teamInTournament': team_in_tour_num,
                'team_one_wins': tournament.team_one_wins,
                'team_two_wins': tournament.team_two_wins,
                'matches': matches_data
            })
    return Response(responseData)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def setTimeSuggestion(request):
    user = request.user
    id = request.data.get('id')
    if id is None:
        return Response({"error": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if user.is_anonymous:
        return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        manager = Manager.objects.get(user=user)
    except Manager.DoesNotExist:
        return Response({"error": "Manager not found"}, status=status.HTTP_404_NOT_FOUND)
    team = manager.team
    try:
        tournament = Tournament.objects.get(id=id)
    except Tournament.DoesNotExist:
        return Response({"error": "Tournament not found"}, status=status.HTTP_404_NOT_FOUND)
    if tournament.team_one != team and tournament.team_two != team:
        return Response({"error": "Tournament not found"}, status=status.HTTP_404_NOT_FOUND)
    tournament.ask_for_other_time = request.data.get('timeSuggestion')
    tournament.asked_team = team
    tournament.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def acceptTimeSuggestion(request):
    user = request.user
    id = request.data.get('id')
    if id is None:
        return Response({"error": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if user.is_anonymous:
        return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        manager = Manager.objects.get(user=user)
    except Manager.DoesNotExist:
        return Response({"error": "Manager not found"}, status=status.HTTP_404_NOT_FOUND)
    team = manager.team
    try:
        tournament = Tournament.objects.get(id=id)
    except Tournament.DoesNotExist:
        return Response({"error": "Tournament not found"}, status=status.HTTP_404_NOT_FOUND)
    if tournament.team_one != team and tournament.team_two != team:
        return Response({"error": "Tournament not found"}, status=status.HTTP_404_NOT_FOUND)
    if tournament.ask_for_other_time is None:
        return Response({"error": "Time suggestion not found"}, status=status.HTTP_404_NOT_FOUND)
    tournament.match_start_time = tournament.ask_for_other_time
    tournament.ask_for_other_time = None
    tournament.asked_team = None
    tournament.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_players_by_teams(request):
    user = request.user
    if user.is_anonymous:
        return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    teams = TournamentRegistration.objects.filter(season=season).select_related(
        'team', 'user').prefetch_related('user__playertotournament_set')
    response = {}
    players = {}
    for team in teams:
        try:
            user = team.user
            team_players = team.user.playertotournament_set.all()
            for team_player in team_players:
                players[team_player.player.id] = team_player.player.username
            response[team.team.pk] = players
            players = {}
        except Team.DoesNotExist:
            return Response({"error": "Team with id " + str(team.team.pk) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    sorted_response = dict(sorted(response.items(), key=lambda x: x[0]))
    return Response(sorted_response)


@api_view(['GET'])
def get_season_by_number(request, season):
    groups_data, playoff_data = get_season_data(season)
    if groups_data is None and playoff_data is None:
        return Response({"error": "Season with number " + str(season) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"groups": groups_data, "playoff": playoff_data})


@api_view(['GET'])
def get_team_by_id(request, team_id):
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return Response({"error": "Team with id " + str(team_id) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    team_resources = TeamResource.objects.filter(team=team)
    try:
        manager = Manager.objects.get(team=team)
        manager_contact = ManagerContact.objects.filter(user=manager.user)
    except Manager.DoesNotExist:
        manager = None
        manager_contact = None
    players = Player.objects.filter(team=team)
    tournaments = Tournament.objects.filter(
        Q(team_one=team) | Q(team_two=team), is_finished=True)
    tournaments_data = []
    for tournament in tournaments:
        tournaments_data.append({
            "id": tournament.id,
            "season": tournament.season.number,
            "matchStartTime": tournament.match_start_time,
            "wins": tournament.team_one_wins if tournament.team_one == team else tournament.team_two_wins,
            "opponent": tournament.team_two.name if tournament.team_one == team else tournament.team_one.name,
            "opponentWins": tournament.team_two_wins if tournament.team_one == team else tournament.team_one_wins,
        })
    return Response(
        {
            "team": TeamsSerializer(team).data,
            "teamRegion": {"url": team.region.flag_url.url, "name": team.region.name},
            "teamResources": TeamResourcesSerializer(team_resources, many=True).data,
            "manager": manager.user.username if manager is not None else None,
            "managerContacts": ManagerContactsSerializer(manager_contact, many=True).data,
            "players": PlayersSerializer(players, many=True).data,
            "tournaments": tournaments_data
        })


@api_view(['GET'])
def get_player_by_id(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return Response({"error": "Player with id " + str(player_id) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    related_matches = Match.objects.filter(Q(player_one=player) | Q(
        player_two=player)).select_related('player_one', 'player_two')
    matches_data = []
    for match in related_matches:
        opponent = match.player_two if match.player_one == player else match.player_one
        opponent_id = opponent.id
        opponent_name = opponent.username
        opponent_tag = opponent.team.tag
        matches_data.append({
            "id": match.id,
            "map": match.map,
            "opponent": opponent_name,
            "opponentTag": opponent_tag,
            "opponentId": opponent_id,
            "winner": True if match.winner == player else False,
        })
    return Response({"player": PlayersSerializer(player).data, "matches": matches_data})


@api_view(['GET'])
def get_tournament_by_id(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return Response({"error": "Tournament with id " + str(tournament_id) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    tournament_data = {
        "id": tournament.id,
        "season": tournament.season.number,
        "matchStartTime": tournament.match_start_time,
        "teamOne": tournament.team_one.name,
        "teamOneId": tournament.team_one.id,
        "teamOneLogo": tournament.team_one.logo.url if tournament.team_one.logo else None,
        "teamTwo": tournament.team_two.name,
        "teamTwoId": tournament.team_two.id,
        "teamTwoLogo": tournament.team_two.logo.url if tournament.team_two.logo else None,
        "teamOneWins": tournament.team_one_wins,
        "teamTwoWins": tournament.team_two_wins,
    }
    related_matches = Match.objects.filter(tournament=tournament)
    matches_data = []
    for match in related_matches:
        if (match.winner is not None):
            winner = True if match.winner == match.player_one else False
        else:
            winner = None
        matches_data.append({
            "id": match.id,
            "map": match.map,
            "playerOneId": match.player_one.id,
            "playerTwoId": match.player_two.id,
            "playerOne": match.player_one.username,
            "playerTwo": match.player_two.username,
            "winner":  winner,
        })

    return Response({"tournament": tournament_data, "matches": matches_data})
