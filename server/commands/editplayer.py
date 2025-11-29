from typing import Dict, Any, List, Optional
import logging
import asyncio
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice
from simple_client import send_message
from net_common import Message, from_jsonb, MessageType, to_jsonb

from commands.base_command import BaseCommand, CommandResult, HelpCategory
from commands.command_processor import command
from commands.utils import get_player_from_context
from commands.context import Context
from flags import PlayerFlags, FlagDisplayTypes
from base_classes import PlayerStat


# Try to use the global client_manager if available (delegates to net_common if configured)
try:
    from client_manager import client_manager as global_client_manager
except Exception:
    global_client_manager = None


def _find_player_by_name(name: str) -> Optional[Any]:
    """Return a player object for the given username when available via client manager.

    This function tries several common registry shapes and returns the inner Player
    object or None.
    """
    if not name:
        return None
    # Try net_common delegate via client_manager module
    try:
        import net_common
        nc_cm = getattr(net_common, 'client_manager', None)
        if nc_cm:
            try:
                c = nc_cm.get_client(name)
                if c:
                    # c may be an object or dict-like; try common shapes
                    handler = getattr(c, 'handler', None)
                    if handler and getattr(handler, 'player', None):
                        return getattr(handler, 'player')
                    if getattr(c, 'player', None):
                        return getattr(c, 'player')
                    # dict-like fallback
                    try:
                        if isinstance(c, dict):
                            h = c.get('handler')
                            if h and getattr(h, 'player', None):
                                return getattr(h, 'player')
                            # maybe player stored directly
                            if c.get('player'):
                                return c.get('player')
                    except Exception:
                        pass
            except Exception:
                logging.debug('net_common.client_manager lookup failed')
    except Exception:
        pass

    # Try our local client_manager wrapper
    try:
        if global_client_manager:
            c = global_client_manager.get_client_by_user(name)
            if c:
                # c may be dict-like
                if isinstance(c, dict):
                    h = c.get('handler')
                    if h and getattr(h, 'player', None):
                        return getattr(h, 'player')
                    if c.get('player'):
                        return c.get('player')
                else:
                    if getattr(c, 'player', None):
                        return getattr(c, 'player')
    except Exception:
        logging.debug('local client_manager lookup failed')

    return None


def _format_display(display_type, status: bool) -> str:
    """Return a human-friendly string for flag given its display_type."""
    try:
        if display_type == FlagDisplayTypes.YESNO:
            return 'Yes' if status else 'No'
        if display_type == FlagDisplayTypes.ONOFF:
            return 'On' if status else 'Off'
    except Exception:
        pass
    # default to On/Off
    return 'On' if status else 'Off'


def get_flag_display(player, flag) -> str:
    """Get display string (Yes/No or On/Off) for a given player's flag.

    Tries multiple common shapes (Player.get_flag, .flags dict, query_flag) and
    falls back to On/Off.
    """
    # 1) Player.get_flag() -> Flag object
    try:
        if getattr(player, 'get_flag', None):
            fobj = player.get_flag(flag)
            if fobj is not None:
                return _format_display(getattr(fobj, 'display_type', None), bool(getattr(fobj, 'status', False)))
    except Exception:
        pass

    # 2) flags dict fallback
    flags_map = getattr(player, 'flags', None) or (player.get('flags') if isinstance(player, dict) else None)
    if flags_map:
        try:
            val_obj = flags_map.get(flag) if isinstance(flags_map, dict) else None
        except Exception:
            val_obj = None
        if val_obj is None:
            try:
                val_obj = flags_map.get(flag.name) or flags_map.get(flag.value)
            except Exception:
                val_obj = None
        if isinstance(val_obj, bool):
            return _format_display(None, val_obj)
        if val_obj is not None:
            return _format_display(getattr(val_obj, 'display_type', None), bool(getattr(val_obj, 'status', False)))

    # 3) query_flag method
    try:
        if getattr(player, 'query_flag', None):
            status = bool(player.query_flag(flag))
            return _format_display(None, status)
    except Exception:
        pass

    return 'Off'


def _format_flags_list(player, client_name: str = None) -> list:
    """Return a nicely formatted list of flag lines for display."""
    lines = []
    header_name = client_name or getattr(player, 'name', 'you')
    lines.append(f"Flags for {header_name}:")
    lines.append("")
    flags_map = getattr(player, 'flags', None) or (player.get('flags') if isinstance(player, dict) else None)
    if not flags_map:
        lines.append("(No flags available)")
        return lines
    max_name_len = max((len(f.name) for f in PlayerFlags), default=20)
    i = 1
    for f in PlayerFlags:
        try:
            val_obj = flags_map.get(f) if isinstance(flags_map, dict) else None
        except Exception:
            val_obj = None
        if val_obj is None:
            try:
                val_obj = flags_map.get(f.name) or flags_map.get(f.value)
            except Exception:
                val_obj = None
        if isinstance(val_obj, bool):
            status = val_obj
        elif val_obj is not None:
            status = bool(getattr(val_obj, 'status', False))
        else:
            status = False
        # Determine display text using player's flag objects / API
        try:
            display_text = get_flag_display(player, f)
        except Exception:
            display_text = 'On' if (isinstance(val_obj, bool) and val_obj) else 'Off'
        lines.append(f"{i:>2}. {f.name:.<{max_name_len}} : {display_text}")
        i += 1
    lines.append("")
    lines.append("Tip: Toggle a flag with: 'ep <FLAG>' or 'ep <FLAG> on|off'\nExample: ep ADMIN or ep ADMIN on")
    return lines


@command(name='editplayer', aliases=['ep'], category=HelpCategory.MISCELLANEOUS,
         summary='View or toggle player flags (admin only for others)')
class EditPlayerCommand(BaseCommand):
    """View or modify PlayerFlags for players.

    Usage:
      editplayer                - list flags for yourself
      editplayer <flag>         - toggle <flag> for yourself
      editplayer <user> <flag> [on|off|toggle] - admin: set flag for user
    """

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        # Debug: log context and client for troubleshooting missing player context
        try:
            logging.debug("editplayer.execute: context keys=%s", list(context.keys()) if isinstance(context, dict) else str(type(context)))
        except Exception:
            pass
        # Resolve actor (support Context enum keys and plain string keys)
        client = None
        if isinstance(context, dict):
            # Try enum key, enum.value, then plain string
            try:
                client = context.get(Context.CLIENT) or context.get(Context.CLIENT.value) or context.get('client')
            except Exception:
                client = context.get('client') if isinstance(context, dict) else None

        try:
            logging.debug("editplayer.execute: client attrs=writer=%s reader=%s player=%s username=%s", getattr(client,'writer',None) is not None, getattr(client,'reader',None) is not None, getattr(client,'player',None), getattr(client,'username',None))
        except Exception:
            pass
        player = get_player_from_context(context, client)
        try:
            logging.debug("editplayer.execute: resolved player=%s", getattr(player,'name', None) if player else None)
        except Exception:
            pass

        # Determine actor admin status (prefer PlayerFlags.ADMIN)
        is_admin = False
        try:
            if player is not None and getattr(player, 'query_flag', None):
                is_admin = bool(player.query_flag(PlayerFlags.ADMIN))
        except Exception:
            is_admin = False
        if not is_admin:
            # fallback to client/context flags
            is_admin = bool(getattr(client, 'is_admin', False) or (context.get('is_admin') if isinstance(context, dict) else False))

        # No args -> list flags for current player
        if not args:
            # If we don't have a player resolved yet, try fallbacks so plain 'ep' works
            if player is None:
                # 1) try client.player using multiple context shapes
                try:
                    possible_client = None
                    if isinstance(context, dict):
                        possible_client = context.get(Context.CLIENT) or context.get(Context.CLIENT.value) or context.get('client')
                    if possible_client is None:
                        possible_client = client
                    if possible_client is not None:
                        player = getattr(possible_client, 'player', None)
                        # handler.player fallback
                        if player is None:
                            handler = getattr(possible_client, 'handler', None)
                            if handler is not None:
                                player = getattr(handler, 'player', None)
                except Exception:
                    player = None

            if player is None:
                # 2) try username in context (processor may set Context.USERNAME)
                try:
                    username = None
                    if isinstance(context, dict):
                        username = context.get(Context.USERNAME.value) or context.get('username')
                    if username:
                        found = _find_player_by_name(username)
                        if found:
                            player = found
                except Exception:
                    player = None

            if player is None:
                # 3) try global client_manager via net_common
                try:
                    import net_common
                    nc_cm = getattr(net_common, 'client_manager', None)
                    if nc_cm and isinstance(context, dict):
                        username = context.get(Context.PLAYER.USERNAME) or context.get('username')
                        if username:
                            cinfo = nc_cm.get_client_by_user(username) if hasattr(nc_cm, 'get_client_by_user') else nc_cm.get_client(username)
                            if cinfo:
                                handler = getattr(cinfo, 'handler', None)
                                if handler and getattr(handler, 'player', None):
                                    player = handler.player
                                elif getattr(cinfo, 'player', None):
                                    player = cinfo.player
                except Exception:
                    pass

            if player is None:
                return CommandResult(success=False, error='no_player', lines=['No player context available'])

            try:
                display_name = getattr(client, 'username', getattr(player, 'name', 'you'))
            except Exception:
                display_name = getattr(player, 'name', 'you')
            # If client supports interactive menu (has reader/writer), run it instead
            try:
                if client is not None and getattr(client, 'writer', None) and getattr(client, 'reader', None):
                    # Launch interactive menu; it will send its own messages.
                    await self._interactive_editplayer(context, client, player)
                    return CommandResult(success=True, lines=['Exiting editor'])
            except Exception:
                # fall back to non-interactive output
                pass

            lines = _format_flags_list(player, client_name=display_name)
            return CommandResult(success=True, lines=lines)

        # If first arg looks like a username and we have 2+ args, treat as admin edit target
        target_player = player
        flag_token = None
        action = 'toggle'
        if len(args) >= 2:
            # args[0] may be target username
            target_name = args[0]
            flag_token = args[1]
            if len(args) >= 3:
                action = args[2].lower()
            # require admin to edit other players
            if not is_admin:
                return CommandResult(success=False, error='permission_denied', message='Only admins can edit other players')
            # find target
            found = _find_player_by_name(target_name)
            if not found:
                return CommandResult(success=False, error='not_found', message=f'Player {target_name} not found')
            target_player = found
        else:
            # single-arg case: toggle flag for self
            flag_token = args[0]
            action = 'toggle'

        # Normalize flag_token to a PlayerFlags member
        chosen_flag = None
        for f in PlayerFlags:
            if f.name.lower() == flag_token.lower() or f.value.lower() == flag_token.lower():
                chosen_flag = f
                break
        if not chosen_flag:
            # try partial match by name
            for f in PlayerFlags:
                if flag_token.lower() in f.name.lower() or flag_token.lower() in f.value.lower():
                    chosen_flag = f
                    break
        if not chosen_flag:
            return CommandResult(success=False, error='bad_flag', message=f'Unknown flag: {flag_token}')

        # Perform action
        # determine current status
        cur = False
        flags_map = getattr(target_player, 'flags', None) or (target_player.get('flags') if isinstance(target_player, dict) else None)
        try:
            if getattr(target_player, 'query_flag', None):
                cur = bool(target_player.query_flag(chosen_flag))
            elif flags_map:
                v = flags_map.get(chosen_flag) or flags_map.get(chosen_flag.name) or flags_map.get(chosen_flag.value)
                if isinstance(v, bool):
                    cur = v
                elif v is not None:
                    cur = bool(getattr(v, 'status', False))
        except Exception:
            cur = False

        # compute new status
        if action in ('on', 'true', '1'):
            new_status = True
        elif action in ('off', 'false', '0'):
            new_status = False
        elif action == 'toggle':
            new_status = not cur
        else:
            return CommandResult(success=False, error='bad_action', message=f'Unknown action: {action}')

        # apply change
        try:
            if hasattr(target_player, 'toggle_flag') and action == 'toggle':
                target_player.toggle_flag(chosen_flag, verbose=False)
            elif hasattr(target_player, 'put_flag'):
                target_player.put_flag(chosen_flag, getattr(getattr(flags_map, 'get', lambda k: None)(chosen_flag), 'display_type', None) if flags_map else None, new_status)
            else:
                # ensure flags_map exists and store under multiple keys
                if not isinstance(flags_map, dict):
                    try:
                        target_player.flags = {}
                        flags_map = target_player.flags
                    except Exception:
                        flags_map = {}
                class SimpleFlag:
                    def __init__(self, name, display_type, status):
                        self.name = name
                        self.display_type = display_type
                        self.status = status
                flags_map[chosen_flag] = SimpleFlag(chosen_flag, None, new_status)
                try:
                    flags_map[chosen_flag.name] = flags_map[chosen_flag]
                except Exception:
                    pass
                try:
                    flags_map[chosen_flag.value] = flags_map[chosen_flag]
                except Exception:
                    pass

            # propagate change to context and client handler if applicable
            if isinstance(context, dict):
                # if editor is the same player, update context entries
                ctx_player = context.get('player') or context.get(Context.PLAYER)
                if getattr(ctx_player, 'name', None) == getattr(target_player, 'name', None):
                    context['player'] = target_player
                    context[Context.PLAYER] = target_player

            try:
                import net_common
                cm = getattr(net_common, 'client_manager', None)
            except Exception:
                cm = None
            if cm:
                for cid, cinfo in getattr(cm, 'clients', {}).items():
                    try:
                        handler = getattr(cinfo, 'handler', None)
                        if handler and getattr(handler, 'player', None) is target_player:
                            handler.player = target_player
                    except Exception:
                        pass

        except Exception:
            logging.exception('Failed to apply flag change')
            return CommandResult(success=False, error='apply_failed', message='Failed to modify flag')

        # Friendly confirmation lines
        target_name = getattr(target_player, 'name', getattr(target_player, 'username', '<player>'))
        prev = 'On' if cur else 'Off'
        now = 'On' if new_status else 'Off'
        if target_player is player:
            # acted on self
            lines = [f"{chosen_flag.name} toggled", f"Previous: {prev}", f"Now:     {now}", "",
                     "Tip: toggle with 'ep <FLAG>' or set with 'ep <FLAG> on' / 'ep <FLAG> off'"]
        else:
            lines = [f"{chosen_flag.name} set for {target_name}", f"Previous: {prev}", f"Now:     {now}"]

        return CommandResult(success=True, lines=lines, data={'flag': chosen_flag.name, 'value': new_status})

    async def _interactive_editplayer(self, context: dict, client, player) -> None:
        """Run an interactive menu over the player's attributes via client's reader/writer.

        This is best-effort: if writer/reader are missing or an error occurs, it returns quietly.
        """
        try:
            writer = getattr(client, 'writer', None)
            reader = getattr(client, 'reader', None)
            if writer is None or reader is None:
                return

            # client-like object expected by async helpers
            client_like = type('ClientLike', (), {})()
            client_like.writer = writer
            client_like.reader = reader
            client_like.return_key = getattr(client, 'return_key', 'Enter')
            client_like.client_settings = getattr(client, 'client_settings', {'screen_columns': 80})

            # Build flags submenu
            flags_menu = Menu(title='Flags & Counters', columns=1)
            for flag in PlayerFlags:
                # create an async action to toggle the flag and report back
                async def make_action(f):
                    async def action():
                        try:
                            # Prefer player API
                            if hasattr(player, 'toggle_flag'):
                                player.toggle_flag(f, verbose=False)
                            elif hasattr(player, 'put_flag'):
                                player.put_flag(f, None, not bool(getattr(player, 'query_flag', lambda x: False)(f)))
                            else:
                                # fallback to flags dict
                                fm = getattr(player, 'flags', None)
                                if not isinstance(fm, dict):
                                    player.flags = {}
                                    fm = player.flags
                                cur = False
                                try:
                                    cur = bool(fm.get(f).status) if fm.get(f) is not None else False
                                except Exception:
                                    cur = False
                                fm[f] = type('F', (), {'name': f, 'display_type': None, 'status': not cur})

                            # send confirmation message
                            # show proper wording according to display_type
                            try:
                                disp = get_flag_display(player, f)
                            except Exception:
                                disp = 'On' if player.query_flag(f) else 'Off'
                            msg = Message(lines=[f"{f.name} set to {disp}"], prompt='')
                            await send_message(writer, msg)
                        except Exception:
                            try:
                                await send_message(writer, Message(lines=[f"Failed to toggle {f.name}"], prompt=''))
                            except Exception:
                                pass
                    return action

                # attach the action
                action_callable = await make_action(flag)
                flags_menu.add_item(MenuItem(text=flag.value, shortcuts=flag.name[:2], action=action_callable))

            # Top-level menu
            main_menu = Menu(title='Player Editor', columns=1)
            # Edit name action
            async def edit_name_action():
                try:
                    await send_message(writer, Message(lines=["Enter a new name (or blank to cancel):"], prompt=''))
                    raw = await reader.readline()
                    if not raw:
                        return
                    obj = from_jsonb(raw)
                    if not isinstance(obj, dict):
                        return
                    # prefer lines[0] or text
                    new_name = None
                    if 'lines' in obj and isinstance(obj['lines'], list) and obj['lines']:
                        new_name = str(obj['lines'][0]).strip()
                    elif 'text' in obj:
                        new_name = str(obj['text']).strip()
                    if not new_name:
                        await send_message(writer, Message(lines=["Name edit cancelled."], prompt=''))
                        return
                    # apply change
                    try:
                        player.name = new_name
                    except Exception:
                        pass
                    await send_message(writer, Message(lines=[f"Name changed to: {player.name}"], prompt=''))
                except Exception:
                    try:
                        await send_message(writer, Message(lines=["Failed to change name"], prompt=''))
                    except Exception:
                        pass

            # Build attributes submenu
            attrs_menu = Menu(title='Attributes', columns=1)
            for stat in PlayerStat:
                # async action to set stat value
                async def make_stat_action(s):
                    async def action():
                        try:
                            await send_message(writer, Message(lines=[f"Enter new value for {s.value} (current: {player.get_stat(s)}) :"], prompt=''))
                            raw = await reader.readline()
                            if not raw:
                                return
                            obj = from_jsonb(raw)
                            if not isinstance(obj, dict):
                                return
                            val = None
                            if 'lines' in obj and isinstance(obj['lines'], list) and obj['lines']:
                                val = str(obj['lines'][0]).strip()
                            elif 'text' in obj:
                                val = str(obj['text']).strip()
                            if not val:
                                await send_message(writer, Message(lines=["Stat edit cancelled."], prompt=''))
                                return
                            try:
                                new_int = int(val)
                            except Exception:
                                await send_message(writer, Message(lines=["Invalid number."], prompt=''))
                                return
                            # apply: Player API may not have set_stat — try attribute or stats dict
                            try:
                                if hasattr(player, 'set_stat'):
                                    player.set_stat(s, new_int)
                                else:
                                    player.stats[s] = new_int
                            except Exception:
                                try:
                                    player.stats[s] = new_int
                                except Exception:
                                    pass
                            await send_message(writer, Message(lines=[f"{s.value} set to {new_int}"], prompt=''))
                        except Exception:
                            try:
                                await send_message(writer, Message(lines=[f"Failed to set {s.value}"], prompt=''))
                            except Exception:
                                pass
                    return action

                action_callable = await make_stat_action(stat)
                attrs_menu.add_item(MenuItem(text=stat.value, shortcuts=stat.name[:2], action=action_callable))

            # We'll provide Edit Name, Attributes, Flags submenu and a quit option
            main_menu.add_item(MenuItem(text='Edit name', shortcuts='N', action=edit_name_action))
            main_menu.add_item(MenuItem(text='Attributes', shortcuts='A', submenu=attrs_menu))
            main_menu.add_item(MenuItem(text='Flags & Counters', shortcuts='F', submenu=flags_menu))
            main_menu.add_item(MenuItem(text='Exit Editor', shortcuts='X', action=None))

            # Run interactive loop
            # notify client for debugging that interactive editor is starting
            try:
                writer.write(to_jsonb(Message(lines=["DEBUG-SYSTEM: entering interactive editor"], type=MessageType.SYSTEM)) + b"\n")
                await writer.drain()
            except Exception:
                pass
            while True:
                # present menu using existing helpers and ask for a choice
                await async_print_menu(client_like, main_menu)
                # give client a short moment to render
                try:
                    await asyncio.sleep(0.02)
                except Exception:
                    pass
                chosen = await async_get_user_choice(client_like, main_menu, stack_depth=1)
                if chosen is None:
                    # leave editor
                    await send_message(writer, Message(lines=["Exiting editor..."], prompt=''))
                    break
                if chosen.submenu:
                    submenu = chosen.submenu
                    # run submenu loop similarly using our simple getter
                    while True:
                        await async_print_menu(client_like, submenu)
                        try:
                            await asyncio.sleep(0.02)
                        except Exception:
                            pass
                        sub_chosen = await async_get_user_choice(client_like, submenu, stack_depth=2)
                        if sub_chosen is None:
                            break
                        action = sub_chosen.action
                        if asyncio.iscoroutinefunction(action):
                            await action()
                        elif callable(action):
                            maybe_res = action()
                            if asyncio.iscoroutine(maybe_res):
                                await maybe_res
                else:
                    # non-submenu selected; currently only Exit or Edit name (no-op)
                    if chosen.text.lower().startswith('exit'):
                        await send_message(writer, Message(lines=["Exiting editor..."], prompt=''))
                        break
                    else:
                        await send_message(writer, Message(lines=["Option not implemented yet."], prompt=''))
                        continue
            # notify client for debugging that interactive editor is exiting
            try:
                writer.write(to_jsonb(Message(lines=["DEBUG-SYSTEM: exiting interactive editor"], type=MessageType.SYSTEM)) + b"\n")
                await writer.drain()
            except Exception:
                pass
        except Exception:
            # Log exception to aid debugging; interactive editor is optional so don't re-raise
            logging.exception('Interactive editor failed')
            return


class EditPlayerHelp:
    def __init__(self):
        self.category = HelpCategory.MISCELLANEOUS
        self.summary = 'View or toggle PlayerFlags for yourself or another player (admin)'
        self.description = 'Examples: editplayer, editplayer ADMIN, editplayer <user> ADMIN on'
        self.usage = [
            ('editplayer', 'List your flags'),
            ('editplayer <flag>', 'Toggle a flag for yourself'),
            ('editplayer <user> <flag> [on|off|toggle]', 'Set a flag for another user (admin only)')
        ]
