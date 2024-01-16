from channels.consumer import AsyncConsumer
from channels.exceptions import StopConsumer
from rest_framework.authtoken.models import Token
from asgiref.sync import sync_to_async, async_to_sync
import asyncio
import json
import environ
import os
import datetime
from django.conf import settings
from django.db.models.signals import post_save
from main.models import Tournament, Match, Player, Manager, Season, Team
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from main.serializers import MatchesSerializer, TeamsSerializer, PlayerToTournament, TournamentsSerializer
from django.db.models import Q
from django.utils import timezone

env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class MatchConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None
        self.user = None


    async def websocket_receive(self, event):
        if (not self.is_first_message_received):
            self.is_first_message_received = True
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                token = data['token']
                action = data['action']
                if action == 'subscribe':
                    self.group_name = data.get('group')
                    try:
                        match_objects = await sync_to_async(Match.objects.filter)(tournament=self.group_name)
                        matches_data = await sync_to_async(lambda: MatchesSerializer(match_objects, many=True).data)()
                        await self.send({
                            'type': 'websocket.send',
                            'text': json.dumps(matches_data)
                        })
                    except Match.DoesNotExist:
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()
                    if self.group_name:
                        await self.channel_layer.group_add(
                            f'match_{self.group_name}', self.channel_name
                        )
                else:
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            except KeyError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                token_obj = await sync_to_async(Token.objects.get)(key=token)
            except Token.DoesNotExist:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            self.user = await sync_to_async(lambda: token_obj.user)()
            post_save.connect(self.match_update_handler, sender=Match)
        else:
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                action = data['action']
                if action == 'update':
                    try:
                        updated_field = data['updated_field']
                    except Match.DoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': json.dumps({})
                        })
                    updated_column = data['updated_column']
                    updated_value = data['updated_value']                        
                    if updated_column == 'winner':
                        await self.update_score(updated_value, updated_field)
                    await self.match_patch(updated_field, updated_column, updated_value)
                elif action == 'create':
                    await self.match_create(event)
                else:
                    pass
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.send',
                    'text': json.dumps({})
                })

    async def timeout_handler(self):
        try:
            await asyncio.sleep(int(env('WEBSOCKET_AUTH_TIMEOUT')))
            if not self.is_first_message_received:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        except asyncio.CancelledError:
            pass


    async def websocket_disconnect(self, event):
        if self.timeout_task:
            self.timeout_task.cancel()
        await self.channel_layer.group_discard(
            f'match_{self.group_name}',
            self.channel_name
        )
        await self.send({
            'type': 'websocket.close',
        })
        raise StopConsumer()


    async def match_patch(self, field, column, data):
        obj = await sync_to_async(Match.objects.get)(id=field)
        match_winner = await sync_to_async(lambda: obj.winner)()
        old_player_one = await sync_to_async(lambda: obj.player_one)()
        old_player_two = await sync_to_async(lambda: obj.player_two)()
        if column == 'winner':
            winner = await sync_to_async(Player.objects.get)(pk=data)
            obj.winner = winner
        elif column == 'player_one':
            player = await sync_to_async(Player.objects.get)(pk=data)
            if match_winner == old_player_one and old_player_one != None:
                obj.winner = player
            obj.player_one = player
        elif column == 'player_two':
            player = await sync_to_async(Player.objects.get)(pk=data)
            if match_winner == old_player_two and old_player_two != None:
                obj.winner = player
            obj.player_two = player
        else:
            setattr(obj, column, data)            
        await sync_to_async(obj.save)()

    async def match_create(self, event):
        tournament = await sync_to_async(Tournament.objects.get)(pk=self.group_name)
        await sync_to_async(Match.objects.create)(
            tournament=tournament,
            user=self.user,
        )


    async def update_score(self, winner, field):
        if winner:
            player = await sync_to_async(Player.objects.get)(pk=winner)
            match = await sync_to_async(Match.objects.get)(pk=field)
            match_winner = await sync_to_async(lambda: match.winner)()
            team = await sync_to_async(lambda: player.team)()
            tournament = await sync_to_async(Tournament.objects.get)(pk=self.group_name)
            team_one = await sync_to_async(lambda: tournament.team_one)()
            team_two = await sync_to_async(lambda: tournament.team_two)()
            if team_one == team:
                tournament.team_one_wins += 1
                if match_winner is not None:
                    tournament.team_two_wins -= 1
            elif team_two == team:
                tournament.team_two_wins += 1
                if match_winner is not None:
                    tournament.team_one_wins -= 1
            else:
                pass

            await sync_to_async(tournament.save)()

    async def match_update(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps({
                'id': event['id'],
                'column': event['column'],
                'data': event['data']
            })
        })

    @staticmethod
    def match_update_handler(instance, **kwargs):
        channel_layer = get_channel_layer()
        matches_data = MatchesSerializer(instance).data
        if type(instance) == Match:
            matches = Match.objects.filter(tournament=instance.tournament)
            matches_data = MatchesSerializer(matches, many=True).data
        async_to_sync(channel_layer.group_send)(
            f"match_{instance.tournament.id}",
            {   
                "type": "new_match_list",
                "text": matches_data
            }
        )

    async def new_match_list(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'])
        })


class TournamentStatusConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None
        self.user = None

    async def websocket_receive(self, event):
        if (not self.is_first_message_received):
            self.is_first_message_received = True
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                token = data['token']
                self.group_name = data.get('group')
                try:
                    token_obj = await sync_to_async(Token.objects.get)(key=token)

                except Token.DoesNotExist:
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
                action = data['action']
                if action == 'subscribe':
                    try:
                        user = await sync_to_async(lambda: token_obj.user)()
                        user_id = await sync_to_async(lambda: user.id)()
                        manger = await sync_to_async(Manager.objects.get)(user=user)
                        team = await sync_to_async(lambda: manger.team)()
                        tournaments = await sync_to_async(Tournament.objects.filter)(Q(team_one=team) | Q(team_two=team))
                        if self.group_name:
                            if self.group_name == user_id:
                                await self.channel_layer.group_add(
                                    f'manager_{self.group_name}', self.channel_name
                                )
                            else:
                                await self.send({
                                    'type': 'websocket.close',
                                })
                                raise StopConsumer()
                        await sync_to_async(self.tournament_update_handler)(manager_id=self.group_name, instance=tournaments)
                    except Manager.DoesNotExist:
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()
                    except Tournament.DoesNotExist:
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()
                else:
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            except KeyError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            self.user = await sync_to_async(lambda: token_obj.user)()
            post_save.connect(self.tournament_update_handler, sender=Tournament)
        else:
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                action = data['action']
                tournament_id = data['id']
                if action == 'start_now':
                    obj = await sync_to_async(Tournament.objects.get)(pk=tournament_id)
                    is_tournament_started = await sync_to_async(lambda: obj.match_start_time.replace(tzinfo=timezone.utc) < datetime.datetime.utcnow().replace(tzinfo=timezone.utc))()
                    if not is_tournament_started:
                        obj.match_start_time = datetime.datetime.utcnow()
                        await sync_to_async(obj.save)()
                elif action == 'finish':
                    obj = await sync_to_async(Tournament.objects.get)(pk=tournament_id)
                    asked_team = await sync_to_async(lambda: obj.asked_team)()
                    manager = await sync_to_async(Manager.objects.get)(user=self.user)
                    team = await sync_to_async(lambda: manager.team)()
                    team_one = await sync_to_async(lambda: obj.team_one)()
                    team_two = await sync_to_async(lambda: obj.team_two)()
                    team_one_wins = await sync_to_async(lambda: obj.team_one_wins)()
                    team_two_wins = await sync_to_async(lambda: obj.team_two_wins)()
                    if obj.ask_for_finished and asked_team != team:
                        obj.is_finished = True
                        obj.ask_for_finished = False
                        obj.asked_team = None
                        if team_one_wins > team_two_wins:
                            obj.winner = team_one
                        elif team_one_wins < team_two_wins:
                            obj.winner = team_two
                        else:
                            obj.winner = None
                    else:
                        obj.ask_for_finished = True
                        obj.asked_team = team
                    await sync_to_async(obj.save)()
            except KeyError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
                        

    async def websocket_disconnect(self, event):
        if self.timeout_task:
            self.timeout_task.cancel()
        await self.channel_layer.group_discard(
            f'manager_{self.group_name}',
            self.channel_name
        )
        await self.send({
            'type': 'websocket.close',
        })
        raise StopConsumer()


    async def timeout_handler(self):
        try:
            await asyncio.sleep(int(env('WEBSOCKET_AUTH_TIMEOUT')))
            if not self.is_first_message_received:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        except asyncio.CancelledError:
            pass


    def tournament_update_handler(self, instance, **kwargs):
        channel_layer = get_channel_layer()
        user = User.objects.get(pk=self.group_name)
        season = Season.objects.get(is_finished=False)
        manager = Manager.objects.get(user=user)
        team = manager.team
        tournaments = Tournament.objects.filter(Q(team_one=team) | Q(team_two=team), season=season)
        if tournaments.count() == 0:
            async_to_sync(channel_layer.group_send)(
                f'manager_{self.group_name}',
                {
                    'type': 'send_tournaments',
                    'text': json.dumps([])
                }
            )
        tournaments = tournaments.order_by('match_start_time')
        response_data = []
        for tournament in tournaments:
            opponent = tournament.team_two if tournament.team_one == team else tournament.team_one
            team_in_tour_num = 1 if tournament.team_one == team else 2
            opponent_data = TeamsSerializer(opponent).data
            opp_players_to_tournament = PlayerToTournament.objects.filter(user=opponent.user, Season=season)
            opp_players_to_tournament_data = []
            for player in opp_players_to_tournament:
                opp_players_to_tournament_data.append({
                    'id': player.player.id,
                    'username': player.player.username
                })
            opponent_data['players'] = opp_players_to_tournament_data
            if tournament.ask_for_finished:
                asked_team = True if tournament.asked_team == team else False
            else: 
                asked_team = None
            if tournament.winner is not None:
                winner = tournament.winner.id
            else:
                winner = None
            if (not tournament.is_finished):
                response_data.append({
                    'id': tournament.id,
                    'startTime': tournament.match_start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'opponent': opponent_data,
                    'isFinished': tournament.is_finished,
                    'teamInTournament': team_in_tour_num,
                    'askForFinished': tournament.ask_for_finished,
                    'askedTeam': asked_team 
                })
            else:
                matches = Match.objects.filter(tournament=tournament)
                matches_data = MatchesSerializer(matches, many=True).data
                response_data.append({
                    'id': tournament.id,
                    'startTime': tournament.match_start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'opponent': opponent_data,
                    'isFinished': tournament.is_finished,
                    'teamInTournament': team_in_tour_num,
                    'team_one_wins': tournament.team_one_wins,
                    'team_two_wins': tournament.team_two_wins,
                    'matches': matches_data,
                    'winner': winner,
                })
        
        async_to_sync(channel_layer.group_send)(
            f"manager_{self.group_name}",
            {   
                "type": "send_tournaments",
                "text": [response_data]
            }
        )

    
    async def send_tournaments(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'])
        })


class AdminConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None

    async def websocket_receive(self, event):
        if (not self.is_first_message_received):
            self.is_first_message_received = True
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                token = data['token']
                self.group_name = data.get('group')
                try:
                    token_obj = await sync_to_async(Token.objects.get)(key=token)

                except Token.DoesNotExist:
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
                action = data['action']
                if action == 'subscribe':
                    try:
                        user = await sync_to_async(lambda: token_obj.user)()
                        self.group_name = await sync_to_async(lambda: user.id)()
                        is_admin = await sync_to_async(lambda: user.is_staff)()
                        season = await sync_to_async(Season.objects.get)(is_finished=False)
                        tournaments = await sync_to_async(Tournament.objects.filter)(season=season)
                        if is_admin:
                            await self.channel_layer.group_add(
                                f'admin_{self.group_name}',
                                self.channel_name
                            )
                            await sync_to_async(self.tournament_update_handler)(instance=tournaments)
                            post_save.connect(self.tournament_update_handler, sender=Tournament)
                        else:
                            await self.send({
                                'type': 'websocket.close',
                            })
                            raise StopConsumer()
                    except:
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()

            except KeyError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        else:
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            if data['action'] == 'set_winner':
                tournament_id = data['tournament_id']
                winner_id = data['winner_id']
                tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                winner = await sync_to_async(Team.objects.get)(id=winner_id)
                tournament.is_finished = True
                tournament.ask_for_finished = False
                tournament.asked_team = None
                tournament.winner = winner
                await sync_to_async(tournament.save)()
                        

    async def websocket_disconnect(self, event):
        if self.timeout_task:
            self.timeout_task.cancel()
        await self.channel_layer.group_discard(
            f'admin_{self.group_name}',
            self.channel_name
        )
        await self.send({
            'type': 'websocket.close',
        })
        raise StopConsumer()
    
    async def timeout_handler(self):
        try:
            await asyncio.sleep(int(env('WEBSOCKET_AUTH_TIMEOUT')))
            if not self.is_first_message_received:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        except asyncio.CancelledError:
            pass

    def tournament_update_handler(self, instance, **kwargs):
        channel_layer = get_channel_layer()
        season = Season.objects.get(is_finished=False)
        tournaments = Tournament.objects.filter(season=season)
        response_data = []
        for tournament in tournaments:
            matches = Match.objects.filter(tournament=tournament)
            if matches:
                matchesExists = True
            else:
                matchesExists = False
            tournament_data = {
                'id': tournament.id,
                'season': tournament.season.number,
                'startTime': tournament.match_start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'isFinished': tournament.is_finished,
                'teamOne': tournament.team_one.pk,
                'teamOneName': tournament.team_one.name,
                'teamOneWins': tournament.team_one_wins,
                'teamTwo': tournament.team_two.pk,
                'teamTwoName': tournament.team_two.name,
                'teamTwoWins': tournament.team_two_wins,
                'stage': tournament.stage,
                'group': tournament.group.pk,
                'winner': tournament.winner.pk if tournament.winner else None,
                'askedTeam': tournament.asked_team.pk if tournament.asked_team else None,
                'askForFinished': tournament.ask_for_finished,
                'matchesExists': matchesExists
            }
            response_data.append(tournament_data)
        async_to_sync(channel_layer.group_send)(
            f"admin_{self.group_name}",
            {   
                "type": "send_tournaments",
                "text": response_data
            }
        )


    async def send_tournaments(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'])
        })