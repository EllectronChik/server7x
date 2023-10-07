from main.serializers import *
from rest_framework import viewsets
from .permissions import *
from main.models import *
from rest_framework.pagination import PageNumberPagination
from django.db.models import F, ExpressionWrapper, BooleanField
from datetime import datetime
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import requests
# Create your views here.

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = '_limit'
    max_page_size =  100


class TeamsViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamsSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination


class PlayersViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayersSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination


class ManagersViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.all()
    serializer_class = ManagersSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise PermissionDenied("You can only create objects with your own id")

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
    

class TeamResourcesViewSet(viewsets.ModelViewSet):
    queryset = TeamResource.objects.all()
    serializer_class = TeamResourcesSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    

class StagesViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()
    serializer_class = StagesSerializer
    permission_classes = (isAdminOrReadOnly, )
    

class RegionsViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionsSerializer
    permission_classes = (isAdminOrReadOnly, )
    

class MatchesViewSet(viewsets.ModelViewSet):
    serializer_class = MatchesSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)

    def get_queryset(self):
        queryset = Match.objects.all()
        season = self.request.query_params.get('season')
        Stage = self.request.query_params.get('stage')
        player_one = self.request.query_params.get('player_one')
        player_two = self.request.query_params.get('player_two')
        is_finished = self.request.query_params.get('is_finished')
        started = self.request.query_params.get('started')
        if season is not None:
            queryset = queryset.filter(season=season)
        if Stage is not None:
            queryset = queryset.filter(stage=Stage)
        if player_one is not None:
            queryset = queryset.filter(player_one=player_one)
        if player_two is not None:
            queryset = queryset.filter(player_two=player_two)
        if is_finished is not None:
            queryset = queryset.filter(is_finished=is_finished)

        if started is not None:
            current_time = datetime.now()
            if started == 'True':
                queryset = queryset.filter(match_start_time__lte=current_time)
            elif started == 'False':
                queryset = queryset.filter(match_start_time__gt=current_time)

        return queryset


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


class AskForStaffViewSet(viewsets.ModelViewSet):
    queryset = AskForStaff.objects.all()
    serializer_class = AskForStaffSerializer
    permission_classes = (isAdminOrOwnerOrReadOnly,)
    def perform_create(self, serializer):

        if serializer.validated_data['user'] != self.request.user:
            raise PermissionDenied("You can only create objects with your own id")

        serializer.save(user=self.request.user)


class GetClanMembers(APIView):
    def get(self, request, clan_tag):
        api_url = f'https://sc2pulse.nephest.com/sc2/api/character/search?term=%5B{clan_tag}%5D'
        
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
                    ch_id = character['id']
                    league_max = item['leagueMax']
                    mmr = item['currentStats']['rating']
                    if (not mmr):
                        mmr = item['ratingMax']
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
                        "name": name,
                        "id": ch_id,
                        "league": league_max,
                        "race": race,
                        "mmr": mmr
                    }
                    character_data.append(character_info)
                return Response(character_data, status=status.HTTP_200_OK)
            else:
                raise Exception(f"Error {response.status_code}")
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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