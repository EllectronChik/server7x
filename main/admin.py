from django.contrib import admin
from .models import *
from django import forms

# Register your models here.
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(Manager)
admin.site.register(ManagerContact)
admin.site.register(TeamResource)
admin.site.register(Stage)
admin.site.register(Region)
admin.site.register(Race)
admin.site.register(League)
admin.site.register(Season)
admin.site.register(Tournament)
admin.site.register(Schedule)
admin.site.register(UserDevice)
admin.site.register(TournamentRegistration)
admin.site.register(PlayerToTournament)
admin.site.register(GroupStage)


class LeagueFrameAdmin(admin.ModelAdmin):
    list_display = ('id', 'league', 'frame_max', 'region')

admin.site.register(LeagueFrame, LeagueFrameAdmin)


class CustomBooleanWidget(forms.widgets.Select):
    def __init__(self, attrs=None):
        choices = [(None, '---------'), (True, 'Player 1 wins'), (False, 'Player 2 wins')]
        super().__init__(attrs, choices)

    
class MatchAdminForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = '__all__'
        widgets = {
            'winner': CustomBooleanWidget(),
        }


class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm

admin.site.register(Match, MatchAdmin)