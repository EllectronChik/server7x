from main.seriializers import *
from rest_framework import viewsets
from .permissions import *
from main.models import *
from rest_framework.pagination import PageNumberPagination

# Create your views here.

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = '_limit'
    max_page_size =  100


class TeamsViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamsSerializer
    permission_classes = (isAdminOrReadOnly, isOwnerOrReadOnly)
    pagination_class = CustomPageNumberPagination


class PlayersViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayersSerializer
    permission_classes = (isAdminOrReadOnly, isOwnerOrReadOnly)
    pagination_class = CustomPageNumberPagination


class ManagersViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.all()
    serializer_class = ManagersSerializer
    permission_classes = (isAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination
    

class ManagerContactsViewSet(viewsets.ModelViewSet):
    queryset = ManagerContact.objects.all()
    serializer_class = ManagerContactsSerializer
    permission_classes = (isAdminOrReadOnly, isOwnerOrReadOnly)
    

class TeamResourcesViewSet(viewsets.ModelViewSet):
    queryset = TeamResource.objects.all()
    serializer_class = TeamResourcesSerializer
    permission_classes = (isAdminOrReadOnly, isOwnerOrReadOnly)
    

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
    permission_classes = (isAdminOrReadOnly, isOwnerOrReadOnly)

    def get_queryset(self):
        queryset = Match.objects.all()
        season = self.request.query_params.get('season')
        Stage = self.request.query_params.get('stage')
        player_one = self.request.query_params.get('player_one')
        player_two = self.request.query_params.get('player_two')
        is_finished = self.request.query_params.get('is_finished')
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
        return queryset

    # filter_fields = ['season', 'stage', 'player_one', 'player_two', 'is_finished']


class RaceViewSet(viewsets.ModelViewSet):
    queryset = Race.objects.all()
    serializer_class = RaceSerializer
    permission_classes = (isAdminOrReadOnly, )