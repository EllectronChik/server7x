from rest_framework import serializers
from djoser.serializers import UserSerializer, TokenSerializer
from django.contrib.auth import get_user_model
from main.models import *
import re


class TeamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


class PlayersSerializer(serializers.ModelSerializer):
    avatar = serializers.URLField(allow_blank=True)
    class Meta:
        model = Player
        fields = '__all__'

    
    def validate_avatar(self, value):
        print('validate avatar ', value)
        if value.split('.')[-1].lower() not in ['jpg', 'png', 'jpeg', 'svg']:
            value = 'http://localhost:8000/media/players/logo/default.svg'
        return value



class ManagersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manager
        fields = '__all__'


class ManagerContactsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagerContact
        fields = '__all__'


class SeasonsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = '__all__'


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

    
class TournamentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = '__all__'


class UserDevicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = '__all__'



class TeamResourcesSerializer(serializers.ModelSerializer):
    url = serializers.CharField()
    class Meta:
        model = TeamResource
        fields = '__all__'
    
    def validate_url(self, value):
        protocol_pattern = "^https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        not_protocol_pattern = "^[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        if not re.match(protocol_pattern, value) and not re.match(not_protocol_pattern, value):
            raise serializers.ValidationError('Invalid URL')
        return value

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


class LeagueSerializer(serializers.ModelSerializer):
    class Meta:
        model = League
        fields = '__all__'


class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = ('id', 'username', 'is_staff')


class CustomTokenSerializer(TokenSerializer):
    user_id = serializers.IntegerField(source='user.id')
    class Meta(TokenSerializer.Meta):
        fields = ('user_id', 'auth_token')