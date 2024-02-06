from server7x.celery import app
from .models import LeagueFrame, League, Team, Race
from .utils import get_blizzard_league_data, form_character_data, get_avatar
import asyncio
import logging


@app.task
def daily_task():
    regions = ['eu', 'us', 'kr']

    for region in regions:
        for league_id in range(1, 7):
            league = League.objects.get(id=league_id)
            logging.info(f'Updating league {league.name} for region {region}')
            max_rating = asyncio.run(
                get_blizzard_league_data(region, league_id))
            obj = LeagueFrame.objects.filter(
                region=region, league=league).first()
            if obj:
                obj.frame_max = max_rating if max_rating is not None else obj.frame_max
                obj.save()
            else:
                LeagueFrame.objects.create(
                    region=region, league=league, frame_max=max_rating)


@app.task
def update_players_data():
    teams = Team.objects.all().prefetch_related('player_set')
    for team in teams:
        registred_players = team.player_set.all()
        fetched_players = form_character_data(team.tag)[0]
        fetched_players_by_ids = {}
        for player in fetched_players:
            fetched_players_by_ids[player['id']] = {
                'username': player['username'],
                'region': player['region'],
                'realm': player['realm'],
                'league': player['league'],
                'race': player['race'],
                'mmr': player['mmr']
            }
        for player in registred_players:
            if player.battlenet_id in fetched_players_by_ids.keys():
                logging.info(f"Updating player {player.username}")
                player.username = fetched_players_by_ids[player.battlenet_id]['username']
                player.region = fetched_players_by_ids[player.battlenet_id]['region']
                player.realm = fetched_players_by_ids[player.battlenet_id]['realm']
                player.league = League.objects.get(
                    id=fetched_players_by_ids[player.battlenet_id]['league'])
                player.race = Race.objects.get(
                    id=fetched_players_by_ids[player.battlenet_id]['race'])
                player.mmr = fetched_players_by_ids[player.battlenet_id]['mmr']
                avatar = get_avatar(
                    player.region, player.realm, player.battlenet_id)
                if (avatar is not None):
                    player.avatar = avatar
                player.save()
