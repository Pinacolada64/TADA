"""tests/test_player_login_restores_class.py

Regression test for a real production bug found by running a live bot
through actual login/combat cycles: Player._load() never restored
char_class, char_race, or gender from the saved JSON -- every reconnect
silently reset them to defaults (char_class=None, char_race=None,
gender=Gender.MALE), exactly matching how commands/connect.py logs a
player back in: `Player(name=char_name, id=username)`, no class/race/
gender kwargs supplied.

This was invisible to the rest of the test suite because every other
test constructs a Player (or fake) with char_class/gender passed directly
as constructor kwargs, never round-tripping through save() -> a fresh
Player(id=...) the way a real reconnect does.

Run with:
    python -m pytest tests/test_player_login_restores_class.py -v
"""
from player import Player
from base_classes import Gender, PlayerClass, PlayerRace


def test_char_class_race_gender_survive_a_relogin(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='relogtest', name='relogtest',
                       char_class=PlayerClass.DRUID,
                       char_race=PlayerRace.ELF,
                       gender=Gender.FEMALE)
    assert original.save(force=True)

    # Simulate a fresh reconnect exactly the way commands/connect.py does:
    # Player(name=char_name, id=username) -- no class/race/gender kwargs.
    relogged = Player(name='relogtest', id='relogtest')

    assert relogged.char_class == PlayerClass.DRUID
    assert relogged.char_race == PlayerRace.ELF
    assert relogged.gender == Gender.FEMALE


def test_missing_char_class_defaults_gracefully(tmp_path):
    """A save with no class chosen yet (char_class=None) shouldn't raise
    or get coerced into some bogus enum member on the next login."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='noclasstest', name='noclasstest')
    assert original.char_class is None
    assert original.save(force=True)

    relogged = Player(name='noclasstest', id='noclasstest')
    assert relogged.char_class is None
