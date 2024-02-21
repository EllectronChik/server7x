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

# Django imports
from django.conf import settings
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError, FieldDoesNotExist

# Importing models, serializers, and utilities
from main.models import Tournament, Match, Player, Manager, Season, Team, GroupStage
from main.serializers import MatchesSerializer, TeamsSerializer, PlayerToTournament
from main.utils import get_season_data

# Load environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


class MatchConsumer(AsyncConsumer):
    """
    WebSocket consumer for handling match-related operations.

    This consumer manages WebSocket connections for handling match-related actions such as subscribing to matches,
    updating match details, creating new matches, and deleting matches.

    Attributes:
        is_first_message_received (bool): Flag to track if the first message is received.
        timeout_task (asyncio.Task): Task for handling timeout.
        group_name (str): Name of the group associated with the WebSocket connection.
        user (User): User associated with the WebSocket connection.
        is_admin_user (bool): Flag to indicate if the user is an admin user.
    """
    async def websocket_connect(self, event):
        """
        Handles WebSocket connection events.

        Args:
            event (dict): The WebSocket connection event.

        Returns:
            None
        """
        # Accept the WebSocket connection
        await self.send({
            'type': 'websocket.accept'
        })

        # Initialize flags and variables
        # Flag to track if the first message is received
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(
            self.timeout_handler())  # Task for handling timeout
        self.group_name = None  # Name of the group associated with the WebSocket connection
        self.user = None  # User associated with the WebSocket connection
        self.is_admin_user = False  # Flag to indicate if the user is an admin user

    async def websocket_receive(self, event):
        """
        Handles receiving messages over the websocket connection.

        This function is responsible for processing incoming messages received over the WebSocket connection.
        It decodes the JSON data, performs various actions based on the received data, and responds accordingly.

        Args:
            event (dict): The event dictionary containing information about the received message.

        Returns:
            None
        """
        # Check if this is the first message received
        if (not self.is_first_message_received):
            # Mark that the first message has been received
            self.is_first_message_received = True
            try:
                # Try to parse the incoming message as JSON
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If parsing fails, close the websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                # Extract token and action from the received data
                token = data['token']
                action = data['action']
                if action == 'subscribe':
                    # Extract group name if provided
                    self.group_name = data.get('group')
                    try:
                        # Query matches for the specified tournament asynchronously
                        match_objects = await sync_to_async(Match.objects.filter)(tournament=self.group_name)
                        # Serialize match objects
                        matches_data = await sync_to_async(lambda: MatchesSerializer(match_objects, many=True).data)()
                        # Send serialized matches data through websocket
                        await self.send({
                            'type': 'websocket.send',
                            'text': json.dumps(matches_data)
                        })
                    except Match.DoesNotExist:
                        # If no matches found for the given tournament, close websocket connection and stop the consumer
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()
                    if self.group_name:
                        # Add the consumer to a group corresponding to the tournament
                        await self.channel_layer.group_add(
                            f'match_{self.group_name}', self.channel_name
                        )
                else:
                    # If action is not 'subscribe', close the websocket connection and stop the consumer
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
            except json.JSONDecodeError:
                # If any JSON decoding error occurs, close the websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            except KeyError:
                # If any required key is missing in the received data, close the websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                # Retrieve user token object asynchronously
                token_obj = await sync_to_async(Token.objects.get)(key=token)
            except Token.DoesNotExist:
                # If the token does not exist, close the websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            # Retrieve user associated with the token
            self.user = await sync_to_async(lambda: token_obj.user)()
            # Check if the user is an admin
            self.is_admin_user = await sync_to_async(lambda: self.user.is_staff)()
            # Connect a signal handler for match updates
            post_save.connect(self.match_update_handler, sender=Match)
        else:
            try:
                # Try to parse the incoming message as JSON
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If parsing fails, close the websocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                # Extract action from the received data
                action = data['action']
                if action == 'update':
                    try:
                        # Extract required fields for updating a match
                        updated_field = data['updated_field']
                    except Match.DoesNotExist:
                        # If match does not exist, send an empty response
                        await self.send({
                            'type': 'websocket.send',
                            'text': json.dumps({})
                        })
                    # Extract other fields for match update
                    updated_column = data['updated_column']
                    updated_value = data['updated_value']
                    if updated_column == 'winner':
                        # If the updated column is 'winner', update the score
                        await self.update_score(updated_value, updated_field)
                    # Update match with the provided data
                    await self.match_patch(updated_field, updated_column, updated_value)
                elif action == 'create':
                    # Create a new match
                    await self.match_create(event)
                elif action == 'delete':
                    # Delete a match
                    match_pk = data['match_pk']
                    await self.match_delete(match_pk)
                else:
                    # No action specified, do nothing
                    pass
            except json.JSONDecodeError:
                # If any JSON decoding error occurs, send an empty response
                await self.send({
                    'type': 'websocket.send',
                    'text': json.dumps({})
                })

    async def timeout_handler(self):
        """
        Handle timeout for WebSocket authentication.

        This function is responsible for handling the timeout period for WebSocket authentication.
        If the first message is not received within the specified duration, it closes the WebSocket connection
        and halts further processing by raising a StopConsumer exception.

        Args:
            self: The WebSocketConsumer instance.

        Returns:
            None
        """
        try:
            # Wait for the specified duration for the first message to be received
            await asyncio.sleep(int(env('WEBSOCKET_AUTH_TIMEOUT')))

            # If the first message has not been received, close the WebSocket connection
            # and raise StopConsumer to halt further processing
            if not self.is_first_message_received:
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        except asyncio.CancelledError:
            # Handle cancellation if the task is cancelled before the timeout
            pass

    async def websocket_disconnect(self, event):
        """
        Handle WebSocket disconnection.

        This function is called when a WebSocket disconnection event occurs.
        It cancels the timeout task if it exists, removes the channel from the group,
        sends a close message to the client, and stops the consumer.

        Args:
            self: The WebSocketConsumer instance.
            event: The event triggering the disconnection.

        Returns:
            None
        """
        # Cancel the timeout task if it exists
        if self.timeout_task:
            self.timeout_task.cancel()

        # Remove the channel from the group
        await self.channel_layer.group_discard(
            # Group name corresponding to the WebSocket connection
            f'match_{self.group_name}',
            self.channel_name  # Channel name to remove from the group
        )

        # Send a close message to the client
        await self.send({
            'type': 'websocket.close',  # Type of message to send for closing WebSocket connection
        })

        # Stop the consumer, indicating that it should no longer handle incoming messages
        raise StopConsumer()  # Raise StopConsumer to stop the consumer loop

    async def match_patch(self, field, column, data):
        """
        Patch a match object with new data asynchronously.

        This function retrieves a Match object asynchronously and updates it based on the provided field, column, and data.
        Depending on the column, it may update winner, player_one, player_two, or any other attribute of the Match object.

        Args:
            self: The instance of the class calling the method.
            field: The ID of the Match object to be updated.
            column: The column/attribute of the Match object to be updated.
            data: The new data to be assigned to the specified column.

        Returns:
            None
        """
        # Retrieve the Match object asynchronously
        obj = await sync_to_async(Match.objects.get)(id=field)

        # Retrieve winner information asynchronously
        match_winner = await sync_to_async(lambda: obj.winner)()

        # Retrieve old player one and player two asynchronously
        old_player_one = await sync_to_async(lambda: obj.player_one)()
        old_player_two = await sync_to_async(lambda: obj.player_two)()

        # Update logic based on the provided column
        if column == 'winner':
            # Retrieve the winner object asynchronously
            winner = await sync_to_async(Player.objects.get)(pk=data)

            # Update winner and match_winner wins count if necessary
            if (match_winner is not None and match_winner != winner):
                match_winner.wins -= 1
                await sync_to_async(match_winner.save)()
            if (winner is not None and winner != match_winner):
                winner.wins += 1
                await sync_to_async(winner.save)()

            # Update the match object with the new winner
            obj.winner = winner
        elif column == 'player_one':
            # Retrieve the player object asynchronously
            player = await sync_to_async(Player.objects.get)(pk=data)

            # Update total_games count for old_player_one and player if necessary
            if (old_player_one is not None and old_player_one != player):
                old_player_one.total_games -= 1
                await sync_to_async(old_player_one.save)()
            if (player is not None and player != old_player_one):
                player.total_games += 1
                await sync_to_async(player.save)()

            # Update winner of the match if old_player_one is the match_winner
            if match_winner == old_player_one and old_player_one is not None:
                obj.winner = player

            # Update the match object with the new player_one
            obj.player_one = player
        elif column == 'player_two':
            # Retrieve the player object asynchronously
            player = await sync_to_async(Player.objects.get)(pk=data)

            # Update total_games count for old_player_two and player if necessary
            if (old_player_two is not None and old_player_two != player):
                old_player_two.total_games -= 1
                await sync_to_async(old_player_two.save)()
            if (player is not None and player != old_player_two):
                player.total_games += 1
                await sync_to_async(player.save)()

            # Update winner of the match if old_player_two is the match_winner
            if match_winner == old_player_two and old_player_two is not None:
                obj.winner = player

            # Update the match object with the new player_two
            obj.player_two = player
        else:
            # For any other column, simply update the match object attribute
            setattr(obj, column, data)

        # Save the updated match object asynchronously
        await sync_to_async(obj.save)()

    async def match_create(self, event):
        """
        Create a new match asynchronously.

        This function creates a new match object for a tournament asynchronously and saves it to the database.

        Args:
            event: The event containing information about the match creation.

        Returns:
            None
        """
        # Retrieve the tournament object asynchronously
        tournament = await sync_to_async(Tournament.objects.get)(pk=self.group_name)

        # Create a new match asynchronously
        await sync_to_async(Match.objects.create)(
            tournament=tournament,
            user=self.user,
        )

    async def match_delete(self, match_pk):
        """
        Delete a match asynchronously.

        This function deletes a match object from the database asynchronously. If the user is an admin,
        it retrieves the match object, deletes it, retrieves all matches for the tournament, and sends
        a WebSocket message with updated match information.

        Args:
            match_pk: The primary key of the match to be deleted.

        Returns:
            None
        """
        # Check if the user is an admin
        if (self.is_admin_user):
            # Retrieve the match object asynchronously
            match = await sync_to_async(Match.objects.get)(pk=match_pk)

            # Delete the match asynchronously
            await sync_to_async(match.delete)()

            # Retrieve all matches for the tournament asynchronously
            matches = await sync_to_async(Match.objects.filter)(tournament=match.tournament)

            # Send WebSocket message with updated match information
            await self.send({
                'type': 'websocket.send',
                'text': json.dumps(matches)
            })

    async def update_score(self, winner, field):
        """
        Update tournament scores based on match results.

        This function updates the scores of teams participating in a tournament based on the outcome of a match.

        Args:
            self: The instance of the class.
            winner (int): The primary key of the winning player.
            field (int): The primary key of the match.

        Returns:
            None
        """
        # Check if there is a winner
        if winner:
            # Retrieve the player object asynchronously
            player = await sync_to_async(Player.objects.get)(pk=winner)

            # Retrieve the match object asynchronously
            match = await sync_to_async(Match.objects.get)(pk=field)

            # Retrieve the winner of the match
            match_winner = await sync_to_async(lambda: match.winner)()

            # Retrieve the team of the player
            team = await sync_to_async(lambda: player.team)()

            # Retrieve the tournament object asynchronously
            tournament = await sync_to_async(Tournament.objects.get)(pk=self.group_name)

            # Retrieve the teams participating in the tournament asynchronously
            team_one = await sync_to_async(lambda: tournament.team_one)()
            team_two = await sync_to_async(lambda: tournament.team_two)()

            # Update the tournament's team wins based on the winner of the match
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

            # Save the tournament asynchronously
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

        # If the instance is of type Match, retrieve all matches for the associated tournament.
        if type(instance) == Match:
            matches = Match.objects.filter(tournament=instance.tournament)
            matches_data = MatchesSerializer(matches, many=True).data

        # Send the updated match list to the corresponding group.
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
                    if obj_inline is not None:
                        paired_number = obj_inline + 1 if obj_inline % 2 == 0 else obj_inline - 1
                        paired_tournament = await sync_to_async(lambda: Tournament.objects.get(inline_number=paired_number, stage=obj.stage, season=obj.season))()
                        if paired_tournament:
                            paired_tournament_winner = await sync_to_async(lambda: paired_tournament.winner)()
                        else:
                            paired_tournament_winner = None
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
            groups_data, playoff_data = get_season_data(season.number)
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
