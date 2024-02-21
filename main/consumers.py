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
        """
        Handle match update event and send updated match list to clients.

        This static method handles the match update event and sends the updated match list to clients
        who are subscribed to the corresponding group.

        Args:
            instance: The instance of the match being updated.
            kwargs: Additional keyword arguments.

        Returns:
            None
        """
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
    """
    WebSocket consumer for handling tournament status updates.

    This class handles WebSocket connections, incoming messages, and disconnections related to
    tournament status updates. It provides functionality for subscribing to tournaments,
    updating tournament status, and managing WebSocket timeouts.

    Attributes:
        is_first_message_received (bool): Flag indicating whether the first message has been received.
        timeout_task (asyncio.Task): Task for handling WebSocket timeout.
        group_name (str): Name of the group associated with the WebSocket connection.
        user (User): User associated with the WebSocket connection.
    """

    async def websocket_connect(self, event):
        """
        Handles WebSocket connection events.

        Args:
            event (dict): The WebSocket connection event.

        Returns:
            None
        """
        await self.send({
            'type': 'websocket.accept'
        })
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None
        self.user = None

    async def websocket_receive(self, event):
        """
        Handle incoming WebSocket messages.

        This method is called whenever a WebSocket message is received.
        It processes the incoming message and takes appropriate actions.

        Args:
            event (dict): The WebSocket event containing the message.

        Returns:
            None
        """

        if not self.is_first_message_received:
            # Check if this is the first message received
            self.is_first_message_received = True
            try:
                # Attempt to parse the JSON data from the message
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If JSON decoding fails, close the WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()

            try:
                # Extract token from the data
                token = data['token']
                # Extract optional group name from the data
                self.group_name = data.get('group')
                try:
                    # Retrieve user associated with the token
                    token_obj = await sync_to_async(Token.objects.get)(key=token)
                except Token.DoesNotExist:
                    # If token is not valid, close the WebSocket connection
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()

                # Extract action from the data
                action = data['action']
                if action == 'subscribe':
                    try:
                        # Retrieve user and associated manager
                        user = await sync_to_async(lambda: token_obj.user)()
                        user_id = await sync_to_async(lambda: user.id)()
                        manager = await sync_to_async(Manager.objects.get)(user=user)
                        team = await sync_to_async(lambda: manager.team)()
                        # Retrieve tournaments associated with the team
                        tournaments = await sync_to_async(Tournament.objects.filter)(
                            Q(team_one=team) | Q(team_two=team)
                        )
                        if self.group_name:
                            if self.group_name == user_id:
                                # Add consumer to manager's group
                                await self.channel_layer.group_add(
                                    f'manager_{self.group_name}', self.channel_name
                                )
                            else:
                                # If group name is specified and doesn't match user id, close connection
                                await self.send({
                                    'type': 'websocket.close',
                                })
                                raise StopConsumer()
                        # Update tournaments for the manager
                        await sync_to_async(self.tournament_update_handler)(
                            manager_id=self.group_name, instance=tournaments
                        )
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
                    # If action is not 'subscribe', close the WebSocket connection
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
            except (json.JSONDecodeError, KeyError):
                # If required keys are missing or JSON decoding fails, close the WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()

            # Set the user associated with the token
            self.user = await sync_to_async(lambda: token_obj.user)()
            # Connect the tournament update handler
            post_save.connect(self.tournament_update_handler, sender=Tournament)
        else:
            try:
                # Attempt to parse the JSON data from the message
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If JSON decoding fails, close the WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()

            try:
                # Extract action and tournament id from the data
                action = data['action']
                tournament_id = data['id']
                if action == 'start_now':
                    # If action is 'start_now', update the start time of the tournament
                    obj = await sync_to_async(Tournament.objects.get)(pk=tournament_id)
                    is_tournament_started = await sync_to_async(lambda: obj.match_start_time.replace(tzinfo=timezone.utc) < datetime.datetime.utcnow().replace(tzinfo=timezone.utc))()
                    if not is_tournament_started:
                        obj.match_start_time = datetime.datetime.utcnow()
                        await sync_to_async(obj.save)()
                elif action == 'finish':
                    # If action is 'finish', handle finishing the tournament
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
                        # If tournament is finished, update winner and proceed to next stage if applicable
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
                            # If paired tournament winner and current tournament winner are both available, create next stage tournament
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
                        # If tournament is not finished, mark it as asking for finish
                        obj.ask_for_finished = True
                        obj.asked_team = team
                    await sync_to_async(obj.save)()
            except KeyError:
                # If required keys are missing, close the WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()

    async def websocket_disconnect(self, event):
        """
        Handle WebSocket disconnection event.

        This method is called when a WebSocket connection is disconnected.
        It cancels any ongoing timeout task, removes the consumer from
        the corresponding group, sends a WebSocket close message, and
        stops the consumer.

        Args:
            event (dict): The disconnection event.

        Returns:
            None
        """
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
        """
        Handle WebSocket timeout.

        This method handles WebSocket timeout by waiting for a specified
        duration. If the first message is not received within this duration,
        it sends a WebSocket close message and stops the consumer.

        Returns:
            None
        """
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
        """
        Handle tournament update event and send updated tournament list to clients.

        This method handles the tournament update event and sends the updated tournament list to clients
        who are subscribed to the corresponding group.

        Args:
            self: The instance of the class.
            instance: The instance of the tournament being updated.
            **kwargs: Additional keyword arguments.

        Returns:
            None
        """

        # Get the channel layer
        channel_layer = get_channel_layer()

        # Get the user associated with the group
        user = User.objects.get(pk=self.group_name)

        # Get the current season that is not finished
        season = Season.objects.get(is_finished=False)

        # Get the manager associated with the user
        manager = Manager.objects.get(user=user)

        # Get the team associated with the manager
        team = manager.team

        # Get tournaments involving the team in the current season
        tournaments = Tournament.objects.filter(
            Q(team_one=team) | Q(team_two=team), season=season)

        # If no tournaments found, send empty list to client
        if tournaments.count() == 0:
            async_to_sync(channel_layer.group_send)(
                f'manager_{self.group_name}',
                {
                    'type': 'send_tournaments',
                    'text': json.dumps([])
                }
            )

        # Order tournaments by match start time
        tournaments = tournaments.order_by('match_start_time')

        # Prepare response data to send to clients
        response_data = []
        for tournament in tournaments:
            # Determine opponent team and team number
            opponent = tournament.team_two if tournament.team_one == team else tournament.team_one
            team_in_tour_num = 1 if tournament.team_one == team else 2

            # Serialize opponent team data
            opponent_data = TeamsSerializer(opponent).data

            # Get players of opponent team participating in the tournament
            opp_players_to_tournament = PlayerToTournament.objects.filter(
                user=opponent.user, Season=season)
            opp_players_to_tournament_data = []
            for player in opp_players_to_tournament:
                opp_players_to_tournament_data.append({
                    'id': player.player.id,
                    'username': player.player.username
                })
            opponent_data['players'] = opp_players_to_tournament_data

            # Determine if the team has been asked for finishing the tournament
            asked_team = True if tournament.asked_team == team else False if tournament.ask_for_finished else None

            # Determine winner if the tournament is finished
            winner = tournament.winner.id if tournament.winner is not None else None

            # Prepare data for tournaments
            if not tournament.is_finished:
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
                # If tournament is finished, include match data
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

        # Send tournament data to clients
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
    """
    Handle WebSocket connections and events for admin users.

    This class implements methods to handle WebSocket connections, receive events from clients,
    and manage WebSocket disconnections for admin users.

    Attributes:
        is_first_message_received (bool): Flag to track if the first message is received.
        timeout_task (asyncio.Task): Task for handling authentication timeout.
        group_name (str): Name of the group associated with the admin user.
    """
    async def websocket_connect(self, event):
        """
        Handle WebSocket connection event.

        This method is called when a WebSocket connection is established. It accepts the connection,
        initializes necessary variables, and starts a timeout handler.

        Args:
            event: The WebSocket connection event.

        Returns:
            None
        """
        # Accept the WebSocket connection
        await self.send({
            'type': 'websocket.accept'
        })

        # Initialize flag to track if the first message is received
        self.is_first_message_received = False
        
        # Start a task for timeout handling
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        
        # Initialize variable for storing group name
        self.group_name = None


    async def websocket_receive(self, event):
        """
        Receives websocket events and handles them accordingly.

        This method receives websocket events and performs actions based on the event data,
        such as subscribing users to a group, updating tournament details, setting winners,
        or creating new tournaments.

        Args:
            event (dict): The websocket event containing data sent by the client.

        Returns:
            None
        """
        if not self.is_first_message_received:
            # If this is the first message received, perform initial setup
            self.is_first_message_received = True
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If JSON decoding fails, close the websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                token = data['token']
                self.group_name = data.get('group')
                try:
                    # Attempt to retrieve user token object asynchronously
                    token_obj = await sync_to_async(Token.objects.get)(key=token)
                except Token.DoesNotExist:
                    # If token does not exist, close websocket connection and stop the consumer
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
                action = data['action']
                if action == 'subscribe':
                    try:
                        # Subscribe user to appropriate group and handle tournament updates
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
                        # If any error occurs during subscription, close websocket connection and stop the consumer
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()

            except KeyError:
                # If required keys are not found in received data, close websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
        else:
            try:
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If JSON decoding fails, close websocket connection and stop the consumer
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            if data['action'] == 'set_winner':
                # Handle setting winner action
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
                # Handle tournament update action
                tournament_id = data['tournament_id']
                field = data['field']
                value = data['value']
                if field == 'is_finished':
                    try:
                        # Handle updating 'is_finished' field of the tournament
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
                        # Handle updating 'winner' field of the tournament
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
                            if paired_number is not None:
                                paired_tournament = await sync_to_async(lambda: Tournament.objects.get(
                                    inline_number=paired_number, stage=tournament.stage, season=tournament.season))()
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
                            if paired_tournament_winner is not None and next_stage_tournament is None:
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
                            if next_stage_tournament is not None:
                                next_stage_tournament_team_one = await sync_to_async(lambda: next_stage_tournament.team_one)()
                                if next_stage_tournament_team_one == paired_tournament_winner:
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
                        # Handle updating 'team_two' field of the tournament
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
                        # Handle updating 'team_one' field of the tournament
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
                        # Handle updating other fields of the tournament
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
                    # Handle creating a new tournament
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
        """
        Handles WebSocket disconnection event.

        This method cancels any timeout task, removes the consumer from the admin group,
        sends a close message to the client, and stops the consumer.

        Args:
            event (dict): The disconnect event.

        Returns:
            None
        """
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
        """
        Timeout handler for WebSocket authentication.

        This method asynchronously sleeps for a specified timeout duration and closes the WebSocket
        connection if the first message is not received within the timeout period.

        Returns:
            None
        """
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
        """
        Handle tournament update event and send updated tournament list to clients.

        This method is responsible for handling the tournament update event and sending the updated
        tournament list to clients subscribed to the corresponding group.

        Args:
            instance: The instance of the tournament being updated.
            kwargs: Additional keyword arguments.

        Returns:
            None
        """
        # Get the channel layer
        channel_layer = get_channel_layer()
        
        # Get the current ongoing season
        season = Season.objects.get(is_finished=False)
        
        # Get all tournaments associated with the current season
        tournaments = Tournament.objects.filter(season=season)
        
        # Initialize an empty list to store response data
        response_data = []
        
        # Iterate over each tournament
        for tournament in tournaments:
            # Get all matches associated with the tournament
            matches = Match.objects.filter(tournament=tournament)
            
            # Check if matches exist for the tournament
            if matches:
                matchesExists = True
            else:
                matchesExists = False
            
            # Prepare tournament data to be sent as response
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
            
            # Append tournament data to the response data list
            response_data.append(tournament_data)
        
        # Send the updated tournament data to the corresponding group of clients
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
    """
    WebSocket consumer for handling group interactions.

    This class implements methods for handling WebSocket connections, receiving and processing messages,
    disconnecting clients, and updating group information.

    Attributes:
        is_first_message_received (bool): Indicates if the first message has been received.
        timeout_task (asyncio.Task): Task for handling authentication timeout.
        group_name (str): Name of the group associated with the client.
        user: User object associated with the WebSocket connection.
        is_admin_user (bool): Indicates if the user is an admin.

    """
    async def websocket_connect(self, event):
        """
        Accepts a WebSocket connection and initializes necessary attributes.

        This method is called when a WebSocket connection is established.
        It accepts the connection, initializes necessary attributes, and starts a timeout handler task.

        Args:
            event: WebSocket connection event.

        Returns:
            None
        """
        await self.send({
            'type': 'websocket.accept'
        })
        # Initialize attributes
        self.is_first_message_received = False
        self.timeout_task = asyncio.create_task(self.timeout_handler())
        self.group_name = None
        self.user = None
        self.is_admin_user = False

    async def websocket_receive(self, event):
        """
        Receives and processes WebSocket messages.

        This method is called when a WebSocket message is received.
        It processes the message, performs necessary actions based on the message content,
        and handles errors gracefully.

        Args:
            event: WebSocket receive event.

        Returns:
            None
        """
        if (not self.is_first_message_received):
            self.is_first_message_received = True
            try:
                # Attempt to decode JSON data from the received message
                data = json.loads(event['text'])
            except json.JSONDecodeError:
                # If decoding fails, close the WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()
            try:
                # Extract token from the received data
                token = data['token']
                self.group_name = data.get('group')
                try:
                    # Retrieve token object asynchronously
                    token_obj = await sync_to_async(Token.objects.get)(key=token)
                except Token.DoesNotExist:
                    # If token does not exist, close the WebSocket connection
                    await self.send({
                        'type': 'websocket.close',
                    })
                    raise StopConsumer()
                action = data['action']
                if action == 'subscribe':
                    try:
                        # Retrieve user, check if admin, and fetch related data
                        user = await sync_to_async(lambda: token_obj.user)()
                        self.group_name = await sync_to_async(lambda: user.id)()
                        is_admin = await sync_to_async(lambda: user.is_staff)()
                        season = await sync_to_async(Season.objects.get)(is_finished=False)
                        tournaments = await sync_to_async(Tournament.objects.filter)(season=season)
                        if is_admin:
                            # If user is admin, add to group and update data
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
                            # If user is not admin, close WebSocket connection
                            await self.send({
                                'type': 'websocket.close',
                            })
                            raise StopConsumer()
                    except:
                        # Catch-all exception handler for any unexpected errors
                        await self.send({
                            'type': 'websocket.close',
                        })
                        raise StopConsumer()

            except KeyError:
                # If required keys are missing, close WebSocket connection
                await self.send({
                    'type': 'websocket.close',
                })
                raise StopConsumer()


    async def websocket_disconnect(self, event):
        """
        Handles disconnection of websocket clients.

        This method cancels the timeout task if it exists, removes the client from the group,
        sends a close signal to the client, and stops the consumer.

        Args:
            event (dict): Websocket disconnect event.

        Returns:
            None
        """
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
        """
        Handles the timeout for authentication.

        This method waits for the specified time for the first message from the client. If no
        message is received within the timeout period, it closes the websocket connection.

        Returns:
            None
        """
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
        """
        Handles updates to group information.

        This method retrieves information about active seasons, groups, tournaments, and team wins.
        It then formats this information and sends it to clients subscribed to the corresponding group.

        Args:
            instance: The instance of the match being updated.
            kwargs: Additional keyword arguments.

        Returns:
            None
        """
        # Importing necessary function to get channel layer
        channel_layer = get_channel_layer()
        
        # Getting the active season that is not finished
        season = Season.objects.get(is_finished=False)
        
        # Getting all group stages related to the active season
        groups = GroupStage.objects.filter(season=season)
        
        # Getting all tournaments related to the active season and having a group
        tournaments = Tournament.objects.filter(season=season, group__isnull=False)
        
        # Dictionary to store team wins
        wins = {}
        
        # Looping through tournaments to count wins for each team
        for tournament in tournaments:
            if tournament.winner:
                wins[tournament.winner.pk] = wins.get(tournament.winner.pk, 0) + 1
        
        # Dictionary to store groups data
        groups_data = {}
        
        # Looping through groups to collect teams data
        for group in groups:
            teams_data = {}
            # Looping through teams in each group
            for team in group.teams.all():
                # Storing team wins in teams_data
                teams_data[str(team.pk)] = wins.get(team.pk, 0)
            # Storing teams_data in groups_data
            groups_data[str(group.pk)] = teams_data
        
        # Checking if groups_data is not empty
        if groups_data:
            # Sending groups_data to the corresponding group channel
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
    """
    Handle WebSocket connections for providing information to clients.

    This consumer class manages WebSocket connections and sends relevant information to clients
    regarding previous seasons, current season status, tournaments, and player data.

    Attributes:
        group_id (str): Unique identifier for the WebSocket connection group.
        previus_seasons (dict): Information about previous seasons.
        players_by_league (dict): Player count by league.

    """
    async def websocket_connect(self, event):
        """
        Handle WebSocket connection event.

        This method is called when a WebSocket connection is established.
        It accepts the connection, adds the channel to a group, and initializes data.

        Args:
            event (dict): WebSocket connect event.

        Returns:
            None
        """
        # Generate a unique group ID for the connection
        self.group_id = uuid.uuid4().hex
        
        # Accept the WebSocket connection
        await self.send({
            'type': 'websocket.accept'
        })
        
        # Add the channel to a group using the generated group ID
        await self.channel_layer.group_add(
            f'groups_{self.group_id}',
            self.channel_name
        )
        
        # Initialize data: previus_seasons and players_by_league
        self.previus_seasons = await self.async_get_previus_seasons()
        self.players_by_league = await self.async_get_players_by_league()
        
        try:
            # Try to get the current season that is not finished
            season = await sync_to_async(Season.objects.get)(is_finished=False)
            
            try:
                # Try to get tournaments associated with the current season
                tournaments = await sync_to_async(Tournament.objects.filter)(season=season)
                
                # Update the group with tournament data
                await sync_to_async(self.group_update_handler)(instance=tournaments)
                
            except Tournament.DoesNotExist:
                pass
            except TypeError:
                pass
            
            # Connect the group_update_handler method to the post_save signal of the Tournament model
            post_save.connect(self.group_update_handler, sender=Tournament)
        
        except Season.DoesNotExist:
            # If no current season is found, send initial data to the client
            await self.send({
                'type': 'websocket.send',
                'text': json.dumps({
                    'state': 0,
                    "previusSeasons": self.previus_seasons,
                    "playersByLeague": self.players_by_league
                })
            })
            
            # Connect the wait_for_season method to the post_save signal of the Season model
            post_save.connect(self.wait_for_season, sender=Season)


    def wait_for_season(self, instance, **kwargs):
        """
        Handle waiting for the next season event.

        This method sends information about waiting for the next season to clients.

        Args:
            instance: The instance of the season.
            kwargs: Additional keyword arguments.

        Returns:
            None
        """
        # Get the channel layer
        channel_layer = get_channel_layer()
        # Send information to clients in the group
        async_to_sync(channel_layer.group_send)(
            f'groups_{self.group_id}',
            {
                'type': 'send_groups',
                'text': {
                    'state': 9,  # State indicating waiting for next season
                    "previusSeasons": self.previus_seasons,  # Previous seasons data
                    "playersByLeague": self.players_by_league  # Players by league data
                }
            }
        )

    @sync_to_async
    def async_get_previus_seasons(self):
        """
        Retrieve data about previous seasons asynchronously.

        This method retrieves data about the previous seasons from the database.

        Returns:
            dict: Dictionary containing information about previous seasons.
        """
        # Retrieve previous seasons from the database
        prev_seasons = Season.objects.filter(is_finished=True).order_by(
            '-number')[:2].prefetch_related('tournament_set')
        seasons_data = {}
        tour_cnt = {}
        for prev_season in prev_seasons:
            # Count tournaments for each previous season
            tour_cnt[str(prev_season.number)] = len(
                prev_season.tournament_set.all())
            # Prepare data for each previous season
            seasons_data[str(prev_season.number)] = {
                'tournamentsCount': tour_cnt[str(prev_season.number)],
                'winner': prev_season.winner.name if prev_season.winner else None
            }
        return seasons_data


    @sync_to_async
    def async_get_players_by_league(self):
        """
        Retrieve player count by league asynchronously.

        This method retrieves the count of players by league from the database.

        Returns:
            dict: Dictionary containing player counts by league.
        """
        players_gmaster = len(Player.objects.filter(league=7))
        players_master = len(Player.objects.filter(league=6))
        players_diamond = len(Player.objects.filter(league=5))
        return {'7': players_gmaster, '6': players_master, '5': players_diamond}

    def group_update_handler(self, instance, **kwargs):
        """
        Handle group update event.

        This method sends updated group information to clients based on the current state.

        Args:
            instance: The instance of the tournament.
            kwargs: Additional keyword arguments.

        Returns:
            None
        """
        # Get the channel layer
        channel_layer = get_channel_layer()
        
        # Get the current season
        season = Season.objects.get(is_finished=False)
        
        # If the season has not started yet and registration is open
        if (season.start_datetime - timezone.now()).total_seconds() > 0 and season.can_register:
            # Send the group information to clients
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
            # Wait for the season to start
            async_to_sync(post_save.connect)(
                self.wait_for_season, sender=Season)
        
        # If the season has not started yet but registration is closed
        elif (season.start_datetime - timezone.now()).total_seconds() > 0:
            # Send the group information to clients
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
        
        # If the season has started
        else:
            # Get season and playoff data
            groups_data, playoff_data = get_season_data(season.number)
            
            # If there is data available for the season and playoffs
            if groups_data:
                # Send the group information to clients
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
            # If there is no data available for the season and playoffs
            else:
                # Send the group information to clients
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
        """
        Handle WebSocket disconnect event.

        This method is called when a WebSocket connection is disconnected.

        Args:
            event (dict): WebSocket disconnect event.

        Returns:
            None
        """
        await self.channel_layer.group_discard(
            f'groups_{self.group_id}',
            self.channel_name
        )
        raise StopConsumer()

    async def websocket_receive(self, event):
        """
        Handle WebSocket receive event.

        This method is called when a WebSocket receives a message.
        It closes the WebSocket connection.

        Args:
            event (dict): WebSocket receive event.

        Returns:
            None
        """
        await self.send({
            'type': 'websocket.close'
        })
        raise StopConsumer()
