# Import necessary modules
from rest_framework import serializers
from djoser.serializers import UserSerializer, TokenSerializer
from rest_framework import status
from django.contrib.auth import get_user_model
from main.models import *
import re
from django.utils import timezone


# Serializer for Teams model
class TeamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


# Serializer for Players model
class PlayersSerializer(serializers.ModelSerializer):
    avatar = serializers.URLField(allow_blank=True)

    class Meta:
        model = Player
        fields = '__all__'

    # Custom validation for avatar URL
    def validate_avatar(self, value):
        if value.split('.')[-1].lower() not in ['jpg', 'png', 'jpeg', 'svg']:
            value = 'http://localhost:8000/media/players/logo/default.svg'
        return value


# Serializer for Managers model
class ManagersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manager
        fields = '__all__'


# Serializer for ManagerContacts model
class ManagerContactsSerializer(serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = ManagerContact
        fields = '__all__'

    # Custom validation for URL format
    def validate_url(self, value):
        protocol_pattern = "^https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        not_protocol_pattern = "^[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        if not re.match(protocol_pattern, value) and not re.match(not_protocol_pattern, value):
            raise serializers.ValidationError('Invalid URL')
        return value


# Serializer for Seasons model
class SeasonsSerializer(serializers.ModelSerializer):
    is_season_started = serializers.SerializerMethodField()
    winner = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = '__all__'

    # Method to determine if season has started
    def get_is_season_started(self, obj):
        return timezone.now() >= obj.start_datetime

    # Method to get the winner of the season
    def get_winner(self, obj):
        if obj.winner:
            return obj.winner.name
        return None


# Serializer for Tournaments model
class TournamentsSerializer(serializers.ModelSerializer):
    season = serializers.SerializerMethodField(required=False)
    is_finished = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Tournament
        fields = ['id', 'season', 'match_start_time', 'is_finished', 'team_one',
                  'team_one_wins', 'team_two', 'team_two_wins', 'stage', 'group']

    # Method to get the season of the tournament
    def get_season(self, obj):
        if hasattr(obj, 'season'):
            return obj.season.number
        return Season.objects.get(is_finished=False).number

    # Method to check if tournament is finished
    def get_is_finished(self, obj):
        if hasattr(obj, 'is_finished'):
            return obj.is_finished
        return False

    # Method to create a new tournament
    def create(self, validated_data):
        is_finished = False
        season = Season.objects.get(is_finished=False)
        tournament = Tournament.objects.create(
            season=season, is_finished=is_finished, **validated_data)
        return tournament


# Serializer for TeamResources model
class TeamResourcesSerializer(serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = TeamResource
        fields = '__all__'

    # Custom validation for URL format
    def validate_url(self, value):
        protocol_pattern = "^https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        not_protocol_pattern = "^[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        if not re.match(protocol_pattern, value) and not re.match(not_protocol_pattern, value):
            raise serializers.ValidationError('Invalid URL')
        return value


# Serializer for Regions model
class RegionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


# Serializer for groupStage model
class GroupStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupStage
        fields = ['id', 'groupMark', 'teams']


# Serializer for PlayerToTournament model
class PlayerToTournamentSerializer(serializers.ModelSerializer):
    season = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    season_number = serializers.IntegerField(write_only=True)

    class Meta:
        model = PlayerToTournament
        fields = ['player', 'season', 'user', 'season_number']

    # Method to get the season of the player's tournament
    def get_season(self, obj):
        return obj.Season.number

    # Method to get the user ID of the player
    def get_user(self, obj):
        return obj.user.id

    # Method to create a new player registration for a tournament
    def create(self, validated_data):
        season_number = validated_data.pop('season_number')
        user = self.context['request'].user
        if not user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication credentials were not provided", code=status.HTTP_401_UNAUTHORIZED)
        player = self.initial_data.get('player')
        try:
            season = Season.objects.get(number=season_number)
        except Season.DoesNotExist:
            raise serializers.ValidationError(
                "Season not found", code=status.HTTP_404_NOT_FOUND)
        if season.is_finished:
            raise serializers.ValidationError(
                "Season is already finished", code=status.HTTP_400_BAD_REQUEST)
        try:
            player = Player.objects.get(user=user, id=player)
        except Player.DoesNotExist:
            raise serializers.ValidationError(
                "You can only register for your team", code=status.HTTP_403_FORBIDDEN)

        if PlayerToTournament.objects.filter(Season=season, user=user, player=player).exists():
            raise serializers.ValidationError(
                "You have already registered for this season", code=status.HTTP_400_BAD_REQUEST)

        registration = PlayerToTournament.objects.create(
            Season=season, user=user, **validated_data)

        return registration


# Serializer for Matches model
class MatchesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = '__all__'

    # Custom validation for matches
    def validate(self, data):
        player_one = data.get('player_one')
        player_two = data.get('player_two')

        if player_one == player_two and player_one is not None:
            raise serializers.ValidationError("Players can't be equal")

        if player_one is not None and player_two is not None and player_one.team == player_two.team:
            raise serializers.ValidationError("Teams can't be equal")

        return data


# Serializer for Race model
class RaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Race
        fields = '__all__'


# Serializer for League model
class LeagueSerializer(serializers.ModelSerializer):
    class Meta:
        model = League
        fields = '__all__'


# Custom User Serializer
class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = ('id', 'username', 'is_staff')


# Custom Token Serializer
class CustomTokenSerializer(TokenSerializer):
    user_id = serializers.IntegerField(source='user.id')

    class Meta(TokenSerializer.Meta):
        fields = ('user_id', 'auth_token')


# Serializer for Map model
class MapSerializer(serializers.ModelSerializer):
    seasons = serializers.SerializerMethodField()
    seasons_numbers = serializers.CharField(write_only=True)

    class Meta:
        model = Map
        fields = ('id', 'name', 'seasons', 'seasons_numbers')

    def get_seasons(self, obj):
        return [season.number for season in obj.seasons.all()]
    
    def create(self, validated_data):
        seasons_numbers = validated_data.pop('seasons_numbers')
        try: 
            seasons_numbers = seasons_numbers.split(',')
        except:
            raise serializers.ValidationError('Invalid seasons numbers')
        map = Map.objects.create(**validated_data)
        for season_number in seasons_numbers:
            season = Season.objects.get(number=season_number)
            map.seasons.add(season)
        return map
    
    def update(self, instance, validated_data):
        if validated_data.get('seasons_numbers'):
            seasons_numbers = validated_data.pop('seasons_numbers')
            try: 
                seasons_numbers = seasons_numbers.split(',')
            except:
                raise serializers.ValidationError('Invalid seasons numbers')
            for season_number in seasons_numbers:
                try:
                    season = Season.objects.get(number=season_number)
                except Season.DoesNotExist:
                    raise serializers.ValidationError(
                        "Season not found", code=status.HTTP_404_NOT_FOUND)
                instance.seasons.add(season)
        return super().update(instance, validated_data)


# Serializer for TournamentRegistration model
class TournamentRegistrationSerializer(serializers.ModelSerializer):
    season = serializers.IntegerField(write_only=True)

    class Meta:
        model = TournamentRegistration
        fields = ['user', 'team', 'season']

    # Method to create a new tournament registration
    def create(self, validated_data):
        season_number = validated_data.pop('season')
        user = self.initial_data.get('user')
        team = self.initial_data.get('team')
        try:
            season = Season.objects.get(number=season_number)
        except Season.DoesNotExist:
            raise serializers.ValidationError(
                "Season not found", code=status.HTTP_404_NOT_FOUND)
        if season.is_finished:
            raise serializers.ValidationError(
                "Season is already finished", code=status.HTTP_400_BAD_REQUEST)
        try:
            manager = Manager.objects.get(user=user, team=team)
        except Manager.DoesNotExist:
            raise serializers.ValidationError(
                "You can only register for your team", code=status.HTTP_403_FORBIDDEN)

        if TournamentRegistration.objects.filter(season=season, user=user, team=team).exists():
            raise serializers.ValidationError(
                "You have already registered for this season", code=status.HTTP_400_BAD_REQUEST)

        registration = TournamentRegistration.objects.create(
            season=season, **validated_data)

        return registration
