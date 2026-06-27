# patch_monster_descriptions.py
import json

DESCRIPTIONS = {
    # RINGWRAITH
    70:  "A cloaked figure of dread, neither living nor dead. Once a great king, now bound in eternal servitude to a dark will.",
    # GOLLUM
    71:  "A wretched, skulking creature, thin as a rail and pale as fish-belly. His wide eyes gleam with desperate hunger.",
    # OLD MAN
    120: "A weathered traveler, his eyes sharp despite his years. He seems to know more about this place than he lets on.",
    # TIN MAN
    122: "A man-shaped figure of polished metal, joints squeaking with every movement. He seems to be looking for something.",
    # SCARECROW
    123: "A gangly figure of straw and burlap, wobbling on unsteady legs. His painted grin never quite reaches his eyes.",
    # COWARDLY LION
    124: "A great mane frames a surprisingly anxious face. He startles at small sounds but holds his ground regardless.",
    # OZ
    125: "A pompous little man surrounded by smoke and bluster. His authority seems to rest entirely on your believing in it.",
    # LITTLE DOG
    127: "A small, scrappy terrier, more bark than bite -- though it eyes you with surprising suspicion.",
    # ADAM & EVE
    128: "Two figures, wide-eyed and newly aware of the world, regarding everything around them with cautious wonder.",
    # MUNCHKINS
    130: "A cheerful crowd of small folk who speak all at once and seem delighted to have a visitor for a change.",
}

with open('monsters.json') as f:
    monsters = json.load(f)

for m in monsters:
    m.setdefault('description', None)
    if m['number'] in DESCRIPTIONS:
        m['description'] = DESCRIPTIONS[m['number']]

with open('monsters.json', 'w') as f:
    json.dump(monsters, f, indent=4)

print(f"Patched {len(DESCRIPTIONS)} descriptions.")
