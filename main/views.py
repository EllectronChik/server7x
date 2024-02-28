import configparser
import ast

from main.models import *
from main.serializers import *
from main.utils import leagueFrames, get_league, form_character_data, get_avatar
from rest_framework import status, viewsets, exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, F, Count, Max

from .permissions import *
from .utils import distribute_teams_to_groups, image_compressor, get_season_data

# Initialize configuration parser
config = configparser.ConfigParser()
config.read('.ini')


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination class to define page size and behavior.
    """
    page_size = 10  # Default page size
    page_size_query_param = '_limit'  # Parameter to specify page size in request query
    max_page_size = 100  # Maximum allowed page size


class TeamsViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and editing Team instances.

    Provides `list`, `create`, `retrieve`, `update`, and `destroy` actions.
    """
    serializer_class = TeamsSerializer  # Serializer class for TeamsViewSet
    # Define permission classes
    permission_classes = (IsAdminOrOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination  # Define pagination class

    def get_queryset(self):
        """
        Get the queryset for Team instances.

        Returns:
            queryset: A queryset of Team instances filtered based on query parameters.
        """
        queryset = Team.objects.all()  # Get all Team instances
        tag = self.request.query_params.get(
            'tag')  # Get tag parameter from request
        if tag is not None:
            # Filter queryset based on tag parameter
            queryset = queryset.filter(tag=tag)
        return queryset

    def perform_create(self, serializer):
        """
        Perform creation of a new Team instance.

        Args:
            serializer: Serializer instance for Team.

        Raises:
            PermissionDenied: If user tries to create with another user's ID.
        """
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")  # Permission check
        logo = serializer.validated_data.get(
            'logo')  # Get logo data from serializer
        if logo:
            # Compress image and update serializer data
            image_file = image_compressor(
                logo, serializer.validated_data['tag'])
            serializer.validated_data['logo'] = image_file
        # Save serializer data with user
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """
        Perform update of an existing Team instance.

        Args:
            serializer: Serializer instance for Team.
        """
        logo = serializer.validated_data.get(
            'logo')  # Get logo data from serializer
        if logo:
            # Compress image and update serializer data
            image_file = image_compressor(
                logo, Team.objects.get(id=serializer.instance.id).tag)
            serializer.validated_data['logo'] = image_file
        # Save serializer data with user
        serializer.save(user=self.request.user)


class PlayersViewSet(viewsets.ModelViewSet):
    """
    A viewset for handling CRUD operations on Player objects.
    """

    serializer_class = PlayersSerializer
    # Set permission classes for the viewset
    permission_classes = (IsAdminOrOwnerOrReadOnly,)
    # Set pagination class for the viewset
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """
        Get the queryset of Player objects based on optional query parameters.

        Returns:
            QuerySet: A queryset of Player objects filtered by optional query parameters.
        """
        queryset = Player.objects.all()
        team = self.request.query_params.get('team')

        if team is not None:
            queryset = queryset.filter(team=team)

        return queryset

    def perform_create(self, serializer):
        """
        Perform custom actions when creating a new Player object.

        Args:
            serializer (PlayersSerializer): The serializer instance used for creating the object.

        Raises:
            PermissionDenied: If the creating user is not the same as the request user.
        """
        if serializer.validated_data['league'] is None:
            # If league is not provided, calculate it based on MMR and region
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

        # Check if the creating user is the same as the request user
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            # Save the object with the request user as the owner
            serializer.save(user=self.request.user)


class ManagersViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for CRUD operations on Manager objects.
    """

    queryset = Manager.objects.all()  # Retrieve all Manager objects
    # Use ManagersSerializer for serialization
    serializer_class = ManagersSerializer
    # Permission classes for view level authorization
    permission_classes = (IsAdminOrOwnerOrReadOnly, )
    # Custom pagination class for pagination
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        """
        Perform custom logic when creating a new Manager object.
        """

        # Check if the user attempting to create the object is the same as the logged-in user
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            # Assign the logged-in user as the owner of the Manager object
            serializer.save(user=self.request.user)

    def get_queryset(self):
        """
        Retrieve the queryset of Manager objects based on optional query parameters.
        """

        queryset = Manager.objects.all()  # Initial queryset containing all Manager objects
        # Retrieve the 'user' query parameter if provided
        user = self.request.query_params.get('user')

        # If 'user' query parameter is provided, filter the queryset to include only Manager objects
        # associated with the specified user
        if user is not None:
            queryset = queryset.filter(user=user)
        return queryset


class ManagerContactsViewSet(viewsets.ModelViewSet):
    """
    A viewset for managing manager contacts.
    """
    # Specify the queryset to retrieve all ManagerContact objects.
    queryset = ManagerContact.objects.all()

    # Specify the serializer class to use for serialization and deserialization.
    serializer_class = ManagerContactsSerializer

    # Specify the permission classes for this viewset.
    # Users must be admins or owners to modify objects, while others can only read.
    permission_classes = (IsAdminOrOwnerOrReadOnly,)

    # Specify the pagination class to paginate the queryset.
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        """
        Perform custom actions after creating a ManagerContact object.

        Args:
            serializer: The serializer instance used to create the object.

        Raises:
            PermissionDenied: If the user trying to create the object is not the owner.
        """
        # Check if the user creating the object is the owner.
        if serializer.validated_data['user'] != self.request.user:
            # If not, deny permission to create the object.
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            # If the user is the owner, save the object with the user's ID.
            serializer.save(user=self.request.user)


class TeamResourcesViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for interacting with TeamResource objects.
    """
    queryset = TeamResource.objects.all()  # Retrieve all TeamResource objects
    # Use the TeamResourcesSerializer for serialization
    serializer_class = TeamResourcesSerializer
    # Set permission classes for viewset
    permission_classes = (IsAdminOrOwnerOrReadOnly,)
    # Use custom pagination class for pagination
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        """
        Perform additional actions upon object creation.

        Args:
            serializer (TeamResourcesSerializer): The serializer instance.

        Raises:
            PermissionDenied: If user attempting to create object is not the owner.
        """
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)

    def get_queryset(self):
        """
        Retrieve the queryset based on provided query parameters.

        Returns:
            queryset: Filtered queryset based on provided query parameters.
        """
        queryset = TeamResource.objects.all()  # Retrieve all TeamResource objects
        # Get 'team' query parameter from request
        team = self.request.query_params.get('team')

        if team is not None:
            # Filter queryset by 'team' if provided
            queryset = queryset.filter(team=team)
        return queryset


class SeasonsViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for handling CRUD operations on Season objects.

    Inherits:
        viewsets.ModelViewSet

    Attributes:
        queryset (QuerySet): Set of all Season objects.
        serializer_class (Serializer): Serializer class for Season objects.
        permission_classes (tuple): Tuple of permission classes.
        pagination_class (Pagination): Pagination class for listing objects.
    """
    queryset = Season.objects.all()
    serializer_class = SeasonsSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def get_object_or_404(self):
        """
        Retrieve a single Season instance by its primary key or return a 404 response if not found.

        Returns:
            Season: The requested Season instance.

        Raises:
            Http404: If the Season instance does not exist.
        """
        number = self.kwargs.get('pk')
        try:
            return Season.objects.get(number=number)
        except Season.DoesNotExist:
            return Response({"error": "Season not found"}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update a Season instance.

        Args:
            request (Request): The HTTP request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: HTTP response with the updated Season data.
        """
        # Retrieve the Season instance or return a 404 error if not found
        instance = self.get_object_or_404()

        # Check if 'is_finished' field is present in request data
        if (request.data.get('is_finished')):
            # Find tournaments without group associated with the current season
            tournaments_off_group = Tournament.objects.filter(
                season=instance, group__isnull=True)

            # If no such tournaments exist, set winner to None
            if not tournaments_off_group:
                instance.winner = None
            else:
                # Find the highest stage tournament without group associated with the current season
                highest_stage = tournaments_off_group.order_by(
                    '-stage').values_list('stage', flat=True).distinct()[0]
                # If the highest stage is 999, consider the second highest stage
                if (highest_stage == 999):
                    highest_stage = Tournament.objects.filter(season=instance, group__isnull=True).order_by(
                        '-stage').values_list('stage', flat=True).distinct()[1]
                # Get the tournament at the highest stage
                tournament = Tournament.objects.get(
                    season=instance, group__isnull=True, stage=highest_stage)
                # Set winner of the season to winner of the tournament, if exists
                instance.winner = tournament.winner if tournament.winner else None

        # Serialize the updated instance with partial data
        serializer = self.get_serializer(
            instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Save the updated instance
        serializer.save()
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Perform creation of a new Season instance.

        Args:
            serializer (Serializer): The serializer instance.

        Raises:
            PermissionDenied: If a Season instance is already created and not finished.
        """
        try:
            # Check if any season is already created and not finished
            season = Season.objects.get(is_finished=False)
            if season:
                # Raise permission denied if such a season exists
                raise exceptions.PermissionDenied("Season is already created")
        except Season.DoesNotExist:
            # Save the new season
            serializer.save()


class TournamentsViewSet(viewsets.ModelViewSet):
    """
    A viewset for managing tournaments.

    This viewset provides CRUD operations for tournaments including creation, retrieval, updating, and deletion.
    It supports permissions for controlling access to these operations and utilizes pagination for handling large datasets.

    Attributes:
        queryset: Queryset representing all tournaments in the database.
        serializer_class: Serializer class used for serializing/deserializing tournament data.
        permission_classes: List of permission classes applied to control access to viewset actions.
        pagination_class: Class for pagination settings used in listing tournaments.
    """
    queryset = Tournament.objects.all()
    serializer_class = TournamentsSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        """
        Custom creation method for tournaments.

        This method performs custom validation and creation logic for tournament objects.
        It checks if a tournament with similar attributes already exists, validates team uniqueness,
        and handles the creation of tournaments with group-specific attributes.

        Args:
            serializer: Serializer instance containing validated data for tournament creation.

        Raises:
            ValidationError: If teams are equal.
            PermissionDenied: If tournament with same attributes already exists.

        Returns:
            None
        """
        # Check if a tournament with the same attributes already exists
        tournament = Tournament.objects.filter(
            season=Season.objects.get(is_finished=False),
            stage=serializer.validated_data['stage'],
            team_one=serializer.validated_data['team_one'],
            team_two=serializer.validated_data['team_two'],
            match_start_time=serializer.validated_data['match_start_time']
        ).first()

        # Check if team_one and team_two are the same
        if serializer.validated_data['team_one'] == serializer.validated_data['team_two']:
            raise exceptions.ValidationError("Teams can't be equal")

        # Check if a tournament already exists with the same attributes
        if tournament:
            raise exceptions.PermissionDenied("Tournament is already created")

        # If 'group' is provided in the validated data
        if 'group' in serializer.validated_data:
            try:
                # Attempt to find a tournament with the same attributes but different team_two
                tournament = Tournament.objects.get(
                    season=Season.objects.get(is_finished=False),
                    stage=serializer.validated_data['stage'],
                    group=serializer.validated_data['group'],
                    team_one=serializer.validated_data['team_one'],
                    match_start_time=serializer.validated_data['match_start_time']
                )
                if tournament and serializer.validated_data['team_one']:
                    tournament.team_two = serializer.validated_data['team_two']
                    tournament.save()
            except Tournament.DoesNotExist:
                try:
                    # Attempt to find a tournament with the same attributes but different team_one
                    tournament = Tournament.objects.get(
                        season=Season.objects.get(is_finished=False),
                        stage=serializer.validated_data['stage'],
                        group=serializer.validated_data['group'],
                        team_two=serializer.validated_data['team_two'],
                        match_start_time=serializer.validated_data['match_start_time']
                    )
                    if tournament and serializer.validated_data['team_two']:
                        tournament.team_one = serializer.validated_data['team_one']
                        tournament.save()
                except Tournament.DoesNotExist:
                    try:
                        # Attempt to find a tournament with the same attributes but different group
                        tournament = Tournament.objects.get(
                            season=Season.objects.get(is_finished=False),
                            stage=serializer.validated_data['stage'],
                            team_one=serializer.validated_data['team_one'],
                            team_two=serializer.validated_data['team_two'],
                            match_start_time=serializer.validated_data['match_start_time']
                        )
                        if tournament and serializer.validated_data['group']:
                            tournament.group = serializer.validated_data['group']
                            tournament.save()
                    except Tournament.DoesNotExist:
                        try:
                            # Attempt to find a tournament with the same attributes but different match_start_time
                            tournament = Tournament.objects.get(
                                season=Season.objects.get(is_finished=False),
                                stage=serializer.validated_data['stage'],
                                group=serializer.validated_data['group'],
                                team_two=serializer.validated_data['team_two'],
                                team_one=serializer.validated_data['team_one']
                            )
                            if tournament and serializer.validated_data['match_start_time']:
                                tournament.match_start_time = serializer.validated_data[
                                    'match_start_time']
                                tournament.save()
                        except Tournament.DoesNotExist:
                            try:
                                # Attempt to find a tournament with the same attributes but different group
                                tournament = Tournament.objects.get(
                                    season=Season.objects.get(
                                        is_finished=False),
                                    group=serializer.validated_data['group'],
                                    team_one=serializer.validated_data['team_one'],
                                    team_two=serializer.validated_data['team_two'],
                                    match_start_time=serializer.validated_data['match_start_time']
                                )
                                if tournament and serializer.validated_data['stage']:
                                    tournament.stage = serializer.validated_data['stage']
                                    tournament.save()
                            except Tournament.DoesNotExist:
                                serializer.save()
        else:
            serializer.save()


class RegionsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing regions.

    This class provides CRUD functionality for managing regions.

    Attributes:
        serializer_class: Serializer class for serializing/deserializing Region objects.
        permission_classes: List of permission classes applied to view methods.

    """

    serializer_class = RegionsSerializer
    permission_classes = (IsAdminOrReadOnly, )

    def get_queryset(self):
        """
        Get queryset of regions.

        This method retrieves a queryset of regions filtered by name if provided,
        otherwise returns all regions ordered by name.

        Returns:
            QuerySet: QuerySet of Region objects.

        """
        name = self.request.query_params.get('name')
        if name is not None:
            return Region.objects.filter(name=name)
        return Region.objects.all().order_by('name')


class TournamentRegistrationsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tournament registrations.

    This class handles CRUD operations for tournament registrations,
    providing endpoints for listing, creating, retrieving, updating, and deleting registrations.

    Attributes:
        queryset (QuerySet): QuerySet of TournamentRegistration objects.
        serializer_class (Serializer): Serializer class for TournamentRegistration objects.
        permission_classes (tuple): Tuple of permission classes.
        pagination_class (Paginator): Paginator class for pagination.

    """

    queryset = TournamentRegistration.objects.all()
    serializer_class = TournamentRegistrationSerializer
    permission_classes = (IsAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def perform_create(self, serializer):
        """
        Creates a new tournament registration object.

        This method is called when a new tournament registration is being created.
        It validates the serializer data to ensure the user is creating an object with their own ID,
        then saves the registration with the current user.

        Args:
            serializer: Serializer instance containing validated data for creating the registration.

        Raises:
            PermissionDenied: If the user is attempting to create a registration with a different ID.

        Returns:
            None

        """
        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class MatchesViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling CRUD operations on matches.

    This class implements methods for retrieving, creating, updating, and deleting match objects.
    It also defines permission classes and pagination.

    Attributes:
        serializer_class: Serializer class for the Match model.
        permission_classes: List of permission classes for view authorization.
        pagination_class: Class for pagination control.

    """

    serializer_class = MatchesSerializer
    permission_classes = (CanEditMatchField,)
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """
        Retrieves the queryset based on filtering criteria.

        This method filters the queryset based on query parameters such as player_one and player_two.

        Returns:
            QuerySet: Filtered queryset of Match objects.
        """

        queryset = Match.objects.all()
        player_one = self.request.query_params.get('player_one')
        player_two = self.request.query_params.get('player_two')
        if player_one is not None:
            queryset = queryset.filter(player_one=player_one)
        if player_two is not None:
            queryset = queryset.filter(player_two=player_two)

        return queryset

    def perform_create(self, serializer):
        """
        Performs creation of a new Match object.

        This method validates the user creating the match and assigns the current user as the creator.

        Args:
            serializer: Serializer instance containing validated data for creating the Match object.

        Raises:
            PermissionDenied: If the user creating the match is not the current authenticated user.

        Returns:
            None
        """

        if serializer.validated_data['user'] != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only create objects with your own id")
        else:
            serializer.save(user=self.request.user)


class MatchPlayersViewSet(viewsets.ViewSet):
    """
    ViewSet for handling player matches.

    This class implements methods for retrieving and serializing players associated with a match.

    Attributes:
        None
    """

    def list(self, request, match_id):
        """
        Retrieve a list of players for a given match.

        This method retrieves the match with the provided ID, then fetches and serializes the players associated
        with that match.

        Args:
            request: HTTP request object.
            match_id (int): ID of the match to retrieve players for.

        Returns:
            Response: HTTP response containing serialized player data or an error if the match is not found.
        """
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            return Response({"error": "Match not found"}, status=404)

        players = match.get_players()
        serializer = PlayersSerializer(players, many=True)
        return Response(serializer.data)


"""
ViewSet for retrieving teams associated with a match.

This ViewSet provides methods for retrieving teams associated with a match,
including handling the retrieval of teams, serialization, and response.

Attributes:
    None
"""


class MatchTeamsViewSet(viewsets.ViewSet):
    """
    ViewSet for retrieving teams associated with a match.

    This ViewSet provides methods for retrieving teams associated with a match,
    including handling the retrieval of teams, serialization, and response.

    Attributes:
        None
    """

    def list(self, request, match_id):
        """
        Retrieve teams associated with a match.

        This method retrieves teams associated with a match identified by the provided match_id.
        It handles exceptions if the match is not found, serializes the retrieved teams,
        and returns a response with the serialized data.

        Args:
            request: HTTP request object.
            match_id (int): Identifier for the match.

        Returns:
            Response: HTTP response object containing serialized teams data.

        """
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            return Response({"error": "Match not found"}, status=404)

        teams = match.get_teams()
        serializer = TeamsSerializer(teams, many=True)
        return Response(serializer.data)


class RaceViewSet(viewsets.ModelViewSet):
    """
    View set for managing race instances.

    This view set provides CRUD operations for race instances, including listing, creating, retrieving,
    updating, and deleting race objects.

    Attributes:
        queryset: Queryset containing all race instances.
        serializer_class: Serializer class for race instances.
        permission_classes: Permission classes for controlling access to race instances.
        pagination_class: Pagination class for paginating race instances.

    """

    queryset = Race.objects.all()
    serializer_class = RaceSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class MapsViewSet(viewsets.ModelViewSet):
    """
    View set for managing map instances.

    This view set provides CRUD operations for map instances, including listing, creating, retrieving,
    updating, and deleting map objects.

    Attributes:
        queryset: Queryset containing all map instances.
        serializer_class: Serializer class for map instances.
        permission_classes: Permission classes for controlling access to map instances.
        pagination_class: Pagination class for paginating map instances.

    """

    queryset = Map.objects.all()
    serializer_class = MapSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class LeagueViewSet(viewsets.ModelViewSet):
    """
    View set for managing league instances.

    This view set provides CRUD operations for league instances, including listing, creating, retrieving,
    updating, and deleting league objects.

    Attributes:
        queryset: Queryset containing all league instances.
        serializer_class: Serializer class for league instances.
        permission_classes: Permission classes for controlling access to league instances.
        pagination_class: Pagination class for paginating league instances.

    """

    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination


class PlayerToTournamentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing player registrations to tournaments.

    This ViewSet handles CRUD operations for player registrations to tournaments,
    including creating, retrieving, updating, and deleting registrations.

    Attributes:
        queryset (QuerySet): Set of all PlayerToTournament objects.
        serializer_class: Serializer class for PlayerToTournament objects.
        permission_classes: Tuple of permission classes required for accessing these views.
        pagination_class: Class for pagination settings.

    """

    queryset = PlayerToTournament.objects.all()
    serializer_class = PlayerToTournamentSerializer
    permission_classes = (IsAdminOrOwnerOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def destroy(self, request, *args, **kwargs):
        """
        Deletes a player's registration to a tournament.

        This method deletes a player's registration to a tournament. It verifies the user's authentication
        and checks if the player and season exist. If the user is authenticated, and the player and season
        exist, it deletes the registration and returns a success response.

        Args:
            request: Request object.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: HTTP response indicating success or failure of the deletion operation.
        """
        player_id = self.kwargs.get('pk')
        user = request.user
        season = Season.objects.get(is_finished=False)
        if user.is_anonymous:
            return Response({"error": "Authentication credentials were not provided"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            player_to_tournament = PlayerToTournament.objects.get(
                player=player, user=user, Season=season)
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
        """
        Returns a filtered queryset based on query parameters.

        This method filters the queryset based on query parameters 'user' and 'season'.
        If 'user' or 'season' is provided, it filters the queryset accordingly.
        If both 'user' and 'season' are provided, it filters the queryset based on both.

        Returns:
            QuerySet: Filtered queryset.
        """
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
    """
    API view for retrieving clan members.

    This class implements the GET method to retrieve clan members using a given clan tag.

    Attributes:
        None
    """

    def get(self, request, clan_tag):
        """
        Handle GET request to retrieve clan members.

        This method retrieves clan members using the provided clan tag.
        It returns a response containing the retrieved data or an error message.

        Args:
            request: HTTP request object.
            clan_tag (str): Tag of the clan to retrieve members from.

        Returns:
            Response: HTTP response containing clan member data or error message.
        """
        try:
            character_data = form_character_data(clan_tag)
            if character_data[1] == status.HTTP_200_OK:
                return Response(character_data[0], status=status.HTTP_200_OK)
            else:
                raise Exception(f"Error {character_data[1]}")
        except Exception as e:
            return Response({"error": str(e)}, status=character_data[1] if character_data[1] else status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetMemberLogo(APIView):
    """
    API view for retrieving member avatars.

    This class implements the GET method to retrieve member avatars based on region, realm, and character ID.

    Attributes:
        None
    """

    def get(self, request, region, realm, character_id):
        """
        Handle GET request to retrieve member avatar.

        This method retrieves the avatar of a member using the provided region, realm, and character ID.
        It returns a response containing the avatar image or an error message if the character is not found.

        Args:
            request: HTTP request object.
            region (str): Region of the member.
            realm (str): Realm of the member.
            character_id (int): ID of the member character.

        Returns:
            Response: HTTP response containing avatar image or error message.
        """
        try:
            avatar = get_avatar(region, realm, character_id)
            if avatar is not None:
                return Response(avatar, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Character not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            error_code = e.response.status_code
            return Response({"error": str(e)}, status=error_code)


class GroupStageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling CRUD operations related to GroupStage model instances.

    This class defines methods for creating, retrieving, updating, and deleting GroupStage instances,
    along with additional functionality for filtering by season.

    Attributes:
        queryset (QuerySet): Queryset representing all GroupStage instances.
        serializer_class (Serializer): Serializer class for GroupStage model.
        permission_classes (tuple): Tuple of permission classes for view authorization.
        pagination_class (Pagination): Pagination class for queryset pagination.

    """

    queryset = GroupStage.objects.all()
    serializer_class = GroupStageSerializer
    permission_classes = (IsAdminOrReadOnly, )
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """
        Returns the queryset of GroupStage instances filtered by season if provided, otherwise returns all instances.

        This method retrieves the 'season' query parameter from the request. If a valid season number is provided,
        the method filters the queryset to include only GroupStage instances belonging to that season.
        If no season parameter is provided or the provided season number is invalid, returns all GroupStage instances.

        Returns:
            QuerySet: Filtered queryset of GroupStage instances.
        """

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
    """
    Check if the user is authenticated.

    This function returns a response indicating whether the user making the request is authenticated.

    Args:
        request: Request object containing metadata about the request.

    Returns:
        Response: HTTP response indicating the authentication status.
    """
    return Response(status=status.HTTP_200_OK, data={"is_authenticated": request.user.is_authenticated})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def is_manager_or_staff(request):
    """
    Check if the user is a manager or staff.

    This function returns a response containing information about whether the user is staff or a manager.

    Args:
        request: Request object containing metadata about the request.

    Returns:
        Response: HTTP response containing the user's staff and manager status.
    """
    user = request.user
    is_manager = Manager.objects.filter(user=user).exists()
    return Response(status=status.HTTP_200_OK, data={
        "is_staff": request.user.is_staff,
        "is_manager": is_manager})


@api_view(['GET'])
def get_team_and_related_data(request):
    """
    Retrieve team and related data based on user ID.

    This function retrieves team and related data based on the provided user ID in the query parameters.
    It fetches information such as team details, players, team resources, manager contacts, and registration status
    for the current season.

    Args:
        request: HTTP request object containing query parameters.

    Returns:
        Response: JSON response containing team and related data.
    """
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
    manager_resources = ManagerContact.objects.filter(user=user_id)
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
        "teamId": team_id,
        "teamName": team_name,
        "teamTag": team_tag,
        "teamLogoUrl": team_logo_url,
        "teamRegionName": team_region_name,
        "teamRegionFlag": team_region_flag,
        "players": [{"id": player.id,
                     "username": player.username,
                     "avatar": player.avatar,
                     "mmr": player.mmr,
                     "league": player.league_id,
                     "race": player.race_id,
                     "wins": player.wins,
                     "battlenet_id": player.battlenet_id,
                     "total_games": player.total_games,
                     "team": player.team_id,
                     "user": player.user_id,
                     "region": player.region} for player in players],
        "teamResources": list(team_resources.values()),
        "managerResources": manager_resources.values(),
        "isRegToCurrentSeason": is_reg_to_current_season
    }

    return Response(team_data)


@api_view(['GET'])
def get_league_by_mmr(request):
    """
    Retrieves league information based on MMR and region.

    This function retrieves the league information based on the provided MMR (Match Making Rating) 
    and region. It returns the league corresponding to the given MMR and region.

    Args:
        request: HTTP request object containing query parameters.

    Returns:
        Response: JSON response containing the league information or error message.
    """
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


@api_view(['GET'])
def get_current_tournaments(request):
    """
    Retrieves a list of ongoing tournaments.

    This function retrieves a list of ongoing tournaments whose match start time is before or equal to
    the current time and are not yet finished. It orders the tournaments by their match start time.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing data of ongoing tournaments.
    """
    tournaments = Tournament.objects.filter(match_start_time__lte=timezone.now(
    ), is_finished=False).order_by('match_start_time')
    serializer = TournamentsSerializer(tournaments, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_current_season(request):
    """
    Retrieves the current season.

    This function retrieves the current season object from the database
    and checks if it has started. If the season has started, it updates
    the registration status accordingly.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing serialized data of the current season.

    """
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
    """
    Retrieves the last season.

    This function retrieves the most recent season object from the database
    and returns its serialized data.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing serialized data of the last season.

    """
    seasons = Season.objects.last()
    serializer = SeasonsSerializer(seasons)
    return Response(serializer.data)


@api_view(['GET'])
def get_last_season_number(request):
    """
    Retrieves the number of the last season.

    This function retrieves the number of the most recent season from the database
    and returns it.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing the number of the last season.

    """
    try:
        season = Season.objects.last()
        season_number = season.number
    except:
        return Response({"error": "Seasons have not yet been held"}, status=status.HTTP_404_NOT_FOUND)
    return Response(season_number)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def randomizeGroups(request):
    """
    API endpoint for randomizing teams into groups for a season.

    This endpoint takes a POST request with the number of groups to create and randomizes teams into those groups
    for the ongoing season. It then returns the group information including group ID, group mark, and the teams
    in each group.

    Args:
        request: HTTP request object containing the 'groupCnt' parameter indicating the number of groups.

    Returns:
        Response: JSON response containing group information if successful, error message otherwise.

    Raises:
        Season.DoesNotExist: If the ongoing season is not found.
    """

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
    """
    Retrieves the player's information for the current tournament.

    This function retrieves the player's information for the ongoing season's tournament.
    It requires the user to be authenticated.

    Args:
        request: HTTP request object.

    Returns:
        Response: Serialized data containing player's tournament information.

    """
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
    """
    Retrieves teams registered for the current season.

    This function retrieves teams registered for the ongoing season.
    It requires admin permissions.

    Args:
        request: HTTP request object.

    Returns:
        Response: Serialized data containing registered team information.

    """
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
    """
    API view for retrieving groups for the current season.

    Retrieves group information for the current season that is not finished yet.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing group information for the current season.

    Raises:
        Http404: If there is no current season available.
    """
    try:
        # Retrieve the current season that is not finished yet
        season = Season.objects.get(is_finished=False)
    except Season.DoesNotExist:
        return Response({"error": "No current season"}, status=status.HTTP_404_NOT_FOUND)

    # Retrieve group stages for the current season
    groupStages = GroupStage.objects.filter(season=season)

    responseData = []
    for groupStage in groupStages:
        # Serialize group information
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
    """
    Endpoint for adding a team to a group in a tournament.

    This function receives a POST request containing the group stage mark and team ID, 
    and adds the team to the specified group for the ongoing season. If the group 
    does not exist, it creates a new group. If the team is already assigned to another 
    group in the same season, it removes the team from the previous group.

    Args:
        request: Request object containing data including 'groupStageMark' and 'teamId'.

    Returns:
        Response: JSON response containing details of the updated group stage.

    """
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
    groupStageData = GroupStageSerializer(groupStage).data
    return Response(groupStageData)


@api_view(['DELETE'])
@permission_classes([permissions.IsAdminUser])
def deleteTeamFromGroup(request):
    """
    Delete a team from a group in the current season's group stage.

    This function deletes a specified team from the group stage of the current season. It requires admin
    permissions to perform this action.

    Args:
        request (Request): The DELETE request object containing the team ID to be deleted.

    Returns:
        Response: A response indicating the success or failure of the deletion operation.
            HTTP_204_NO_CONTENT if successful.
            HTTP_400_BAD_REQUEST if teamId is missing in the request data.
            HTTP_404_NOT_FOUND if the specified team is not found.
    """
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
    """
    Retrieves tournaments associated with the current season.

    Retrieves tournaments associated with the ongoing season. If no ongoing season exists,
    returns a 404 error indicating no current season found.

    Args:
        request: HTTP request object.

    Returns:
        Response: HTTP response object containing tournament data or error message.
    """
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
    """
    Deletes tournaments associated with the current season.

    Deletes tournaments associated with the ongoing season. If no ongoing season exists,
    returns a 404 error indicating no current season found.

    Args:
        request: HTTP request object.

    Returns:
        Response: HTTP response object indicating successful deletion or error message.
    """
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
    """
    Retrieves tournaments associated with the manager's team.

    This function retrieves tournaments associated with the manager's team for the current season.
    It fetches the tournaments, processes them, and returns the relevant data in a response.

    Args:
        request: Request object containing metadata about the HTTP request.

    Returns:
        Response: JSON response containing tournament data.
    """
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
    """
    PATCH method to set time suggestion for a tournament.

    This method sets a time suggestion for a tournament based on the request data.

    Args:
        request (Request): Django Request object containing user and data.

    Returns:
        Response: HTTP response indicating success or failure.

    """
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
    """
    PATCH method to accept a time suggestion for a tournament.

    This method accepts a time suggestion for a tournament based on the request data.

    Args:
        request (Request): Django Request object containing user and data.

    Returns:
        Response: HTTP response indicating success or failure.

    """
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
    """
    Retrieves players grouped by teams for the current season.

    This function retrieves players grouped by teams for the current season. It requires authentication
    and returns a response containing player information grouped by teams.

    Args:
        request: HTTP request object containing user authentication.

    Returns:
        Response: HTTP response containing player information grouped by teams.
                  If authentication fails, returns 401 Unauthorized.
                  If no current season is found, returns 404 Not Found.

    """
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
    """
    Retrieve season data by season number.

    This function retrieves group and playoff data for a given season number.

    Args:
        request: HTTP request object.
        season (int): Season number to retrieve data for.

    Returns:
        Response: JSON response containing group and playoff data.
    """
    groups_data, playoff_data = get_season_data(season)
    if groups_data is None and playoff_data is None:
        return Response({"error": "Season with number " + str(season) + " not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"groups": groups_data, "playoff": playoff_data})


@api_view(['GET'])
def get_team_by_id(request, team_id):
    """
    Retrieve team data by team ID.

    This function retrieves detailed data for a team identified by its ID,
    including team information, resources, manager details, player details, and tournament history.

    Args:
        request: HTTP request object.
        team_id (int): ID of the team to retrieve data for.

    Returns:
        Response: JSON response containing detailed team data.
    """
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
    """
    Retrieve player information and related matches by player ID.

    This function retrieves player information and matches related to the player specified by the ID.
    It returns a response containing player details and match data.

    Args:
        request: HTTP request object.
        player_id (int): ID of the player to retrieve.

    Returns:
        Response: JSON response containing player information and related matches.
    """
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
            "map": match.map.name if match.map is not None else None,
            "opponent": opponent_name,
            "opponentTag": opponent_tag,
            "opponentId": opponent_id,
            "winner": True if match.winner == player else False,
        })
    return Response({"player": PlayersSerializer(player).data, "matches": matches_data})


@api_view(['GET'])
def get_tournament_by_id(request, tournament_id):
    """
    Retrieve tournament information and related matches by tournament ID.

    This function retrieves tournament information and matches related to the tournament specified by the ID.
    It returns a response containing tournament details and match data.

    Args:
        request: HTTP request object.
        tournament_id (int): ID of the tournament to retrieve.

    Returns:
        Response: JSON response containing tournament information and related matches.
    """
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
            "map": match.map.name if match.map is not None else None,
            "playerOneId": match.player_one.id,
            "playerTwoId": match.player_two.id,
            "playerOne": match.player_one.username,
            "playerTwo": match.player_two.username,
            "winner":  winner,
        })

    return Response({"tournament": tournament_data, "matches": matches_data})


@api_view(['GET'])
def get_statistics(request):
    """
    Retrieve statistics related to players, leagues, races, matches, and maps.

    This function retrieves various statistics related to players, leagues, races, matches, and maps.
    It returns a JSON response containing these statistics.

    Args:
        request: HTTP request object.

    Returns:
        Response: JSON response containing statistics related to players, leagues, races, matches, and maps.
    """
    players_cnt = Player.objects.count()
    teams_in_season_cnt = Season.objects.annotate(teamCount=Count(
        'tournamentregistration')).values('number', 'teamCount')
    league_stats = (
        Player.objects
        .filter(league__in=[5, 6, 7])
        .values('league')
        .annotate(playerCount=Count('id'))
    )

    league_stats = list(league_stats)
    league_stats.append({
        'league': 0,
        'playerCount': players_cnt - sum([x['playerCount'] for x in league_stats]),
    })

    race_stats = (
        Player.objects
        .values('race')
        .annotate(playerCount=Count('id'))
    )
    
    match_stats = {
        'totalMatches': Match.objects.count(),
        'mirrors': Match.objects.filter(player_one__race=F('player_two__race')).count(),
        'tvzCount': Match.objects.filter(Q(player_one__race=2, player_two__race=1) | Q(player_one__race=1, player_two__race=2)).count(),
        'tvzTerranWins': Match.objects.filter(Q(player_one__race=2, player_two__race=1) | Q(player_one__race=1, player_two__race=2), winner__race=2).count(),
        'tvpCount': Match.objects.filter(Q(player_one__race=2, player_two__race=3) | Q(player_one__race=3, player_two__race=2)).count(),
        'tvpTerranWins': Match.objects.filter(Q(player_one__race=2, player_two__race=3) | Q(player_one__race=3, player_two__race=2), winner__race=2).count(),
        'pvzCount': Match.objects.filter(Q(player_one__race=3, player_two__race=1) | Q(player_one__race=1, player_two__race=3)).count(),
        'pvzProtossWins': Match.objects.filter(Q(player_one__race=3, player_two__race=1) | Q(player_one__race=1, player_two__race=3), winner__race=3).count(),
    }

    maps_data = (
        Map.objects
        .annotate(
            tvzCount=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=2, player_two__race=1) | Q(player_one__race=1, player_two__race=2)))),
            tvzTerranWins=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=2, player_two__race=1) | Q(player_one__race=1, player_two__race=2)), match__winner__race=2)),
            tvpCount=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=2, player_two__race=3) | Q(player_one__race=3, player_two__race=2)))),
            tvpTerranWins=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=2, player_two__race=3) | Q(player_one__race=3, player_two__race=2)), match__winner__race=2)),
            pvzCount=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=3, player_two__race=1) | Q(player_one__race=1, player_two__race=3)))),
            pvzProtossWins=Count('match', filter=Q(match__in=Match.objects.filter(
                Q(player_one__race=3, player_two__race=1) | Q(player_one__race=1, player_two__race=3)), match__winner__race=3)),
        )
        .values('id', 'name', 'tvzCount', 'tvzTerranWins', 'tvpCount', 'tvpTerranWins', 'pvzCount', 'pvzProtossWins')
    )

    response_data = {
        'playerCnt': players_cnt,
        'maxTeamsInSeasonCnt': max(teams_in_season_cnt, key=lambda x: x['teamCount'])['teamCount'],
        'inSeasonTeams': list(teams_in_season_cnt),
        'leagueStats': league_stats,
        'raceStats': list(race_stats),
        'matchStats': match_stats,
        'maps': list(maps_data),
    }
    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_manager_contacts(request):
    """
    Endpoint for adding manager contacts.

    This view function allows authenticated users to add manager contacts by providing a list of URLs.

    Args:
        request (Request): HTTP request object containing user data and list of URLs.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    urls = request.data.get('urls')
    if not urls or not type(urls) is list:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    for url in urls:
        ManagerContact.objects.create(user=user, url=url)
    return Response(status=status.HTTP_200_OK, data={"urls": urls})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def patch_manager_contact(request):
    """
    Endpoint for updating manager contact.

    This view function allows authenticated users to update a manager contact URL.

    Args:
        request (Request): HTTP request object containing user data, contact ID, and updated data.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    contact_id = request.data.get('id')
    data = request.data.get('data')
    try:
        contact = ManagerContact.objects.get(id=contact_id, user=user)
        contact.url = data
        contact.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except ManagerContact.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def patch_team_resource_url(request):
    """
    Endpoint for updating team resource URL.

    This view function allows authenticated users to update a team resource URL.

    Args:
        request (Request): HTTP request object containing user data, resource ID, and updated data.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    res_id = request.data.get('id')
    data = request.data.get('data')
    try:
        resource = TeamResource.objects.get(id=res_id, user=user)
        resource.url = data
        resource.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except TeamResource.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def patch_team_resource_name(request):
    """
    Endpoint for updating team resource name.

    This view function allows authenticated users to update a team resource name.

    Args:
        request (Request): HTTP request object containing user data and resource ID.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    res_id = request.data.get('id')
    data = request.data.get('data')
    try:
        resource = TeamResource.objects.get(id=res_id, user=user)
        resource.name = data
        resource.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except TeamResource.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_manager_contact(request):
    """
    Endpoint for deleting manager contact.

    This view function allows authenticated users to delete a manager contact.

    Args:
        request (Request): HTTP request object containing user data and contact ID.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    contact_id = request.data.get('id')
    try:
        contact = ManagerContact.objects.get(id=contact_id, user=user)
        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except ManagerContact.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_team_resource(request):
    """
    Endpoint for deleting team resource.

    This view function allows authenticated users to delete a team resource.

    Args:
        request (Request): HTTP request object containing user data and resource ID.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    user = request.user
    res_id = request.data.get('id')
    try:
        resource = TeamResource.objects.get(id=res_id, user=user)
        resource.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except TeamResource.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_team_resource(request):
    """
    Endpoint for creating team resource.

    This view function allows authenticated users to create a team resource.

    Args:
        request (Request): HTTP request object containing user data.

    Returns:
        Response: HTTP response containing the ID of the created resource and the ID of the associated team.
    """
    user = request.user
    team = Team.objects.get(user=user)
    resource = TeamResource.objects.create(
        user=user, name='', url='', team=team)
    return Response({"id": resource.id, "teamId": team.id}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_manager_contact(request):
    """
    Endpoint for creating manager contact.

    This view function allows authenticated users to create a manager contact.

    Args:
        request (Request): HTTP request object containing user data.

    Returns:
        Response: HTTP response containing the ID of the created contact.
    """
    user = request.user
    contact = ManagerContact.objects.create(user=user, url='')
    return Response({"id": contact.id}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([permissions.IsAdminUser])
def set_staff_user_by_id(request):
    """
    Endpoint for setting staff status of a user by ID.

    This view function allows admin users to set the staff status of a user by their ID.

    Args:
        request (Request): HTTP request object containing the user ID and the desired state.

    Returns:
        Response: HTTP response indicating success or failure.
    """
    state = request.data.get('state')
    user_id = request.data.get('id')
    if user_id is None:
        return Response({"error": "User id is required"}, status=status.HTTP_400_BAD_REQUEST)
    elif user_id == request.user.id:
        return Response({"error": "You cannot set yourself as a staff"}, status=status.HTTP_400_BAD_REQUEST)
    elif type(user_id) is not int:
        if user_id.isnumeric() == False:
            return Response({"error": "User id must be a number"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    if state is None:
        return Response({"error": "State is required"}, status=status.HTTP_400_BAD_REQUEST)
    elif type(state) is not int:
        if state.isnumeric() == False:
            return Response({"error": "State must be a number"}, status=status.HTTP_400_BAD_REQUEST)
    elif not (int(state) == 0 or int(state) == 1):
        return Response({"error": "State must be 0 or 1"}, status=status.HTTP_400_BAD_REQUEST)
    elif user.is_staff and int(state) == 1:
        return Response({"error": "User is already staff"}, status=status.HTTP_400_BAD_REQUEST)
    elif not user.is_staff and int(state) == 0:
        return Response({"error": "User is already not staff"}, status=status.HTTP_400_BAD_REQUEST)
    user.is_staff = state
    user.save()

    return Response({"message": "User staff status updated"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def get_all_users(request):
    """
    Endpoint for retrieving all users.

    This view function allows admin users to retrieve information about all users.

    Args:
        request (Request): HTTP request object.

    Returns:
        Response: HTTP response containing user data.
    """
    if request.user.is_superuser == False:
        users = User.objects.filter(is_superuser=False, is_staff=False)
    else:
        users = User.objects.filter(is_superuser=False)
    users_data = []
    for user in users:
        users_data.append({
            "id": user.id,
            "username": user.username,
            "isStaff": user.is_staff
        })
    return Response(users_data)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def get_maps_by_season(request):
    currnet_season = Season.objects.get(is_finished=False)
    current_season_maps = Map.objects.filter(seasons=currnet_season)
    other_season_maps = Map.objects.exclude(seasons=currnet_season)

    return Response({
        "currentSeasonMaps": current_season_maps.values(),
        "otherSeasonMaps": other_season_maps.values()
    })
