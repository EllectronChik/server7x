from django.db import models

# Create your models here.
class Match(models.Model):
    season = models.IntegerField()
    stage = models.ForeignKey('Stage', on_delete=models.PROTECT)
    player_one = models.ForeignKey('Player', on_delete=models.PROTECT, related_name='player_one')
    player_one_wins = models.IntegerField()
    player_two = models.ForeignKey('Player', on_delete=models.PROTECT, related_name='player_two')
    player_two_wins = models.IntegerField()
    match_time = models.DateTimeField()
    is_finished = models.BooleanField()

    def __str__(self):
        return f"{self.player_one} vs {self.player_two}"


class Stage(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Player(models.Model):
    username = models.CharField(max_length=100)
    mmr = models.IntegerField()
    race = models.ForeignKey('Race', on_delete=models.PROTECT)
    wins = models.IntegerField()
    total_games = models.IntegerField()
    team = models.ForeignKey('Team', on_delete=models.PROTECT)

    def __str__(self):
        return self.username
    

class Team(models.Model):
    name = models.CharField(max_length=100)
    tag = models.CharField(max_length=10)
    logo = models.FileField(upload_to='teams/logo/', null=True)
    region = models.ForeignKey('Region', on_delete=models.PROTECT)

    def __str__(self):
        return self.name
    

class Region(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

class TeamResource(models.Model):
    team = models.ForeignKey('Team', on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    url = models.URLField()

    def __str__(self):
        return self.name
    

class Manager(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    team = models.ForeignKey('Team', on_delete=models.PROTECT)

    def __str__(self):
        return self.user


class ManagerContact(models.Model):
    manager = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    url = models.URLField()

    def __str__(self):
        return self.url
    

class Race(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name