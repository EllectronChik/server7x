# Import necessary modules and packages
import configparser
import datetime
import random
import requests
from rest_framework import status
from rest_framework.response import Response
from main.models import GroupStage, LeagueFrame, Season, Tournament, Match
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Max


# Read configuration from .ini file
config = configparser.ConfigParser()
config.read('.ini')


# Asynchronous function to fetch Blizzard league data
async def get_blizzard_league_data(region, league):
    """
    Fetches data about a specific league from the Blizzard API.

    Args:
        region (str): The region code ('eu', 'us', or 'kr').
        league (int): The league ID.

    Returns:
        int or None: The maximum rating of the specified league, or None if data retrieval fails.
    """
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    # Get current season
    season = await get_season()
    # Determine region multiplier
    match region:
        case 'eu':
            region_multi = 0
        case 'us':
            region_multi = 1
        case 'kr':
            region_multi = 2
    # API URL for fetching league data
    api_url = f'https://{region}.api.blizzard.com/data/sc2/league/{season}/201/0/{league - 1}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
    # Handle different HTTP status codes
    if response.status_code == 200:
        data = response.json()
        for tier in data['tier']:
            if tier['id'] == 0:
                if tier['max_rating']:
                    return tier['max_rating']
                else:
                    last_max_id = region_multi * 6 + league - 1
                    try:
                        last_max = LeagueFrame.get(id=last_max_id).frame_max
                    except:
                        last_max = 0
                return last_max + 500

    elif response.status_code == 401:
        get_new_access_token()
        return await get_blizzard_league_data(region, league)

    elif response.status_code == 404:
        api_url = f'https://{region}.api.blizzard.com/data/sc2/league/{season - 1}/201/0/{league - 1}?locale=en_US&access_token={token}'
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            for tier in data['tier']:
                if tier['id'] == 0:
                    return tier['max_rating']
        elif response.status_code == 401:
            get_new_access_token()
            return await get_blizzard_league_data(region, league)
        else:
            return None


# Function to fetch current season
async def get_season():
    """
    Fetches the current season data from the StarCraft II Pulse API.

    Returns:
        str or None: The Battle.net ID of the current season, if available. None if data is unavailable.
    """
    current_time = datetime.datetime.utcnow().isoformat()
    # URL to fetch current season data
    get_season = f'https://sc2pulse.nephest.com/sc2/api/season/state/{current_time}Z/DAY'

    response = requests.get(get_season)

    if response.status_code == 200:
        data = response.json()
        if data and isinstance(data, list):
            season = data[0]
            if 'season' in season and 'battlenetId' in season['season']:
                battlenetId = season['season']['battlenetId']
                return battlenetId
            else:
                return None
        else:
            return None
    else:
        return None


# Function to get new access token
def get_new_access_token():
    """
    Retrieves a new access token from the Blizzard OAuth token endpoint.

    This function sends a POST request to the Blizzard OAuth token endpoint
    with client credentials to obtain a new access token.

    Returns:
        str: The new access token obtained from the OAuth token endpoint.

    Raises:
        int: The HTTP status code if the request fails.
    """
    token_url = 'https://oauth.battle.net/token'

    client_id = config['BLIZZARD']['BLIZZARD_API_ID']
    client_secret = config['BLIZZARD']['BLIZZARD_API_SECRET']

    data = {
        'grant_type': 'client_credentials',
    }

    response = requests.post(token_url, data=data,
                             auth=(client_id, client_secret))
    # Handle response
    if response.status_code == 200:
        config.set('BLIZZARD', 'BLIZZARD_API_TOKEN',
                   response.json()['access_token'])
        with open('.ini', 'w') as f:
            config.write(f)
        return response.json()['access_token']
    else:
        return (response.status_code)


# Function to fetch Blizzard data
def get_blizzard_data(region, realm, character_id):
    """
    Fetches Blizzard data for a given StarCraft II character.

    Args:
        region (int): The region code for the character. 
            1 for US, 2 for EU, 3 for KO.
        realm (int): The realm code for the character. 
            Should be 1 or 2.
        character_id (int): The unique identifier for the character.

    Returns:
        JsonResponse: A JSON response containing the Blizzard data if successful.
        JsonResponse: A JSON response indicating the character was not found if the request fails.
    """
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    # API URL for fetching Blizzard data
    api_url = f'https://us.api.blizzard.com/sc2/metadata/profile/{region}/{realm}/{character_id}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
     # Handle response
    if response.status_code == 200:
        return response
    elif response.status_code == 401:
        get_new_access_token()
        return get_blizzard_data(region, realm, character_id)
    else:
        return Response({"error": "Character not found"}, status=404)


# Function to distribute teams to groups
def distribute_teams_to_groups(teams, num_groups):
    """
    Distributes teams into groups for a group stage of a season.

    Args:
        teams (list): A list of Team objects to be distributed into groups.
        num_groups (int): The number of groups to distribute the teams into.

    Returns:
        dict: A dictionary indicating the status of the operation. If successful, returns {'status': 201}.
              If there's an error with the number of groups, returns {'error': 'Invalid number of groups', 'status': 400}.
    """
    try:
        random.shuffle(teams)
        num_groups = int(num_groups)
    except:
        return {"error": "Invalid number of groups", "status": 400}
    try:
        # Delete existing group stage data for the season
        GroupStage.objects.filter(season=teams[0].season).delete()
    except IndexError:
        pass
    teams_per_group = len(teams) // int(num_groups)
    if teams_per_group == 0:
        teams_per_group = 1
    for group_mark in range(ord('A'), ord('A') + num_groups):
        group_mark = chr(group_mark)
        try:
            group_stage, created = GroupStage.objects.get_or_create(
                season=teams[0].season,
                groupMark=group_mark
            )
            for i in range(teams_per_group):
                team = teams.pop(0).team
                group_stage.teams.add(team)
        except IndexError:
            break
    cnt = 0
    for remaining_team in teams:
        group_stage, created = GroupStage.objects.get_or_create(
            season=remaining_team.season,
            groupMark=chr(ord('A') + cnt)
        )
        group_stage.teams.add(remaining_team.team)
        cnt += 1
    return {"status": 201}


# Function to compress image
def image_compressor(image, team_name=None):
    """
    Compresses the given image and returns an InMemoryUploadedFile object.

    Parameters:
    image (str): The path to the image file.
    team_name (str, optional): The name of the team associated with the image. 
        If provided, the compressed image will be named with the team name.

    Returns:
    InMemoryUploadedFile: The compressed image file object.

    This function compresses the given image to fit within a maximum size of 720x720 pixels.
    It uses the Lanczos resampling method for resizing and saves the compressed image as a PNG file.
    If a team name is provided, the compressed image will be named using the team name,
    otherwise, the original image name will be used.
    If the resulting image name exceeds 100 characters, it will be truncated to 90 characters
    before appending the '.png' extension.
    """
    max_size = (720, 720)
    imagePl = Image.open(image)
    imagePl.thumbnail(max_size, Image.Resampling.LANCZOS)
    image_buffer = BytesIO()
    imagePl.save(image_buffer, format='PNG')
    if team_name:
        name = f'{team_name}.png'
    else:
        name = image.name
    if len(name) > 100:
        name = image.name[:90] + '.png'
    image_file = InMemoryUploadedFile(
        image_buffer, None, name, 'image/png', image_buffer.tell(), None
    )
    return image_file


# Function to fetch avatar
def get_avatar(region, realm, character_id):
    """
    Retrieves the avatar URL for a given character from the Blizzard API.

    Args:
        region (int): The region code for the character. 
            1 for US, 2 for EU, 3 for KO.
        realm (int): The realm ID where the character exists.
            Should be 1 or 2.
        character_id (int): The ID of the character.

    Returns:
        str or None: The URL of the character's avatar if found, 
            otherwise None.

    Raises:
        requests.exceptions.HTTPError: If there's an HTTP error 
            while fetching the data from the Blizzard API.
    """
    try:
        response = get_blizzard_data(region, realm, character_id)
        if response.status_code == 404:
            return None
        data = response.json()
        avatar = data['avatarUrl']
        return avatar
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        else:
            raise e


# Function to fetch league frames
def leagueFrames():
    """
    Retrieve the maximum frame values for different leagues and regions.

    Returns:
        dict: A dictionary containing maximum frame values for different leagues and regions.
              Keys follow the format: {REGION}_{LEAGUE}, e.g., EU_1, US_2, KR_3.
              Values represent the maximum frame for the respective league and region.
    """
    league_frames = {
        'EU_1': LeagueFrame.objects.get(region='eu', league=1).frame_max,
        'EU_2': LeagueFrame.objects.get(region='eu', league=2).frame_max,
        'EU_3': LeagueFrame.objects.get(region='eu', league=3).frame_max,
        'EU_4': LeagueFrame.objects.get(region='eu', league=4).frame_max,
        'EU_5': LeagueFrame.objects.get(region='eu', league=5).frame_max,
        'EU_6': LeagueFrame.objects.get(region='eu', league=6).frame_max,
        'US_1': LeagueFrame.objects.get(region='us', league=1).frame_max,
        'US_2': LeagueFrame.objects.get(region='us', league=2).frame_max,
        'US_3': LeagueFrame.objects.get(region='us', league=3).frame_max,
        'US_4': LeagueFrame.objects.get(region='us', league=4).frame_max,
        'US_5': LeagueFrame.objects.get(region='us', league=5).frame_max,
        'US_6': LeagueFrame.objects.get(region='us', league=6).frame_max,
        'KR_1': LeagueFrame.objects.get(region='kr', league=1).frame_max,
        'KR_2': LeagueFrame.objects.get(region='kr', league=2).frame_max,
        'KR_3': LeagueFrame.objects.get(region='kr', league=3).frame_max,
        'KR_4': LeagueFrame.objects.get(region='kr', league=4).frame_max,
        'KR_5': LeagueFrame.objects.get(region='kr', league=5).frame_max,
        'KR_6': LeagueFrame.objects.get(region='kr', league=6).frame_max
    }
    return league_frames


# Function to determine league based on MMR
def get_league(mmr, league_frames, region):
    """
    Determines the league of a player based on their Match Making Rating (MMR) and predefined league frames.

    Args:
        mmr (int): The Match Making Rating of the player.
        league_frames (dict): A dictionary containing league frame values for different regions.
            Example: {'region_1': 1000, 'region_2': 1500, ...}
        region (str): The region code for which the league is being determined.

    Returns:
        int: The league of the player ranging from 1 to 7, where 1 represents the lowest league and 7 represents the highest.

    """
    mmr = int(mmr)
    if (mmr > league_frames[f'{region}_6']):
        league_max = 7
    elif (mmr > league_frames[f'{region}_5']):
        league_max = 6
    elif (mmr > league_frames[f'{region}_4']):
        league_max = 5
    elif (mmr > league_frames[f'{region}_3']):
        league_max = 4
    elif (mmr > league_frames[f'{region}_2']):
        league_max = 3
    elif (mmr > league_frames[f'{region}_1']):
        league_max = 2
    else:
        league_max = 1
    return league_max


# Function to format character data
def form_character_data(clan_tag: str):
    """
    Forms character data based on a given clan tag.

    Args:
        clan_tag (str): The clan tag to search for.

    Returns:
        tuple: A tuple containing character data and response status.
            The character data is a list of dictionaries containing information about each character.
            The response status is an HTTP status code indicating the success of the operation.
    """
    # Construct the API URL using the clan tag
    api_url = f'https://sc2pulse.nephest.com/sc2/api/character/search?term=%5B{clan_tag}%5D'

    # Make a GET request to the API
    response = requests.get(api_url)

    # Get league frames
    league_frames = leagueFrames()

    # Check if the response is successful
    if response.status_code == 200:
        # Parse response JSON data
        data = response.json()

        # Check if data is empty
        if len(data) == 0:
            # Return 404 status if data is empty
            return [None, status.HTTP_404_NOT_FOUND]

        # Initialize an empty list to store character data
        character_data = []

        # Iterate over each item in the response data
        for item in data:
            # Extract character information
            character = item['members']['character']
            name = character['name'].split('#')[0]
            ch_id = character['battlenetId']
            region = character['region']
            mmr = item['currentStats']['rating']

            # Handle missing mmr
            if not mmr:
                mmr = item['ratingMax']

            # Map certain regions to 'KR'
            if region in ['TW', 'CN']:
                region = 'KR'

            # Get the maximum league
            league_max = get_league(mmr, league_frames, region)
            if league_max == 7:
                league_max = item['leagueMax'] + 1

            # Map regions to numerical values
            match region:
                case 'US':
                    region = 1
                case 'EU':
                    region = 2
                case 'KR':
                    region = 3

            realm = character['realm']

            # Determine the race based on games played
            if 'protossGamesPlayed' in item['members']:
                race = 3
            elif 'zergGamesPlayed' in item['members']:
                race = 1
            elif 'terranGamesPlayed' in item['members']:
                race = 2
            elif 'randomGamesPlayed' in item['members']:
                race = 4
            else:
                race = 'unknown'

            # Construct character information dictionary
            character_info = {
                "username": name,
                "region": region,
                "realm": realm,
                "id": ch_id,
                "league": league_max,
                "race": race,
                "mmr": mmr
            }

            # Append character information to character_data list
            character_data.append(character_info)

        # Define region priority
        region_priority = {
            2: 0,
            1: 1,
            3: 2
        }

        # Sort character data based on region and mmr
        character_data = sorted(character_data, key=lambda k: (
            region_priority.get(k['region'], float('inf')), -k['mmr']))

        # Set response status to 200 OK
        resp_status = status.HTTP_200_OK

        # Return character data and response status
        return [character_data, resp_status]

    else:
        # Return None and 404 status if the response is not successful
        return [None, status.HTTP_404_NOT_FOUND]



# Function to fetch season data
def get_season_data(season):
    """
    Retrieve data for a specific season including group stage and playoff information.

    Args:
        season (int): The number of the season.

    Returns:
        tuple: A tuple containing group stage data and playoff data.
            The first element is a dictionary representing group stage data.
            The second element is a dictionary representing playoff data.
            If no data is found for the given season, returns (None, None).
    """
    # Retrieve the season object with the given number
    season = Season.objects.filter(number=season).prefetch_related('groupstage_set', 'tournament_set')
    season_first = season.first()

    # Check if season exists
    if not season_first:
        return None, None

    # Retrieve group stage and tournament objects related to the season
    groups = season_first.groupstage_set.all()
    tournaments_in_group = season_first.tournament_set.filter(group__isnull=False)
    tournaments_off_group = season_first.tournament_set.filter(group__isnull=True)

    # Count wins for each team in tournaments with groups
    wins = {}
    for tournament in tournaments_in_group:
        if tournament.winner:
            wins[tournament.winner.pk] = wins.get(tournament.winner.pk, 0) + 1

    # Determine playoff stages and gather playoff data
    playoff_data = {}
    stage_nums = []
    max_stage = tournaments_off_group.aggregate(Max('stage'))['stage__max']
    second_max_stage = 0
    if max_stage == 999:
        try:
            second_max_stage = tournaments_off_group.values_list('stage', flat=True).order_by('-stage').distinct()[1]
        except IndexError:
            second_max_stage = 0
        max_stage = second_max_stage

    if max_stage:
        for stage in range(1, max_stage + 1):
            stage_nums.append(stage)
        if second_max_stage != 0:
            stage_nums.append(999)

        stages = {}
        for stage in stage_nums:
            tournaments = season_first.tournament_set.filter(
                group__isnull=True, stage=stage).order_by('inline_number').prefetch_related('match_set')

            for tournament in tournaments:
                matches = tournament.match_set.all()
                team_one_wins = 0
                team_two_wins = 0
                for match in matches:
                    if match.winner and match.winner.team == tournament.team_one:
                        team_one_wins += 1
                    elif match.winner and match.winner.team == tournament.team_two:
                        team_two_wins += 1
                stages[str(tournament.inline_number)] = {
                    'teamOne': tournament.team_one.name,
                    'teamTwo': tournament.team_two.name,
                    'teamOneWins': team_one_wins,
                    'teamTwoWins': team_two_wins,
                    'winner': tournament.winner.name if tournament.winner else None
                }

            if stages:
                playoff_data[str(stage)] = stages
            stages = {}

    # Gather group stage data
    groups_data = {}
    for group in groups:
        teams_data = {}
        for team in group.teams.all():
            teams_data[str(team.name)] = wins.get(team.pk, 0)
        groups_data[str(group.groupMark)] = teams_data

    return groups_data, playoff_data
