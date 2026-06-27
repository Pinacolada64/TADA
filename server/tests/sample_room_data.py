# fake data - make sure keys match those in Room class
# these are nice room descriptions, but not sure where they can be used

from old_server.common import K  # keys

roomsData = [
    {K.number: 1,
     K.name: 'Brookdale',
     K.desc: "You find yourself in the lovely upper left corner of the map. "
             "A small town nestles in the valley, a day's travel most likely. "
             "A dirt path leads south, and a babbling brook flows eastwards.",
     K.exits: {'s': 3, 'e': 2},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Claw'},

    {K.number: 2,
     K.name: 'Suntop Lookout',
     K.desc: "The sun shines brightly overhead. A dirt path meanders eastwards "
             "towards more tranquil scenery. A foreboding forest of dark, evil "
             "trees looms to the south.",
     K.exits: {'s': 4, 'w': 1},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Sword'},

    {K.number: 3,
     K.name: 'Near Castle',
     K.desc: "Behold, the castle Brackenwald can be spied beyond some "
             "rolling hills. Eastwards is the reputedly haunted forest.",
     K.exits: {'n': 1, 'e': 4},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Fist'},

    {K.number: 4,
     K.name: 'Dark Forest',
     K.desc: "The sun overhead filters dimly through twisted branches. There is "
             "a rusty sword on the ground--looks like you're going to need it.",
     K.exits: {'n': 2, 'w': 3},
     K.monster: 1,
     K.item: 0,
     K.weapon: 1,
     K.food: 0,
     K.alignment: '+'},
]

