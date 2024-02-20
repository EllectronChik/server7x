# Import necessary modules
from server7x.celery import app
from .models import LeagueFrame, League, Team, Race
from .utils import get_blizzard_league_data, form_character_data, get_avatar
import asyncio
import logging

# Define a Celery task to update league data daily


@app.task
def daily_task():
    # List of regions to update
    regions = ['eu', 'us', 'kr']

    # Iterate over regions
    for region in regions:
        # Iterate over league IDs
        for league_id in range(1, 7):
            # Retrieve league instance
            league = League.objects.get(id=league_id)
            # Log the process
            logging.info(f'Updating league {league.name} for region {region}')
            # Fetch maximum rating asynchronously
            max_rating = asyncio.run(
                get_blizzard_league_data(region, league_id))
            # Retrieve LeagueFrame object if exists
            obj = LeagueFrame.objects.filter(
                region=region, league=league).first()
            if obj:
                # Update frame_max if data is not None
                obj.frame_max = max_rating if max_rating is not None else obj.frame_max
                obj.save()
            else:
                # Create a new LeagueFrame if not exists
                LeagueFrame.objects.create(
                    region=region, league=league, frame_max=max_rating)

# Define a Celery task to update players' data


@app.task
def update_players_data():
    # Retrieve all teams with related player data pre-fetched
    teams = Team.objects.all().prefetch_related('player_set')
    # Iterate over teams
    for team in teams:
        # Retrieve all registered players for the team
        registred_players = team.player_set.all()
        # Fetch player data from Blizzard API
        fetched_players = form_character_data(team.tag)[0]
        # Create a dictionary to map fetched players' IDs to their data
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
        # Iterate over registered players
        for player in registred_players:
            # Check if player ID exists in fetched players' data
            if player.battlenet_id in fetched_players_by_ids.keys():
                # Log player update
                logging.info(f"Updating player {player.username}")
                # Update player attributes
                player.username = fetched_players_by_ids[player.battlenet_id]['username']
                player.region = fetched_players_by_ids[player.battlenet_id]['region']
                player.realm = fetched_players_by_ids[player.battlenet_id]['realm']
                player.league = League.objects.get(
                    id=fetched_players_by_ids[player.battlenet_id]['league'])
                player.race = Race.objects.get(
                    id=fetched_players_by_ids[player.battlenet_id]['race'])
                player.mmr = fetched_players_by_ids[player.battlenet_id]['mmr']
                # Fetch and update player avatar
                avatar = get_avatar(
                    player.region, player.realm, player.battlenet_id)
                if avatar is not None:
                    player.avatar = avatar
                player.save()
