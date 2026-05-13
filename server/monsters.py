import json
import logging

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


def load_monsters(path: str) -> list[dict]:
    with open(path) as f:
        monsters = json.load(f)
    logging.info("Loaded %d monsters from '%s'", len(monsters), path)
    return monsters


def save_monsters(monsters: list[dict], path: str):
    with open(path, 'w') as f:
        json.dump(monsters, f, indent=4)
    print(f"Saved {len(monsters)} monsters to '{path}'.")
