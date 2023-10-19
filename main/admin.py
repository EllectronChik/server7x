from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(Manager)
admin.site.register(ManagerContact)
admin.site.register(TeamResource)
admin.site.register(Stage)
admin.site.register(Region)
admin.site.register(Match)
admin.site.register(Race)
admin.site.register(AskForStaff)
admin.site.register(League)

class LeagueFrameAdmin(admin.ModelAdmin):
    list_display = ('id', 'league', 'frame_max', 'region')

admin.site.register(LeagueFrame, LeagueFrameAdmin)