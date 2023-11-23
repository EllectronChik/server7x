from django.db import models
import os
from django.forms import ValidationError


# Create your models here.
class Match(models.Model):
    player_one = models.ForeignKey('Player', 
                                   on_delete=models.PROTECT, 
                                   related_name='player_one', 
                                   null=True, blank=True, default=None)
    player_two = models.ForeignKey('Player', 
                                   on_delete=models.PROTECT, 
                                   related_name='player_two', 
                                   null=True, blank=True, default=None)
    winner = models.BooleanField(null=True, blank=True, default=None)
    tournament = models.ForeignKey('Tournament', on_delete=models.PROTECT)
    map = models.CharField(max_length=100)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    def get_teams(self):
        teams = [self.player_one.team, self.player_two.team]
        return teams

    def get_players(self):
        players = [self.player_one, self.player_two]
        return players

    def __str__(self):
        return f"{self.player_one} vs {self.player_two}"
    
    def clean(self):
        if self.player_one == self.player_two:
            raise ValidationError("Players can't be equal")
        if self.player_one.team == self.player_two.team:
            raise ValidationError("Teams can't be equal")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class UserDevice(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    device = models.IntegerField()

    def __str__(self):
        return f"{self.user} - {self.device}"


class Tournament(models.Model):
    team_one = models.ForeignKey('Team', 
                                 on_delete=models.PROTECT,
                                 related_name='team_one',)
    team_two = models.ForeignKey('Team', 
                                 on_delete=models.PROTECT,
                                 related_name='team_two',)
    match_start_time = models.DateTimeField()
    season = models.ForeignKey('Season', on_delete=models.PROTECT)
    stage = models.ForeignKey('Stage', on_delete=models.PROTECT)
    is_finished = models.BooleanField()
    
    def __str__(self):
        return f"{self.team_one} vs {self.team_two}"
    
    def clean(self):
        if self.team_one == self.team_two:
            raise ValidationError("Teams can't be equal")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Schedule(models.Model):
    DAY_CHOICES = (
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
        (7, 'Sunday'),
    )
    time = models.TimeField()
    day = models.IntegerField(choices=DAY_CHOICES)

    def __str__(self):
        return str(self.date_time)


class Stage(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Season(models.Model):
    number = models.IntegerField()
    start_datetime = models.DateTimeField()
    is_finished = models.BooleanField()
    can_register = models.BooleanField()

    def __str__(self):
        return str(self.number)

class Player(models.Model):
    username = models.CharField(max_length=100)
    avatar = models.URLField(default="http://localhost:8000/media/players/logo/default.svg")
    mmr = models.IntegerField()
    league = models.ForeignKey('League', on_delete=models.PROTECT)
    race = models.ForeignKey('Race', on_delete=models.PROTECT)
    wins = models.IntegerField()
    total_games = models.IntegerField()
    team = models.ForeignKey('Team', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    region = models.IntegerField(choices=((1, 'US'), (2, 'EU'), (3, 'KR')), default=2)

    def __str__(self):
        return self.username
    

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tag = models.CharField(max_length=10)
    logo = models.FileField(upload_to='teams/logo/', null=True)
    region = models.ForeignKey('Region', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(max_length=100)
    flag_url = models.FileField(default='../media/country_flags/no_flag.svg', upload_to='country_flags/')

    def __str__(self):
        return self.name
    

class TeamResource(models.Model):
    team = models.ForeignKey('Team', on_delete=models.PROTECT)
    url = models.URLField()
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def __str__(self):
        return self.url
    

class Manager(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.PROTECT)
    team = models.ForeignKey('Team', on_delete=models.PROTECT)

    def __str__(self):
        return self.user.username


class ManagerContact(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    url = models.URLField()
    

    def __str__(self):
        return self.url
    

class Race(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class League(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class LeagueFrame(models.Model):
    league = models.ForeignKey('League', on_delete=models.PROTECT)
    frame_max = models.IntegerField()
    region = models.CharField(max_length=2)

    def __str__(self):
        return f"{self.league} max frame: {self.frame_max}"