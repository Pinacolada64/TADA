# commands/editplayer.py
from typing import Dict, Any, List, Optional
import logging
import asyncio
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice
from player import Player
from simple_client import send_message
from net_common import Message, from_jsonb, MessageType, to_jsonb

from commands.base_command import BaseCommand, CommandResult, HelpCategory
from commands.command_processor import command
from commands.utils import get_player_from_context
from commands.context import Context
from flags import PlayerFlags, FlagDisplayTypes, Flag
from base_classes import PlayerStat, Combination


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
                        return h.player
                    if c.get('player'):
                        return c.get('player')
                else:
                    if getattr(c, 'player', None):
                        return c.player
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


class HitPointsMenu(Menu):
    """Menu to set hit points. Built synchronously; actions are async coroutines."""
    def __init__(self):
        super().__init__(title='Set Hit Points', columns=1)
        hp_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for hp in hp_values:
            def make_action(h):
                async def action():
                    try:
                        player = self.context.get('player') if getattr(self, 'context', None) else None
                        if player is not None:
                            try:
                                setattr(player, 'hit_points', h)
                            except Exception:
                                pass
                        await send_message(self.context.get('client'), Message(lines=[f'Hit Points set to {h}'], prompt=''))
                    except Exception:
                        try:
                            await send_message(self.context.get('client'), Message(lines=[f'Failed to set Hit Points'], prompt=''))
                        except Exception:
                            pass
                return action
            self.add_item(MenuItem(text=str(hp), shortcuts=str(hp)[0], action=make_action(hp)))


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
                client = context.get(Context.CLIENT) or context.get(context.CLIENT.value) or context.get('client')
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
            # attach context so handlers can find player/client
            flags_menu.context = {'player': player, 'client': client_like}

            # create an async action factory to toggle the flag for the current player
            def make_toggle_action(f: PlayerFlags):
                async def action():
                    try:
                        # Resolve player from menu context if available, else use captured player
                        p = flags_menu.context.get('player') if getattr(flags_menu, 'context', None) else player
                        writer_local = flags_menu.context.get('client') if getattr(flags_menu, 'context', None) else None
                        # Toggle using Player API when available
                        try:
                            if hasattr(p, 'toggle_flag'):
                                p.toggle_flag(f)
                            else:
                                # fallback: update p.flags dict
                                flags_map = getattr(p, 'flags', None) or (p.get('flags') if isinstance(p, dict) else None)
                                if not isinstance(flags_map, dict):
                                    try:
                                        p.flags = {}
                                        flags_map = p.flags
                                    except Exception:
                                        flags_map = {}
                                curr = False
                                try:
                                    v = flags_map.get(f) or flags_map.get(f.name) or flags_map.get(f.value)
                                    if isinstance(v, bool):
                                        curr = v
                                    elif v is not None:
                                        curr = bool(getattr(v, 'status', False))
                                except Exception:
                                    curr = False
                                new_status = not curr
                                class SimpleFlag:
                                    def __init__(self, name, display_type, status):
                                        self.name = name
                                        self.display_type = display_type
                                        self.status = status
                                flags_map[f] = SimpleFlag(f, None, new_status)
                                try:
                                    flags_map[f.name] = flags_map[f]
                                except Exception:
                                    pass
                                try:
                                    flags_map[f.value] = flags_map[f]
                                except Exception:
                                    pass
                        except Exception:
                            logging.exception('Failed to toggle flag via API')
                        # report new status
                        try:
                            display = get_flag_display(p, f)
                        except Exception:
                            display = 'On' if getattr(p, 'flags', {}).get(f, False) else 'Off'
                        # send result to client if writer is available
                        try:
                            w = writer_local if writer_local is not None else getattr(flags_menu.context.get('client'), 'writer', None) if getattr(flags_menu, 'context', None) else getattr(player, 'writer', None)
                            if w:
                                await send_message(w, Message(lines=[f"{f.name} set to {display}"], prompt=''))
                        except Exception:
                            # best-effort only
                            pass
                    except Exception:
                        logging.exception('Toggle flag action failed')
                return action

            # create an async action to toggle the flag and report back
            for flag in PlayerFlags:
                logging.debug("Adding flag menu item for %s", flag.name)
                # Try to get the status string from player's helper; fall back to get_flag_display
                try:
                    flag_line = player.show_flag_line_item(flag, None)
                    parts = flag_line.split(": ")
                    flag_status = parts[1] if len(parts) > 1 else get_flag_display(player, flag)
                except Exception:
                    flag_status = get_flag_display(player, flag)
                # dot_leader_handler should accept a player parameter (format_menu_lines may call with player)
                dot_handler = (lambda p, f=flag: get_flag_display(p if p is not None else player, f))
                flags_menu.add_item(MenuItem(text=flag.value, shortcuts=flag.name[:2],
                                             dot_leader_handler=dot_handler,
                                             action=make_toggle_action(flag)))

            # Build alignment submenu (synchronous builder returning Menu instance)
            def build_alignment_submenu():
                from base_classes import Alignment
                menu = Menu(title='Set Alignment', columns=1)
                alignments = [align for i, align in enumerate(Alignment)]  # ['Good', 'Neutral', 'Evil']
                for align in alignments:
                    def make_action(a):
                        async def action():
                            try:
                                # set alignment on player
                                p = menu.context.get('player') if menu.context else None
                                if p is not None:
                                    try:
                                        setattr(p, 'alignment', a)
                                    except Exception:
                                        pass
                                await send_message(menu.context.get('client'),
                                                   Message(lines=[f'Alignment set to {a}'], prompt=''))
                            except Exception:
                                try:
                                    await send_message(menu.context.get('client'),
                                                       Message(lines=[f'Failed to set alignment'], prompt=''))
                                except Exception:
                                    pass
                        return action
                    menu.add_item(MenuItem(text=align, shortcuts=align[0], action=make_action(align)))
                return menu

            # Build attributes submenu
            attrs_menu = Menu(title='Attributes', columns=1)
            attrs_menu.context = {'player': player, 'client': client_like}
            for stat in PlayerStat:
                # action factory for stats
                def make_stat_action(s):
                    async def action():
                        try:
                            await send_message(writer, Message(lines=[f"Enter new value for {s.value} (current: {player.get_stat(s)}) :"], prompt=''))
                            raw = await reader.readline()
                            if not raw:
                                return
                            obj = from_jsonb(raw)
                            logging.debug("make_stat_action received raw: %r -> obj: %r", raw, obj)
                            if not isinstance(obj, dict):
                                return
                            val = None
                            if 'lines' in obj and isinstance(obj['lines'], list) and obj['lines']:
                                val = str(obj['lines'][0]).strip()
                            elif 'text' in obj:
                                val = str(obj['text']).strip()
                            logging.debug("Parsed stat value string: %r", val)
                            if not val:
                                await send_message(writer, Message(lines=["Stat edit cancelled."], prompt=''))
                                return
                            try:
                                new_int = int(val)
                            except Exception:
                                await send_message(writer, Message(lines=["Invalid number."], prompt=''))
                                return
                            logging.debug("Setting stat %s to %d on player %s", s, new_int, getattr(player, 'name', None))
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
                            logging.debug("After set, player.get_stat(%s) = %r", s, player.get_stat(s) if hasattr(player, 'get_stat') else player.stats.get(s))
                            # propagate stat change to context and client handler (best-effort)
                            try:
                                if isinstance(context, dict):
                                    ctx_player = context.get('player') or context.get(Context.PLAYER)
                                    if getattr(ctx_player, 'name', None) == getattr(player, 'name', None):
                                        context['player'] = player
                                        context[Context.PLAYER] = player
                            except Exception:
                                pass
                            try:
                                import net_common
                                cm = getattr(net_common, 'client_manager', None)
                            except Exception:
                                cm = None
                            if cm:
                                for cid, cinfo in getattr(cm, 'clients', {}).items():
                                    try:
                                        handler = getattr(cinfo, 'handler', None)
                                        if handler and getattr(handler, 'player', None) is player:
                                            handler.player = player
                                    except Exception:
                                        pass
                            await send_message(writer, Message(lines=[f"{s.value} set to {new_int}"], prompt=''))
                        except Exception:
                            try:
                                await send_message(writer, Message(lines=[f"Failed to set {s.value}"], prompt=''))
                            except Exception:
                                pass
                    return action

                action_callable = make_stat_action(stat)
                # dot leader shows current stat value; accept a player parameter
                def _dot_for_stat(p, s=stat):
                    try:
                        if p is None:
                            p = player
                        if hasattr(p, 'get_stat'):
                            return str(p.get_stat(s))
                        # stats dict may use enum key or name
                        st = getattr(p, 'stats', None)
                        if isinstance(st, dict):
                            val = st.get(s)
                            if val is None:
                                val = st.get(getattr(s, 'name', None), '<none>')
                            return str(val)
                    except Exception:
                        pass
                    return '<none>'

                attrs_menu.add_item(MenuItem(text=stat.value, shortcuts=stat.name[:2], action=action_callable, dot_leader_handler=_dot_for_stat))

            # build combinations submenu
            from base_classes import CombinationTypes
            combinations_submenu = Menu(title="Combinations", columns=1)
            combinations_submenu.context = {'player': player, 'client': client_like}
            logging.info(combinations_submenu.context)

            def format_combo_display(p, c):
                try:
                    if not hasattr(p, 'combinations') or not isinstance(p.combinations, dict):
                        return '(none)'
                    combo_obj = p.combinations.get(c) or p.combinations.get(c.value) or p.combinations.get(c.name)
                    if combo_obj is None:
                        return '(none)'
                    comb = getattr(combo_obj, 'combination', None)
                    if comb is None:
                        return str(combo_obj)
                    if isinstance(comb, (list, tuple)) and len(comb) == 3:
                        return f"{int(comb[0]):02d}-{int(comb[1]):02d}-{int(comb[2]):02d}"
                    return str(comb)
                except Exception as e:
                    return f'(error {e})'

            def make_combo_action(c):
                async def action():
                    try:
                        # Prompt the client and read one line. Support reader.readline returning bytes or a dict.
                        await send_message(writer, Message(
                            lines=[f"Enter new combination for {c.value} in format xx-xx-xx (blank to cancel):"],
                            prompt=''))
                        try:
                            if hasattr(writer, 'drain'):
                                await writer.drain()
                        except Exception:
                            pass

                        raw = await reader.readline()
                        if not raw:
                            return

                        # raw may already be a dict in some test harnesses; handle both
                        if isinstance(raw, dict):
                            obj = raw
                        else:
                            try:
                                obj = from_jsonb(raw)
                            except Exception:
                                # try decoding as utf-8 then parse simple forms
                                try:
                                    txt = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else str(raw)
                                    # If txt looks like JSON, attempt from_jsonb via bytes
                                    try:
                                        obj = from_jsonb(txt.encode('utf-8'))
                                    except Exception:
                                        obj = {'lines': [txt.strip()]}
                                except Exception:
                                    obj = None
                        if not isinstance(obj, dict):
                            return
                        new_val = None
                        if 'lines' in obj and isinstance(obj['lines'], list) and obj['lines']:
                            new_val = str(obj['lines'][0]).strip()
                        elif 'text' in obj:
                            new_val = str(obj['text']).strip()
                        if not new_val:
                            await send_message(writer, Message(lines=["Combination edit cancelled."], prompt=''))
                            return
                        # validate three numbers separated by dashes or whitespace and ensure each is 1..99
                        import re
                        # Accept flexible input like '04-05-09', '4-5-9', or '4 5 9'
                        digits = re.findall(r"\d{1,2}", new_val)
                        if len(digits) != 3:
                            await send_message(writer, Message(
                                lines=["Invalid format. Expected three numeric groups like '4 5 9' or '04-05-09'."], prompt=''))
                            return
                        # canonicalize to zero-padded dash-separated form
                        try:
                            parts = [f"{int(d):02d}" for d in digits]
                            canonical = "-".join(parts)
                        except Exception:
                            await send_message(writer, Message(
                                lines=["Invalid numeric values. Please enter numbers between 0 and 99."], prompt=''))
                            return
                        try:
                            if not hasattr(player, 'combinations') or not isinstance(player.combinations, dict):
                                player.combinations = {}
                            # always create a fresh Combination object and set its tuple
                            combo_obj = Combination(c)
                            combo_obj.combination = tuple(int(d) for d in digits)
                            # store under enum key and string keys to be resilient to different lookups
                            try:
                                player.combinations[c] = combo_obj
                            except Exception:
                                player.combinations[str(c)] = combo_obj
                            try:
                                player.combinations[c.value] = combo_obj
                            except Exception:
                                try:
                                    player.combinations[str(c.value)] = combo_obj
                                except Exception:
                                    pass
                            try:
                                player.combinations[c.name] = combo_obj
                            except Exception:
                                try:
                                    player.combinations[str(c.name)] = combo_obj
                                except Exception:
                                    pass
                            # ensure the stored object's .combination attribute is set
                            try:
                                stored = player.combinations.get(c) or player.combinations.get(c.value) or player.combinations.get(c.name)
                                if stored is not None and hasattr(stored, 'combination'):
                                    stored.combination = combo_obj.combination
                            except Exception:
                                pass
                            # Debug: explicit log for the stored combo object and tuple
                            try:
                                stored = player.combinations.get(c) or player.combinations.get(c.value) or player.combinations.get(c.name)
                                logging.debug("After storing combo for %s: stored=%r; type=%s; tuple=%r", c, stored, type(stored), getattr(stored, 'combination', None))
                            except Exception:
                                logging.exception('Failed to debug-log stored combination')

                            # send success confirmation to client
                            try:
                                await send_message(writer, Message(lines=[f"{c.value} combination set to {canonical}"], prompt=''))
                                try:
                                    if hasattr(writer, 'drain'):
                                        await writer.drain()
                                except Exception:
                                    pass
                            except Exception:
                                logging.exception('Failed to send success message after storing combination')
                        except Exception:
                            logging.exception('Exception while storing combination')
                            await send_message(writer, Message(lines=[f"Failed to set combination for {c.value}"], prompt=''))
                    except Exception:
                        logging.exception('Unhandled exception in combination action')
                        try:
                            await send_message(writer, Message(lines=[f"Failed to set combination for {c.value}"], prompt=''))
                        except Exception:
                            pass
                return action

            from base_classes import CombinationTypes
            combos_src = getattr(player, 'combinations', {}) or {}
            if isinstance(combos_src, dict):
                keys = list(combos_src.keys())
            elif isinstance(combos_src, list):
                keys = list(combos_src)
            else:
                keys = [combos_src]
            for combo_key in keys:
                # try to resolve a CombinationTypes enum when stored as a string/key
                c = combo_key
                if isinstance(combo_key, str):
                    for ct in CombinationTypes:
                        if combo_key == ct.name or combo_key == ct.value or combo_key == str(ct):
                            c = ct
                            break
                # friendly text and shortcut
                text = getattr(c, 'value', str(c))
                shortcut = (getattr(c, 'name', None) or str(text))[:1]
                combinations_submenu.add_item(MenuItem(
                    text=text,
                    shortcuts=shortcut,
                    action=make_combo_action(c),
                    dot_leader_handler=(lambda p=None, c=c: format_combo_display(p, c))
                ))

            # Debug: temporary menu item to dump the player's combinations for interactive troubleshooting
            async def debug_combos_action():
                try:
                    combos = getattr(player, 'combinations', None) or {}
                    lines = ["Current combinations:"]
                    if not combos:
                        lines.append("(none)")
                    else:
                        if isinstance(combos, dict):
                            for k, v in combos.items():
                                try:
                                    if hasattr(v, 'combination'):
                                        comb = v.combination
                                        if isinstance(comb, (list, tuple)) and len(comb) == 3:
                                            s = f"{int(comb[0]):02d}-{int(comb[1]):02d}-{int(comb[2]):02d}"
                                        else:
                                            s = str(comb)
                                    else:
                                        s = str(v)
                                except Exception:
                                    s = '<error>'
                                lines.append(f"{k}: {s}")
                        elif isinstance(combos, list):
                            for idx, v in enumerate(combos):
                                try:
                                    if hasattr(v, 'combination'):
                                        comb = v.combination
                                        if isinstance(comb, (list, tuple)) and len(comb) == 3:
                                            # s = f"{int(comb[0]):02d}-{int(comb[1]):02d}-{int(comb[2]):02d}"
                                            s = "-".join(f"{int(part):02d}" for part in comb)
                                        else:
                                            s = str(comb)
                                    else:
                                        s = str(v)
                                except Exception:
                                    s = '<error>'
                                lines.append(f"[{idx}]: {s}")
                        else:
                            try:
                                lines.append(str(combos))
                            except Exception:
                                lines.append('<unprintable>')
                    await send_message(writer, Message(lines=lines, prompt=''))
                except Exception:
                    logging.exception('debug_combos_action failed')

            combinations_submenu.add_item(MenuItem(text='Debug combos', shortcuts='D', action=debug_combos_action))

            # Top-level menu
            main_menu = Menu(title='Player Editor', columns=1)
            # ensure client-like has player for rendering dot leaders
            client_like.player = player
            # attach context to main menu so nested handlers can access it
            main_menu.context = {'player': player, 'client': client_like}

            def show_name(player_obj):
                return player_obj.name

            # Edit name action: no-arg coroutine so menu runner can call it without parameters
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

            # We'll provide Edit Name, Attributes, Flags submenu and a quit option
            main_menu.add_item(MenuItem("Alignment", "al", submenu=build_alignment_submenu()))
            main_menu.add_item(MenuItem("Armor / Shield", "as", action=None))  # not implemented
            main_menu.add_item(MenuItem("Attributes", "at", submenu=attrs_menu))
            main_menu.add_item(MenuItem("Character Names", "cn", action=None))  # not implemented
            main_menu.add_item(MenuItem("Combinations", "co", submenu=combinations_submenu))
            main_menu.add_item(MenuItem('Flags & Counters', shortcuts='F', submenu=flags_menu))
            main_menu.add_item(MenuItem("Hit Points", "hp", submenu=HitPointsMenu()))
            main_menu.add_item(MenuItem("Map Information", "mi", action=None))  # not implemented
            main_menu.add_item(MenuItem("Money", "mo", action=None))  # not implemented
            main_menu.add_item(MenuItem("Statistics", "st", action=None))  # not implemented
            main_menu.add_item(MenuItem("Weapons", "we", action=None))  # not implemented

            main_menu.add_item(MenuItem(text='Edit name', shortcuts='N', action=edit_name_action,
                                        dot_leader_handler=(lambda p=None: getattr(p if p is not None else player, 'name', '<unknown>'))
                                        ))
            main_menu.add_item(MenuItem(text='Exit Editor', shortcuts='X', action=None))

            # Run interactive loop
            # notify client for debugging that interactive editor is starting
            try:
                msg = Message(lines=["DEBUG-SYSTEM: starting interactive editor"], type=MessageType.SYSTEM)
                await send_message(msg, writer)
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
                chosen = await async_get_user_choice(reader=reader, writer=writer, client=client, menu=main_menu,
                                                     stack_depth=1)
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
                    # non-submenu selected: run its action if present, otherwise handle exit
                    if chosen.text.lower().startswith('exit'):
                        await send_message(writer, Message(lines=["Exiting editor..."], prompt=''))
                        break

                    # if the menu item has an action, execute it (support async and sync callables)
                    action = chosen.action
                    if action is None:
                        await send_message(writer, Message(lines=["Option not implemented yet."], prompt=''))
                        continue

                    try:
                        if asyncio.iscoroutinefunction(action):
                            await action()
                        elif callable(action):
                            maybe = action()
                            if asyncio.iscoroutine(maybe):
                                await maybe
                    except Exception:
                        logging.exception('Error executing menu action')
                        try:
                            await send_message(writer, Message(lines=["Action failed."], prompt=''))
                        except Exception:
                            pass
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
            ('editplayer', 'Edit your own character interactively'),
            ('editplayer <flag>', 'Toggle a flag for yourself'),
            ('editplayer <user> <flag> [on|off|toggle]', 'Set a flag for another user (admin only)')
        ]
