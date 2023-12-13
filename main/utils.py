import configparser
import datetime
import random
import requests
from rest_framework.response import Response
from main.models import GroupStage, LeagueFrame
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile


config = configparser.ConfigParser()
config.read('.ini')

async def get_blizzard_league_data(region, league):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    season = await get_season()
    match region:
        case 'eu':
            region_multi = 0
        case 'us':
            region_multi = 1
        case 'kr':
            region_multi = 2
    api_url = f'https://{region}.api.blizzard.com/data/sc2/league/{season}/201/0/{league - 1}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
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
        


async def get_season():
    current_time = datetime.datetime.utcnow().isoformat()

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


def get_new_access_token():
    token_url = 'https://oauth.battle.net/token'

    client_id = config['BLIZZARD']['BLIZZARD_API_ID']
    client_secret = config['BLIZZARD']['BLIZZARD_API_SECRET']

    data = {
        'grant_type': 'client_credentials',
    }

    response = requests.post(token_url, data=data, auth=(client_id, client_secret))

    if response.status_code == 200:
        config.set('BLIZZARD', 'BLIZZARD_API_TOKEN', response.json()['access_token'])
        with open('.ini', 'w') as f:
            config.write(f)
        return response.json()['access_token']
    else:
        return (response.status_code)

    
def get_blizzard_data(region, realm, character_id):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    api_url = f'https://us.api.blizzard.com/sc2/metadata/profile/{region}/{realm}/{character_id}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
    print(api_url)
    print(response)
    if response.status_code == 200:
        return response
    elif response.status_code == 401:
        get_new_access_token()
        return get_blizzard_data(region, realm, character_id)
    else:
        return Response({"error": "Character not found"}, status=404)
    

def distribute_teams_to_groups(teams, num_groups):
    try:
        random.shuffle(teams)
        num_groups = int(num_groups)
    except:
        return Response({"error": "Invalid number of groups"}, status=400)
    try:
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
                season = teams[0].season,
                groupMark = group_mark
            )
            for i in range(teams_per_group):
                team = teams.pop(0).team
                group_stage.teams.add(team)
        except IndexError:
                break
    cnt = 0
    for remaining_team in teams:
        group_stage, created = GroupStage.objects.get_or_create(
            season = remaining_team.season, 
            groupMark = chr(ord('A') + cnt)
        )
        group_stage.teams.add(remaining_team.team)
        cnt += 1

def image_compressor(image, team_name=None):
    
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