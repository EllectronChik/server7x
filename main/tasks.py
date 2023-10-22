from server7x.celery import app
from .models import LeagueFrame, League
from .utils import get_blizzard_league_data
import asyncio


@app.task
def monthly_task():
    regions = ['eu', 'us', 'kr']

    for region in regions:
        for league_id in range(1, 7):
            league = League.objects.get(id=league_id)
            max_rating = asyncio.run(get_blizzard_league_data(region, league_id))
            obj = LeagueFrame.objects.filter(region=region, league=league).first()
            if obj:
                obj.frame_max = max_rating
                obj.save()
            else:
                LeagueFrame.objects.create(region=region, league=league, frame_max=max_rating)
