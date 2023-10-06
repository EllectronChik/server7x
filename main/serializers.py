from rest_framework import serializers
from djoser.serializers import UserSerializer, TokenSerializer
from django.contrib.auth import get_user_model
from main.models import *



class TeamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


class PlayersSerializer(serializers.ModelSerializer):
    Wins = serializers.HiddenField(default=0)
    TotalGames = serializers.HiddenField(default=0)
    class Meta:
        model = Player
        fields = '__all__'


class ManagersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manager
        fields = '__all__'


class ManagerContactsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagerContact
        fields = '__all__'


class TeamResourcesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamResource
        fields = '__all__'


class StagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = '__all__'


class RegionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


class MatchesSerializer(serializers.ModelSerializer):
    player_one_wins = serializers.HiddenField(default=0)
    player_two_wins = serializers.HiddenField(default=0)
     
    class Meta:
        model = Match
        fields = '__all__'


class RaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Race
        fields = '__all__'


class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = ('id', 'username', 'email', 'is_staff')


class CustomTokenSerializer(TokenSerializer):
    user_id = serializers.IntegerField(source='user.id')
    class Meta(TokenSerializer.Meta):
        fields = ('user_id', 'auth_token')


class AskForStaffSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = AskForStaff
        fields = '__all__'