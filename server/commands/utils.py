from typing import Any, Dict, Optional
from commands.context import Context


def get_player_from_context(context: Optional[Dict[str, Any]], client: Any = None) -> Optional[Any]:
    """Return the Player object using the processing context or the client as fallback.

    Lookup order:
    - context[Context.PLAYER]
    - context[Context.PLAYER.value]
    - context['player']
    - getattr(client, 'player', None)
    - getattr(client, 'handler', None) and getattr(client.handler, 'player', None)
    """
    if context and isinstance(context, dict):
        # enum key
        player = context.get(Context.PLAYER) if Context.PLAYER in context else None
        if not player:
            # value-key
            player = context.get(Context.PLAYER.value) or context.get('player')
        if player:
            return player
    # fallback to client
    try:
        if client is not None:
            p = getattr(client, 'player', None)
            if p is not None:
                return p
            handler = getattr(client, 'handler', None)
            if handler is not None:
                return getattr(handler, 'player', None)
    except Exception:
        pass
    return None

