from django.db import models
import os
from django.forms import ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


# Model for a match between two players
class Match(models.Model):
    player_one = models.ForeignKey('Player',
                                   on_delete=models.PROTECT,
                                   related_name='player_one',
                                   null=True, blank=True, default=None)
    player_two = models.ForeignKey('Player',
                                   on_delete=models.PROTECT,
                                   related_name='player_two',
                                   null=True, blank=True, default=None)
    winner = models.ForeignKey(
        'Player', on_delete=models.PROTECT, null=True, blank=True, default=None)
    tournament = models.ForeignKey('Tournament', on_delete=models.PROTECT)
    map = models.CharField(max_length=100, null=True, blank=True, default=None)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def get_teams(self):
        # Returns the teams involved in the match
        teams = [self.player_one.team, self.player_two.team]
        return teams

    def get_players(self):
        # Returns the players involved in the match
        players = [self.player_one, self.player_two]
        return players

    def __str__(self):
        # Returns a string representation of the match
        return f"{self.player_one} vs {self.player_two}"

    def clean(self):
        # Validates the match instance
        if (self.player_one == self.player_two and self.player_one is not None):
            raise ValidationError(f"Players can't be equal, {self.player_one}")
        if (not (self.player_one is None) and not (self.player_two is None)):
            if self.player_one.team == self.player_two.team:
                raise ValidationError("Teams can't be equal")

    def save(self, *args, **kwargs):
        # Overrides save method to perform additional validation
        self.clean()
        super().save(*args, **kwargs)


# Model for a tournament
class Tournament(models.Model):
    team_one = models.ForeignKey('Team',
                                 on_delete=models.PROTECT,
                                 related_name='team_one',)
    team_two = models.ForeignKey('Team',
                                 on_delete=models.PROTECT,
                                 related_name='team_two',)
    match_start_time = models.DateTimeField()
    team_one_wins = models.IntegerField(default=0)
    team_two_wins = models.IntegerField(default=0)
    winner = models.ForeignKey('Team', on_delete=models.PROTECT,
                               null=True, blank=True, default=None, related_name='winner')
    ask_for_other_time = models.DateTimeField(
        null=True, blank=True, default=None)
    ask_for_finished = models.BooleanField(null=True, blank=True, default=None)
    asked_team = models.ForeignKey('Team', on_delete=models.PROTECT,
                                   null=True, blank=True, default=None, related_name='asked_team')
    season = models.ForeignKey('Season', on_delete=models.PROTECT)
    stage = models.IntegerField()
    group = models.ForeignKey(
        'GroupStage', on_delete=models.CASCADE, null=True, blank=True, default=None)
    is_finished = models.BooleanField()
    inline_number = models.IntegerField(null=True, blank=True, default=None)
    next_stage_tournament = models.ForeignKey(
        'Tournament', on_delete=models.CASCADE, null=True, blank=True, default=None, related_name='next_stage_tournament_related_name')

    def __str__(self):
        # Returns a string representation of the tournament
        return f"{self.group if self.group else self.season}{f'[{self.stage}]' if not self.group else ''}:  {self.team_one} vs {self.team_two}"

    def clean(self):
        # Validates the tournament instance
        if self.team_one == self.team_two:
            raise ValidationError("Teams can't be equal")

    def save(self, *args, **kwargs):
        # Overrides save method to perform additional validation
        self.clean()
        super().save(*args, **kwargs)


# Model for tournament registration
class TournamentRegistration(models.Model):
    season = models.ForeignKey('Season', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    team = models.ForeignKey('Team', on_delete=models.PROTECT)

    def __str__(self):
        # Returns a string representation of the tournament registration
        return f"{self.season} - {self.team}"


# Model for a season
class Season(models.Model):
    number = models.IntegerField()
    start_datetime = models.DateTimeField()
    is_finished = models.BooleanField()
    can_register = models.BooleanField()
    winner = models.ForeignKey('Team', on_delete=models.PROTECT, null=True,
                               blank=True, default=None, related_name='season_winner')

    def __str__(self):
        # Returns a string representation of the season
        return str(self.number)


# Model for group stage
class GroupStage(models.Model):
    groupMark = models.CharField(max_length=100)
    season = models.ForeignKey('Season', on_delete=models.PROTECT)
    teams = models.ManyToManyField('Team')

    def __str__(self):
        # Returns a string representation of the group stage
        return str(self.season) + str(self.groupMark)


# Model for a player
class Player(models.Model):
    username = models.CharField(max_length=100)
    avatar = models.URLField(
        default="http://localhost:8000/media/players/logo/default.svg")
    mmr = models.IntegerField()
    league = models.ForeignKey('League', on_delete=models.PROTECT)
    race = models.ForeignKey('Race', on_delete=models.PROTECT)
    wins = models.IntegerField()
    total_games = models.IntegerField()
    team = models.ForeignKey('Team', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    region = models.IntegerField(
        choices=((1, 'US'), (2, 'EU'), (3, 'KR')), default=2)
    battlenet_id = models.IntegerField(null=True, blank=True, default=None)

    def __str__(self):
        # Returns a string representation of the player
        return self.username


# Model for a team
class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tag = models.CharField(max_length=10)
    logo = models.ImageField(upload_to='teams/logo/', max_length=255)
    region = models.ForeignKey('Region', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def __str__(self):
        # Returns a string representation of the team
        return self.name

    def save(self, *args, **kwargs):
        # Overrides save method to handle logo changes
        try:
            this = Team.objects.get(id=self.id)
            if this.logo != self.logo:
                old_logo = this.logo
                if old_logo:
                    os.remove(old_logo.path)
        except:
            pass
        super(Team, self).save(*args, **kwargs)


# Model for a region
class Region(models.Model):
    name = models.CharField(max_length=100)
    flag_url = models.FileField(
        default='../media/country_flags/no_flag.svg', upload_to='country_flags/')

    def __str__(self):
        # Returns a string representation of the region
        return self.name


# Model for player-tournament relation
class PlayerToTournament(models.Model):
    player = models.ForeignKey('Player', on_delete=models.PROTECT)
    Season = models.ForeignKey('Season', on_delete=models.PROTECT)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def __str__(self):
        # Returns a string representation of the player-tournament relation
        return self.player.username


# Model for team resources
class TeamResource(models.Model):
    team = models.ForeignKey('Team', on_delete=models.PROTECT)
    url = models.URLField()
    name = models.CharField(max_length=100)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)

    def __str__(self):
        # Returns a string representation of the team resource
        return self.name


# Model for a manager
class Manager(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.PROTECT)
    team = models.ForeignKey('Team', on_delete=models.PROTECT)

    def __str__(self):
        # Returns a string representation of the manager
        return self.user.username


# Model for manager contact
class ManagerContact(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    url = models.URLField()

    def __str__(self):
        # Returns a string representation of the manager contact
        return self.url


# Model for a race
class Race(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        # Returns a string representation of the race
        return self.name


# Model for a league
class League(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        # Returns a string representation of the league
        return self.name


# Model for league frame
class LeagueFrame(models.Model):
    league = models.ForeignKey('League', on_delete=models.PROTECT)
    frame_max = models.IntegerField()
    region = models.CharField(max_length=2)

    def __str__(self):
        # Returns a string representation of the league frame
        return f"{self.league} max frame: {self.frame_max}"
