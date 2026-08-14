"""tests/server/test_player_load_save.py

All regression coverage for Player.save()/Player._load() round-tripping
in one place: Player.save() always writes the full __dict__ (minus a
small _SESSION_ONLY exclusion set), but _load() only restores a
hand-picked allowlist -- every field found missing from that allowlist
was silently reset to its __init__ default on the very next login, then
that default got written back out on the next save, permanently erasing
whatever had actually been there.

Found one field at a time, live, across several playtesting/feature
sessions -- shield/armor/active_shield_id, then loan_amount/loan_days,
then party, then food/drink, then _survival_counter, then dead_monsters,
then char_class/char_race/gender, then name (a case-preserving rename
reverting to lowercase), then birthday (logon_events/birthday.py's
greeting never firing) -- until a systematic audit of every kwargs.get()
default in __init__ against what _load() actually restores turned up a
final batch of ten more in one pass: experience, honor, poisoned,
diseased, natural_alignment, current_alignment, moves_made, wizard_glow,
once_per_day, last_play_date.

`allies` was audited too and found to have the same gap, but is
dead/legacy code (character_editor.py, an unwired prototype) superseded
by the already-correctly-restored `party` -- left alone rather than
restoring a field nothing live reads.

This was invisible to the rest of the test suite because every other
test constructs a Player (or fake) with these fields passed directly as
constructor kwargs, never round-tripping through save() -> a fresh
Player(id=...) the way a real reconnect does (commands/connect.py's
_authenticate(): `Player(name=char_name, id=username)`, no other kwargs).

Run with:
    python -m pytest tests/server/test_player_load_save.py -v
"""
from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

from base_classes import Alignment, Gender, PlayerClass, PlayerRace
from player import Player


# ---------------------------------------------------------------------------
# char_class / char_race / gender / name / creation state
# ---------------------------------------------------------------------------

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


def test_paused_creation_state_survives_a_relogin(tmp_path):
    """Same bug class as char_class/race/gender/name above: resumable
    character creation (commands/new_player.py's main_flow()) needs
    creation_done/creation_step to round-trip through a relogin exactly
    like every other field commands/connect.py's _authenticate() relies
    on, since it reconstructs a fresh Player(name=..., id=...) on every
    login rather than keeping the in-memory object alive."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='pausedtest', name='pausedtest')
    original.creation_done = False
    original.creation_step = 5
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='pausedtest', id='pausedtest')
    assert relogged.creation_done is False
    assert relogged.creation_step == 5


def test_finished_character_has_no_stale_creation_state(tmp_path):
    """A normal, fully-created character never had creation_done/
    creation_step set at all -- getattr(player, 'creation_done', True)
    at every call site must treat that absence as "finished", not crash
    or misbehave."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='finishedtest', name='finishedtest')
    assert original.save(force=True)

    relogged = Player(name='finishedtest', id='finishedtest')
    assert getattr(relogged, 'creation_done', True) is True


# ---------------------------------------------------------------------------
# birthday
# ---------------------------------------------------------------------------

def test_birthday_survives_a_relogin(tmp_path):
    """Same bug class as char_class/race/gender/name above, found live
    while testing logon_events/birthday.py: __init__ only sets
    self.birthday from a 'birthday' kwarg, which commands/connect.py's
    _authenticate() never passes on reconnect, so without _load()
    restoring it, every login silently reset a character's birthday to
    None -- and then wrote that None back out on the very next save,
    permanently erasing it. This meant the birthday greeting could never
    fire for any character that had actually logged in even once after
    its birthday was set."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='birthdaytest', name='birthdaytest')
    original.birthday = datetime.datetime(1990, 7, 27)
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='birthdaytest', id='birthdaytest')
    assert relogged.birthday == datetime.datetime(1990, 7, 27)


def test_no_birthday_on_file_stays_none(tmp_path):
    """A character with no birthday ever set shouldn't have _load()
    invent one or raise."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='nobdaytest', name='nobdaytest')
    assert original.birthday is None
    assert original.save(force=True)

    relogged = Player(name='nobdaytest', id='nobdaytest')
    assert relogged.birthday is None


# ---------------------------------------------------------------------------
# experience / honor / poisoned / diseased / alignment / moves_made /
# wizard_glow / once_per_day / last_play_date -- found in one pass via a
# systematic audit of every kwargs.get() default in __init__ against what
# _load() actually restores.
# ---------------------------------------------------------------------------

def test_experience_honor_moves_made_wizard_glow_survive_a_relogin(tmp_path):
    """experience is the most severe of these: it's the counter
    combat/resolution.py's _add_exp() drives xp_level from, so every
    login was silently zeroing a character's progress toward their next
    level, even though xp_level itself was (and still is) restored."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='statstest', name='statstest')
    original.experience = 12345
    original.honor = 500
    original.moves_made = 999
    original.wizard_glow = 7
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='statstest', id='statstest')
    assert relogged.experience == 12345
    assert relogged.honor == 500
    assert relogged.moves_made == 999
    assert relogged.wizard_glow == 7


def test_ammo_rounds_max_damage_survive_a_relogin(tmp_path):
    """ammo_rounds/ammo_max/ammo_damage (set by commands/use.py's ammo
    branch) were written by save() but never read back -- same gap as
    experience/honor above, just not caught by the same audit pass.
    Unlike readied_weapon (genuinely session-only, see _SESSION_ONLY),
    these three are not: a player who READY'd a weapon and USEd ammo,
    then quit and reconnected, saw STAT report "0/0 rounds" on the same
    weapon even though the save file on disk still had the real values --
    found live via tools/bot_ammo_reconnect_check.py against a real
    running server."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='ammotest', name='ammotest')
    original.ammo_rounds = 4
    original.ammo_max    = 4
    original.ammo_damage = 2
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='ammotest', id='ammotest')
    assert relogged.ammo_rounds == 4
    assert relogged.ammo_max    == 4
    assert relogged.ammo_damage == 2


def test_poisoned_and_diseased_survive_a_relogin(tmp_path):
    """poisoned/diseased are real booleans -- kept out of _load()'s generic
    int()-casting simple_keys loop (which would turn True/False into 1/0)
    and given their own bool() restore instead. Before this fix, a poisoned
    or diseased player was silently cured on every reconnect."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='sicktest', name='sicktest')
    original.poisoned = True
    original.diseased = True
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='sicktest', id='sicktest')
    assert relogged.poisoned is True
    assert relogged.diseased is True
    assert isinstance(relogged.poisoned, bool)
    assert isinstance(relogged.diseased, bool)


def test_healthy_player_stays_healthy_after_a_relogin(tmp_path):
    """The False/False case shouldn't get coerced into something truthy."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='healthytest', name='healthytest')
    assert original.poisoned is False
    assert original.diseased is False
    assert original.save(force=True)

    relogged = Player(name='healthytest', id='healthytest')
    assert relogged.poisoned is False
    assert relogged.diseased is False


def test_alignment_survives_a_relogin(tmp_path):
    """natural_alignment/current_alignment are stored as the enum's string
    value, same as guild/char_class/char_race/gender -- but were never
    restored at all, so every login reset both to Alignment.NEUTRAL
    regardless of what the player actually was."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='aligntest', name='aligntest')
    original.natural_alignment = Alignment.EVIL
    original.current_alignment = Alignment.GOOD
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='aligntest', id='aligntest')
    assert relogged.natural_alignment == Alignment.EVIL
    assert relogged.current_alignment == Alignment.GOOD


def test_once_per_day_survives_a_relogin(tmp_path):
    """Gates events like encounters/djinn_sighting.py, encounters/galadriel.py,
    bar/skip.py, and commands/use.py from firing more than once per
    real-world day. Never restored, so a reconnect let all of them fire
    again the same day."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='oncetest', name='oncetest')
    original.once_per_day = ['djinn_sighting', 'galadriel']
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='oncetest', id='oncetest')
    assert relogged.once_per_day == ['djinn_sighting', 'galadriel']


def test_last_play_date_survives_a_relogin(tmp_path):
    """Same restore pattern as last_connection, for the "have we already
    shown today's X" family of checks that compare against it."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='lastplaytest', name='lastplaytest')
    original.last_play_date = datetime.datetime(2020, 1, 1)
    original.unsaved_changes = True
    assert original.save(force=True)

    relogged = Player(name='lastplaytest', id='lastplaytest')
    assert relogged.last_play_date == datetime.datetime(2020, 1, 1)


# ---------------------------------------------------------------------------
# food / drink
# ---------------------------------------------------------------------------

class TestFoodDrinkPersistence(unittest.TestCase):
    """player.food/player.drink were written by Player.save() (full
    __dict__ dump) but never read back by _load() -- the same gap
    shield/armor/loan_amount/party had before earlier fixes. Found live
    while testing spells/charm.py's CHARM POTION: a player's thirst
    silently reset to "not thirsty" (drink=20, the __init__ default) on
    every reconnect, so DrinkCommand's "You're not thirsty" gate made it
    impossible to ever drink anything again after logging back in."""

    def test_food_and_drink_survive_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='fooddrinktest', name='Fooddrinktest')
            player.food = 3
            player.drink = 5
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='fooddrinktest', name='Fooddrinktest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.food, 3)
            self.assertEqual(reloaded.drink, 5)


# ---------------------------------------------------------------------------
# loan_amount / loan_days
# ---------------------------------------------------------------------------

class TestLoanPersistence(unittest.TestCase):
    """player.loan_amount/loan_days (silver owed to Vinny at the Bar, and
    days left to repay) were written by Player.save() (full __dict__
    dump) but never read back by _load() -- the exact same gap
    shield/armor/active_shield_id had before an earlier fix, found live
    while playtesting encounters/djinn_sighting.py (a player's debt
    silently reset to 0 on every reconnect, so the debt-collection ambush
    -- both the existing Bar overdue-loan check and the random Blue Djinn
    sighting -- could never actually fire in practice)."""

    def test_loan_amount_and_days_survive_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='loantest', name='Loantest')
            player.loan_amount = 500
            player.loan_days = 3
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='loantest', name='Loantest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.loan_amount, 500)
            self.assertEqual(reloaded.loan_days, 3)


# ---------------------------------------------------------------------------
# party (owned allies)
# ---------------------------------------------------------------------------

class TestPartyPersistence(unittest.TestCase):
    """player.party (owned allies) was written by Player.save() (full
    __dict__ dump) but never read back by _load() -- the same gap
    shield/armor/active_shield_id and loan_amount/loan_days had before
    earlier fixes. Found live while playtesting
    encounters/ally_starvation.py: a player's allies silently vanished on
    every reconnect, so no party-dependent mechanic
    (ally_events.try_ally_find_gold, try_hungry_ally, try_ally_death_save,
    encounters/ally_starvation.py) could ever actually fire against a
    real, persisted ally."""

    def test_owned_ally_survives_save_and_load(self):
        import net_common
        from bar.ally_data import Ally

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='partytest', name='Partytest')
            ally = Ally(name='Grog', gender='m', strength=15, to_hit=4)
            player.party.add_member(player, ally)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='partytest', name='Partytest')
            self.assertTrue(reloaded._load())
            self.assertEqual(len(reloaded.party), 1)
            restored = reloaded.party[0]
            self.assertIsInstance(restored, Ally)
            self.assertEqual(restored.name, 'Grog')
            self.assertEqual(restored.strength, 15)


# ---------------------------------------------------------------------------
# _survival_counter
# ---------------------------------------------------------------------------

class TestSurvivalCounterPersistence(unittest.TestCase):
    """player._survival_counter (survival.py's survival_tick() command
    counter) used to be session-only, resetting to 0 on every login --
    Ryan pointed out that let a player dodge hunger/thirst indefinitely by
    just logging out and back in right before the next depletion step.
    Same gap food/drink had before an earlier fix -- now a plain
    Player.__init__/simple_keys field like everything else in this file."""

    def test_survival_counter_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='survivalcountertest', name='Survivalcountertest')
            player._survival_counter = 7
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='survivalcountertest', name='Survivalcountertest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded._survival_counter, 7)


# ---------------------------------------------------------------------------
# duel_wins / duel_losses
# ---------------------------------------------------------------------------

class TestDuelRecordPersistence(unittest.TestCase):
    """player.duel_wins/duel_losses (combat/duel.py's DuelSession._end(),
    the personal SPORT DUEL win/loss record) -- same simple_keys pattern
    as _survival_counter above; written by save() via the full __dict__
    dump, so it must also be listed in _load()'s simple_keys tuple or it
    silently resets to 0 on every relogin."""

    def test_duel_record_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='duelrecordtest', name='Duelrecordtest')
            player.duel_wins = 3
            player.duel_losses = 1
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='duelrecordtest', name='Duelrecordtest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.duel_wins, 3)
            self.assertEqual(reloaded.duel_losses, 1)


# ---------------------------------------------------------------------------
# defeated_by / PlayerFlags.UNCONSCIOUS
# ---------------------------------------------------------------------------

class TestUnconsciousStatePersistence(unittest.TestCase):
    """player.defeated_by (combat/duel.py's DuelSession._end(), read by
    logon_events/unconscious_wake.py) -- same simple_keys pattern as
    duel_wins/duel_losses above; must survive a relogin so the wake-up
    line can still name the opponent even across a disconnect.
    PlayerFlags.UNCONSCIOUS itself round-trips via the generic flags
    serialization, not simple_keys."""

    def test_defeated_by_and_unconscious_flag_survive_save_and_load(self):
        import net_common
        from flags import PlayerFlags

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='unconscioustest', name='Unconscioustest')
            player.set_flag(PlayerFlags.UNCONSCIOUS)
            player.defeated_by = 'Belwin'
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='unconscioustest', name='Unconscioustest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.defeated_by, 'Belwin')
            self.assertTrue(reloaded.query_flag(PlayerFlags.UNCONSCIOUS))


# ---------------------------------------------------------------------------
# dead_monsters / monsters_killed
# ---------------------------------------------------------------------------

class TestDeadMonstersPersistence(unittest.TestCase):
    """Regression coverage for player.dead_monsters (the re-encounter/
    examine/teleport/charm gate, cleared by bar/zelda.py's Resurrect
    Monsters) and player.kill_log / player.monsters_killed (the derived
    @property, len(kill_log)) -- two separate lists as of the kill_log
    split (see player.py's __init__ comment and combat/engine.py's
    _record_kill):

      - dead_monsters survives a real save/load round-trip (same pattern
        as TestPartyPersistence above).
      - kill_log survives a real save/load round-trip too, and
        monsters_killed always reflects its current length, including
        duplicate entries (killing the same monster twice counts twice --
        Ryan's request; no dedup).
      - An older save file written before dead_monsters existed (key
        'monsters_killed' holding what used to be a deduplicated list) is
        migrated into dead_monsters on load, so upgrading doesn't
        silently erase kill history.
    """

    def test_dead_monsters_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='killtest', name='Killtest')
            player.dead_monsters.append(7)
            player.dead_monsters.append(7)   # same monster, killed twice
            player.dead_monsters.append(12)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='killtest', name='Killtest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.dead_monsters, [7, 7, 12])

    def test_kill_log_survives_save_and_load_and_drives_monsters_killed(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='killtest3', name='Killtest3')
            player.kill_log.append(7)
            player.kill_log.append(7)   # same monster, killed twice
            player.kill_log.append(12)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='killtest3', name='Killtest3')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.kill_log, [7, 7, 12])
            self.assertEqual(reloaded.monsters_killed, 3)

    def test_monsters_killed_is_read_only_derived_count(self):
        player = Player(id='killtest2', name='Killtest2')
        self.assertEqual(player.monsters_killed, 0)
        player.kill_log.extend([1, 2, 3, 3])
        self.assertEqual(player.monsters_killed, 4)
        with self.assertRaises(AttributeError):
            player.monsters_killed = 99

    def test_old_save_with_monsters_killed_key_migrates(self):
        """A save written before dead_monsters existed had a deduplicated
        'monsters_killed' list under that key -- must still load, not
        silently lose the player's kill history."""
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            path = Path(tmp) / 'player-oldsave.json'
            path.write_text(json.dumps({'id': 'oldsave', 'name': 'Oldsave',
                                         'monsters_killed': [3, 8, 15]}))

            player = Player(id='oldsave', name='Oldsave')
            self.assertTrue(player._load())
            self.assertEqual(player.dead_monsters, [3, 8, 15])
            self.assertEqual(player.monsters_killed, 3)

    def test_dead_monsters_key_takes_priority_over_old_key(self):
        """If a save somehow has both keys, the current dead_monsters key wins."""
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            path = Path(tmp) / 'player-bothkeys.json'
            path.write_text(json.dumps({'id': 'bothkeys', 'name': 'Bothkeys',
                                         'dead_monsters': [1, 1, 1],
                                         'monsters_killed': [99]}))

            player = Player(id='bothkeys', name='Bothkeys')
            self.assertTrue(player._load())
            self.assertEqual(player.dead_monsters, [1, 1, 1])


if __name__ == '__main__':
    unittest.main()
