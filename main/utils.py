import configparser
import datetime
import requests
from rest_framework.response import Response


config = configparser.ConfigParser()
config.read('.ini')

async def get_blizzard_league_data(region, league):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    season = await get_season()
    api_url = f'https://{region}.api.blizzard.com/data/sc2/league/{season}/201/0/{league - 1}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        
        for tier in data['tier']:
            if tier['id'] == 0:
                return tier['max_rating']

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
    print(get_season)

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
    api_url = f'https://eu.api.blizzard.com/sc2/metadata/profile/{region}/{realm}/{character_id}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
    if response.status_code == 200:
        return response
    elif response.status_code == 401:
        get_new_access_token()
        return get_blizzard_data(region, realm, character_id)
    else:
        return Response({"error": "Character not found"}, status=404)