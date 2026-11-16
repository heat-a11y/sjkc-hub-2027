"""JADUAL SPESIFIKASI UJIAN — the per-paper blue-print table (Round 28).

The ministry's exam-specification sheet is a *per-question* table: a row per
question carrying the skill, the text genre (Part 1) or lexico-grammar focus
(Part 2), the theme, the learning standard in the wording of the year being
printed, the Bloom column the item is plotted in, and the CEFR level, closed
by a summary (items per level, LOTS:HOTS, total marks).

``table(paper)`` builds that table from a *generated* paper, so the printed
JSU describes the paper that was actually set:

- one row per printed question, in the paper's own numbering;
- the standard's wording is the wording of that paper's year, so a Year 5
  paper never quotes the Year 6 sentence;
- the CEFR level is the level that question was given, and the objective
  items always fall into the official 5 / 15 / 5 (A2 Low / A2 Mid /
  Revise A2) mix;
- the LOTS:HOTS split is counted from the real questions, not asserted.

``issues(paper, table)`` then checks the table against the blue-print, so a
paper that has drifted is reported instead of printed.
"""

from __future__ import annotations

import re

from . import data as D

#: The ministry's own Part 1 genres and Part 2 focuses.
READING_GENRES = D.JSU_READING_GENRES
GRAMMAR_FOCUS = D.JSU_GRAMMAR_FOCUS

#: Bloom columns, in the order the sheet prints them.  The first two are LOTS
#: (low order thinking skills), the rest HOTS.
TAXONOMY = ("Remembering", "Understanding", "Applying", "Analysing",
            "Evaluating", "Creating")
LOTS_LEVELS = ("Remembering", "Understanding")

#: Skill name per part, for the years whose sheet we have not transcribed.
#: The official name is a property of the part's job, not of the year.
_SKILL_BY_JOB = {
    "vocab": "Short Text",
    "cloze": "Lexico-grammar Multiple Choice",
    "comprehension": "Longer Text Multiple Choice",
    "match": "Matching Multiple Texts",
    "words": "Word Completion",
}
_SKILL_BY_WRITING_STYLE = {
    "letter": "Short Communicative Message",
    "email": "Note Expansion",
    "sentences": "Guided Writing",
    "paragraph": "Note Expansion",
}

# ---------------------------------------------------------------------------
# Part 1: which genre a short text is
# ---------------------------------------------------------------------------
#: Every rule scores a stimulus; the highest score names the text.  A first
#: match would be wrong here: a poster for a book fair says "RM3" (an
#: advertisement signal) *and* "fair" (a poster signal), and an email's
#: "Subject:" line looks exactly like a speaker turn in a dialogue.
_GENRE_RULES = (
    ("Emails", re.compile(
        r"\b(from|to|subject|reply|forward|email|dear (sir|madam|mr|ms)|"
        r"yours sincerely|kind regards|best wishes|regards)\b", re.I), 2),
    ("Text Messages (SMS) / Post-it Notes", re.compile(
        r"\b(sms|text message|whatsapp|telegram|post-it|posted note)\b", re.I), 3),
    ("Dialogues", re.compile(r"^[ \t]*[A-Z][a-z]{1,12}[ \t]*:", re.M), 2),
    ("Advertisements", re.compile(
        r"\b(sale|discount|off\b|rm\s?\d|price|buy now|offer|free\b|"
        r"order now|cash|voucher|%|worth only|cheap)\b", re.I), 2),
    ("Posters", re.compile(
        r"\b(competition|contest|concert|show|carnival|excursion|"
        r"audition|performance|exhibition|fair|campaign|project|trip|"
        r"shows?\b|screening|talks?\b|"
        r"jamboree|assembly|present your|slides|week|holiday|"
        r"champion|anniversary|open day)\b", re.I), 2),
    ("Labels / Signs / Charts", re.compile(
        r"\b(exit|entrance|toilet|library|staff only|no (smoking|running|"
        r"entry|parking)|danger|max\b|level \d|floor \d|opening hours|"
        r"price list|menu|lift|stairs)\b", re.I), 3),
    ("Notices", re.compile(
        r"\b(notice|please|kindly|remember|all pupils|all students|"
        r"parents|guardian|reminder|deadline|due date|assemble|"
        r"report to|collect)\b", re.I), 3),
    ("Notices", re.compile(
        r"(\d{1,2}[.:]\d{2}|\d{1,2}\s?(am|pm)|leaves|departs|returns|"
        r"arrive|attend|bring|due)\b", re.I), 1),
)
#: A notice is the fallback: it is the only Part 1 text type with no marker of
#: its own, and the ministry's first row is a notice.
_GENRE_FALLBACK = "Notices"

#: Words that end in a colon in a short text but are a letter's field label,
#: not a speaker turn -- otherwise every email reads as a dialogue.
_NOT_SPEAKERS = {"subject", "from", "to", "date", "time", "venue", "note",
                 "attention", "ref", "no", "tel", "fax", "for", "and", "the"}


def _words_focus(part, item) -> str:
    """Name the text type Part 5 really is.

    Criteria §4 calls Part 5 "word definitions, picture completion, or gap
    filling with spelling support", and the generator knows which of the
    three it built.  It used to print the literal string ``NIL`` here, which
    is not a text type and cannot go into a teacher document that goes to
    the school.
    """
    style = str(getattr(part, "style", "") or "")
    if style == "letter" or hasattr(item, "first"):
        # first letter given, one underscore per remaining letter
        return "Spelling (letter cues)"
    if any(getattr(it, "wordbox", None) for it in part.items):
        return "Picture / word box"
    clue = str(getattr(item, "clue", "") or "")
    stem = str(getattr(item, "stem", "") or "")
    if clue or "____" in stem:
        return "Word definitions"
    return "Word box"


def _genre(stimulus) -> str:
    """Which Part 1 text type a short stimulus is."""
    if isinstance(stimulus, (list, tuple)):
        text = "\n".join(str(s) for s in stimulus)
    else:
        text = str(stimulus or "")
    if not text.strip():
        return ""
    scores: dict = {}
    for genre, pattern, weight in _GENRE_RULES:
        hits = len(pattern.findall(text))
        if genre == "Dialogues":
            speakers = {m.group(0).strip().rstrip(":").lower()
                        for m in pattern.finditer(text)} - _NOT_SPEAKERS
            # a dialogue needs more than one speaker, and a whole turn
            hits = len(speakers) if len(speakers) > 1 else 0
        if hits:
            # a second mention of the same marker is weaker evidence than the
            # first: three clock times do not outvote "shows today"
            scores[genre] = scores.get(genre, 0) + weight * (2 if hits > 1
                                                            else 1)
    if not scores:
        return _GENRE_FALLBACK
    # a stable tie-break: the order the ministry lists its genres in
    for genre, _, _ in _GENRE_RULES:
        if scores.get(genre) == max(scores.values()):
            return genre
    return max(scores, key=lambda g: scores[g])


# ---------------------------------------------------------------------------
# Part 2: which lexico-grammar focus a blank is
# ---------------------------------------------------------------------------
#: Checked in order, so a word that could be read two ways is read the way the
#: part is testing it: a form of *be* is an auxiliary, a possessive is a
#: determiner, a bare personal pronoun is a pronoun.
_GRAMMAR_RULES = (
    ("Modal Verbs", {"can", "could", "will", "would", "shall", "should",
                     "may", "might", "must", "ought"}),
    ("Auxiliary Verbs", {"is", "are", "was", "were", "am", "be", "been",
                         "being", "do", "does", "did", "have", "has", "had",
                         "n't"}),
    ("Determiners", {"a", "an", "the", "this", "that", "these", "those",
                     "some", "any", "each", "every", "his", "her", "its",
                     "their", "our", "my", "your", "no", "many", "much",
                     "most", "few", "little", "all", "both", "half",
                     "either", "neither", "another", "such"}),
    ("Pronouns", {"he", "she", "it", "we", "they", "i", "you", "him", "them",
                  "me", "us", "mine", "ours", "theirs", "who", "whom",
                  "which", "what"}),
    ("Prepositions", {"in", "on", "at", "to", "from", "with", "for", "of",
                      "by", "under", "over", "between", "into", "near",
                      "beside", "behind", "above", "through", "during",
                      "before", "after", "until", "across", "along",
                      "around", "upon", "off", "out", "up", "down",
                      "without", "towards", "toward", "against", "among",
                      "onto", "inside", "outside", "past", "like"}),
    ("Conjunctions", {"and", "but", "or", "so", "because", "if", "when",
                      "while", "although", "though", "unless", "than",
                      "then", "as", "since", "whenever"}),
    ("Adverbs", {"quickly", "slowly", "carefully", "loudly", "happily",
                 "sadly", "suddenly", "very", "always", "often",
                 "sometimes", "never", "here", "there", "today",
                 "yesterday", "tomorrow", "now", "well", "hard", "fast",
                 "together", "again", "already", "still", "soon", "late",
                 "early", "away", "back"}),
)
#: A blank answered with one of these can only be filled by reading the sense
#: of the whole sentence, which is what the ministry calls Applying.
_FUNCTION_WORDS = {w for _, words in _GRAMMAR_RULES for w in words}

#: The ministry plots eight lexico-grammar focuses under Part 2.  Our blanks
#: are very often *content* words -- the passage tests 3.2.3, guessing a word
#: from context -- and mislabelling a content word as one of the ministry's
#: grammar focuses would be a lie, so a content word is reported by its real
#: class instead, and "Lexis" when the sentence alone cannot tell us.
EXTRA_FOCUS = ("Nouns", "Verbs", "Adjectives", "Lexis")
_ADJECTIVES = {
    "happy", "sad", "angry", "tired", "hungry", "thirsty", "busy", "funny",
    "scared", "quiet", "loud", "clean", "dirty", "tidy", "messy", "big",
    "small", "tall", "short", "long", "hot", "cold", "warm", "cool", "new",
    "old", "good", "bad", "nice", "kind", "fast", "slow", "early", "late",
    "delicious", "interesting", "exciting", "important", "difficult",
    "favourite", "favorite", "careful", "safe", "busy", "free", "full",
    "strong", "weak", "heavy", "light", "fresh", "rich", "poor",
}
_NOUN_SUFFIX = ("tion", "sion", "ment", "ness", "ity", "ship", "ance", "ence",
                "ist", "age", "dom", "er", "or")
_ADJECTIVE_SUFFIX = ("ful", "less", "able", "ible", "ous", "ive", "ish",
                     "ent", "ant", "ic", "al")


def _focus_for_word(word: str, stem: str = "") -> str:
    """The lexico-grammar focus a Part 2 blank tests."""
    w = re.sub(r"[^a-z']", "", str(word or "").lower())
    if not w:
        return ""
    for focus, words in _GRAMMAR_RULES:
        if w in words:
            return focus
    if w.endswith("ly") and len(w) > 4:
        return "Adverbs"
    if w in _ADJECTIVES or w.endswith(_ADJECTIVE_SUFFIX):
        return "Adjectives"
    if w.endswith(("ing", "ed")) and len(w) > 4:
        return "Verbs"
    if w.endswith(_NOUN_SUFFIX):
        return "Nouns"
    # A bare content word: the token *before* the gap says which it is.  After
    # a determiner or a possessive the gap was the subject, so it is a noun
    # ("Ava's ______ cooks"); after a plain noun or a pronoun it is that
    # subject's verb ("Farid ______ his uncle", "He ______ the fruit").
    before = ""
    if stem:
        parts = re.split(r"_{2,}", str(stem))
        if len(parts) > 1 and parts[0].strip():
            before = re.sub(r"[^A-Za-z']", "",
                            parts[0].strip().split()[-1]).lower()
    if before in _DETERMINER_WORDS or before.endswith("'s"):
        return "Nouns"
    if before and w.endswith(("s", "es")):
        return "Verbs"
    return "Lexis"


_DETERMINER_WORDS = {"a", "an", "the", "his", "her", "its", "their", "our",
                     "my", "your", "this", "that", "these", "those", "some"}
# ---------------------------------------------------------------------------
# Bloom: what the question actually asks the pupil to do
# ---------------------------------------------------------------------------
#: Genuine inference: a question whose answer is *not* in the text.  A bare
#: "How long is the walk?" or "How do you travel to Penang?" asks for something
#: the text states, which is understanding, not analysing -- treating every
#: "how" and "why" as inference would push the whole paper over the blue-print.
_INFERENCE = re.compile(
    r"(why (must|might|would|should|could|do you think|is it|are they|"
    r"did|does|was|were)\b"
    r"|how (do|does|did) you (think|know|feel|understand|say)\b"
    r"|what (do|does|did) you (think|believe) (the|why)\b"
    r"|what (can|could|do) you (tell|deduce|infer|conclude|suggest)\b"
    r"|\b(infer|inferring|suggest|suggests|deduce|deducting|conclude|"
    r"concluding|justify|justify why|give a reason|explain why)\b)", re.I)
_MAIN_IDEA = re.compile(
    r"\b(main (idea|message|point)|in general|overall|"
    r"best (title|summary|description)|the (text|passage) is (about|mainly))\b",
    re.I)
_RECALL = re.compile(
    r"^\s*(who|what|where|when|how many|how much|how old|name the|"
    r"which of|list )\b", re.I)

#: How much each part contributes to a question's demand, before the stem is
#: read.  A cloze or a matching task is applied knowledge; spelling a word is
#: harder work than recalling a fact from a short text.
_DEMAND_BY_KIND = {"cloze": 1.0, "match": 1.0, "vocab": 0.8,
                   "comprehension": 1.2, "words": 1.4}

#: The official objective split is 5 / 15 / 5 -- one fifth, three fifths, one
#: fifth.  Years whose sheet we do not hold keep the same proportion at the
#: year's own band rather than inventing a blue-print.
_OFFICIAL_PROPORTION = (0.2, 0.6, 0.2)


def _exam(paper) -> str:
    """Which exam the JSU is written for: the paper's own exam type.

    This used to read the acronym out of the *source sheet's* name, on the
    reasoning that a Year 6 table quoting UASA standards should not say
    "UPSA".  But the sheet is the standard-setting source and is always
    named for the UASA, whichever exam the paper is -- so a mid-year paper
    printed "MID-YEAR EXAMINATION (UASA) YEAR 4".  The acronym names the
    exam sitting in front of the pupil, and only the paper knows that.
    """
    return D.EXAM_ABBR.get(str(paper.meta.get("exam_type", "upsa")).lower(),
                           "UPSA")


#: The table follows the paper's language, like the rest of the document: an
#: English paper may not carry a Malay heading (the Round 12 English-only
#: rule), and the ministry's own Malay sheet is not a reason to break it.
#: zh falls back to English, which is what the paper's own subject line does.
#: Every heading the two renderers print, so the .docx and the .html can
#: never drift apart or fall back to the wrong language.  Keyed by
#: ``(lang, exam_type)`` because the heading has to agree with the cover: a
#: mid-year UPSA paper whose JSU read "END-OF-SEMESTER" contradicted its own
#: first page.  ``data.EXAM_CAPTION`` already draws the same distinction.
#: zh falls back to English, which is what the paper's own subject line does.
TITLES = {
    ("bm", "upsa"): ("JADUAL SPESIFIKASI UJIAN PERTENGAHAN SESI AKADEMIK "
                     "({exam}) TAHUN {year} BAHASA INGGERIS"),
    ("bm", "uasa"): ("JADUAL SPESIFIKASI UJIAN AKHIR SESI AKADEMIK "
                     "({exam}) TAHUN {year} BAHASA INGGERIS"),
    ("en", "upsa"): ("TEST SPECIFICATION FOR THE MID-YEAR EXAMINATION "
                     "({exam}) YEAR {year} ENGLISH"),
    ("en", "uasa"): ("TEST SPECIFICATION FOR THE END-OF-YEAR EXAMINATION "
                     "({exam}) YEAR {year} ENGLISH"),
}
#: Every heading the two renderers print, so the .docx and the .html can
#: never drift apart or fall back to the wrong language.
LABELS = {
    "bm": {"no": "No.", "skill": "Kemahiran", "focus": "Fokus / Jenis Teks",
           "theme": "Tema", "standard": "Piawaian Pembelajaran",
           "taxonomy": "Taksonomi", "cefr": "CEFR", "marks": "Markah",
           "target": "sasaran jadual",
           "source": "Sumber", "total_marks": "Jumlah markah",
           "time": "Masa", "minutes": "minit", "questions": "Jumlah soalan",
           "objective_mix": "Taburan CEFR objektif"},
    "en": {"no": "No.", "skill": "Skill", "focus": "Focus / Text type",
           "theme": "Theme", "standard": "Learning standard",
           "taxonomy": "Taxonomy", "cefr": "CEFR", "marks": "Marks",
           "target": "blue-print",
           "source": "Source", "total_marks": "Total marks",
           "time": "Time", "minutes": "minutes", "questions": "Total questions",
           "objective_mix": "Objective CEFR spread"},
}


def _lang(paper) -> str:
    lang = str(paper.meta.get("lang", "bm") or "bm").lower()
    return lang if lang in {"en", "bm"} else "en"


def labels(paper) -> dict:
    return LABELS[_lang(paper)]


def title(paper) -> str:
    """The table's own heading, in the paper's language and exam type."""
    lang = _lang(paper)
    exam_type = str(paper.meta.get("exam_type", "upsa") or "upsa").lower()
    template = TITLES.get((lang, exam_type)) or TITLES[("en", exam_type)]
    return template.format(exam=_exam(paper), year=paper.year())


#: kept for the callers written before the table became public API
_title = title


def _band_words(year: int) -> str:
    return {"a1": "A1", "a2": "A2", "b1": "B1", "b2": "B2"}.get(
        D.PASSAGE_CEFR.get(year, "a1"), "A1")


#: Parts whose questions ask the pupil to *read* what a text says.  These are
#: the lower-order-thinking parts in the blue-print's 40% LOTS, and they are
#: the two parts that change with the stem: a genuine "why ...?" inference in
#: a comprehension question is higher-order work, an ordinary who/what
#: question is not.
_LOTS_PARTS = frozenset({1, 3})
#: Parts that ask the pupil to *apply* or *analyse*: the lexico-grammar
#: choices (P2), matching on meaning (P4) and word completion (P5) -- the
#: blue-print's 60% HOTS.
#:
#: Round 40 nearly rewrote this to ``{3, 4}`` on the strength of the criteria
#: prose ("HOTS in Parts 3, 4, 6, 7"), but ``JSU_Y4Y5Y6.xlsx`` plots every
#: question in its own Bloom column and says otherwise: P1 and P3 sit in
#: *Understanding*, P2 and P5 in *Applying*.  The sheet is the contract; the
#: checklist line is a summary of it and the two disagree.  The prose version
#: also failed the sheet's own 40:60 tally (14:13 instead of 10:17).
_HOTS_PARTS = frozenset({2, 4, 5})

#: The Bloom column the ministry sheet plots for each part, read off
#: ``JSU_Y4Y5Y6.xlsx`` column-by-column: Remembering/Understanding live under
#: G-L, Applying under M-O, Analysing under P-R.
_BLOOM_BY_PART = {1: "Understanding", 2: "Applying", 3: "Understanding",
                  4: "Analysing", 5: "Applying"}


def _taxonomy(part, item) -> str:
    """The Bloom column a question belongs in, read from the question itself.

    Round 40: the HOTS parts were all forced to "Applying", which mislabelled
    Part 4.  The ministry sheet plots all six matching questions in the
    *Analysing* column (P-R), because matching a description to a text means
    breaking the text down and deciding which half fits -- not recalling a
    rule and using it.
    """
    if part.kind == "writing":
        return "Creating"
    if part.num in _HOTS_PARTS:
        return _BLOOM_BY_PART.get(part.num, "Applying")
    stem = str(getattr(item, "stem", "") or getattr(item, "clue", "")
               or item.prompt or "")
    if _INFERENCE.search(stem):
        return "Analysing"
    if _MAIN_IDEA.search(stem):
        return "Understanding"
    if _RECALL.search(stem):
        return "Remembering"
    return "Understanding"


def _demand(part, item, qno: int, count: int, year: int) -> float:
    """A deterministic 0-2 estimate of how hard a question is to answer."""
    score = _DEMAND_BY_KIND.get(part.kind, 1.0)
    stem = str(getattr(item, "stem", "") or getattr(item, "clue", "")
               or item.prompt or "")
    if _INFERENCE.search(stem):
        score += 0.6
    elif _MAIN_IDEA.search(stem):
        score += 0.4
    if part.kind in ("words", "cloze"):
        from . import dskp
        answer = str(getattr(item, "ans_text", "") or
                     getattr(item, "answer", "") or "")
        first = re.sub(r"[^A-Za-z']", "", answer.split()[0]) if answer else ""
        if first and not dskp.allowed(first.lower(), year):
            score += 0.2
    # a stable spread so two questions of equal shape do not collapse into one
    score += 0.2 * (qno % max(count, 1)) / max(count, 1)
    return round(score, 4)


def _theme(paper, part) -> str:
    """The RPT theme this question is really about."""
    theme = str(paper.meta.get("theme") or "")
    specific = str(getattr(part, "source_theme", "") or "")
    if part.num == 3 and specific:
        return specific
    if part.kind == "writing" and specific:
        return specific
    return specific or theme or (D.RPT_THEMES.get(int(paper.year())) or [""])[0]


def _standards_for_part(paper, part) -> list[str]:
    """Every learning standard this part can assess, in the paper's year wording.

    A JSU row carries *one* standard, the way the ministry sheet does, so a
    part that assesses several is walked in order: question 1 takes the first,
    question 2 the second, and the list starts again.  The standard printed is
    always the wording for the paper's own year -- a Year 5 row must never
    quote the Year 6 sentence.
    """
    year = int(paper.year())
    jsu = D.JSU.get(year) or {}
    codes = list(((jsu.get("parts") or {}).get(part.num) or {})
                 .get("learning_standards") or [])
    _first: dict[str, str] = {}
    # Years 4-6 have the ministry's own JSU sheet, and the sheet words each
    # standard its own way -- the printed JSU must quote that wording, not the
    # DSKP ladder's.  Where the sheet lists several variants of one code (a
    # short text, one or two paragraphs, two or more) they are all offered, so
    # the part's questions walk the sheet's own menu.
    sheet = D.JSU_SHEET_STANDARDS.get(year, {}).get(part.num) or []
    if sheet:
        # The sheet lists one code several times, once per rung of the ladder
        # ("guided writing at sentence level" ... "independent writing"), and a
        # JSU row carries *one* standard.  The first wording of a code is the
        # rung that year is actually assessed at, so the list is collapsed to
        # one entry per code; printing 4.3.2 twice with two different sentences
        # in the same part is what made a Year 4 Part 5 look like it was
        # assessing a Year 5 standard.
        seen: list[str] = []
        for code, text in sheet:
            if code not in seen:
                seen.append(code)
                _first[code] = text
        return [f"{code} {_first[code]}" for code in seen]
    # Years 4-6 are assessed against the same ladder of codes -- the ministry
    # words each one differently for each year -- so a paper whose own sheet
    # we do not hold is still read off the ladder rather than off a guess.
    official = bool(codes) or year in (4, 5, 6)
    if not codes and official:
        for sheet in (D.JSU.get(6), D.JSU.get(5), D.JSU.get(4)):
            spec = ((sheet or {}).get("parts") or {}).get(part.num) or {}
            codes = list(spec.get("learning_standards") or [])
            if codes:
                break
    if not codes:
        # Year 1-3: the DSKP strand the part is built on, which is what those
        # papers are actually assessed against.
        return [f"{code} {D.DSKP_TITLES[code]}"
                for code in D.DSKP.get(year, {}).get(part.num, [])
                if D.DSKP_TITLES.get(code)]
    out: list[str] = []
    for code in codes:
        record = D.JSU_STANDARDS.get(code) or {}
        text = record.get(year) if official else None
        if not text:
            text = D.DSKP_TITLES.get(code, "")
        line = f"{code} {text}".strip()
        if line:
            out.append(line)
    return out


def _standard(standards: list[str], index: int) -> str:
    """The single standard a question row carries."""
    if not standards:
        return ""
    return standards[index % len(standards)]


#: Years 1-3 have no sheet of their own, and the Year 6 job names would
#: misdescribe their parts -- a Year 1 Part 1 is word recognition from a
#: picture, not a short text.
_SKILL_BY_JOB_LOWER = {
    "vocab": "Word Recognition",
    "cloze": "Lexico-grammar",
    "comprehension": "Reading Comprehension",
    "match": "Matching",
    "words": "Spelling",
}


def _skill(paper, part) -> str:
    """The skill column: the sheet's own name, or the year's own job name."""
    jsu_part = ((D.JSU.get(int(paper.year())) or {}).get("parts") or {}) \
        .get(part.num) or {}
    if jsu_part.get("skill"):
        return jsu_part["skill"]
    if part.kind == "writing":
        return _SKILL_BY_WRITING_STYLE.get(part.style, part.style.title())
    if jsu_part:
        return _SKILL_BY_JOB.get(part.kind) or part.kind.title()
    return _SKILL_BY_JOB_LOWER.get(part.kind) or part.kind.title()


#: What a writing part asks for, when the sheet does not spell the task out.
_WRITING_FOCUS = {"letter": "Letter: personal or formal message",
                  "email": "Email: personal message",
                  "speech": "Speech: spoken message",
                  "report": "Report: factual account"}


def _marks_per_q(part) -> float:
    try:
        return part.marks_per_q()
    except Exception:
        return 0.0


def _cefr_plan(year: int, n_objective: int) -> list[tuple[str, int]]:
    """The official level quotas, in the order they are handed out.

    The year 6 sheet fixes the objective mix at 5 A2 Low / 15 A2 Mid /
    5 Revise A2.  A year with no sheet keeps the same 1:3:1 proportion at that
    year's own band, so the table is never empty and never invents a mix the
    ministry has not stated.
    """
    jsu = D.JSU.get(year) or {}
    mix = jsu.get("cefr_mix")
    if mix and sum(mix.values()) == n_objective:
        order = ["A2 Low", "A2 Mid", "Revise A2"]
        return [(k, int(mix.get(k, 0))) for k in order if mix.get(k)]
    if mix and n_objective:
        # The sheet counts a fixed number of objective items; a paper built
        # for another year of the same format has a few more or fewer.  Keep
        # the sheet's own 1:3:1 ratio rather than dropping questions or
        # inventing a mix, and say so in the table summary.
        order = [k for k in ("A2 Low", "A2 Mid", "Revise A2") if mix.get(k)]
        total = sum(mix.values())
        scaled = {k: int(round(n_objective * mix[k] / total)) for k in order}
        drift = n_objective - sum(scaled.values())
        scaled[order[1] if len(order) > 1 else order[0]] += drift
        return [(k, scaled[k]) for k in order]
    band = _band_words(year)
    low, mid, high = _OFFICIAL_PROPORTION
    n_low = int(round(n_objective * low))
    n_high = int(round(n_objective * high))
    n_mid = n_objective - n_low - n_high
    return [(f"{band} Low", n_low), (f"{band} Mid", n_mid),
            (f"Revise {band}", n_high)]


def table(paper) -> dict:
    """Build the JSU for one generated paper.

    Returns a dict with ``rows`` (one per printed question), the ``cefr_mix``
    it handed out, the ``lots_hots`` split it counted, the official
    ``target`` and the ``total_marks`` the paper is worth.
    """
    year = int(paper.year())
    jsu = D.JSU.get(year) or {}

    rows = []
    for part in paper.parts:
        jsu_part = (jsu.get("parts") or {}).get(part.num) or {}
        skill = _skill(paper, part)
        theme = _theme(paper, part)
        standards = _standards_for_part(paper, part)
        for i, (qno, item) in enumerate(zip(part.qnos(), part.items)):
            stem = str(getattr(item, "stem", "") or getattr(item, "clue", "")
                       or item.prompt or "")
            if part.kind == "vocab":
                # Years 1-3 ask for a word from a picture, so there is no short
                # text to name a genre for.
                focus = _genre(getattr(item, "stimulus", None)) or (
                    "Pictures / Realia" if year <= 3 else "Short text")
            elif part.kind == "cloze":
                answer = (getattr(item, "ans_text", "")
                          or getattr(item, "answer", "") or "")
                focus = _focus_for_word(answer, stem) or "Sentence completion"
            elif part.kind == "comprehension":
                focus = getattr(part, "source_title", "") or "Linear"
            elif part.kind == "match":
                focus = "Linear"
            elif part.kind == "words":
                focus = _words_focus(part, item)
            else:
                focus = jsu_part.get("task") or _WRITING_FOCUS.get(part.style) \
                    or (getattr(item, "style", "") or part.style).title()
            rows.append({
                "qno": qno, "part": part.num, "skill": skill,
                "focus": focus, "theme": theme,
                "standard": _standard(standards, i),
                "taxonomy": _taxonomy(part, item),
                "level": "", "marks": _marks_per_q(part),
                "_demand": _demand(part, item, i, len(part.items), year),
            })

    # --- the CEFR level each objective question is given ------------------
    # An objective question is one the pupil answers by selecting; the two
    # writing parts are planned, not levelled against the item mix.
    writing_nums = {p.num for p in paper.parts if p.kind == "writing"}
    objective = [r for r in rows if r["part"] not in writing_nums]
    writing = [r for r in rows if r["part"] in writing_nums]
    order = sorted(objective, key=lambda r: (r["_demand"], r["qno"]))
    plan = _cefr_plan(year, len(objective))
    cursor = 0
    for level, quota in plan:
        for r in order[cursor:cursor + quota]:
            r["level"] = level
        cursor += quota
    for r in objective[cursor:]:           # a year that is not 20/60/20
        r["level"] = plan[-1][0]
    for r in writing:
        jsu_part = (jsu.get("parts") or {}).get(r["part"]) or {}
        r["level"] = jsu_part.get("cefr") or f"{_band_words(year)} Low"
    for r in rows:
        r.pop("_demand", None)

    mix: dict = {}
    for r in rows:
        mix[r["level"]] = mix.get(r["level"], 0) + 1
    writing_nums = {p.num for p in paper.parts if p.kind == "writing"}
    lots = sum(1 for r in rows
               if r["part"] not in writing_nums
               and r["taxonomy"] in LOTS_LEVELS)
    hots = sum(1 for r in rows if r["part"] in writing_nums
               or r["taxonomy"] not in LOTS_LEVELS)
    return {
        "year": year,
        "title": _title(paper),
        "source": jsu.get("title") or f"DSKP content standards, Year {year}",
        "source_file": jsu.get("source", ""),
        "rows": rows,
        "cefr_mix": dict(sorted(mix.items())),
        "objective_mix": dict(plan and {k: v for k, v in plan}),
        "lots_hots": (lots, hots),
        "target_lots_hots": (jsu.get("lots"), jsu.get("hots")),
        "total_marks": sum(p.marks for p in paper.parts),
    }


def issues(paper, t: dict | None = None) -> list[str]:
    """Every way a paper's JSU departs from the blue-print it was built to."""
    t = t or table(paper)
    out: list[str] = []
    paper_questions = paper.max_qno()
    if len(t["rows"]) != paper_questions:
        out.append(f"the table has {len(t['rows'])} rows for a paper of "
                   f"{paper_questions} questions")
    plan = dict(t.get("objective_mix") or {})
    if plan:
        writing_nums = {p.num for p in paper.parts if p.kind == "writing"}
        got = {}
        for r in t["rows"]:
            if r["part"] not in writing_nums:
                got[r["level"]] = got.get(r["level"], 0) + 1
        for level, want in plan.items():
            if got.get(level, 0) != want:
                out.append(f"the table gives {got.get(level, 0)} objective "
                           f"questions {level}; the blue-print says {want}")
    for r in t["rows"]:
        if not r["standard"]:
            out.append(f"Q{r['qno']} has no learning standard")
        if not r["level"]:
            out.append(f"Q{r['qno']} has no CEFR level")
    target = t.get("target_lots_hots")
    if target and all(target):
        lots, hots = t["lots_hots"]
        total = max(lots + hots, 1)
        want_lots = target[0] * total // 100
        # a question can move: one "why ...?" stem in a comprehension part is
        # higher-order work by the pupil's own reasoning, so the split is held
        # to a quarter of the target rather than to the exact count
        if abs(lots - want_lots) > max(1, want_lots // 4):
            out.append(f"LOTS:HOTS is {lots * 100 // total}:"
                       f"{hots * 100 // total}; the blue-print asks "
                       f"{target[0]}:{target[1]}")
    for issue in _writing_issues(paper):
        out.append(issue)
    return out


def _writing_issues(paper) -> list[str]:
    from . import bank
    return bank.jsu_issues(paper)


# ---------------------------------------------------------------------------
# terminal report
# ---------------------------------------------------------------------------

def report(paper) -> str:
    """The table as a teacher reads it on a terminal: one line per question,
    then the summary the ministry sheet closes with."""
    t = table(paper)
    lang = str(paper.meta.get("lang", "bm") or "bm").lower()
    L = LABELS[lang if lang in LABELS else "en"]
    out = ["", f"  {title(paper)}", "  " + "-" * 78,
           f"  {L['no']:>3}  {L['skill'][:22]:<22} {L['focus'][:20]:<20} "
           f"{L['taxonomy'][:11]:<11} {L['cefr']:<9} {L['marks']}"]
    for r in t["rows"]:
        marks = r["marks"]
        mark = f"{marks:g}" if float(marks).is_integer() else f"{marks:.1f}"
        out.append(f"  {r['qno']:>3}  {r['skill'][:22]:<22} {r['focus'][:20]:<20} "
                   f"{r['taxonomy'][:11]:<11} {r['level']:<9} {mark}")
    lots, hots = t["lots_hots"]
    tl, th = t.get("target_lots_hots") or (0, 0)
    line = f"  LOTS : HOTS = {lots} : {hots}"
    if tl and th:
        line += f"  ({L['target']}: {tl} : {th})"
    out += ["  " + "-" * 78, line]
    out.append("  " + "   ".join(f"{k}: {v}" for k, v in t["objective_mix"].items())
               + f"   ({L['objective_mix']})")
    out.append(f"  {L['questions']}: {len(t['rows'])}   "
               f"{L['total_marks']}: {t['total_marks']}")
    out.append(f"  {L['source']}: {t['source']}")
    bad = issues(paper, t)
    out += ["  " + "-" * 78,
            "  OFF BLUE-PRINT:" if bad else "  ON BLUE-PRINT ✓"]
    out += [f"    ! {i}" for i in bad]
    return "\n".join(out)
