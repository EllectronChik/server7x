from channels.consumer import AsyncConsumer
from channels.exceptions import StopConsumer
from rest_framework.authtoken.models import Token
from asgiref.sync import sync_to_async, async_to_sync
import asyncio
import json
import environ
import os
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
from main.models import Tournament, Match, Player
from channels.layers import get_channel_layer
from main.serializers import MatchesSerializer
from functools import partial


env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class ScoreConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())


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
                    group_name = data.get('group')
                    try:
                        obj = await sync_to_async(Tournament.objects.get)(pk=group_name)
                    except Tournament.DoesNotExist:
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()
                    if group_name:
                        await self.channel_layer.group_add(
                            f'tournament_{group_name}', self.channel_name
                        )
                        await self.send({
                            'type': 'websocket.send',
                            'text': json.dumps({
                                'team_one_wins': obj.team_one_wins,
                                'team_two_wins': obj.team_two_wins
                            })
                        })
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
            post_save.connect(self.tournament_update_handler, sender=Tournament)


    async def websocket_disconnect(self, event):
        if not self.is_first_message_received:
            await self.send({
                'type': 'websocket.close',
            })
            raise StopConsumer()
        if self.timeout_task:
            self.timeout_task.cancel()

    
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

    @staticmethod
    def tournament_update_handler(instance, **kwargs):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"tournament_{instance.id}",
            {   
                "type": "tournament_update",
                "team_one_wins": instance.team_one_wins,
                "team_two_wins": instance.team_two_wins
            }
        )

    async def tournament_update(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps({
                'team_one_wins': event['team_one_wins'],
                'team_two_wins': event['team_two_wins']
            })
        })


class MatchConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_id = None
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
                        self.group_id = self.group_name
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
                    await self.match_patch(updated_field, updated_column, updated_value)
                    if updated_column == 'winner':
                        await self.update_score(updated_value)
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
        if not self.is_first_message_received:
            await self.send({
                'type': 'websocket.close',
            })
            raise StopConsumer()
        if self.timeout_task:
            self.timeout_task.cancel()


    async def match_patch(self, field, column, data):
        obj = await sync_to_async(Match.objects.get)(id=field)
        if column == 'winner':
            winner = await sync_to_async(Player.objects.get)(pk=data)
            obj.winner = winner
        else:
            setattr(obj, column, data)            
        await sync_to_async(obj.save)()


    async def update_score(self, winner):
        if winner:
            player = await sync_to_async(Player.objects.get)(pk=winner)
            team = await sync_to_async(lambda: player.team)()
            tournament = await sync_to_async(Tournament.objects.get)(pk=self.group_id)
            team_one = await sync_to_async(lambda: tournament.team_one)()
            team_two = await sync_to_async(lambda: tournament.team_two)()
            if team_one == team:
                tournament.team_one_wins += 1
            elif team_two == team:
                tournament.team_two_wins += 1
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
        async_to_sync(channel_layer.group_send)(
            f"match_{instance.tournament.id}",
            {   
                "type": "new_match_list",
                "text": [matches_data]
            }
        )

    async def new_match_list(self, event):
        await self.send({
            'type': 'websocket.send',
            'text': json.dumps(event['text'])
        })