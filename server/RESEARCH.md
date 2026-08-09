# RESEARCH.md — real-world history behind TADA's names and places

TADA's ally roster and dungeon geography borrow names from real history
alongside the pop-culture references (Batman, Star Wars, etc.). This doc
collects what digging into those names turned up, for two reasons: it's
genuinely interesting, and it stops the same research from having to
happen twice. Individual `allies.json` entries with a real-world basis
point back here via their `comment` field.

## Julia Felix — Pompeii

**Ally:** `JULIA FELIX` (allies.json)

Julia Felix was a real, well-documented figure from Pompeii. She owned a
large property on the Via dell'Abbondanza — the *Praedia of Julia
Felix* — that included a private bath complex, shops, and dining rooms.
After the earthquake of AD 62 badly damaged much of the city (17 years
before Vesuvius finished the job), she had the complex repaired and
opened it for public rent, since the city's own public baths were still
out of commission. A painted advertisement for the rental survived and
was excavated intact:

> "In the property of Julia Felix, daughter of Spurius, to let: an
> elegant bath suitable for respectable people, shops with rooms over
> them, and upper-floor apartments..."

She's one of the relatively rare named, non-elite Roman women visible in
the archaeological record specifically *as* a businesswoman — the
property was hers, not her husband's or father's, which is part of why
she keeps coming up in scholarship on women's economic life in the Roman
world.

## Dura-Europos — the "great wall of Dura"

**Ally:** `TRAJAN OF DURA` (allies.json)
**In-game:** `level_4.json`/`level_6.json` room descriptions ("The great
wall of Dura is vaguely visible to the east..."), `messages.json`'s
"DURA-EUROPOS PRESENTS" intro banner, `bar/bar_none.py`'s `_LORE`
keyword set (Guss gets nervous if you say "DURA" to him)

Dura-Europos was a real fortress city on the west bank of the Euphrates,
in what's now eastern Syria. Its history runs through three empires:

- **Founded** around 303 BC by the Seleucid Empire (Alexander's
  successors) as a military garrison/trading post.
- **Parthian era** — captured by the Parthian Empire around 113 BC,
  who held it for roughly two and a half centuries as a frontier and
  caravan city, absorbing a mix of Greek, Semitic, and Iranian culture.
- **Roman era** — annexed by Rome in the AD 160s during the Parthian
  campaigns of Lucius Verus (co-emperor with Marcus Aurelius) and
  garrisoned as a Roman frontier fortress on the empire's eastern edge.
  The historical **Trajan** (emperor AD 98–117, `TRAJAN OF DURA`'s
  likely namesake) campaigned against Parthia in this same region a
  few decades earlier, though Dura's formal Roman garrison came after
  his reign.
- **Destroyed** in AD 256/257 by a Sasanian Persian siege under Shapur
  I. The Romans dug in the city's own streets to build defensive
  ramparts against Sasanian siege-mining — and in doing so, buried
  entire buildings under rubble intact. The city was abandoned and
  never resettled.

That accidental burial is why Dura-Europos is sometimes called *"the
Pompeii of the Syrian desert"* — same mechanism as Pompeii (sudden burial
that freezes a moment in time), different disaster. Between that and
Julia Felix, TADA's ally roster has an unintentional matched set of
"cities preserved by catastrophe."

**What makes Dura-Europos famous archaeologically** is the density of
exceptionally preserved religious buildings found within its walls,
spanning three faiths side by side:

- **The Dura-Europos church** (converted ~AD 233) — the oldest known
  Christian building identified with confidence, predating the later
  era of monumental church architecture after Christianity's legalization.
  Its baptistery room has the earliest known cycle of Christian wall
  paintings (the Good Shepherd, the healing of the paralytic, women at
  Christ's tomb).
- **The Dura-Europos synagogue** — remarkable for extensive figurative
  wall paintings depicting Hebrew Bible narrative scenes (Moses, Elijah,
  Esther, and more), which is unusual against the aniconic (image-avoiding)
  tradition seen in most other ancient synagogue remains.
- **A Mithraeum** — a temple to Mithras, the soldier's-cult mystery
  religion popular in the Roman military.

The site also produced the **Feriale Duranum**, a papyrus fragment
recording the official religious festival calendar of the Roman garrison
stationed there — a direct administrative record tying the city to Rome's
emperors and state religion, found nowhere else in this form.

## Why this is worth keeping around

SPUR's original ally roster already mixed myth (gods), fiction (movie/TV
characters), and music (real bands/singers) freely. Names like Julia
Felix and Dura-Europos show that mix reaches into real archaeology too —
not obviously fictional on the surface, easy to miss unless you go
looking. Worth checking any other roster/room name that looks like it
*might* be real before assuming it's invented.
