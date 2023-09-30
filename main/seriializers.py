from rest_framework import serializers
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
    class Meta:
        model = Match
        fields = '__all__'


class RaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Race
        fields = '__all__'