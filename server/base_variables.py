from base_classes import PlayerStat, PronounType, Gender

# Step 1: Create a consolidated data dictionary.
# The key is the PlayerStat member.
# The value is another dictionary containing:
# 1) the statistic name tuple in the form ("long name", "short name")
# 2) the display name and the phrases to display if the player's Expert Mode is disabled.
STAT_DATA = {
    PlayerStat.CHR: {
        "name": ("Charisma", "Cha"),
        "phrases": ("less influential", "more influential")
    },
    PlayerStat.CON: {
        "name": ("Constitution", "Con"),
        "phrases": ("less hearty", "more hearty")
    },
    PlayerStat.DEX: {
        "name": ("Dexterity", "Dex"),
        "phrases": ("less agile", "more agile")
    },
    PlayerStat.INT: {
        "name": ("Intelligence", "Int"),
        "phrases": ("dumber", "smarter")
    },
    PlayerStat.STR: {
        "name": ("Strength", "Str"),
        "phrases": ("weaker", "stronger")
    },
    PlayerStat.WIS: {
        "name": ("Wisdom", "Wis"),
        "phrases": ("less wise", "wiser")
    },
}

PRONOUN_MAP = {
    Gender.MALE: {
        PronounType.SUBJECTIVE: "he",
        PronounType.OBJECTIVE: "him",
        PronounType.POSSESSIVE_ADJECTIVE: "his",
        PronounType.POSSESSIVE_PRONOUN: "his",
        PronounType.REFLEXIVE: "himself",
    },
    Gender.FEMALE: {
        PronounType.SUBJECTIVE: "she",
        PronounType.OBJECTIVE: "her",
        PronounType.POSSESSIVE_ADJECTIVE: "her",
        PronounType.POSSESSIVE_PRONOUN: "hers",
        PronounType.REFLEXIVE: "herself",
    },
}
