import configparser

import requests

from main.models import *
from main.serializers import *
from rest_framework import status, viewsets, exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from djoser.utils import logout_user
from django.utils import timezone
from django.contrib.auth.models import User

from .permissions import *
from .utils import get_blizzard_data, get_new_access_token
# Create your views here.

config = configparser.ConfigParser()
config.read('.ini')

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = '_limit'
    max_page_size =  100


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
            raise exceptions.PermissionDenied("You can only create objects with your own id")  
        else:
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

            league = get_league(serializer.validated_data['mmr'], league_frames, region)
            serializer.validated_data['league'] = league
        
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied("You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class ManagersViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.all()
    serializer_class = ManagersSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly, )

    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied("You can only create objects with your own id")
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

    def perform_create(self, serializer):
        
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied("You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)
    

class TeamResourcesViewSet(viewsets.ModelViewSet):
    queryset = TeamResource.objects.all()
    serializer_class = TeamResourcesSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)

    def perform_create(self, serializer):
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied("You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = TeamResource.objects.all()
        team = self.request.query_params.get('team')

        if team is not None:
            queryset = queryset.filter(team=team)
        return queryset
    

class StagesViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()
    serializer_class = StagesSerializer
    permission_classes = (isAdminOrReadOnly, )


class SeasonsViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonsSerializer
    permission_classes = (isAdminOrReadOnly, )
    
    def get_object_or_404(self):
        number = self.kwargs.get('pk')
        try:
            return Season.objects.get(number=number)
        except Season.DoesNotExist:
            return Response({"error": "Season not found"}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object_or_404()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)



class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = (isAdminOrReadOnly, )


class TournamentsViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all()
    serializer_class = TournamentsSerializer
    permission_classes = (isAdminOrReadOnly, )


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

    def perform_create(self, serializer):
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied("You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)
    

class MatchesViewSet(viewsets.ModelViewSet):
    serializer_class = MatchesSerializer
    permission_classes = (canEditMatchField,)

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
            raise exceptions.PermissionDenied("You can only create objects with your own id")
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


class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    permission_classes = (isAdminOrReadOnly, )
    

class UserDeviceViewSet(viewsets.ModelViewSet):
    queryset = UserDevice.objects.all()
    serializer_class = UserDevicesSerializer
    permission_classes = (permissions.IsAdminUser | permissions.IsAuthenticated, )
    
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
            user_device = UserDevice.objects.create(user=self.request.user, device=0)
        
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

    def destroy(self, request, *args, **kwargs):
        player_id = self.kwargs.get('pk')
        user = request.user
        if user.is_anonymous:
            return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
        print(player_id)
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            player_to_tournament = PlayerToTournament.objects.get(player=player, user=user)
            player_to_tournament.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PlayerToTournament.DoesNotExist:
            try:
                player_to_tournament = PlayerToTournament.objects.get(player=player)
                if player_to_tournament:
                    return Response({"error": "You are not owner of this player"}, status=status.HTTP_403_FORBIDDEN)
            except PlayerToTournament.DoesNotExist:
                return Response({"error": "Player does not registered"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "Player does not registered"}, status=status.HTTP_404_NOT_FOUND)

class GetClanMembers(APIView):
    def get(self, request, clan_tag):
        api_url = f'https://sc2pulse.nephest.com/sc2/api/character/search?term=%5B{clan_tag}%5D'

        league_frames = leagueFrames()
        
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if len(data) == 0:
                    return Response({"error": "Clan not found"}, status=status.HTTP_404_NOT_FOUND)
                character_data = []
                for item in data:
                    character = item['members']['character']
                    name = character['name'].split('#')[0]
                    ch_id = character['battlenetId']
                    region = character['region']
                    mmr = item['currentStats']['rating']
                    if (not mmr):
                        mmr = item['ratingMax']
                    if region in ['TW', 'CN']:
                        region = 'KR'

                    league_max = get_league(mmr, league_frames, region)
                    if league_max == 7:
                        league_max = item['leagueMax'] + 1

                    match region:
                        case 'US':
                            region = 1
                        case 'EU':
                            region = 2
                        case 'KR':
                            region = 3


                    realm = character['realm']


                    if ('protossGamesPlayed' in item['members']):
                        race = 3
                    elif ('zergGamesPlayed' in item['members']):
                        race = 1
                    elif ('terranGamesPlayed' in item['members']):
                        race = 2
                    elif ('randomGamesPlayed' in item['members']):
                        race = 4
                    else:
                        race = 'unknown'




                    character_info = {
                        "username": name,
                        "region": region,
                        "realm": realm,
                        "id": ch_id,
                        "league": league_max,
                        "race": race,
                        "mmr": mmr
                    }

                    character_data.append(character_info)
                region_priority = {
                    2: 0,
                    1: 1,
                    3: 2
                }
                character_data = sorted(character_data, key=lambda k: (region_priority.get(k['region'], float('inf')), -k['mmr']))

                return Response(character_data, status=status.HTTP_200_OK)
            else:
                raise Exception(f"Error {response.status_code}")
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




def get_avatar(region, realm, character_id):
    try:
        response = get_blizzard_data(region, realm, character_id)
        if response.status_code == 404:
            return None
        data = response.json()
        avatar = data['avatarUrl']
        return avatar
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        else:
            raise e



@api_view(['GET'])
def get_team_and_related_data(request):
    user_id = request.query_params.get('user', None)
    if user_id is None:
        print("User ID is required in query parameter")
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
    print(team_region_flag)
    try:
        season = Season.objects.get(is_finished=False)
    except:
        season = None
    is_reg_to_current_season = TournamentRegistration.objects.filter(user=user_id, team=team, season=season).exists()

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
                     "region": player.region} for player in players]
,
        "team_resources": list(team_resources.values()),
        "is_reg_to_current_season": is_reg_to_current_season
    }

    return Response(team_data)


def leagueFrames():
    league_frames = {
            'EU_1': LeagueFrame.objects.get(region='eu', league=1).frame_max,
            'EU_2': LeagueFrame.objects.get(region='eu', league=2).frame_max,
            'EU_3': LeagueFrame.objects.get(region='eu', league=3).frame_max,
            'EU_4': LeagueFrame.objects.get(region='eu', league=4).frame_max,
            'EU_5': LeagueFrame.objects.get(region='eu', league=5).frame_max,
            'EU_6': LeagueFrame.objects.get(region='eu', league=6).frame_max,
            'US_1': LeagueFrame.objects.get(region='us', league=1).frame_max,
            'US_2': LeagueFrame.objects.get(region='us', league=2).frame_max,
            'US_3': LeagueFrame.objects.get(region='us', league=3).frame_max,
            'US_4': LeagueFrame.objects.get(region='us', league=4).frame_max,
            'US_5': LeagueFrame.objects.get(region='us', league=5).frame_max,
            'US_6': LeagueFrame.objects.get(region='us', league=6).frame_max,
            'KR_1': LeagueFrame.objects.get(region='kr', league=1).frame_max,
            'KR_2': LeagueFrame.objects.get(region='kr', league=2).frame_max,
            'KR_3': LeagueFrame.objects.get(region='kr', league=3).frame_max,
            'KR_4': LeagueFrame.objects.get(region='kr', league=4).frame_max,
            'KR_5': LeagueFrame.objects.get(region='kr', league=5).frame_max,
            'KR_6': LeagueFrame.objects.get(region='kr', league=6).frame_max
        }
    return league_frames


def get_league(mmr, league_frames, region):
    mmr = int(mmr)
    if (mmr > league_frames[f'{region}_6']):
        league_max = 7
    elif (mmr > league_frames[f'{region}_5']):
        league_max = 6
    elif (mmr > league_frames[f'{region}_4']):
        league_max = 5
    elif (mmr > league_frames[f'{region}_3']):
        league_max = 4
    elif (mmr > league_frames[f'{region}_2']):
        league_max = 3
    elif (mmr > league_frames[f'{region}_1']):
        league_max = 2
    else:
        league_max = 1
    return league_max


@api_view(['GET'])
def get_league_by_mmr(request):
    mmr = request.query_params.get('mmr', None)
    region = request.query_params.get('region', None)
    league_frames = leagueFrames()

    if mmr is None:
        return Response({"error": "MMR is required in query parameter"}, status=status.HTTP_400_BAD_REQUEST)
    if region is None:
        return Response({"error": "Region is required in query parameter"}, status=status.HTTP_400_BAD_REQUEST)
    if mmr=='NaN':
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
    tournaments = Tournament.objects.filter(match_start_time__lte = timezone.now(), is_finished = False).order_by('match_start_time')
    serializer = TournamentsSerializer(tournaments, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_current_season(request):
    seasons = Season.objects.filter(is_finished = False)
    if len(seasons) == 0:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)
    season = seasons[0]
    serializer = SeasonsSerializer(season)
    return Response(serializer.data)


@api_view(['GET'])
def get_last_season(request):
    seasons = Season.objects.last()
    print(request, seasons)
    serializer = SeasonsSerializer(seasons)
    return Response(serializer.data)


@api_view(['GET'])
def get_last_season_number(request):
    season = Season.objects.last().number
    print(request, season)
    return Response(season)