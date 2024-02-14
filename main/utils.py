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

    response = requests.post(token_url, data=data,
                             auth=(client_id, client_secret))

    if response.status_code == 200:
        config.set('BLIZZARD', 'BLIZZARD_API_TOKEN',
                   response.json()['access_token'])
        with open('.ini', 'w') as f:
            config.write(f)
        return response.json()['access_token']
    else:
        return (response.status_code)


def get_blizzard_data(region, realm, character_id):
    token = config['BLIZZARD']['BLIZZARD_API_TOKEN']
    api_url = f'https://us.api.blizzard.com/sc2/metadata/profile/{region}/{realm}/{character_id}?locale=en_US&access_token={token}'
    response = requests.get(api_url)
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
        return {"error": "Invalid number of groups", "status": 400}
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


def get_avatar(region, realm, character_id):
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


def leagueFrames():
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


def get_league(mmr, league_frames, region):
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


def form_character_data(clan_tag: str):
    api_url = f'https://sc2pulse.nephest.com/sc2/api/character/search?term=%5B{clan_tag}%5D'
    response = requests.get(api_url)
    league_frames = leagueFrames()
    if response.status_code == 200:
        data = response.json()
        if len(data) == 0:
            return [None, status.HTTP_404_NOT_FOUND]
        character_data = []
        for item in data:
            character = item['members']['character']
            name = character['name'].split('#')[0]
            ch_id = character['battlenetId']
            region = character['region']
            mmr = item['currentStats']['rating']
            if (not mmr):
                mmr = item['ratingMax']
            if region in ['TW', 'CN']:
                region = 'KR'

            league_max = get_league(mmr, league_frames, region)
            if league_max == 7:
                league_max = item['leagueMax'] + 1

            match region:
                case 'US':
                    region = 1
                case 'EU':
                    region = 2
                case 'KR':
                    region = 3
            realm = character['realm']
            if ('protossGamesPlayed' in item['members']):
                race = 3
            elif ('zergGamesPlayed' in item['members']):
                race = 1
            elif ('terranGamesPlayed' in item['members']):
                race = 2
            elif ('randomGamesPlayed' in item['members']):
                race = 4
            else:
                race = 'unknown'
            character_info = {
                "username": name,
                "region": region,
                "realm": realm,
                "id": ch_id,
                "league": league_max,
                "race": race,
                "mmr": mmr
            }

            character_data.append(character_info)
        region_priority = {
            2: 0,
            1: 1,
            3: 2
        }
        character_data = sorted(character_data, key=lambda k: (
            region_priority.get(k['region'], float('inf')), -k['mmr']))
        resp_status = status.HTTP_200_OK
        return [character_data, resp_status]
    else:
        return [None, status.HTTP_404_NOT_FOUND]


def get_season_data(season):
    season = Season.objects.filter(number=season).prefetch_related('groupstage_set', 'tournament_set')
    season_first = season.first()
    if (not season_first):
        return None, None
    groups = season_first.groupstage_set.all()
    tournaments_in_group = season_first.tournament_set.filter(group__isnull=False)
    tournaments_off_group = season_first.tournament_set.filter(group__isnull=True)
    wins = {}
    playoff_data = {}
    for tournament in tournaments_in_group:
        if tournament.winner:
            wins[tournament.winner.pk] = wins.get(
                tournament.winner.pk, 0) + 1
    stage_nums = []
    max_stage = tournaments_off_group.aggregate(Max('stage'))['stage__max']
    second_max_stage = 0
    if max_stage == 999:
        second_max_stage = tournaments_off_group.values_list('stage', flat=True).order_by('-stage').distinct()[1]
        max_stage = second_max_stage
    for stage in range(1, max_stage + 1):
        stage_nums.append(stage)
    if second_max_stage != 0:
        stage_nums.append(999)
    stages = {}
    if (max_stage):
        for stage in stage_nums:
            print(stage, max_stage)
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
    groups_data = {}
    for group in groups:
        teams_data = {}
        for team in group.teams.all():
            teams_data[str(team.name)] = wins.get(team.pk, 0)
        groups_data[str(group.groupMark)] = teams_data
    return groups_data, playoff_data