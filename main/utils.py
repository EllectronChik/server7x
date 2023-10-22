import configparser
import datetime
import requests


config = configparser.ConfigParser()
config.read('.ini')

def get_blizzard_league_data(region, league):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    api_url = f'https://{region}.api.blizzard.com/data/sc2/league/{get_season()}/201/0/{league - 1}?locale=en_US&access_token={token}'

    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        
        for tier in data['tier']:
            if tier['id'] == 2:
                return tier['max_rating']

    elif response.status_code == 401:
        new_token = get_new_access_token()
        config.set('BLIZZARD', 'BLIZZARD_API_TOKEN', new_token)
        with open('.ini', 'w') as f:
            print('rewriting config file')
            config.write(f)
        return get_blizzard_data()


def get_season():
    current_time = datetime.datetime.utcnow().isoformat()

    get_season = f'https://sc2pulse.nephest.com/sc2/api/season/state/{current_time}/HOUR'

    response = requests.get(get_season)

    if response.status_code == 200:
        data = response.json()
        if data and isinstance(data, list):
            season = data[0]
            if 'season' in season and 'battlenetId' in season['season']:
                battlenetId = season['season']['battlenetId']
                print(battlenetId)
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
        return response.json()['access_token']
    else:
        return (response.status_code)

    
def get_blizzard_data(region, realm, character_id):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    api_url = f'https://eu.api.blizzard.com/sc2/metadata/profile/{region}/{realm}/{character_id}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
    return response