from django.contrib import admin
from .models import *
from django import forms

# Register Django models for administration.
# Each model is registered with its corresponding admin class, if any.

# Registering basic models directly.
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(Manager)
admin.site.register(ManagerContact)
admin.site.register(TeamResource)
admin.site.register(Region)
admin.site.register(Race)
admin.site.register(League)
admin.site.register(Season)
admin.site.register(Tournament)
admin.site.register(TournamentRegistration)
admin.site.register(PlayerToTournament)
admin.site.register(GroupStage)

# Defining admin class for the LeagueFrame model to customize its display in the admin panel.
class LeagueFrameAdmin(admin.ModelAdmin):
    list_display = ('id', 'league', 'frame_max', 'region')

# Registering LeagueFrame model with the customized admin class.
admin.site.register(LeagueFrame, LeagueFrameAdmin)

# Custom widget for representing Boolean field in a dropdown menu.
class CustomBooleanWidget(forms.widgets.Select):
    def __init__(self, attrs=None):
        choices = [(None, '---------'), (True, 'Player 1 wins'), (False, 'Player 2 wins')]
        super().__init__(attrs, choices)

# Form for customizing Match model in the admin panel.
class MatchAdminForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = '__all__'
        widgets = {
            'winner': CustomBooleanWidget(),
        }

# Admin class for the Match model with the custom form.
class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm

# Registering Match model with the customized admin class.
admin.site.register(Match, MatchAdmin)
