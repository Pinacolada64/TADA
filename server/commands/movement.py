# movement
import logging
from abc import ABC
from typing import T, List

from net_common import Message, MessageType, K
from commands.help import BaseHelpText, HelpCategory
from commands.base_command import Command, CommandResult

# Fallback compass text mapping
compass_txts = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west', 'u': 'up', 'd': 'down'}


class MovementCommand(Command, ABC):
    """Handles player movement commands."""

    def __init__(self, context: T = None):
        super().__init__(context)
        # client manager needed for broadcasting messages to other players in the room
        # and for updating player locations in rooms
        data = context if context else {}
        self.writer = data.get('writer')
        self.client_manager = None

    @property
    def name(self) -> str:
        return 'move'

    @property
    def aliases(self) -> list:
        return ['n', 's', 'e', 'w', 'u', 'd',
                'go north', 'go south', 'go east', 'go west',
                'go up', 'go down']

    async def _execute(self, params: list[str], data: dict) -> CommandResult:
        """Execute the movement command.

        :param data: Dictionary containing command data
        :return: CommandResult instance with the result of the command
        """
        cmd = data.get('cmd')
        player = data.get('player')
        game_map = data.get('game_map')
        writer = data.get('writer')
        client_manager = data.get('client_manager')

        if not cmd or not player or not game_map or not writer or not client_manager:
            return CommandResult(
                success=False,
                error='missing_data',
                message='Missing required data for movement command.'
            )

        try:
            message = await self.move_command(self, args, player, game_map)
            return CommandResult(
                success=True,
                message=message.lines if isinstance(message.lines, str) else '\n'.join(message.lines),
                data={'changes': message.changes}
            )
        except Exception as e:
            logging.exception("Error executing movement command: %s", e)
            return CommandResult(
                success=False,
                error='command_error',
                message=f"Error executing command {self.name}: {str(e)}"
            )

    async def move_command(self, args: list, player, game_map) -> Message:
        """
        Handle player movement commands.

        :param self: CommandHandler instance
        :param args: List of command words (e.g., ['n'], ['go', 'north'])
        :param player: Player instance
        :param game_map: GameMap instance
        :return: Message instance with the result of the command
        """
        logging.debug("movement command: %s" % args)
        logging.debug("player location: %s" % player.room)
        logging.debug("exits: %s" % game_map.rooms[player.room].exits)
        if args in compass_txts:
            room = game_map.rooms[player.room]
            logging.debug("parser: current room #: %s" % player.room)
            direction = arg[0]
            logging.debug("parser: direction: %s" % direction)
            # 'rooms' is a list of Room objects?
            logging.debug("parser: exits: %s" % room.exits)
            """
            >>> exits = {'n': 1, 's': 3}
        
            >>> exits.keys()
            dict_keys(['n', 's'])
            >>> exits['n']
            1
            """
            # json data (dict):
            # check if 'direction' is in room exits
            if direction in room.exits:  # rooms[player.room].exits.keys():
                logging.debug("move %s => %s" % (direction, player.room))
                # delete player from list of players in current room, then
                # add player to list of players in room they moved to
                self.client_manager.remove_player_from_room(player.id, player.room)
                player.move(destination_room=room.exits[direction], direction=direction)
                self.client_manager.add_player_to_room(player.id, player.room)
                # update player.room to new room number
                logging.debug("parser: new room #: %s" % player.room)
                # player.room = room.exits[direction]
                logging.debug("parser: moved %s to room %s" % (player.name, player.room))
                # get new room desc:
                # player.move(room.exits[direction], direction)
                room_name = game_map.rooms[player.room].name
                message = Message(lines=[f"You move {compass_txts[direction]}."],
                                  type=MessageType.REGULAR)
                await end_message(self.writer, message=message,
                                     changes={K.room_name: room_name,
                                              K.room: game_map.rooms[player.room].desc})
                # tell other players in the room that player has entered
                self.client_manager.players_in_room(
                    Message(lines=f"{player.name} enters.",
                            type=MessageType.ANNOUNCEMENT),
                    room=player.room,
                    exclude=[player.id]
                )

        """
        This is the way the original Apple code handled up/down exits.
        I'm fully aware up/down exits could just be a room number, or 0
        for no connection--my self-written level 8 map does exactly this.
        """
        if cmd[0][:1] == 'u' or cmd[0][:1] == 'd':
            room = game_map.rooms[player.room]
            room_exits = room.exits
            room_connection = room_exits.get('rc', 0)
            room_transport = room_exits.get('rt', 0)
            # example: level 1, room 20
            if cmd[0] == 'u' and room_connection == 1:
                if room_transport != 0:
                    logging.debug("parser: %s moves Up to %i" % (player.id, room_transport))
                    # player.room = room_transport
                    player.move(destination_room=room_transport, direction='u')
                    return Message(lines=["You move up."],
                                   changes={K.room_name: room.name,
                                            K.room: room.desc}
                                   )
                else:
                    logging.debug("parser: %s moves Up to Shoppe" % player.name)
                    player.move(destination_room=room_transport, direction='u')
                    # don't change player.room, return them to where they left
                    return Message(lines=["TODO: write Shoppe routine..."])
            if cmd[0] == 'd' and room_connection == 2:
                if room_transport != 0:
                    logging.debug("parser: %s moves Down to %i" % (player.name, room_transport))
                    player.move(destination_room=room_transport, direction='d')

                    # get new room desc:
                    # FIXME: TypeError: 'Room' object is not subscriptable
                    """
                    temp = game_map.rooms[number]
                    logging.info(f"room info: {temp}")
                    desc = temp["desc"]
                    logging.info(f"desc: {desc}")
                    """
                    # FIXME: see server.py, line 24:
                    #  thought maybe this would show the new room desc
                    return Message(lines=["You move down."],
                                   changes={K.room_name: room.name,
                                            K.room: room.desc}
                                   )
                else:
                    logging.debug("parser: %s moves Down to Shoppe" % player.name)
                    player.move(destination_room=room_transport, direction='d')

                    # don't change player.room, return them to where they left
                    message = Message(lines=["TODO: write Shoppe routine..."])
                    # return the placeholder message
                    return message

            else:
                return Message(lines=["Ye cannot travel that way."])
        return None


class MoveHelp(BaseHelpText):
    name = "movement"
    aliases = ["move"]

    def __init__(self, context=None):
        super().__init__()
        self.category = HelpCategory.MOVEMENT
        self.summary = "Move in compass directions"
        self.usage = [("n/s/e/w/u/d", "Move in a direction")]
        self.examples = [
            ("n", "Move north if there is an exit in that direction."),
            ("go east", "Move east if there is an exit in that direction."),
            ("help move", "Show help for the 'move' command"),
        ]
        self.notes = [
            "You can use either 'help' or '?' to access help.",
            "Command names are case-insensitive.",
            "Some commands may have aliases (shown in parentheses)."
        ]
