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

Same bug class found again later for `name` (see
test_renamed_display_name_survives_a_relogin below): a case-preserving
EditPlayer rename reverted to lowercase on the next login.

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


def test_renamed_display_name_survives_a_relogin(tmp_path):
    """Same bug class as char_class/race/gender above, found live: EditPlayer's
    Character Names > rename (commands/editplayer.py's edit_name()) sets
    player.name and it gets saved, but commands/connect.py's _authenticate()
    always reconstructs Player(name=char_name, id=username), where char_name
    comes from creds.get('char_name') -- a credentials-file key nothing ever
    actually writes, so it's always None and falls back to the lowercased
    login username. Without _load() restoring name from the save file, a
    case-preserving rename (e.g. 'railbender' -> 'Railbender') was silently
    discarded on the very next login, always reverting to lowercase."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='railbender', name='railbender')
    original.name = 'Railbender'
    original.unsaved_changes = True
    assert original.save(force=True)

    # Simulate a fresh reconnect exactly the way commands/connect.py does:
    # Player(name=char_name, id=username) -- char_name always falls back
    # to the lowercased login username since nothing ever populates
    # creds['char_name'].
    relogged = Player(name='railbender', id='railbender')

    assert relogged.name == 'Railbender'


def test_new_character_with_no_save_file_keeps_constructor_name(tmp_path):
    """A brand-new character (no save file yet) must still get its name
    from the constructor kwarg -- _load() only overrides it once a save
    file with a 'name' field actually exists."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    brand_new = Player(name='Freshman', id='freshman')
    assert brand_new.name == 'Freshman'
