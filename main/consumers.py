from channels.consumer import AsyncConsumer
from channels.exceptions import StopConsumer
from rest_framework.authtoken.models import Token
from asgiref.sync import sync_to_async, async_to_sync
import asyncio
import json
import environ
import os
import datetime
import uuid
from django.conf import settings
from django.db.models.signals import post_save
from main.models import Tournament, Match, Player, Manager, Season, Team, GroupStage
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from main.serializers import MatchesSerializer, TeamsSerializer, PlayerToTournament, SeasonsSerializer
from django.db.models import Q, Max
from django.utils import timezone
from django.core.exceptions import ValidationError, FieldDoesNotExist

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
        self.is_admin_user = False

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
            self.is_admin_user = await sync_to_async(lambda: self.user.is_staff)()
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
                elif action == 'delete':
                    match_pk = data['match_pk']
                    await self.match_delete(match_pk)
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
            if (match_winner is not None and match_winner != winner):
                match_winner.wins -= 1
                await sync_to_async(match_winner.save)()
            if (winner is not None and winner != match_winner):
                winner.wins += 1
                await sync_to_async(winner.save)()
            obj.winner = winner
        elif column == 'player_one':
            player = await sync_to_async(Player.objects.get)(pk=data)
            if (old_player_one is not None and old_player_one != player):
                old_player_one.total_games -= 1
                await sync_to_async(old_player_one.save)()
            if (player is not None and player != old_player_one):
                player.total_games += 1
                await sync_to_async(player.save)()
            if match_winner == old_player_one and old_player_one != None:
                obj.winner = player
            obj.player_one = player
        elif column == 'player_two':
            player = await sync_to_async(Player.objects.get)(pk=data)
            if (old_player_two is not None and old_player_two != player):
                old_player_two.total_games -= 1
                await sync_to_async(old_player_two.save)()
            if (player is not None and player != old_player_two):
                player.total_games += 1
                await sync_to_async(player.save)()
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

    async def match_delete(self, match_pk):
        if (self.is_admin_user):
            match = await sync_to_async(Match.objects.get)(pk=match_pk)
            await sync_to_async(match.delete)()
            matches = await sync_to_async(Match.objects.filter)(tournament=match.tournament)
            await self.send({
                'type': 'websocket.send',
                'text': json.dumps(matches)
            })

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
            post_save.connect(self.tournament_update_handler,
                              sender=Tournament)
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
                    obj_inline = await sync_to_async(lambda: obj.inline_number)()
                    paired_number = obj_inline + 1 if obj_inline % 2 == 0 else obj_inline - 1
                    paired_tournament = await sync_to_async(lambda: Tournament.objects.get(inline_number=paired_number, stage=obj.stage, season=obj.season))()
                    if paired_tournament:
                        paired_tournament_winner = await sync_to_async(lambda: paired_tournament.winner)()
                    else:
                        paired_tournament_winner = None
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
                        if paired_tournament_winner is not None and obj.winner is not None:
                            next_stage_tournament = await sync_to_async(lambda: Tournament(
                                team_one=obj.winner,
                                team_two=paired_tournament_winner,
                                season=obj.season,
                                stage=obj.stage + 1,
                                inline_number=obj.inline_number // 2,
                                match_start_time=(
                                    datetime.datetime.combine(
                                        datetime.datetime.now() + datetime.timedelta(days=1),
                                        datetime.time(15, 0)))
                            ))()
                            await sync_to_async(next_stage_tournament.save)()
                            obj.next_stage_tournament = next_stage_tournament
                            paired_tournament.next_stage_tournament = next_stage_tournament
                            await sync_to_async(paired_tournament.save)()
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
        tournaments = Tournament.objects.filter(
            Q(team_one=team) | Q(team_two=team), season=season)
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
            opp_players_to_tournament = PlayerToTournament.objects.filter(
                user=opponent.user, Season=season)
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
                    'teamOneWins': tournament.team_one_wins,
                    'teamTwoWins': tournament.team_two_wins,
                    'askedTeam': asked_team,
                    'tournamentInGroup': True if tournament.group is not None else False,
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
                    'teamOneWins': tournament.team_one_wins,
                    'teamTwoWins': tournament.team_two_wins,
                    'matches': matches_data,
                    'winner': winner,
                    'tournamentInGroup': True if tournament.group is not None else False,
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
                            post_save.connect(
                                self.tournament_update_handler, sender=Tournament)
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
            if data['action'] == 'update':
                tournament_id = data['tournament_id']
                field = data['field']
                value = data['value']
                if field == 'is_finished':
                    try:
                        tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                        team_one = await sync_to_async(lambda: tournament.team_one)()
                        team_two = await sync_to_async(lambda: tournament.team_two)()
                        team_one_wins = await sync_to_async(lambda: tournament.team_one_wins)()
                        team_two_wins = await sync_to_async(lambda: tournament.team_two_wins)()
                        try:
                            tournament.is_finished = value
                            if value is True:
                                tournament.ask_for_finished = False
                                tournament.asked_team = None
                                if team_one_wins > team_two_wins:
                                    tournament.winner = team_one
                                elif team_one_wins < team_two_wins:
                                    tournament.winner = team_two
                                else:
                                    tournament.winner = None
                            else:
                                tournament.winner = None
                            await sync_to_async(tournament.save)()
                        except ValidationError:
                            await self.send({
                                'type': 'websocket.send',
                                'text': 'Incorrect Value'
                            })
                    except FieldDoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': 'Field not found'
                        })
                elif field == 'winner':
                    try:
                        tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                        obj_inline = tournament.inline_number
                        if (obj_inline):
                            try:
                                paired_number = obj_inline + 1 if obj_inline % 2 == 0 else obj_inline - 1
                            except:
                                paired_number = None
                        else:
                            paired_number = None
                        try:
                            if (paired_number is not None):
                                paired_tournament = await sync_to_async(lambda: Tournament.objects.get(inline_number=paired_number, stage=tournament.stage, season=tournament.season))()
                            else:
                                paired_tournament = None
                        except Tournament.DoesNotExist:
                            paired_tournament = None
                        if paired_tournament is not None:
                            paired_tournament_winner = await sync_to_async(lambda: paired_tournament.winner)()
                        else:
                            paired_tournament_winner = None
                        winner = await sync_to_async(Team.objects.get)(pk=value)
                        try:
                            tournament.is_finished = True
                            tournament.ask_for_finished = False
                            tournament.asked_team = None
                            tournament.winner = winner
                            try:
                                next_stage_tournament = await sync_to_async(lambda: tournament.next_stage_tournament)()
                            except:
                                next_stage_tournament = None
                            if (paired_tournament_winner is not None and next_stage_tournament is None):
                                next_stage_tournament = await sync_to_async(lambda: Tournament(
                                    team_one=paired_tournament_winner,
                                    team_two=winner,
                                    season=paired_tournament.season,
                                    stage=paired_tournament.stage + 1,
                                    is_finished=False,
                                    inline_number=paired_number // 2,
                                    match_start_time=(
                                        datetime.datetime.combine(
                                            datetime.datetime.now() + datetime.timedelta(days=1),
                                            datetime.time(15, 0)))))()
                                await sync_to_async(next_stage_tournament.save)()
                                paired_tournament.next_stage_tournament = next_stage_tournament
                                await sync_to_async(paired_tournament.save)()
                                tournament.next_stage_tournament = next_stage_tournament
                            if (next_stage_tournament is not None):
                                next_stage_tournament_team_one = await sync_to_async(lambda: next_stage_tournament.team_one)()
                                if (next_stage_tournament_team_one == paired_tournament_winner):
                                    next_stage_tournament.team_two = winner
                                else:
                                    next_stage_tournament.team_one = winner
                                await sync_to_async(next_stage_tournament.save)()
                            await sync_to_async(tournament.save)()
                        except ValidationError:
                            await self.send({
                                'type': 'websocket.send',
                                'text': 'Incorrect Value'
                            })
                    except FieldDoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': 'Field not found'
                        })
                elif field == 'team_two':
                    try:
                        tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                        team_two = await sync_to_async(Team.objects.get)(pk=value)
                        try:
                            tournament.team_two = team_two
                            await sync_to_async(tournament.save)()
                        except ValidationError:
                            await self.send({
                                'type': 'websocket.send',
                                'text': 'Incorrect Value'
                            })
                    except FieldDoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': 'Field not found'
                        })
                elif field == 'team_one':
                    try:
                        tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                        team_one = await sync_to_async(Team.objects.get)(pk=value)
                        try:
                            tournament.team_one = team_one
                            await sync_to_async(tournament.save)()
                        except ValidationError:
                            await self.send({
                                'type': 'websocket.send',
                                'text': 'Incorrect Value'
                            })
                    except FieldDoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': 'Field not found'
                        })
                else:
                    try:
                        await sync_to_async(lambda: Tournament._meta.get_field(field))()
                        tournament = await sync_to_async(Tournament.objects.get)(id=tournament_id)
                        try:
                            setattr(tournament, field, value)
                            await sync_to_async(tournament.save)()
                        except ValidationError:
                            await self.send({
                                'type': 'websocket.send',
                                'text': 'Incorrect Value'
                            })
                    except FieldDoesNotExist:
                        await self.send({
                            'type': 'websocket.send',
                            'text': 'Field not found'
                        })
            if data['action'] == 'create_tournament':
                try:
                    match_start_time = data['match_start_time']
                    team_one_pk = data['team_one']
                    team_two_pk = data['team_two']
                    inline_number = data.get('inline_number')
                    if team_one_pk == team_two_pk:
                        raise ValidationError("Teams can't be equal")
                    stage = data['stage']
                    season = await sync_to_async(Season.objects.get)(is_finished=False)
                    team_one = await sync_to_async(Team.objects.get)(pk=team_one_pk)
                    team_two = await sync_to_async(Team.objects.get)(pk=team_two_pk)
                    data = {
                        'season': season,
                        'match_start_time': match_start_time,
                        'team_one': team_one,
                        'team_two': team_two,
                        'stage': stage,
                        'is_finished': False,
                        'inline_number': inline_number
                    }
                    await sync_to_async(Tournament.objects.create)(**data)
                except ValidationError:
                    await self.send({
                        'type': 'websocket.send',
                        'text': 'Incorrect Value'
                    })

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
                'group': tournament.group.pk if tournament.group else None,
                'winner': tournament.winner.pk if tournament.winner else None,
                'askedTeam': tournament.asked_team.pk if tournament.asked_team else None,
                'askForFinished': tournament.ask_for_finished,
                'matchesExists': matchesExists,
                'inlineNumber': tournament.inline_number
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


class groupsConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None
        self.user = None
        self.is_admin_user = False

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
                            self.is_admin_user = True
                            self.user = user
                            await self.channel_layer.group_add(
                                f'groups_{self.group_name}',
                                self.channel_name
                            )
                            await sync_to_async(self.group_update_handler)(instance=tournaments)
                            post_save.connect(
                                self.group_update_handler, sender=Tournament)
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

    async def websocket_disconnect(self, event):
        if self.timeout_task:
            self.timeout_task.cancel()
        await self.channel_layer.group_discard(
            f'groups_{self.group_name}',
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

    def group_update_handler(self, instance, **kwargs):
        channel_layer = get_channel_layer()
        season = Season.objects.get(is_finished=False)
        groups = GroupStage.objects.filter(season=season)
        tournaments = Tournament.objects.filter(
            season=season, group__isnull=False)
        wins = {}
        for tournament in tournaments:
            if tournament.winner:
                wins[tournament.winner.pk] = wins.get(
                    tournament.winner.pk, 0) + 1
        groups_data = {}
        for group in groups:
            teams_data = {}
            for team in group.teams.all():
                teams_data[str(team.pk)] = wins.get(team.pk, 0)
            groups_data[str(group.pk)] = teams_data
        if groups_data:
            async_to_sync(channel_layer.group_send)(
                f'groups_{self.group_name}',
                {
                    'type': 'send_groups',
                    'text': groups_data
                }
            )

    async def send_groups(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'])
        })


class InfoConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        self.group_id = uuid.uuid4().hex
        await self.send({
            'type': 'websocket.accept'
        })
        await self.channel_layer.group_add(
            f'groups_{self.group_id}',
            self.channel_name
        )
        self.previus_seasons = await self.async_get_previus_seasons()
        self.players_by_league = await self.async_get_players_by_league()
        try:
            season = await sync_to_async(Season.objects.get)(is_finished=False)
            try:
                tournaments = await sync_to_async(Tournament.objects.filter)(season=season)
                await sync_to_async(self.group_update_handler)(instance=tournaments)
            except Tournament.DoesNotExist:
                pass
            except TypeError:
                pass
            post_save.connect(self.group_update_handler, sender=Tournament)
        except Season.DoesNotExist:
            await self.send({
                'type': 'websocket.send',
                'text': json.dumps({
                    'state': 0,
                    "previusSeasons": self.previus_seasons,
                    "playersByLeague": self.players_by_league
                })
            })
            post_save.connect(self.wait_for_season, sender=Season)

    def wait_for_season(self, instance, **kwargs):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'groups_{self.group_id}',
            {
                'type': 'send_groups',
                'text': {
                        'state': 9,
                        "previusSeasons": self.previus_seasons,
                        "playersByLeague": self.players_by_league
                }
            }
        )

    @sync_to_async
    def async_get_previus_seasons(self):
        prev_seasons = Season.objects.filter(is_finished=True).order_by(
            '-number')[:2].prefetch_related('tournament_set')
        seasons_data = {}
        tour_cnt = {}
        for prev_season in prev_seasons:
            tour_cnt[str(prev_season.number)] = len(
                prev_season.tournament_set.all())
            seasons_data[str(prev_season.number)] = {
                'tournamentsCount': tour_cnt[str(prev_season.number)],
                'winner': prev_season.winner.name if prev_season.winner else None
            }
        return seasons_data

    @sync_to_async
    def async_get_players_by_league(self):
        players_gmaster = len(Player.objects.filter(league=7))
        players_master = len(Player.objects.filter(league=6))
        players_diamond = len(Player.objects.filter(league=5))
        return {'7': players_gmaster, '6': players_master, '5': players_diamond}

    def group_update_handler(self, instance, **kwargs):
        channel_layer = get_channel_layer()
        season = Season.objects.get(is_finished=False)
        if (season.start_datetime - timezone.now()).total_seconds() > 0 and season.can_register:
            async_to_sync(channel_layer.group_send)(
                f'groups_{self.group_id}',
                {
                    'type': 'send_groups',
                    'text': {
                        'state': 1,
                        'season': season.number,
                        "previusSeasons": self.previus_seasons,
                        "playersByLeague": self.players_by_league
                    }
                }
            )
            async_to_sync(post_save.connect)(
                self.wait_for_season, sender=Season)
        elif (season.start_datetime - timezone.now()).total_seconds() > 0:
            async_to_sync(channel_layer.group_send)(
                f'groups_{self.group_id}',
                {
                    'type': 'send_groups',
                    'text': {
                        'state': 0,
                        "previusSeasons": self.previus_seasons,
                        "playersByLeague": self.players_by_league
                    }
                }
            )
        else:
            groups = GroupStage.objects.filter(season=season)
            tournaments_in_group = Tournament.objects.filter(
                season=season, group__isnull=False)
            wins = {}
            playoff_data = {}
            for tournament in tournaments_in_group:
                if tournament.winner:
                    wins[tournament.winner.pk] = wins.get(
                        tournament.winner.pk, 0) + 1
            max_stage = Tournament.objects.filter(
                season=season, group__isnull=True).aggregate(Max('stage'))['stage__max']
            stages = {}
            if (max_stage):
                for stage in range(1, max_stage + 1):
                    tournaments = Tournament.objects.filter(
                        season=season, group__isnull=True, stage=stage).order_by('inline_number')
                    for tournament in tournaments:
                        matches = Match.objects.filter(tournament=tournament)
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
            if groups_data:
                async_to_sync(channel_layer.group_send)(
                    f'groups_{self.group_id}',
                    {
                        'type': 'send_groups',
                        'text': {
                            "state": 2,
                            "startedSeason": {
                                "groups": groups_data,
                                "playoff": playoff_data
                            },
                            "season": season.number,
                            "previusSeasons": self.previus_seasons,
                            "playersByLeague": self.players_by_league
                        }
                    }
                )
            else:
                async_to_sync(channel_layer.group_send)(
                    f'groups_{self.group_id}',
                    {
                        'type': 'send_groups',
                        'text': {
                            "state": 0,
                            "previusSeasons": self.previus_seasons,
                            "playersByLeague": self.players_by_league
                        }
                    }
                )

    async def send_groups(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'], ensure_ascii=False)
        })

    async def websocket_disconnect(self, event):
        await self.channel_layer.group_discard(
            f'groups_{self.group_id}',
            self.channel_name
        )
        raise StopConsumer()

    async def websocket_receive(self, event):
        await self.send({
            'type': 'websocket.close'
        })
        raise StopConsumer()
