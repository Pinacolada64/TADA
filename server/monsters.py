import json
import logging

monster_flags = [
    (';;',  'heavy_armor'),
    (';',   'light_armor'),
    ('>>',  'chance_find_gold_2x'),
    ('>',   'chance_find_gold'),
    ('++',  'cast_multiple_spells'),
    ('+',   'cast_one_spell'),
    (']',   'double_attacks'),
    (':',   'mechanical'),
    ('.',   'increase_strength'),
    ('E',   'evil'),
    ('G',   'good'),
    ('<',   're_animates'),
    ('#',   'cast_turn_to_stone'),
    ('*',   'poisonous_attack'),
    ('@',   'diseased_attack'),
    ('&',   'experience_drain'),
    ('%',   'magic_resistant'),
    ('~',   'appears_unaffected'),
    ('-',   'fire_attack'),
    ('X',   'no_gold'),
    ('$',   'multiple_monsters'),
    ('?',   'no_article'),
    ('AC',  'charmable'),
    ('!',   'has_quote'),
]

monster_flag_labels = {
    # flags with [?] are uncertain usage
    'heavy_armor':          'Heavy armor',
    'light_armor':          'Light armor',
    'chance_find_gold_2x':  '2x chance find gold',
    'chance_find_gold':     'Chance find gold',
    'cast_multiple_spells': 'Cast multiple spells',
    'cast_one_spell':       'Cast one spell',
    'double_attacks':       'Double attacks',
    'mechanical':           'Mechanical being',
    'increase_strength':    'Increase strength',
    'evil':                 'Evil',
    'good':                 'Good',
    're_animates':          'Re-animates',
    'cast_turn_to_stone':   'Cast turn to stone',
    'poisonous_attack':     'Poisonous attack',
    'diseased_attack':      'Diseased attack',
    'experience_drain':     'Experience drain',
    'magic_resistant':      'Magic resistant',
    'appears_unaffected':   'Appears unaffected [?]',
    'fire_attack':          'Fire attack',
    'no_gold':              'No gold on body',
    'multiple_monsters':    'Multiple monsters',
    'no_article':           'No article (suppress THE) [?]',
    'charmable':            'Charmable',
    'has_quote':            'Has quote',
}

monster_sizes = {
    1: 'huge',
    2: 'large',
    3: 'big',
    4: 'man_sized',
    5: 'short',
    6: 'small',
    7: 'swift',
}

all_monster_keys = [v for _, v in monster_flags]

empty_monster_flags = {k: False for k in all_monster_keys}

def load_monsters(path: str) -> list[dict]:
    with open(path) as f:
        monsters = json.load(f)
    logging.info("Loaded %d monsters from '%s'", len(monsters), path)
    return monsters


def get_monster(monsters: list[dict], number: int) -> dict | None:
    """Look up a monster by its 'number' field.

    monsters.json's numbering has gaps (e.g. #135 doesn't exist), so a
    monster's position in the list doesn't equal number - 1 -- callers must
    not index the list positionally by a room's stored monster number.
    """
    return next((m for m in monsters if m.get('number') == number), None)


def save_monsters(monsters: list[dict], path: str):
    with open(path, 'w') as f:
        json.dump(monsters, f, indent=4)
    logging.info(f"Saved %d monsters to '%s'.", len(monsters), path)


def load_quotes(path: str) -> dict[int, str]:
    """Load monster_quotes.json into {number: quote} (SPUR.MISC4.S monster.quote file)."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d quotes from '%s'", len(data), path)
        return {q['number']: q['quote'] for q in data}
    except FileNotFoundError:
        logging.warning("'%s' not found, quotes unavailable.", path)
        return {}
