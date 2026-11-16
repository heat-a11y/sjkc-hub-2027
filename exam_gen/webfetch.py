"""Reading passages for Part 3, and the question builder that turns them into
comprehension MCQs.

Round 27 — the passages are a shipped KSSR story corpus.  The module used to
download five Project Gutenberg books (Aesop's Fables, Kipling's *Just So
Stories*, the Velveteen Rabbit, McGuffey's First Reader, *The Tale of Peter
Rabbit*) and scaffold questions from them.  That corpus is gone: it is
nineteenth-century English about kings, camels and rabbits, it sits in none of
the KSSR themes (Towns and Cities, Wild Life, Food and Health, Growing Up,
It's an Emergency, Cool Jobs ...), and it asks a pupil to recognise *velveteen*,
*corkscrew* and *frock* — words on no year ladder.  The KSSR gate added in
Round 26 refused nearly all of it and left Years 1-2 with no passage at all.

What serves Part 3 now is :mod:`exam_gen.kssr_stories`: short passages written
to the KSSR Semakan 2017 DSKP, one pack per year, each story inside that
year's CEFR cap and Part 3 word band, tagged with the RPT theme it belongs to,
and able to answer the official five questions with on-ladder options.  They
ship with the app, so generation is offline, fast and deterministic — the
Wikimedia-Commons photographs in :mod:`exam_gen.art` are the only live-network
feature left.

The machinery the rest of the app relies on is unchanged: a passage is ranked
A1/A2/B1 by :func:`exam_gen.bank.passage_band`, capped per year by
``data.PASSAGE_CEFR`` and ``data.PASSAGE_WORD_CEIL``, screened by
``data.BLOCKED_SUBSTRINGS``, and kept only when **every** word a pupil would
have to recognise is on the DSKP ladder for that year
(:func:`kssr_questions`).  :func:`_fact_questions` is also what the mined
textbook corpus uses to build its own questions, so it stays here.
"""

from __future__ import annotations

import json
import os
import re

from . import dskp, kssr_stories
from .models import MCQItem


#: The only sources this app will ever serve reading passages from, each with
#: who wrote it and under what terms.  ``fetch_source`` refuses anything not in
#: here, so the registry — not the caller — decides what enters the corpus.
#:
#: Round 27: these used to be five Project Gutenberg books (Aesop's Fables,
#: Kipling's *Just So Stories*, the Velveteen Rabbit, McGuffey's First Reader
#: and *The Tale of Peter Rabbit*).  All of it is nineteenth-century English
#: about kings, camels and rabbits; none of it sits in a KSSR theme, and the
#: words it asked a pupil to recognise (*velveteen*, *corkscrew*, *frock*) are
#: not on any year ladder.  The KSSR gate refused nearly all of it and left
#: Years 1-2 with no passage at all.  The registry now points at the shipped
#: KSSR story corpus (:mod:`exam_gen.kssr_stories`) — CEFR-banded, on-ladder,
#: theme-tagged, and needing no network.
SOURCES = {
    "KSSR Stories · Year 1": {
        "year": 1, "cefr": "A1",
        "publisher": "Penjana Kertas Ujian (written for the KSSR Semakan 2017 "
                     "DSKP, Year 1)",
        "licence": "shipped with the app (CC BY-SA 4.0)",
    },
    "KSSR Stories · Year 2": {
        "year": 2, "cefr": "A1",
        "publisher": "Penjana Kertas Ujian (written for the KSSR Semakan 2017 "
                     "DSKP, Year 2)",
        "licence": "shipped with the app (CC BY-SA 4.0)",
    },
    "KSSR Stories · Year 3": {
        "year": 3, "cefr": "A2",
        "publisher": "Penjana Kertas Ujian (written for the KSSR Semakan 2017 "
                     "DSKP, Year 3)",
        "licence": "shipped with the app (CC BY-SA 4.0)",
    },
    "KSSR Stories · Year 5": {
        "year": 5, "cefr": "A2",
        "publisher": "Penjana Kertas Ujian (written for the KSSR Semakan 2017 "
                     "DSKP, Year 5)",
        "licence": "shipped with the app (CC BY-SA 4.0)",
    },
    "KSSR Stories · Year 6": {
        "year": 6, "cefr": "B1",
        "publisher": "Penjana Kertas Ujian (written for the KSSR Semakan 2017 "
                     "DSKP, Year 6)",
        "licence": "shipped with the app (CC BY-SA 4.0)",
    },
}

#: A passage may only be used when at least this share of its content words is
#: acceptable vocabulary for the year (see :func:`kssr_coverage`).  It is
#: reported to the teacher as a per-source diagnostic; the hard gate is the
#: per-question one in :func:`kssr_questions`.
KSSR_MIN_COVERAGE = 0.6


NOUNS = {
    "animals": ["fox", "crow", "lion", "wolf", "goat", "donkey", "mouse", "mole",
                "tortoise", "hare", "monkey", "cat", "dog", "sheep", "horse", "hen",
                "cock", "bird", "ant", "bee", "fly", "frog", "fish", "snake", "eagle",
                "dove", "stag", "bull", "crane", "crab", "peacock", "pig", "duck",
                "cow", "tiger", "rat", "goose", "bat", "lamb", "hart", "kite",
                "nightingale", "raven", "sprat", "lioness", "hound", "mastiff",
                "whelp", "puppy", "kitten", "calf", "ewe", "bullock", "serpent",
                "viper", "swallow", "sparrow", "lark", "pigeon", "turtle", "camel",
                "crocodile", "whale", "seal", "dolphin", "otter", "squirrel",
                "leopard", "jackal", "hyena", "puma", "beast", "monster", "worm",
                "spider", "butterfly", "grasshopper", "cricket", "lobster", "shark",
                # Round 27: the KSSR everyday animals a primary passage is
                # actually about.  Every one is on the *Year 1* ladder, so a
                # Year 1 comprehension can ask about the chick in front of it.
                "chick", "elephant", "giraffe", "zebra", "parrot"],
    "people": ["man", "woman", "boy", "girl", "king", "queen", "farmer", "master",
               "servant", "traveller", "shepherd", "neighbour", "mother", "father",
               "sister", "brother", "child", "friend", "merchant", "hunter", "sailor",
               "son", "daughter", "wife", "husband", "owner", "trader", "cook",
               "baker", "butcher", "carpenter", "tailor", "shoemaker", "peasant",
               "huntsman", "judge", "thief", "robber", "giant", "prince", "princess",
               "slave", "beggar", "stranger", "guest", "host", "doctor", "teacher",
               "clerk", "porter", "miller", "woodman", "preacher", "widow",
               # Round 27: the KSSR everyday people (see ``animals``).
               "pupil", "singer", "postman",
               # Round 27: the roles an RPT theme actually puts in a story.  A
               # Year 5 text is full of a coach, a player or a nurse, and
               # without them those sentences carried no blankable noun at all.
               "player", "coach", "captain", "referee", "goalkeeper", "nurse",
               "pilot", "firefighter", "soldier", "officer", "journalist",
               "artist", "writer", "painter", "scientist", "engineer",
               "mechanic", "builder", "cleaner", "rider", "swimmer", "runner",
               "athlete", "champion", "lawyer", "dentist", "designer",
               "manager", "secretary", "receptionist", "fisherman",
               "librarian", "guide", "explorer", "inventor", "driver",
               "climber", "hiker", "diver", "volunteer", "carer",
               "shopkeeper", "caretaker", "veterinarian", "auditor",
               "worker", "passenger", "musician", "conductor", "owner"],
    "places": ["town", "city", "village", "forest", "field", "river", "mountain",
               "hill", "house", "street", "market", "farm", "road", "cave", "sea",
               "lake", "cottage", "garden", "grove", "wood", "tree", "nest", "den",
               "lair", "pond", "pool", "well", "fountain", "orchard", "meadow",
               "pasture", "barn", "stable", "mill", "shop", "shore", "bank",
               "sand", "cliff", "island", "desert", "valley", "swamp", "stream",
               "brook", "spring", "bridge", "tower", "castle", "palace", "temple",
               "yard", "marsh", "creek", "flood", "garden", "park", "harbour",
               # Round 27: the KSSR everyday places — the words a primary
               # passage's questions are actually about ("Where do the
               # children learn?" -> school, library, classroom).
               "school", "playground", "beach", "library", "kitchen", "bedroom",
               "bathroom", "zoo", "hospital", "clinic", "cafe", "cinema",
               "supermarket", "station", "hall", "building",
               # Round 27: the places a Year 6 RPT text is about.
               "cave", "warehouse", "factory", "mill", "mine", "workshop",
               "bakery", "quarry", "laboratory", "studio", "warehouse",
               "bridge", "station", "airport", "port", "harbour", "hut",
               "dam", "reservoir", "quarry", "pier", "terminal", "depot", "oven", "entrance"],
    "food": ["bread", "cheese", "meat", "grapes", "fig", "apple", "corn", "wheat",
             "honey", "milk", "egg", "cake", "fruit", "vegetables", "beans", "nuts",
             "food", "feast", "supper", "dinner", "breakfast", "lunch", "pie",
             "porridge", "oats", "barley", "grain", "seed", "berries", "olive",
             "pear", "peach", "melon", "carrot", "onion", "salt", "sugar", "jam",
             "cream", "butter", "sausage", "bacon", "soup", "stew", "broth",
             "bones", "roots", "leaves", "straw", "hay",
             # Round 27: the KSSR everyday food and drink.
             "rice", "noodles", "sandwich", "juice", "water", "biscuit",
             "chocolate", "sweet", "tea", "mango", "banana", "orange"],
}


def cache_path() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "exam-gen", "web_passages.json")


def _nowords(word: str) -> str:
    return re.sub(r"[^a-z]", "", word.lower())


def _norm(word: str) -> str:
    """Lowercase, strip punctuation, and drop a simple plural/possessive ending."""
    tok = _nowords(word)
    if tok.endswith("'s"):
        tok = tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and len(tok[:-1]) > 2:
        base = tok[:-1]
        if _class_for(base):
            tok = base
    return tok


def _class_for(tok: str) -> str | None:
    """Class of a token (exact, or a regular plural of a class word), or None.

    Round 27: only the exact headword resolved, so "the *boys* were late" and
    "the *leaves* fell" silently produced no question even though a plural is
    the same blankable noun.  A passage says "my friends" far more often than
    "my friend", so the regular singular forms are tried as well.
    """
    if not tok:
        return None
    for cls, words in NOUNS.items():
        if tok in words:
            return cls
    for stem in dskp._stems(tok):
        if stem == tok:
            continue
        for cls, words in NOUNS.items():
            if stem in words:
                return cls
    return None


ALL_NOUNS = tuple(w for cls in NOUNS.values() for w in cls)


def _fact_questions(passage: str, max_q: int = 5,
                    year: int | None = None) -> list[dict]:
    """Return raw MCQ templates for a passage, one per fact sentence.

    A fact sentence is one that mentions a known noun (animals / people /
    places / food).  The noun is blanked in the question stem and two same-class
    nouns are used as distractors, so every question is answerable straight from
    the passage.  A subject-position noun is preferred, but any sentence that
    contains a known noun anywhere counts, so short passages still yield enough
    questions.

    Hardening (Round 12/S1): distractors are same-class nouns that never appear
    anywhere in the passage (so no option is duplicated by the text), the option
    display is deduplicated case-insensitively, and the random generator is
    seeded from the sentence so results are deterministic across runs.

    Round 26: pass ``year`` and the question itself obeys the KSSR ladder —
    only an on-list noun is ever blanked, and the distractors must be on-list
    too, so a passage that slipped past the band gate still cannot ask a pupil
    to recognise an off-curriculum word.
    """
    import random as _rnd
    import zlib
    toks = set(_nowords(w) for w in re.findall(r"[A-Za-z]+", passage.lower()))
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", passage) if s.strip()]
    qs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for s in sents:
        if len(qs) >= max_q:
            break
        ws = s.split()
        if len(ws) < 4 or len(ws) > 40:
            continue
        low = [_nowords(w) for w in ws]
        class_of = [_class_for(t) for t in low]
        known = [i for i in range(len(low)) if class_of[i]]
        if not known:
            continue
        idx = next((i for i in known if i <= 1), known[0])
        target = _norm(ws[idx])
        if not target:
            continue
        if year is not None and not dskp.allowed(target, year):
            continue
        key = (target, " ".join(low[: min(len(low), 9)]))
        if key in seen:
            continue
        seen.add(key)
        cls = class_of[idx]
        distractors = [w for w in NOUNS[cls]
                       if _norm(w) != target
                       and _nowords(w) not in toks and w != target]
        if year is not None:
            distractors = [w for w in distractors if dskp.allowed(w, year)]
        if len(distractors) < 2:
            continue
        rng = _rnd.Random(zlib.crc32(s[:60].encode("utf-8", "ignore")))
        picks = rng.sample(distractors, 2)
        opts = [target] + picks
        rng.shuffle(opts)
        # Round 19: options are displayed in lower case (the answer sits
        # mid-sentence); the old `.title()` casing turned "house" into "House"
        # next to lowercase "cat"/"hay", which the teacher's papers never do.
        display, seen_disp = [], set()
        for o in opts:
            d = o
            if d.casefold() in seen_disp:
                continue
            seen_disp.add(d.casefold())
            display.append(d)
        ans = display.index(target)
        stem_before = " ".join(ws[:idx])
        stem_after = " ".join(ws[idx + 1:])
        if stem_before:
            stem = f"{stem_before} ______ {stem_after}"
        else:
            stem = f"______ {stem_after}"
        stem = stem.strip()
        # Round 18: blanking the LAST word of a sentence dropped the final
        # punctuation, leaving stems that hang ("Greg, let's go to the ____").
        # Carry the sentence's terminal period/question mark over when present.
        if (len(stem_after) == 0 and len(ws[idx]) > 1
                and ws[idx][-1] in ".!?") and not re.search(r"[.!?]\s*$", stem):
            stem += ws[idx][-1]
        qs.append({"stem": stem, "opts": display, "ans": ans,
                   "ans_text": target, "cls": cls})
    return qs


def fetch_source(name: str) -> list[str]:
    """Return the passages of one registered story pack.

    The registry is the gate: a name that is not in :data:`SOURCES` raises
    ``KeyError`` rather than being turned into a request, so a caller cannot
    widen the corpus by passing a URL through this function.  Round 27 removed
    the network entirely — the packs ship with the app (see
    :mod:`exam_gen.kssr_stories`), so this never blocks and a paper is
    identical on a plane and on a desktop.  Wikimedia-Commons photographs
    (:mod:`exam_gen.art`) are the app's only live-network feature.
    """
    rec = SOURCES[name]
    return [s["text"] for s in kssr_stories.STORIES.get(rec["year"], [])]


def update_cache(sources: list[str] | None = None, keep_existing: bool = True
                 ) -> dict:
    """Fetch/refresh passage cache.  Passages keep their paired question sets.

    Each passage stores its questions twice: ``qs`` for the generic question
    builder, and ``qs_by_year`` for the KSSR ladder of every supported year, so
    a Year 1 paper is only ever offered options a Year 1 pupil knows.  The
    extra key is additive — a cache written before Round 26 still loads and is
    simply filtered more strictly.

    Offline-safe (AGENTS.md): a source that fails to download is skipped, so a
    refresh on a plane keeps the passages already on disk instead of wiping
    them.
    """
    from . import data as D
    cache = {}
    if keep_existing and os.path.exists(cache_path()):
        try:
            with open(cache_path(), encoding="utf-8") as fh:
                cache = json.load(fh)
        except Exception:
            cache = {}
    years = [y for y in (1, 2, 3, 5, 6) if y in D.PASSAGE_CEFR] or [5, 6]
    for name in sources or list(SOURCES):
        if name not in SOURCES:
            continue
        try:
            texts = fetch_source(name)
        except Exception:
            continue
        passages = []
        rec = SOURCES[name]
        for story in kssr_stories.STORIES.get(rec["year"], []):
            t = story["text"]
            row = {"text": t, "qs": _fact_questions(t),
                   # Round 27: a story knows which year and which RPT theme it
                   # was written for.  Carrying them on the row lets the
                   # generator prefer a Year 1 pack for a Year 1 paper instead
                   # of any story that merely shares the A1 band.
                   "year": rec["year"], "theme": story.get("theme", ""),
                   "title": story.get("title", ""),
                   "cefr": rec.get("cefr", "")}
            by_year = {str(y): _fact_questions(t, year=y) for y in years}
            row["qs_by_year"] = {y: qs for y, qs in by_year.items() if qs}
            passages.append(row)
        passages = [p for p in passages if p["qs"]]
        if passages:
            cache[name] = passages
    try:
        os.makedirs(os.path.dirname(cache_path()), exist_ok=True)
        with open(cache_path(), "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
    except Exception:
        pass
    return cache


def load_cache() -> dict:
    if not os.path.exists(cache_path()):
        return {}
    try:
        with open(cache_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def stats() -> dict:
    cache = load_cache()
    total = sum(len(v) for v in cache.values())
    return {"sources": len(cache), "passages": total,
            "available": bool(total), "libreoffice": True}


def _content_words(text: str) -> list[str]:
    """The words a pupil is actually asked about.

    Three things are dropped because they carry no curriculum signal:
    function words and the closed vocabularies (scoring prepositions would push
    every English passage over the line), and proper nouns — a passage's
    characters' names are not vocabulary, and "Aisyah" is not a finding.  What
    is left is the lexis a SJK pupil must already know.
    """
    raw = str(text or "")
    proper = {t for t in re.findall(r"(?<![.!?]\\s)(?<!^)\\b[A-Z][a-z']+", raw)}
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", raw):
        n = dskp.normalise(w)
        if len(n) < 3 or n in dskp.FUNCTION or n in dskp.CLOSED or n in proper:
            continue
        out.append(n)
    return out


def kssr_coverage(text: str, year: int) -> float:
    """Share of a passage's content words that are on the DSKP ladder for
    ``year`` (0.0-1.0).

    This is a *diagnostic*, not the gate.  The ladder is a vocabulary target
    list of a few hundred words, so honest classroom prose still scores well
    under 1.0 and a real passage can never reach a high bar; what the gate
    must protect is the word a pupil is actually asked to recognise, and that
    is checked question by question in :func:`kssr_questions`.
    """
    words = _content_words(text)
    if not words:
        return 0.0
    ok = sum(1 for w in words if dskp.allowed(w, year))
    return ok / len(words)


def kssr_questions(passage: dict, year: int, count: int = 5) -> list[dict]:
    """The passage's questions a pupil of ``year`` may be asked.

    A question survives only when the blanked answer *and* every option is
    acceptable vocabulary for the year, and the passage must still be able to
    supply ``count`` of them — the official Part 3 size.  An off-curriculum
    word is never offered as the thing a child has to recognise, which is the
    promise the CEFR band alone could not keep.

    A passage refreshed by :func:`update_cache` carries a ``qs_by_year`` set
    built on the year's ladder, so the question is already clean.  A cache
    written before Round 26 has only the year-agnostic ``qs``, and those are
    filtered here instead — which is strict enough that such a passage is
    usually refused, so a refresh is what restores a source to service.
    """
    out = []
    rows = (passage.get("qs_by_year") or {}).get(str(int(year)))
    for q in (rows or passage.get("qs") or []):
        opts = [str(o) for o in (q.get("opts") or [])]
        if len(opts) < 2:
            continue
        # A cache written before Round 26 carries no ``ans_text``; the answer is
        # the option at ``ans``, so read it from there rather than dropping
        # every question in an old cache.
        ans = q.get("ans")
        answer = str(q.get("ans_text") or "").strip()
        if not answer and isinstance(ans, int) and 0 <= ans < len(opts):
            answer = opts[ans].strip()
        if not answer:
            continue
        if not all(dskp.allowed(o, year) for o in opts):
            continue
        if not dskp.allowed(answer, year):
            continue
        out.append(q)
        if len(out) >= count:
            break
    return out


def _passes_year_gate(year: int, text: str) -> bool:
    """True when a passage passes the year's CEFR band + word ceiling +
    content blocklist (Round 12/S2).  The KSSR vocabulary contract is applied
    per question by :func:`kssr_questions`."""
    from . import bank, data as D
    if year not in D.PASSAGE_CEFR:
        return True
    if len(str(text).split()) > D.PASSAGE_WORD_CEIL[year]:
        return False
    if bank._passage_blocked(str(text)):
        return False
    rank = bank._BAND_RANK
    return (rank[bank.passage_band(str(text))]
            <= rank[D.PASSAGE_CEFR[year]])


def passages_for_year(cache: dict, year: int, count: int = 5) -> list[dict]:
    """Every cached passage a pupil of ``year`` may be shown.

    The cache is stored per source, so this is also the single place that
    flattens it for the generator.  A passage is served only when it clears
    the band gate *and* can supply ``count`` questions the DSKP allows, so a
    Year 1 paper can never be handed a passage that asks about a word off the
    Year 1 ladder.
    """
    year = int(year)
    out = []
    for rows in (cache or {}).values():
        for p in (rows or []):
            if not isinstance(p, dict):
                continue
            if not _passes_year_gate(year, p.get("text", "")):
                continue
            if len(kssr_questions(p, year, count)) < count:
                continue
            out.append(p)
    # Round 27: a passage written for the year comes first.  Year 1 and Year 2
    # share the A1 band, and without this a Year 1 paper was regularly handed a
    # Year 2 story (or a Year 3 one) that happened to clear the band gate.  A
    # lower year's story is still allowed as a fallback, so a thin year is never
    # left with nothing.
    mine = [p for p in out if p.get("year") == year]
    if mine:
        older = sorted((p for p in out if p.get("year") not in (None, year)),
                       key=lambda p: -int(p.get("year") or 0))
        return mine + older
    return sorted(out, key=lambda p: -int(p.get("year") or 0))


def usable_for_year(year: int) -> int:
    """Cached passages that a year could actually use for Part 3.  A source
    whose lexis is off the DSKP ladder counts as nothing here, which is how a
    teacher sees at a glance that it cannot serve that year."""
    return len(passages_for_year(load_cache(), int(year)))
