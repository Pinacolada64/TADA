# Gender Usage Audit

Date: 2026-08-11

Scope: every read/write of `Gender` (players, allies/NPCs, mounts) across
`server/`.

## TL;DR

Gender is fully wired but purely cosmetic — pronoun substitution and NPC
address terms only, never a number, roll, or gate anywhere. It has no
SPUR precedent (the original BASIC game had no gender concept at all), so
this is a from-scratch TADA system that's mostly fully realized for its
intended (flavor) purpose, with one real, documented gap: a Wizard/Witch
class-name swap that exists in dead code but was never connected to the
live creation path.

---

## Storage

- `base_classes.py:162-164` — `Gender` enum, binary (`MALE`/`FEMALE`).
- `player.py:199` — defaults to `MALE` if unset.
- `player.py:1437-1443` — load-from-save string-matches the saved value
  back to the `Gender` enum.
- `new_player_2.py:141` — same default pattern in the alternate player
  class.
- `bar/ally_data.py:78-102` — allies/mounts have their own `Ally.gender`
  field, initially a raw `'m'`/`'f'` string, normalized to `Gender.MALE`/
  `Gender.FEMALE` in `__post_init__` (lines 91-102).
- Confirmed **no SPUR precedent** — grepping `SPUR-code/*.S` and
  `programming-notes/spur-variables.md` for gender/sex/pronoun handling
  turns up nothing. This is a wholly TADA-original system, not a port of
  an original mechanic.

## Setting

- `commands/new_player.py:723-744` (`_choose_gender`) — Step 3 of
  character creation, asked once, sets `ctx.player.gender`.
- `commands/new_player.py:1487-1491` (`_generate_random_name`) — picks
  from a male- or female-appropriate random name list based on
  `player.gender`.
- **No admin edit path** — `commands/editplayer.py` has no gender
  field/menu anywhere (unlike `char_class`/`char_race`, both editable at
  `commands/editplayer.py:1547-1615`). Once set at creation, a
  character's gender can never be changed in-game by anyone, including a
  DM.
- Mounts/charmed allies get a random gender rolled on capture
  (`ally_events/capture_horse.py:128-148`, `spells/charm.py:225-238`,
  `player.py:1074-1095`) — explicitly commented in-code as a TADA
  addition since SPUR never tracked mount gender at all. Cosmetic only
  (feeds the random-name pool and flavor text).

## Pronoun-substitution machinery (bulk of its usage)

- `tada_utilities.py:416-482` (`get_pronoun`) + `base_variables.py:33-48`
  (`PRONOUN_MAP`) — central 5-form pronoun resolver (subjective,
  objective, possessive adjective, possessive pronoun, reflexive) for
  MALE vs. FEMALE.
- `base_classes.py:167-172` — `PronounType` enum (the 5 grammatical
  forms).
- `messages.py:487-569` (`_PRONOUN_TOKENS`) — generic `%s/%o/%p/%P/%r`
  token substitution for JSON-authored ally/NPC message templates.
- `ally_events/farewell.py:46-148` — reuses the same token scheme for an
  ally's farewell message.
- `ally_events/starvation.py:159-161` — gendered possessive pronoun in
  ally-starvation flavor text.
- `encounters/dwarf.py:274-278`, `encounters/little_girl.py:272-275` —
  gendered pronouns (possessive/objective) in encounter flavor text for
  the *player*.
- `street/jakes.py:220-224` — gendered pronoun substitution for a
  *mount's* gender in stable/journey flavor text.
- `logon_events/birthday.py:135-141` — gendered possessive pronoun
  ("his/her" vs. flat "their") in the birthday-greeting message.
- `commands/look.py:66-70` — `you examine yourself` room-broadcast uses
  the reflexive pronoun.
- `commands/look.py:148-156` — examining a mount ally reports its gender
  directly as flavor text ("is a female/male ... horse").
- `party.py:91,124,183` — serializes/reads an ally's gender for
  party-roster bookkeeping — storage plumbing, not a behavioral branch.

## Gendered NPC dialogue / address terms (keyed on the player's gender)

- `bar/vinny.py:37-48` (`_gender_terms`) — female players addressed
  'honey'/'doll'; male players 'weasel'/'mac'. Used throughout Vinny's
  dialogue (e.g. `bar/vinny.py:383`) and reused by
  `logon_events/birthday.py:165-167`.
- `bar/skip.py:40-49` (`_gender_address`) — female players get 'miss',
  everyone else gets 'mac' (`bar/skip.py:104` usage).
- `bar/zelda.py:195` — fortune-teller's target-lookup pronoun
  ("She"/"He") based on the looked-up player's gender.
- `bar/zelda.py:433` — gendered possessive pronoun in the
  fortune-reading broadcast line.
- `combat/engine.py:650-651` — mount-taming success message picks
  "master"/"mistress" title based on the player's gender (Druid/Ranger
  horse-taming flavor text) — the only gender reference inside the
  combat engine itself, and it's a word choice, not a probability/damage
  modifier.

## Mechanical effect: none found

Gender never appears in a numeric formula, probability roll, price
calculation, or eligibility gate anywhere searched (`combat/engine.py`,
`combat/duel.py`, `combat/resolution.py`, `shoppe/*`, `commands/stats.py`,
`commands/cast.py`, all class/race bonus tables). It is purely cosmetic:
pronoun substitution plus a fixed vocabulary swap in three NPCs'
dialogue.

## The one real gap: Wizard/Witch class naming

- `base_classes.py:181-183` — the live `PlayerClass` enum has an explicit
  `TODO`: `"Wizard" if player.gender == Gender.MALE else 'Witch'` —
  **unimplemented** in the active class-name display path.
- `create_character.py:281` (`display_classes`) — this swap **is**
  implemented, but only in the legacy/unused `create_character.py`
  creation flow, which isn't wired into `simple_server.py`. In the live
  game, a female Wizard is always displayed/labeled "Wizard," never
  "Witch."

## No relationship system to gate on gender

- `grep -i "marry|marriage|wedding|spouse"` — zero hits. No
  marriage/social-bonding system exists in the codebase at all, so
  there's no gender-gated relationship mechanic to check or extend.
- No honor-system, duel-system, or death-message gendering of any kind
  was found beyond the pronoun-infrastructure files already listed.

## Ideas for humor/poignancy (cosmetic-tier, matching how gender is used elsewhere)

- **Wire up the existing Wizard/Witch TODO** — smallest possible win,
  the code already exists in `create_character.py:281`, it just needs to
  move into the live `commands/new_player.py`/display path referenced by
  `base_classes.py:181-183`.
- **Extend the title-swap pattern** to other classes with gendered
  English titles, if any read naturally in `commands/stats.py` or duel
  victory announcements.
- **More gendered flavor beats** beyond the two encounters that already
  have them (`encounters/dwarf.py`, `encounters/little_girl.py`) — e.g. a
  death message variant, a birthday message variant, or a bar toast that
  leans into the honey/doll vs. weasel/mac voice already established for
  Skip and Vinny.
- Since gender has zero mechanical footprint today, any of the above is
  risk-free to add — no balance implications, purely narrative surface
  area. (Contrast with Charisma — see the separate `CHARISMA_AUDIT.md` —
  where adding new mechanical hooks needs more care about balance.)

---

## Sourcing

Findings compiled via a full-codebase grep/read pass (Explore-agent
research task, not a live test run). File:line references reflect the
state of the code as of 2026-08-11 — re-verify before relying on any
specific line number if the surrounding file has since been edited.
