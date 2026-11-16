"""Presets, part configuration and defaults for the exam generator.

Every year's UPSA/UASA paper follows the same official 7-part structure
seen in the SJKC UPSA 2026 Bahasa Inggeris papers (50 marks total):

    Part 1  [ 5]  contextual vocabulary  MCQ        (Q 1-5)
    Part 2  [ 4]  cloze passage          MCQ        (Q 6-9)
    Part 3  [ 5]  reading comprehension  MCQ        (Q 10-14)
    Part 4  [ 6]  matching A/B/C texts   MCQ        (Q 15-20)
    Part 5  [ 5]  definitions / words               (Q 21-25)
    Part 6  [10]  guided writing                    (Q 26+)
    Part 7  [15]  essay / email                     (last Q)
    TOTAL       50
"""

from __future__ import annotations

YEARS = (1, 2, 3, 4, 5, 6)          # supported SJKC year levels

# The official papers do not use one option marker throughout.  Years 1-2
# print "A)" while Years 3-6 print "A.", and a paper that mixes the two (or
# renders the wrong one for its year) looks like a photocopy error to pupils
# and markers.  Every renderer asks data.option_labels() rather than writing
# "ABC"[i] itself.
OPTION_MARKER = {1: ")", 2: ")", 3: ".", 4: ".", 5: ".", 6: "."}

_OPTION_LETTERS = "ABCDEFGHIJ"


def option_marker(year) -> str:
    """``")"`` for Years 1-2, ``"."`` for Years 3-6."""
    try:
        return OPTION_MARKER[int(year)]
    except (KeyError, TypeError, ValueError):
        return "."


def option_labels(n: int, year=None) -> list[str]:
    """``["A)", "B)", "C)"]`` for Years 1-2, ``["A.", ...]`` from Year 3."""
    marker = option_marker(year)
    return [f"{_OPTION_LETTERS[i]}{marker}" for i in range(n)]

# The official paper time.  Criteria §1 ("Key Exam Specifications"):
#
#   Year 1, Year 2, Year 3: 1 Hour (60 minutes) for UPSA / 1 Hour 15 Minutes
#   (75 minutes) for UASA
#   Year 5, Year 6: 1 Hour 15 Minutes (75 minutes) for both UPSA and UASA
#
# The time is a fact about (year, exam type), never about the year alone: a
# UASA lower-primary paper is a 75-minute paper, and the invigilator runs the
# clock off the line printed on the cover.  Year 4 has no line in the
# criteria and keeps the Year 5 format contract Round 36 established.
DURATION_MINUTES = {
    (1, "upsa"): 60, (1, "uasa"): 75,
    (2, "upsa"): 60, (2, "uasa"): 75,
    (3, "upsa"): 60, (3, "uasa"): 75,
    (4, "upsa"): 75, (4, "uasa"): 75,
    (5, "upsa"): 75, (5, "uasa"): 75,
    (6, "upsa"): 75, (6, "uasa"): 75,
}

#: The canonical wording of a duration, in the paper's own language.  It
#: always carries its own unit, so no caller has to append one -- which is
#: how the JSU header used to read "1 hour 15 minutes minutes".
_DURATION_WORDS = {
    "en": {"hour": "hour", "hours": "hours", "minute": "minute",
           "minutes": "minutes"},
    "bm": {"hour": "jam", "hours": "jam", "minute": "minit",
           "minutes": "minit"},
}


def duration(year: int, exam_type: str = "upsa") -> int:
    """The official paper time in minutes for ``(year, exam_type)``."""
    year = int(year)
    exam_type = str(exam_type or "upsa").lower()
    if (year, exam_type) not in DURATION_MINUTES:
        exam_type = "upsa"                      # unknown type: the UPSA rule
    return DURATION_MINUTES.get((year, exam_type),
                                DURATION_MINUTES.get((year, "upsa"), 60))


def duration_text(minutes: int, lang: str = "en") -> str:
    """``75 -> "1 hour 15 minutes"`` (en) / ``"1 jam 15 minit"`` (bm)."""
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        total = 0
    w = _DURATION_WORDS.get(str(lang or "en").lower(), _DURATION_WORDS["en"])
    if total <= 0:
        return ""
    hours, mins = divmod(total, 60)
    if not mins:
        return f"{hours} {w['hour'] if hours == 1 else w['hours']}"
    if not hours:
        return f"{mins} {w['minute'] if mins == 1 else w['minutes']}"
    return (f"{hours} {w['hour'] if hours == 1 else w['hours']} "
            f"{mins} {w['minute'] if mins == 1 else w['minutes']}")


#: The mid-year (UPSA) wording per year, kept for the callers that predate
#: the exam-type split: ``models.Paper.duration()`` and the GUI's duration
#: hint.  The UPSA string for Years 1-3 is 60 minutes, for Years 4-6 75.
DURATION = {y: duration_text(duration(y, "upsa"), "en") for y in YEARS}


# Round 13 follow-up: the cover shows one bilingual caption line UNDER the
# school crest — English · Malay · Chinese — with the exam acronym underneath.
EXAM_ABBR = {"upsa": "UPSA", "uasa": "UASA"}
EXAM_CAPTION = {
    "upsa": {"en": "Mid-Year Academic Session Test",
             "ms": "Ujian Pertengahan Sesi Akademik",
             "zh": "\u671f\u4e2d\u6d4b\u8bc4"},       # 期中测评
    "uasa": {"en": "End-of-Year Academic Session Test",
             "ms": "Ujian Akhir Sesi Akademik",
             "zh": "\u5e74\u7ec8\u6d4b\u8bc4"},       # 年终测评
}

SUBJECT = {"bm": "Bahasa Inggeris", "en": "English Language"}
SUBJECT_CODE = "013"

TOTAL = 50

# Difficulty levels — easy/medium/hard.  All remain SJKC-appropriate; the
# generator shifts the source-year level of the question pool (see bank.shift_year).
DIFFICULTIES = ("easy", "medium", "hard")


# ---------------------------------------------------------------------------
# vocabulary band guard (R7/R4): words a year's Part 1 pool must NOT contain
# ---------------------------------------------------------------------------
# bank._vocab_pool() drops any pool item whose stem/options mention these
# words, and bank.band_violations(year) audits the pools in the test suite.
# Lower years may not reach for the most advanced lexis; Years 5/6 own the
# full band and so have no entries.
VOCAB_BAND = {
    1: ("thermometer", "headmaster", "conductor", "campsite", "charity",
        "surgeon", "monsoon", "recycle", "dentist", "clinic", "telescope",
        "microscope", "surgery", "rainforest", "orangutan", "passengers"),
    2: ("surgeon", "monsoon", "recycle", "charity", "headmaster", "surgery",
        "dentist", "telescope", "microscope", "rainforest", "orangutan",
        "passengers", "conductor"),
    3: ("surgeon", "monsoon", "charity", "headmaster", "surgery", "telescope",
        "microscope", "rainforest", "orangutan", "passengers"),
    # Year 4 sits between Year 3 and Year 5, so it inherits Year 3's
    # A1+/Waystage ceiling: every word a Year 3 pool must avoid is too advanced
    # for Year 4 too.  "dentist" is the one Year 3 entry the official ladder
    # does not put out of reach by Year 4, so it is not carried over.
    4: ("surgeon", "monsoon", "charity", "headmaster", "surgery",
        "telescope", "microscope", "rainforest", "orangutan", "passengers"),
    5: ("surgery", "surgeon"),
    6: (),
}

# ---------------------------------------------------------------------------
# Part 1 confusion sets (Round 26).  An MCQ distractor is only fair when it is
# the same *kind* of thing as the answer: a pupil must be able to eliminate by
# reading the stimulus, not by noticing that the other two options are absurd.
# The official UASA papers do this — "restaurant / shop / hotel", "nasi lemak /
# fried noodles / grilled fishes", "the first 12 applicants / the last 12".
#
# A Part 1 pool item names one of these sets and draws its three options from
# it, so a hand-edit that mixes categories cannot reach a paper: the test
# ``test_part1_options_are_one_plausible_set`` checks every option against the
# declared set.
# ---------------------------------------------------------------------------
PART1_SETS = {
    "audition_item": {"a short poem", "a musical instrument", "a painting",
                      "a magic trick", "a dance routine"},
    "bring_pool": {"a cap and a towel", "a cap and a bottle of water",
                   "a towel and a hat", "a violin and a book",
                   "a helmet and a whistle"},
    "bring_robot": {"a laptop", "a robot", "a screwdriver set", "a torch",
                    "a bicycle"},
    "bin_colour": {"in the blue bin", "in the red bin", "in the grey bin",
                   "in the green bin", "in the yellow bin"},
    "canteen_meal": {"nasi lemak", "fried noodles", "grilled fishes",
                     "chicken rice", "satay", "nasi goreng"},
    "class_size": {"twenty-eight", "thirty-eight", "twenty-two", "twenty",
                   "twelve", "thirty"},
    "closed_day": {"on Monday", "on Friday", "on Sunday", "on Tuesday",
                   "on Saturday"},
    "club_activity": {"act out short stories", "play football matches",
                      "grow vegetables", "repair computers", "design posters",
                      "sing in a choir"},
    "club_place": {"first twelve applicants", "last twelve applicants",
                   "all the pupils", "any applicant", "only the teachers"},
    "date": {"12 March", "2 March", "12 April", "31 May", "20 May",
             "by 15 August", "by 1 July", "by 30 September", "14 August",
             "17 August"},
    "debate_topic": {"banning mobile phones in schools",
                     "building a new canteen", "planting trees by the river",
                     "starting a school choir", "holding a night market"},
    "delivery": {"on Friday", "on Wednesday", "on Sunday", "on Tuesday",
                 "on Monday"},
    "destination": {"next to the post office", "next to the railway station",
                    "behind the school canteen", "in the school library",
                    "at the town square"},
    "distance": {"3 km", "5 km", "13 km", "2 km", "30 km"},
    "duty_time": {"6.00 p.m.", "4.00 p.m.", "2.00 p.m.", "5.00 p.m.",
                  "6.45 p.m.", "7.30 a.m.", "8.15 a.m.", "1.00 p.m.",
                  "3.30 p.m.", "9.00 a.m."},
    "frequency": {"every twenty minutes", "every two hours", "once a day",
                  "once a week", "every ten minutes"},
    "hours": {"ten hours", "two hours", "twenty hours", "six hours",
              "eight hours", "five hours"},
    "job_choice": {"a pilot", "an astronaut", "a film director", "a baker",
                   "a nurse", "a farmer"},
    "keep_time": {"one week", "one month", "one year", "two weeks",
                  "fourteen days", "four days", "forty days", "ten days"},
    "menu_dish": {"rambutan pudding", "fried noodles", "nasi lemak",
                  "grilled fishes", "chicken rice", "satay"},
    "online_action": {"tell a teacher", "reply at once",
                      "meet the stranger alone", "block the message",
                      "call the stranger"},
    "pages": {"40 pages", "14 pages", "10 pages", "4 pages", "100 pages"},
    "place": {"in the canteen", "in the library", "in the playground",
              "at the Banquet Hall", "at the school field",
              "at the shopping centre", "by the swimming pool"},
    "price": {"RM1", "RM2", "RM2.50", "RM3", "RM4", "RM5", "RM5.50", "RM7",
              "RM8", "RM10", "RM18", "RM35", "RM40", "RM45", "RM60", "RM78",
              "RM80", "RM120", "RM180"},
    "provided": {"shin guards", "sports shoes", "water bottles",
                 "the robot parts", "the ingredients", "the notebook"},
    "register": {"through the link", "at the school gate", "by phone",
                 "in the school canteen", "at the post office",
                 "through the class teacher"},
    "river_problem": {"plastic bottles", "fallen leaves", "rain water", "sand",
                      "dead fish", "empty cans"},
    "signup": {"on the school website", "on the school notice board",
               "in the school canteen", "at the school office",
               "through the class teacher"},
    "small_number": {"two", "three", "four", "five", "six", "seven", "eight",
                     "ten", "twelve", "twenty"},
    "sport_event": {"the hundred metres final", "the tug of war",
                    "the relay race", "the high jump", "the football match"},
    "theme_contest": {"My Family Favourite Dish", "My School Playground",
                      "My Holiday Budget", "My Favourite Cartoon",
                      "My Dream Job"},
    "time_words": {"at half past eight", "at eight o'clock",
                   "at half past nine", "at nine o'clock",
                   "at quarter past eight"},
    "transport": {"by train", "by lorry", "by aeroplane", "by boat", "by bus"},
}

# ---------------------------------------------------------------------------
# legitimate capitalised option heads (Round 24): an MCQ option may legitimately
# START WITH a capital letter when it is a proper noun / festival / place /
# brand / acronym (the teacher's own papers print "Kuala Lumpur", "Chinese New
# Year" and LRT next to lowercase distractors).  The QC ``option-case`` rule
# must tolerate these — only incidental mixed-case styling (a common word
# capitalised for no reason, ``Wood`` vs ``stream``) is a hard failure.
# ---------------------------------------------------------------------------
LEGIT_OPTION_CAPS = frozenset({
    "LRT", "Ami", "Bangkok", "Cameron Highlands", "Chinese New Year",
    "Hari Merdeka", "Jia Wei", "KL", "Kuala Lumpur", "Mei", "Mooncake Festival",
    "Sea Games", "Singapore", "Teachers' Day",
})

# Round 26: ISO currency codes a price option may be written with.  Teacher
# papers print "RM180" beside lowercase distractors, which must not read as a
# mixed-case (shouted) option.
CURRENCY_CODES = frozenset({
    "AUD", "EUR", "GBP", "MYR", "NPR", "NZD", "RMB", "RM", "SGD", "USD",
})

# ---------------------------------------------------------------------------
# Round 11/F27: CEFR-banded web reading passages (Part 3 comprehension).
# ---------------------------------------------------------------------------
# Web passages (Project Gutenberg Aesop, Just So Stories, Velveteen Rabbit)
# are ranked A1/A2/B1 by counting ``PROFICIENT_TOKENS`` and capped per year by
# ``PASSAGE_CEFR`` (the highest band the year may read) and a word-count
# ceiling.  ``BLOCKED_SUBSTRINGS`` filters content that must never reach a
# paper regardless of band (racial/enslavement content etc.).  See
# ``bank.passage_band``.
# Year 4 opens KSSR Stage 2, so its ceiling is the same a2 band as Years 3
# and 5; only Year 6 reaches the b1 narrative register.
PASSAGE_CEFR = {1: "a1", 2: "a1", 3: "a2", 4: "a2", 5: "a2", 6: "b1"}

# Part 3 is a *reading-comprehension* passage, so it cannot be as short as the
# 20-30 word figure the criteria give for the paper as a whole: five 3-option
# questions need a text that carries facts.  The criteria's Part 3 row asks
# for a 50-150 word narrative/informational text, and the per-year rows ask
# for "very short" at Year 1 rising to "longer" at Year 6.  These bands keep
# every year inside the 50-150 rule while honouring the year-level trend.
#
# ``PASSAGE_WORD_BAND`` is what a *generated* Part 3 must sit inside.
# Year 4's band is interpolated between Year 3 and Year 5 and matches the
# school's own Y4 UASA 2025 paper, whose Part 3 runs to about 165 words.
PASSAGE_WORD_BAND = {1: (40, 80), 2: (45, 90), 3: (50, 100), 4: (65, 125),
                     5: (80, 150), 6: (90, 150)}

# Admissibility ceiling for a *candidate* passage (mined textbook chunk or
# reference prose) before it is offered to the generator.  It stays looser
# than the band on purpose: a long but simple text is still eligible, and the
# generator then trims it to the band rather than discarding the source.
PASSAGE_WORD_CEIL = {1: 80, 2: 100, 3: 150, 4: 180, 5: 220, 6: 300}

# Tokens that lift a reading text out of the lower-primary band (kept exact /
# lowercase, common -ed/-ing/-s inflections listed explicitly).  >=3 hits
# classify a passage as B1, 1-2 as A2, 0 as A1.  Curated from the Aesop /
# Just-So / Velveteen-Rabbit corpus plus the Round 11 offenders.
PROFICIENT_TOKENS = frozenset("""
acknowledged accustomed acquainted addressed admiration adorned admonished
advised afflicted alarmed aloft altogether amazed amusements ancient annoyed
anxiety approached arrogance ashamed attained attire avarice aversion banquet
beauteous befallen begged beguiled beheld beseeched bewildered bewilderment
boast boasted bountiful brink calamity captive cautioned chanced clamour
clambered clever comprehended concealed condescend conferred confined
conflagration confounded conjured conquered consoled conspired consumed
contemplated contended contrived conveyed covetous cowering cunning dainties
deceived deliberated demeanour descended despised destroyed destitute devoured
devouring disguise dismayed dispersed distressed doomed dreadful earnestly
elegance emboldened eminent employed encouraged endangered ensnared entangled
entreated envied esteemed eternity exasperated exclaimed exhorted exquisite
extinguished fatigued forbearance foretell fortitude fortunate fowls frail
frailty futile gasped generous gigantic glided gracious grudgingly hastened
haughtiness heedless hesitated humiliation imprisoned impudent incessant
incessantly incited indolent inert infamy ingratitude iniquity inquired
insolent intent interrupted intrepid inundated jest jostled lamented
lamentation languid lashed legion leisure listened magnificence malicious
malignant manipulates marvelled meadow meditated meddling menace meritorious
messenger miserable misfortune mischievous mode moored mournful murmured
neglect negligent nourishment obliged observed obstacle obstinacy occasioned
odorous offensive oppression outstretched overtook overwhelmed parch passed
persuaded perseverance pester plunged pounced pouncing precipitous predicament
presumptuous pretension prevail prisoner procure profited prohibited
promiscuous prompted prosper prosperous prostrated prevailed purloined
questioned ravenous ravaged reared rebuked recollected reconcile recovered
reflection refrained rejoiced remarked reminiscence repented replenished
reproached repulsed rescuers resemblance resolved resorted respected restraint
retire revelled reverence ridiculed reckless roused salvage scandal scarce
scarcity scattered scorned scrutinised seized severity shattered shone
similitude snared spare speechless splendour stealth stigmatised stipulated
subdue subdued subjected submissive suffocated suffocating summoned
supercilious supplanted supplication surpassed surveyed talons teeming
temperament tempted tenderness thither threshold token toiled tormented
transported treacherous tributary trudge tyrant unbounded uncouth undeniable
unfrequented vanquished vengeance venture vexed vicinity victuals vigour
vindicated virtue vowed wandered wary wavered weary wicked withered withdrew
wretched zeal
""".split())

# Content that must never reach a paper regardless of band (lowercase).
BLOCKED_SUBSTRINGS = (
    "black servant", "bred in the bone", "color of his skin",
    "colour of his skin", "enslaved", "former masters", "purchaser", "slave",
)

# ---------------------------------------------------------------------------
# The ministry JSU sheet itself (`JSU_Y4Y5Y6.xlsx`, hidden `Ref` sheet)
# ---------------------------------------------------------------------------
# `JSU_STANDARDS` further down is the DSKP ladder -- the wording the DSKP PDFs
# use.  The JSU a teacher actually hands the principal is a *different*
# document with its own, task-shaped wording ("Make and give reasons for
# simple predictions", not "Offer help, advice and invitations"), and the
# visible `Yr6_TST_v1a` template prints that wording.  So the JSU quotes this
# table: for every year and part, exactly the standards the sheet allows
# there, in the sheet's own words.
#
# Ten Year 6 rows are mis-plotted in the sheet and are corrected here to the
# code that owns the wording: 4.1.2/4.1.3/4.1.4/4.1.5 do not exist in the
# KSSR ladder at all, and rows 36/46/49/62/65 carry 4.2.1/4.2.2 beside the
# punctuation and spelling wordings that belong to 4.3.1/4.3.2.  Each
# correction is a row where the *same* sentence is printed twice under two
# codes; `TestJsuTable` asserts no printed code is outside the ladder and that
# only the sheet's own 3.1.3/3.2.3 pair shares a sentence.
JSU_SHEET_STANDARDS = {
    4: {   # column O of the hidden Ref sheet
        1: [
            ("3.2.1",
             "Understand the main idea of short simple texts"),
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.2",
             "Understand specific information and details of short "
             "simple texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
        ],
        2: [
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by visuals and the topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
        ],
        3: [
            ("3.2.1",
             "Understand the main idea of short simple texts"),
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.2",
             "Understand specific information and details of short "
             "simple texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by visuals and the topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
        ],
        4: [
            ("3.2.1",
             "Understand the main idea of short simple texts"),
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.2",
             "Understand specific information and details of short "
             "simple texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by visuals and the topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
        ],
        5: [
            ("4.3.2",
             "Spell an increased range of familiar high frequency words "
             "accurately in guided writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
        ],
        6: [
            ("4.2.2",
             "Make and give reasons for simple predictions"),
            ("4.2.2",
             "Make and respond to simple offers and invitations"),
            ("4.2.2",
             "Ask for, give and respond to simple advice"),
            ("4.2.5",
             "Connect sentences using basic coordinating conjunctions"),
            ("4.2.5",
             "Connect sentences into a coherent paragraph using basic "
             "coordinating conjunctions and reference pronouns"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops and question marks "
             "appropriately in guided writing at sentence level"),
            ("4.3.1",
             "Use capital letters, full stops, question marks and commas "
             "in lists appropriately in guided writing at discourse "
             "level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.2",
             "Spell an increased range of familiar high frequency words "
             "accurately in guided writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
        ],
        7: [
            ("4.2.3",
             "Give simple directions"),
            ("4.2.3",
             "Describe basic everyday routines"),
            ("4.2.3",
             "Narrate factual events and experiences of interest"),
            ("4.2.4",
             "Describe people and objects using suitable words and "
             "phrases"),
            ("4.2.4",
             "Describe people and objects using suitable statements"),
            ("4.2.4",
             "Describe people, places and objects using suitable "
             "statements"),
            ("4.2.5",
             "Connect sentences using basic coordinating conjunctions"),
            ("4.2.5",
             "Connect sentences into a coherent paragraph using basic "
             "coordinating conjunctions and reference pronouns"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops and question marks "
             "appropriately in guided writing at sentence level"),
            ("4.3.1",
             "Use capital letters, full stops, question marks and commas "
             "in lists appropriately in guided writing at discourse "
             "level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.2",
             "Spell an increased range of familiar high frequency words "
             "accurately in guided writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
        ],
    },
    5: {   # column P of the hidden Ref sheet
        1: [
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
        ],
        2: [
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        3: [
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        4: [
            ("3.2.1",
             "Understand the main idea of simple texts of one or two "
             "paragraphs"),
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "texts of one or two paragraphs"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title and topic"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        5: [
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
        6: [
            ("4.2.2",
             "Make and respond to simple offers and invitations"),
            ("4.2.2",
             "Ask for, give and respond to simple advice"),
            ("4.2.2",
             "Describe future plans or events"),
            ("4.2.5",
             "Connect sentences into a coherent paragraph using basic "
             "coordinating conjunctions and reference pronouns"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.2.5",
             "Connect sentences into two coherent paragraphs or more "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops, question marks and commas "
             "in lists appropriately in guided writing at discourse "
             "level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists, question "
             "marks, and speech marks appropriately at discourse level"),
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
        7: [
            ("4.2.3",
             "Describe basic everyday routines"),
            ("4.2.3",
             "Narrate factual events and experiences of interest"),
            ("4.2.3",
             "Narrate factual and imagined events and experiences"),
            ("4.2.4",
             "Describe people and objects using suitable statements"),
            ("4.2.4",
             "Describe people, places and objects using suitable "
             "statements"),
            ("4.2.4",
             "Describe personality"),
            ("4.2.5",
             "Connect sentences into a coherent paragraph using basic "
             "coordinating conjunctions and reference pronouns"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.2.5",
             "Connect sentences into two coherent paragraphs or more "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops, question marks and commas "
             "in lists appropriately in guided writing at discourse "
             "level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists, question "
             "marks, and speech marks appropriately at discourse level"),
            ("4.3.2",
             "Spell most high frequency words accurately in guided "
             "writing"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
    },
    6: {   # column Q of the hidden Ref sheet
        1: [
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.1.1",
             "Understand the main idea in simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
            ("3.1.2",
             "Understand specific information and details in simple "
             "longer texts"),
        ],
        2: [
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
            ("3.1.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        3: [
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.1.1",
             "Understand the main idea in simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
            ("3.1.2",
             "Understand specific information and details in simple "
             "longer texts"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
            ("3.1.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        4: [
            ("3.2.1",
             "Understand the main idea of simple texts of two paragraphs "
             "or more"),
            ("3.2.1",
             "Understand the main idea of simple longer texts"),
            ("3.1.1",
             "Understand the main idea in simple longer texts"),
            ("3.2.2",
             "Understand specific information and details of two "
             "paragraphs or more"),
            ("3.2.2",
             "Understand specific information and details of simple "
             "longer texts"),
            ("3.1.2",
             "Understand specific information and details in simple "
             "longer texts"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by title, topic and other known words"),
            ("3.2.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
            ("3.1.3",
             "Guess the meaning of unfamiliar words from clues provided "
             "by other known words and by context"),
        ],
        5: [
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
        6: [
            ("4.2.2",
             "Ask for, give and respond to simple advice"),
            ("4.2.2",
             "Describe future plans or events"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.2.5",
             "Connect sentences into two coherent paragraphs or more "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists, question "
             "marks, and speech marks appropriately at discourse level"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
        7: [
            ("4.2.3",
             "Narrate factual events and experiences of interest"),
            ("4.2.3",
             "Narrate factual and imagined events and experiences"),
            ("4.2.4",
             "Describe people, places and objects using suitable "
             "statements"),
            ("4.2.4",
             "Describe personality"),
            ("4.2.5",
             "Connect sentences into one or two coherent paragraphs "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.2.5",
             "Connect sentences into two coherent paragraphs or more "
             "using basic coordinating conjunctions and reference "
             "pronouns"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists and "
             "question marks appropriately in independent writing at "
             "discourse level"),
            ("4.3.1",
             "Use capital letters, full stops,commas in lists, question "
             "marks, and speech marks appropriately at discourse level"),
            ("4.3.2",
             "Spell a range of high frequency words accurately in "
             "independent writing"),
            ("4.3.2",
             "Spell most high frequency words accurately in independent "
             "writing"),
        ],
    },
}

# RPT (Rancangan Pengajaran Tahunan) unit themes, mirroring the official
# `RPT BI *.docx` planners shipped with the 2026 exam papers.
RPT_THEMES = {
    1: ["World of Self, Family and Friends", "World of Stories", "World of Knowledge"],
    2: ["World of Self, Family and Friends", "World of Stories", "World of Knowledge"],
    3: ["World of Self, Family and Friends", "World of Stories", "World of Knowledge"],
    # The ten modules of the official `Y4_RPT.docx` planner.
    4: ["Where Are You From?", "My Week", "In the Past", "Celebrations",
        "Eating Right", "Getting Around", "Helping Out", "Amazing Animals",
        "Get Active!", "What's the Matter?"],
    5: ["Towns and Cities", "Days", "Wild Life", "Learning World", "Food and Health",
        "Sport", "Growing Up", "Going Away"],
    6: ["It's an Emergency", "Life in the Past", "Adventure Time", "Cool Jobs",
        "Getting Around", "How Is It Made?", "Music and Song", "Tell Me a Story",
        "What's Your Opinion?", "It's a Mystery!"],
}

# Year 4 is taught through its own RPT modules, so each module needs keywords
# of its own to pick on-theme passages, questions and writing prompts.  They are
# taken from the module titles and sub-topics in `Y4_RPT.docx`.
_THEME_KEYWORDS_Y4 = {
    "Where Are You From?": [
        "country", "village", "town", "city", "state", "region", "hometown",
        "where i live", "live in", "born", "origin", "village life", "kampung",
        "neighbour", "neighborhood", "street", "address", "place", "land",
        "map", "flag", "language", "culture", "tradition", "famous", "proud",
    ],
    "My Week": [
        "week", "weekend", "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday", "daily", "routine", "every day",
        "morning", "afternoon", "evening", "night", "breakfast", "lunch",
        "dinner", "homework", "tuition", "chores", "schedule", "timetable",
        "clock", "early", "late", "always", "usually", "often", "sometimes",
    ],
    "In the Past": [
        "past", "long ago", "ago", "history", "historic", "old", "once",
        "used to", "grandfather", "grandmother", "kampung", "traditional",
        "ancestor", "museum", "tin", "mining", "king", "sultan", "empire",
        "old days", "remember", "story", "years ago", "different",
    ],
    "Celebrations": [
        "celebrate", "celebration", "festival", "hari raya", "christmas",
        "deepavali", "wedding", "birthday", "anniversary", "parade",
        "firework", "fireworks", "lantern", "ketupat", "ang pao", "gift",
        "present", "dress", "new clothes", "guest", "visit", "tradition",
        "decoration", "performance", "candle", "moon cake", "mooncake",
    ],
    "Eating Right": [
        "food", "healthy", "eat", "drink", "water", "milk", "fruit",
        "vegetable", "rice", "nasi lemak", "bread", "egg", "meat", "fish",
        "sugar", "salt", "oil", "junk food", "fast food", "canteen", "menu",
        "cook", "cookbook", "portion", "balance", "energy", "vitamin",
        "obesity", "allergy", "allergic", "diabetes", "wash hands",
    ],
    "Getting Around": [
        "transport", "travel", "bus", "car", "train", "lrt", "mrt", "taxi",
        "plane", "boat", "ferry", "bicycle", "bike", "walk", "station",
        "airport", "ticket", "journey", "commute", "road", "street",
        "traffic", "drive", "ride", "crossing", "seatbelt", "map", "direction",
        "left", "right", "straight", "distance",
    ],
    "Helping Out": [
        "help", "helping", "helper", "volunteer", "neighbour", "neighbor",
        "kindness", "kind", "share", "sharing", "care", "clean", "cleaning",
        "tidy", "wash", "litter", "recycle", "donate", "charity", "community",
        "teamwork", "together", "cooperate", "friendly", "respect", "thank you",
    ],
    "Amazing Animals": [
        "animal", "wild", "wildlife", "zoo", "safari", "tiger", "lion",
        "elephant", "monkey", "orangutan", "bird", "parrot", "eagle", "fish",
        "dolphin", "turtle", "snake", "frog", "insect", "butterfly", "bee",
        "ant", "camel", "horse", "cow", "goat", "chicken", "duck", "penguin",
        "panda", "habitat", "jungle", "rainforest", "ocean", "protect",
        "endangered", "extinct", "feed", "cub", "puppy", "hatch",
    ],
    "Get Active!": [
        "sport", "sports", "exercise", "active", "play", "game", "football",
        "badminton", "swim", "running", "race", "relay", "cycling", "skating",
        "gym", "gymnastics", "fitness", "healthy body", "energy", "muscle",
        "stretch", "warm up", "cool down", "team", "medal", "trophy", "prize",
        "sports day", "field", "court", "net", "goal", "coach", "training",
    ],
    "What's the Matter?": [
        "matter", "emergency", "accident", "danger", "dangerous", "safety",
        "safe", "fire", "firefighter", "police", "ambulance", "hospital",
        "doctor", "ill", "illness", "sick", "fever", "cough", "cold",
        "headache", "stomach ache", "hurt", "pain", "injury", "wound", "bandage",
        "first aid", "alarm", "help", "evacuate", "smoke", "drown", "bully",
        "stranger", "trouble", "problem", "advice", "problem-solution",
    ],
}

# Keyword map used to prefer questions/passages that match the active RPT theme.
THEME_KEYWORDS = {
    "World of Self, Family and Friends": [
        "family", "friend", "home", "house", "school", "teacher", "classroom",
        "breakfast", "uniform", "name", "brother", "sister", "mother", "father",
        "grandmother", "grandfather", "aunt", "uncle", "pet", "cat", "dog",
        "birthday", "morning",
    ],
    "World of Stories": [
        "story", "stories", "tale", "fable", "fairy", "magic", "once upon",
        "fox", "crow", "lion", "mouse", "tortoise", "hare", "wolf", "monkey",
        "goat", "hen", "bird", "duck",
    ],
    "World of Knowledge": [
        "know", "fact", "national", "flower", "plant", "animal", "weather",
        "sea", "sea animals", "rainbow", "star", "moon", "knowledge",
    ],
    "Towns and Cities": [
        "town", "city", "market", "mall", "shop", "street", "jalan", "kuala lumpur",
        "twin towers", "penang", "batu caves", "tower", "station", "landmark",
        "skyscraper",
    ],
    "Days": [
        "day", "week", "monday", "sunday", "saturday", "morning", "afternoon",
        "evening", "night", "routine", "early", "hour",
    ],
    "Wild Life": [
        "wild", "animal", "tiger", "orangutan", "monkey", "bird", "hornbill",
        "forest", "rainforest", "jungle", "national park", "tapir", "pangolin",
        "proboscis", "ranger", "zoo", "elephant",
    ],
    "Learning World": [
        "school", "class", "learn", "learns", "teacher", "pupils", "read",
        "library", "subject", "science", "mathematics", "english", "study",
        "test", "uniform", "canteen", "homework", "assembly",
    ],
    "Food and Health": [
        "food", "nasi lemak", "satay", "roti canai", "kuih", "market", "hawker",
        "cook", "rice", "fruit", "vegetables", "healthy", "soup", "breakfast",
        "eat", "drink", "wash", "canteen",
    ],
    "Sport": [
        "sport", "game", "play", "football", "race", "relay", "run", "ball",
        "field", "team", "exercise",
    ],
    "Growing Up": [
        "grow", "grow up", "past", "present", "change", "memory", "younger",
        "lesson", "time",
    ],
    "Going Away": [
        "travel", "trip", "away", "bus", "train", "plane", "holiday", "beach",
        "hill", "tour", "visit", "journey", "travels",
    ],
    "It's an Emergency": [
        "emergency", "fire", "rescue", "accident", "ambulance", "police",
        "danger", "safety", "firefighter", "help", "alarm", "911", "999",
        "drown", "smoke", "evacuate", "equipment",
    ],
    "Life in the Past": [
        "past", "long ago", "history", "museum", "grandfather", "grandmother",
        "kampung", "traditional", "tin", "1925", "old days", "merchant",
        "ancient", "ago", "horse", "candle", "planted",
    ],
    "Adventure Time": [
        "adventure", "mountain", "explore", "climb", "jungle", "island",
        "camp", "hike", "trek", "waterfall", "expedition", "brave", "cave",
        "jungle", "dense", "raft",
    ],
    "Cool Jobs": [
        "job", "work", "works", "career", "occupation", "vocation", "profession",
        "engineer", "doctor", "teacher", "chef", "firefighter", "pilot",
        "dentist", "nurse", "police", "farmer", "ranger", "astronaut", "zookeeper",
        "vet", "electrician", "plumber", "mechanic", "designer", "photographer",
        "scientist", "reporter", "musician", "policeman", "policewoman",
    ],
    "Getting Around": [
        "transport", "travel", "bus", "lrt", "train", "plane", "station",
        "ticket", "journey", "commute", "road", "bridge", "skiff", "ferry",
        "funicular", "monorail", "airport", "vehicle",
    ],
    "How Is It Made?": [
        "made", "make", "factory", "produce", "product", "process", "material",
        "craft", "chocolate", "bread", "build", "machine", "coal", "mould",
        "factory", "manufactured",
    ],
    "Music and Song": [
        "music", "song", "sing", "band", "instrument", "drum", "guitar",
        "piano", "choir", "concert", "melody", "rhythm", "lyrics", "tune",
        "flute", "perform",
    ],
    "Tell Me a Story": [
        "story", "tale", "legend", "fiction", "hero", "character", "plot",
        "myth", "once upon", "dragon", "fairy", "kingdom", "adventure",
    ],
    "What's Your Opinion?": [
        "opinion", "think", "believe", "agree", "disagree", "prefer", "reason",
        "should", "choice", "decide", "advice", "view", "point of view", "feel",
        "argument", "best", "important",
    ],
    "It's a Mystery!": [
        "mystery", "detective", "clue", "secret", "solve", "strange",
        "investigate", "puzzle", "disappear", "hidden", "surprise", "suspect",
    ],
}

# Round 22: curated description->word tiles for the upper-primary fill-in-the-
# space exercise (Part 5, `words`/letter).  Teacher directive: "align the theme
# and the answers", "statements without space" — a pupil reads a clean
# description and fills the pattern below.  Each answer word is a member of
# ``THEME_KEYWORDS[theme]`` (single-word members only) so the tile always stays
# on the active RPT theme; the clue is a plain statement, never a blanked
# textbook usage line.
THEME_LETTER_WORDS = {
    5: {
        "Towns and Cities": [
            ("It is a large town where many people live and work.", "city"),
            ("It is a very tall building.", "tower"),
            ("People buy and sell things here every day.", "market"),
            ("Buses and trains stop at this place.", "station"),
            ("It is a famous place that people like to visit.", "landmark"),
        ],
        "Days": [
            ("It is the time when the sun comes up.", "morning"),
            ("It is the time of the day after twelve o'clock.", "afternoon"),
            ("It is the time when the sun goes down.", "evening"),
            ("It is the day after Friday.", "saturday"),
            ("It is what you do at the same time each day.", "routine"),
        ],
        "Wild Life": [
            ("It is a big wild cat with black stripes.", "tiger"),
            ("It is a huge animal with a long trunk.", "elephant"),
            ("It is a clever animal that likes to climb trees.", "monkey"),
            ("It is a big bird with a long curved beak.", "hornbill"),
            ("It is a large area covered with many trees.", "forest"),
        ],
        "Learning World": [
            ("This person helps pupils to learn new things.", "teacher"),
            ("Pupils borrow books from this quiet room.", "library"),
            ("It is a subject in which we learn about numbers.", "mathematics"),
            ("Pupils wear this special set of clothes at school.", "uniform"),
            ("Pupils buy their food and drinks here.", "canteen"),
        ],
        "Food and Health": [
            ("It is the first meal of the day.", "breakfast"),
            ("Apples and oranges are kinds of this.", "fruit"),
            ("It describes food that is good for your body.", "healthy"),
            ("It is a hot liquid food that we eat with a spoon.", "soup"),
            ("We do this to make food ready to eat.", "cook"),
        ],
        "Sport": [
            ("Players kick this ball to score a goal.", "football"),
            ("It is a group of players who play together.", "team"),
            ("Runners try to finish first in this event.", "race"),
            ("In this race, runners pass a baton to their teammates.", "relay"),
            ("We do this to keep our body strong and fit.", "exercise"),
        ],
        "Growing Up": [
            ("It is something you remember from the past.", "memory"),
            ("It means to become different over time.", "change"),
            ("It describes a person who is not old yet.", "younger"),
            ("We learn something new from this at school.", "lesson"),
            ("It is the time that has already gone by.", "past"),
        ],
        "Going Away": [
            ("It is a long trip from one place to another.", "journey"),
            ("It is a time when we rest and enjoy ourselves.", "holiday"),
            ("People swim and play in the sand at this place.", "beach"),
            ("This big vehicle carries many people along the road.", "bus"),
            ("This machine flies high in the sky with people inside.", "plane"),
        ],
    },
    6: {
        "It's an Emergency": [
            ("It is a loud sound that warns people of danger.", "alarm"),
            ("This special vehicle takes sick people to hospital.", "ambulance"),
            ("It means to save someone from danger.", "rescue"),
            ("This person puts out fires and saves people.", "firefighter"),
            ("It is something that burns and can spread quickly.", "fire"),
        ],
        "Life in the Past": [
            ("It is the study of things that happened long ago.", "history"),
            ("Old and precious things are kept in this building.", "museum"),
            ("People used this for light before electricity.", "candle"),
            ("It describes something that came from a very long time ago.",
             "ancient"),
            ("This animal carried people from place to place long ago.", "horse"),
        ],
        "Adventure Time": [
            ("It is a very high piece of land.", "mountain"),
            ("It is land with water all around it.", "island"),
            ("Water falls down from high rocks at this place.", "waterfall"),
            ("It is a thick forest where many trees grow close together.",
             "jungle"),
            ("It is a long journey to find out about new places.", "expedition"),
        ],
        "Cool Jobs": [
            ("This person treats sick people and gives them medicine.", "doctor"),
            ("This person cooks tasty food in a restaurant.", "chef"),
            ("This person checks and looks after our teeth.", "dentist"),
            ("This person flies an aeroplane.", "pilot"),
            ("This person repairs cars and machines.", "mechanic"),
        ],
        "Getting Around": [
            ("Buses and trains stop here to let people on and off.", "station"),
            ("We buy this before we ride on a train or bus.", "ticket"),
            ("We use it to cross over a river or a road.", "bridge"),
            ("It is a boat that carries people and cars across the water.",
             "ferry"),
            ("It is a train that runs on a single rail.", "monorail"),
        ],
        "How Is It Made?": [
            ("Goods are made in this large building.", "factory"),
            ("It is something that a company makes and sells.", "product"),
            ("It is a device that helps us do work.", "machine"),
            ("Wood, paper and metal are kinds of this.", "material"),
            ("It is a sweet food made from cocoa beans.", "chocolate"),
        ],
        "Music and Song": [
            ("We play this stringed instrument with our fingers.", "guitar"),
            ("This big instrument has black and white keys.", "piano"),
            ("We hit this instrument to make a beat.", "drum"),
            ("It is a group of people who sing together.", "choir"),
            ("People gather to listen to music at this event.", "concert"),
        ],
        "Tell Me a Story": [
            ("It is a very old story that people still tell today.", "legend"),
            ("It is the brave main person in a story.", "hero"),
            ("It is the main events that happen in a story.", "plot"),
            ("It is a big creature in stories that can breathe fire.", "dragon"),
            ("It is an old story about gods and heroes.", "myth"),
        ],
        "What's Your Opinion?": [
            ("It is what you think or feel about something.", "opinion"),
            ("It is the thing you pick when you want one of two.", "choice"),
            ("It is helpful words that you give to a friend.", "advice"),
            ("It means to think the same way as another person.", "agree"),
            ("It is why you think or do something.", "reason"),
        ],
        "It's a Mystery!": [
            ("It is a strange thing that is not easy to explain.", "mystery"),
            ("This person tries to solve a crime by finding clues.", "detective"),
            ("It is a small sign that helps you find the answer.", "clue"),
            ("It is something that is kept hidden from other people.", "secret"),
            ("It is a game or question that you try to solve.", "puzzle"),
        ],
    },
}

# Per-year part configuration.  `kind` picks the question generator in bank.py.
# `style` refines that generator (lower vs upper primary layouts).
PARTS = {
    1: [
        {"id": 1, "kind": "vocab",    "style": "lower", "marks": 5,  "count": 5,
         "lead": {"bm": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet.",
                  "en": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet."}},
        {"id": 2, "kind": "cloze",    "style": "lower", "marks": 4,  "count": 4,
         "lead": {"bm": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet.",
                  "en": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet."}},
        {"id": 3, "kind": "comprehension", "style": "lower", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 4, "kind": "match",    "style": "lower", "marks": 6,  "count": 6,
         "lead": {"bm": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 5, "kind": "words",    "style": "letter", "marks": 5, "count": 5,
         # Round 41 (SPEC 57): the ministry spelling task.  Years 1-3 were
         # built as a multiple choice; UASA YEAR 1/2/3.pdf print every
         # letter blank and give the clue as a riddle, so this lead must
         # NOT promise a first letter -- unlike Years 4-6 below.
         "lead": {"bm": "Baca petunjuk setiap perkataan di bawah. Apakah perkataan bagi setiap satu?",
                  "en": "Read the clues below. What is the word for each one?"}},
        {"id": 6, "kind": "writing",  "style": "sentences", "marks": 10, "count": 5,
         "example": True,
         "lead": {"bm": "Use the words provided below to make sentences. "
                        "(in, on, under) An example is given below.",
                  "en": "Use the words provided below to make sentences. "
                        "(in, on, under) An example is given below."}},
        {"id": 7, "kind": "writing", "style": "paragraph", "marks": 15, "count": 5,
         "lead": {"bm": "Tulis TIGA ayat bagi setiap budak lelaki / budak perempuan "
                        "yang kamu lukis sambil memakai pakaian yang berbeza. "
                        "Contoh diberikan di bawah.\nWord box: T-shirt, shirt, "
                        "trousers, jeans, skirt, dress, shorts, cap, hat, shoes, "
                        "socks, jacket, sweater, umbrella",
                  "en": "Write THREE sentences for each boy/girl you draw wearing "
                        "different outfits. An example is given below.\nWord box: "
                        "T-shirt, shirt, trousers, jeans, skirt, dress, shorts, "
                        "cap, hat, shoes, socks, jacket, sweater, umbrella"}},
    ],
    2: [
        {"id": 1, "kind": "vocab",    "style": "lower", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet.",
                  "en": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet."}},
        {"id": 2, "kind": "cloze",    "style": "lower", "marks": 4, "count": 4,
         "lead": {"bm": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet.",
                  "en": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet."}},
        {"id": 3, "kind": "comprehension", "style": "lower", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 4, "kind": "match",    "style": "lower", "marks": 6, "count": 6,
         "lead": {"bm": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 5, "kind": "words",    "style": "letter", "marks": 5, "count": 5,
         # Round 41 (SPEC 57): the ministry spelling task.  Years 1-3 were
         # built as a multiple choice; UASA YEAR 1/2/3.pdf print every
         # letter blank and give the clue as a riddle, so this lead must
         # NOT promise a first letter -- unlike Years 4-6 below.
         "lead": {"bm": "Baca petunjuk setiap perkataan di bawah. Apakah perkataan bagi setiap satu?",
                  "en": "Read the clues below. What is the word for each one?"}},
        {"id": 6, "kind": "writing",  "style": "sentences", "marks": 10, "count": 5,
         "example": True,
         "lead": {"bm": "Use the words provided below to make sentences. An example is "
                        "given below.",
                  "en": "Use the words provided below to make sentences. An example is "
                        "given below."}},
        {"id": 7, "kind": "writing", "style": "paragraph", "marks": 15, "count": 5,
         "lead": {"bm": "Tulis TIGA ayat bagi setiap budak lelaki / budak perempuan "
                        "yang kamu lukis sambil memakai pakaian yang berbeza. "
                        "Contoh diberikan di bawah.\nWord box: T-shirt, shirt, "
                        "trousers, jeans, skirt, dress, shorts, cap, hat, shoes, "
                        "socks, jacket, sweater, umbrella",
                  "en": "Write THREE sentences for each boy/girl you draw wearing "
                        "different outfits. An example is given below.\nWord box: "
                        "T-shirt, shirt, trousers, jeans, skirt, dress, shorts, "
                        "cap, hat, shoes, socks, jacket, sweater, umbrella"}},
    ],
    3: [
        {"id": 1, "kind": "vocab",    "style": "lower", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet.",
                  "en": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet."}},
        {"id": 2, "kind": "cloze",    "style": "lower", "marks": 4, "count": 4,
         "lead": {"bm": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet.",
                  "en": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet."}},
        {"id": 3, "kind": "comprehension", "style": "lower", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 4, "kind": "match",    "style": "lower", "marks": 6, "count": 6,
         "lead": {"bm": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 5, "kind": "words",    "style": "letter", "marks": 5, "count": 5,
         "lead": {"bm": "Baca petunjuk setiap perkataan di bawah. Apakah perkataan bagi setiap satu?",
                  "en": "Read the clues below. What is the word for each one?"}},
        {"id": 6, "kind": "writing",  "style": "email", "marks": 10, "count": 1,
         "lead": {"bm": "Write an email to your friend based on the notes below. "
                        "The email should be between 30 and 50 words.",
                  "en": "Write an email to your friend based on the notes below. "
                        "The email should be between 30 and 50 words."}},
        {"id": 7, "kind": "writing", "style": "email", "marks": 15, "count": 1,
         "lead": {"bm": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words.",
                  "en": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words."}},
    ],
    5: [
        {"id": 1, "kind": "vocab",    "style": "upper", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet.",
                  "en": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet."}},
        {"id": 2, "kind": "cloze",    "style": "upper", "marks": 4, "count": 4,
         "lead": {"bm": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet.",
                  "en": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet."}},
        {"id": 3, "kind": "comprehension", "style": "upper", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 4, "kind": "match",    "style": "upper", "marks": 6, "count": 6,
         "lead": {"bm": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 5, "kind": "words",    "style": "letter", "marks": 5, "count": 5,
         "lead": {"bm": "Read the descriptions of some words. What is the word for each "
                        "one? The first letter is already there. There is one space for "
                        "each letter in the word.",
                  "en": "Read the descriptions of some words. What is the word for each "
                        "one? The first letter is already there. There is one space for "
                        "each letter in the word."}},
        {"id": 6, "kind": "writing",  "style": "email", "marks": 10, "count": 1,
         "lead": {"bm": "Write an email to your friend based on the notes below. "
                        "The email should be between 30 and 50 words.",
                  "en": "Write an email to your friend based on the notes below. "
                        "The email should be between 30 and 50 words."}},
        {"id": 7, "kind": "writing", "style": "email", "marks": 15, "count": 1,
         "lead": {"bm": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words.",
                  "en": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words."}},
    ],
    6: [
        {"id": 1, "kind": "vocab",    "style": "upper", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet.",
                  "en": "Read the text carefully in each question. For each question, "
                        "choose the correct answer A, B or C. Then, mark the "
                        "correct answer A, B or C on your answer sheet."}},
        {"id": 2, "kind": "cloze",    "style": "upper", "marks": 4, "count": 4,
         "lead": {"bm": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet.",
                  "en": "Read the text below and choose the correct word for each blank. "
                        "Choose the correct answer for each blank: A, B or C. "
                        "Then, mark the correct answer A, B or C on your "
                        "answer sheet."}},
        {"id": 3, "kind": "comprehension", "style": "upper", "marks": 5, "count": 5,
         "lead": {"bm": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the text carefully. For each question, choose the correct "
                        "answer A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 4, "kind": "match",    "style": "upper", "marks": 6, "count": 6,
         "lead": {"bm": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet.",
                  "en": "Read the texts below (A, B and C). Choose the answers (A, B or C) "
                        "that fit the descriptions. Choose the correct answer for each "
                        "question: A, B or C. Then, mark the correct answer A, B "
                        "or C on your answer sheet."}},
        {"id": 5, "kind": "words",    "style": "letter", "marks": 5, "count": 5,
         "lead": {"bm": "Read the descriptions of some words. What is the word for each "
                        "one? The first letter is already there. There is one space for "
                        "each letter in the word.",
                  "en": "Read the descriptions of some words. What is the word for each "
                        "one? The first letter is already there. There is one space for "
                        "each letter in the word."}},
        {"id": 6, "kind": "writing",  "style": "letter", "marks": 10, "count": 1,
         "lead": {"bm": "Write a letter to your friend based on the notes below. "
                        "The letter should be between 30 and 50 words.",
                  "en": "Write a letter to your friend based on the notes below. "
                        "The letter should be between 30 and 50 words."}},
        {"id": 7, "kind": "writing", "style": "email", "marks": 15, "count": 1,
         "lead": {"bm": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words.",
                  "en": "Write an email to your friend based on the notes below. "
                        "The email should be between 60 and 80 words."}},
    ],
}

# Year 4 is assessed on the same seven parts as Year 5: 5/4/5/6/5/10/15 = 50
# marks, both writing parts an email, Part 6 30-50 words and Part 7 60-80.  The
# school's own Y4 UASA 2025 uses those instructions word for word, so PARTS[4]
# is PARTS[5] -- derived from it rather than retyped, so the two years cannot
# drift apart.
PARTS[4] = PARTS[5]

# Instructions block shown under the header (as in the official papers).
ARAHAN = {
    "bm": [
        "Buka kertas ujian ini apabila diberitahu.",
        "Tulis nama dan nama kelas kamu pada ruang yang disediakan.",
        "Tandakan jawapan kamu bagi Part 1, Part 2, Part 3 dan Part 4 pada "
        "ruang jawapan objektif di halaman terakhir kertas ujian ini.",
        "Jawab soalan Part 5, Part 6 dan Part 7 dalam ruang jawapan yang "
        "disediakan pada kertas ujian ini.",
        "Kertas ujian ini hendaklah diserahkan kepada guru bertugas pada "
        "akhir ujian.",
    ],
    "en": [
        "Open this test paper when you are told to do so.",
        "Write your name and class in the spaces provided.",
        "Mark your answers for Part 1, Part 2, Part 3 and Part 4 on the "
        "objective answer space on the last page of this test paper.",
        "Answer the questions in Part 5, Part 6 and Part 7 in the answer "
        "space provided in this test paper.",
        "Hand in this test paper to the invigilator at the end of the test.",
    ],
}


# ---------------------------------------------------------------------------
# Round 14 (S5): DSKP content-standard tags for coverage reports.
# ---------------------------------------------------------------------------
# Each paper part maps onto KSSR Bahasa Inggeris content standards
# (Document Standard Kurikulum dan Pentaksiran).  ``DSKP`` is per year per
# part (list of standard codes); ``DSKP_TITLES`` expands a code's meaning for
# the coverage report.  Teachers can use codes like "3.2" to record coverage
# across a term.
DSKP_TITLES = {
    "3.1": "Recognise and reproduce words in linear and non-linear texts",
    "3.2": "Understand a variety of linear and non-linear texts and use "
           "strategies to construct meaning",
    "3.3": "Read independently for information and enjoyment",
    "4.1": "Form letters and words in neat and legible print using cursive",
    "4.2": "Communicate basic information intelligibly for a range of "
           "purposes in print and digital media",
    "4.3": "Communicate with appropriate language form and style for a range "
           "of purposes in print and digital media",
}

# default part -> standards (identical shape across years unless overridden)
_DSKP_DEFAULT = {
    1: ["3.1"],                # contextual vocabulary
    2: ["3.2"],                # cloze passage
    3: ["3.2"],                # reading comprehension
    4: ["3.2"],                # matching texts A/B/C
    5: ["3.1", "4.2"],         # choose-the-word
    6: ["4.2"],                # guided writing / sentences
    7: ["4.3"],                # essay / email / paragraph
}

DSKP = {y: {k: list(v) for k, v in _DSKP_DEFAULT.items()}
        for y in YEARS}
# Year 1/2 Part 5 is picture-words; Year 5/6 Part 6 is a short letter/email.
DSKP[1][5] = ["4.1", "3.1"]
DSKP[2][5] = ["4.1", "3.1"]

DEFAULT_CONFIG = {
    # Identity is empty until a teacher types it, never a placeholder: a
    # redaction marker is not a school, and it printed on every paper and
    # every marking scheme before Round 37.  ``docx._header_block`` omits the
    # identity line when both are blank, and the GUI restores whatever was
    # typed from settings.json.
    "school": "",
    "teacher": "",
    "exam_type": "upsa",
    "session": 2026,
    "subject_key": "bi",
    "year": 3,
    "duration": "",
    "lang": "en",            # paper instruction language (papers are English)
    # Fail-safe defaults (Round 38): an export nobody thought about is a
    # *pupil* paper.  The key and the JSU are a teacher document, and the
    # teacher document has to be asked for on purpose -- `--teacher` in the
    # CLI, the key switch in the GUI.  ``paper.key`` is unaffected: a
    # generated paper is still markable, ``render_doc`` still honours these.
    "answer_key": False,
    "jsu": False,
    "answer_sheet": True,    # bubble grid for MCQ parts
    "difficulty": "medium",  # easy | medium | hard
    "pictures": True,        # topic illustrations on reading parts + lower years
    "seed": 1,
    "parts": [1, 2, 3, 4, 5, 6, 7],
    # Round 13 (S2/S8) additions — school identity + pupil IDs on every paper.
    "crest": "",             # optional school-crest image path (embed in header)
    "pupil_id": "",          # optional pupil/set ID stamped on the header
    "qr": False,             # stamp the pupil ID as a QR code too
}


def default_crest_path() -> str:
    """Resolve the school-crest image installed in the app data dir.

    Falls back to $EXAM_GEN_DATA/crest.png, then
    ~/.local/share/exam-gen/crest.png; '' when absent. Renderers use this
    whenever conf['crest'] is empty so the crest is a real default (S2).
    """
    import os
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "materials", "2027")
    for base in (os.environ.get("EXAM_GEN_DATA", ""),
                 os.path.join(os.path.expanduser("~"), ".local", "share",
                              "exam-gen"),
                 bundled):
        if not base:
            continue
        cand = os.path.join(base, "crest.png")
        if os.path.exists(cand):
            return cand
    return ""


def persist_crest(src: str) -> str:
    """Copy an uploaded school crest into the app data dir as ``crest.png``.

    Returns the destination path, or ``''`` when the source cannot be read.
    An upload must not depend on the picker's original file surviving on the
    desktop: the bytes are stored exactly where ``default_crest_path()``
    looks, so the crest stays the default across restarts and machines
    (Round 13 S2 follow-up).
    """
    import os
    import shutil
    src = str(src or "").strip()
    if not src or not os.path.isfile(src):
        return ""
    for base in (os.environ.get("EXAM_GEN_DATA", ""),
                 os.path.join(os.path.expanduser("~"), ".local", "share",
                              "exam-gen")):
        if not base:
            continue
        dst = os.path.join(base, "crest.png")
        try:
            os.makedirs(base, exist_ok=True)
            with open(src, "rb") as fin, open(dst, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            return dst
        except OSError:
            continue
    return ""


# ---------------------------------------------------------------------------
# JSU — Jadual Spesifikasi Ujian (Round 27)
#
# The official exam-specification table for the upper primary years
# (`/home/school/Downloads/exam2026/JSU_Y4Y5Y6.xlsx`).  It is the blue-print
# every generated paper is measured against: for each part it names the skill,
# the text genre, the theme, the learning standard and the CEFR band, plus the
# LOTS/HOTS split and the objective CEFR mix.
#
# `data.PARTS` already fixes the *shape* of a paper (7 parts, 50 marks); this
# fixes the *content*, so a teacher can see that a Part 6 letter really asks
# for what standard 4.2.2 asks for.  Years 1-3 have no JSU sheet in the
# ministry table, so they are simply absent and `bank.jsu_issues` has nothing
# to say about them.
# ---------------------------------------------------------------------------

def _jsu_sheet_tasks(year: int, part_num: int) -> list[str]:
    """Every task wording the sheet allows for a writing part, in sheet order.

    The ministry cell says *choose one* of its options, so a Year 4 paper whose
    Part 6 asks for an offer is as on-blue-print as one that asks for a
    prediction.  Judging the prompt against the whole list keeps the audit
    faithful to the sheet instead of pinning it to whichever option was read
    first.
    """
    out: list[str] = []
    for _code, text in (JSU_SHEET_STANDARDS.get(int(year)) or {}).get(
            int(part_num), []):
        text = str(text).strip()
        if text and text not in out:
            out.append(text)
    return out


# Years 4 and 5 are assessed on the same seven parts and the same objective
# format as Year 6 -- 5/4/5/6/5 marks for Parts 1-5, an email of 30-50 words,
# a longer email of 60-80, the 40:60 LOTS/HOTS split and the A2 Low / A2 Mid /
# Revise A2 objective mix.  The sheet gives each year its own learning
# standards (JSU_SHEET_STANDARDS) and its own wording of the writing task, so
# the two entries below differ exactly there and nowhere else.
def _jsu_upper(year: int, title: str, p6_task: str, p6_signals: list,
               p7_task: str, p7_signals: list) -> dict:
    sheet = JSU_SHEET_STANDARDS[year]

    def codes(part: int) -> list:
        out: list = []
        for code, _text in sheet[part]:
            if code not in out:
                out.append(code)
        return out

    return {
        "title": title,
        "source": f"JSU_Y4Y5Y6.xlsx / Ref column {'OPQ'[year - 4]}",
        "total_marks": 50,
        "duration_minutes": 75,
        "lots": 40, "hots": 60,
        "cefr_mix": {"A2 Low": 5, "A2 Mid": 15, "Revise A2": 5},
        "parts": {
            1: {"marks": 5, "items": 5, "skill": "Short Text",
                "genres": ["Notices", "Posters", "Labels", "Signs and Charts",
                           "Emails", "Advertisements", "Dialogues"],
                "themes": ["World of Knowledge",
                           "World of Self, Family and Friends"],
                "learning_standards": codes(1), "cefr": "A2 Low"},
            2: {"marks": 4, "items": 4, "skill": "Lexico-grammar",
                "focus": ["Tenses", "Determiners", "Pronouns", "Nouns",
                          "Prepositions", "Adverbs"],
                "themes": [], "learning_standards": codes(2),
                "cefr": "A2 Low"},
            3: {"marks": 5, "items": 5, "skill": "Longer Text",
                "themes": [], "learning_standards": codes(3),
                "cefr": "A2 Mid"},
            4: {"marks": 6, "items": 6, "skill": "Matching Multiple Texts",
                "themes": ["World of Knowledge"],
                "learning_standards": codes(4), "cefr": "A2 Mid"},
            5: {"marks": 5, "items": 5, "skill": "Word Completion",
                "themes": ["World of Knowledge"],
                "learning_standards": codes(5), "cefr": "Revise A2"},
            6: {"marks": 10, "items": 1,
                "skill": "Short Communicative Message", "themes": [],
                "learning_standards": codes(6), "cefr": "A2 Low",
                "task": p6_task, "signals": p6_signals,
                "tasks": _jsu_sheet_tasks(year, 6)},
            7: {"marks": 15, "items": 1, "skill": "Note Expansion",
                "themes": [], "learning_standards": codes(7),
                "cefr": "A2 Mid", "task": p7_task, "signals": p7_signals,
                "tasks": _jsu_sheet_tasks(year, 7)},
        },
    }

JSU = {
    6: {
        "title": "Year 6 UASA",
        "source": "JSU_Y4Y5Y6.xlsx / Sheet1",
        "total_marks": 50,
        "duration_minutes": 75,   # the criteria UASA time, same as DURATION[6]
        "lots": 40, "hots": 60,
        "cefr_mix": {"A2 Low": 5, "A2 Mid": 15, "Revise A2": 5},
        "parts": {
            1: {
                "marks": 5, "items": 5,
                "skill": "Short Text",
                "genres": ["Advertisements", "Notices", "Emails",
                           "Labels", "Signs and Charts", "Dialogues"],
                "themes": ["World of Knowledge",
                           "World of Self, Family and Friends"],
                "learning_standards": ["3.2.2", "3.2.1", "3.1.2"],
                "cefr": "A2 Low",
            },
            2: {
                "marks": 4, "items": 4,
                "skill": "Lexico-grammar",
                "focus": ["Tenses", "Determiners", "Pronouns", "Nouns"],
                "themes": [],
                "learning_standards": ["3.2.3"],
                "cefr": "A2 Low",
            },
            3: {
                "marks": 5, "items": 5,
                "skill": "Longer Text",
                "themes": [],
                "learning_standards": ["3.2.2", "3.2.3"],
                "cefr": "A2 Mid",
            },
            4: {
                "marks": 6, "items": 6,
                "skill": "Matching Multiple Texts",
                "themes": ["World of Knowledge"],
                "learning_standards": ["3.2.2", "3.2.3"],
                "cefr": "A2 Mid",
            },
            5: {
                "marks": 5, "items": 5,
                "skill": "Word Completion",
                "themes": ["World of Knowledge"],
                "learning_standards": ["3.2.3", "4.3.2"],
                "cefr": "Revise A2",
            },
            6: {
                "marks": 10, "items": 1,
                "skill": "Short Communicative Message",
                "themes": [],
                "learning_standards": ["4.2.2"],
                "cefr": "A2 Low",
                "task": "Describe future plans or events",
                # 4.2.2 is wider than its task line: it also covers
                # arranging, inviting and offering help, so a letter that
                # "organises a book sale" or asks a friend to "start" a
                # recycling programme is on-standard too.  Every signal is a
                # stem about *intention or arrangement*, never a topic word, so
                # "write about the alphabet" can never match.
                "signals": ["plan", "future", "will", "going to", "next",
                            "holiday", "trip", "visit", "outing", "arrang",
                            "organising", "organizing", "organise ",
                            "organize ", "event", "invit", "advice",
                            "offer", "help", "want", "hope", "wish",
                            "decid", "start", "begin", "change",
                            "ask", "request", "complain", "permission",
                            "suggest", "support", "thank"],
                # The generator is stricter than the audit.  A broad keyword
                # test lets a past-narrative letter ("your class lost a
                # sports day match") through on the word "match", so the
                # writer is chosen on markers that can only belong to an
                # intention or an arrangement: no past-tense verb can match.
                "writer_signals": ["going to", " will ", "next ", "want to",
                                   "want ", "would like", "hopes to",
                                   "hope to", "plan to", "planning",
                                   "invite", "inviting", "ask for",
                                   "suggest", "permission", "arrang",
                                   "organis", "organiz", "coming",
                                   "future", "is holding", "are holding"],
            },
            7: {
                "marks": 15, "items": 1,
                "skill": "Note Expansion",
                "themes": [],
                "learning_standards": ["4.2.3"],
                "cefr": "A2 Mid",
                "task": "Narrate factual events and experiences of interest",
                # 4.2.3 is about something that already happened, so every
                # signal is past or narrative in force.
                "signals": ["visit", "attend", "last", "yesterday", "trip",
                            "experience", "happened", "met", "went", "saw",
                            "story", "told", "remember", "ago", "watched",
                            "played", "won", "lost", "met", "bought", "ate",
                            "rode", "flew", "swam", "built", "began",
                            "finished", "prize", "match", "show",
                            "concert", "read", "learn", "report",
                            "every day", "used to", "conversation", "came",
                            "talked", "brought", "joined", "started",
                            "ended", "spent", "gave", "took", "travell",
                            "travel", "climbed", "swam", "cooked",
                            "watching",
                            # 4.2.3 is the *past* standard, so every regular
                            # past participle belongs to it.  "organised" is
                            # why 4.2.2 above matches the -ing and the bare
                            # stem only: a gotong-royong that already happened
                            # is an experience, a book sale still to arrange
                            # is a plan.
                            "organised", "organised", "arranged", "decided",
                            "made", "ran", "sent", "left", "felt", "kept",
                            "brought", "taught", "caught", "sang", "wrote",
                            "drew", "ate", "drank", "slept", "flew", "rode",
                            "wore", "broke", "chose", "drove", "put", "cut",
                            "hit", "shut", "cost", "meant", "met"],
                "writer_signals": ["won", "bought", "found", "helped", "had",
                                   "lost", "learned", "learnt", "watched",
                                   "visited", "travelled", "traveled", "held",
                                   "baked", "told", "read", "met", "saw",
                                   "went", "explored", "talked", "got",
                                   "played", "was ", "were ", "ago", "last ",
                                   "yesterday", "remember", "happened",
                                   "story", "journey", "wasn", "weren"],
            },
        },
    },
}

JSU[4] = _jsu_upper(
    4, "Year 4 UASA",
    "Make and respond to simple offers and invitations",
    ["offer", "invitation", "invite", "accept", "decline", "agree", "yes",
     "no thank", "wonderful", "sorry", "free", "join", "come", "guest"],
    "Narrate factual events and experiences of interest",
    ["visit", "attend", "last", "yesterday", "trip", "experience", "happened",
     "met", "went", "saw", "story", "told", "remember", "ago", "watch",
     "bought", "played", "ate", "home", "weekend", "day"])
JSU[5] = _jsu_upper(
    5, "Year 5 UASA",
    "Make and respond to simple offers and invitations",
    ["offer", "invitation", "invite", "accept", "decline", "agree", "free",
     "join", "come", "guest", "wonderful", "sorry", "yes", "no thank"],
    "Narrate factual and imagined events and experiences",
    ["visit", "attend", "last", "yesterday", "trip", "experience", "happened",
     "met", "went", "saw", "story", "told", "remember", "ago", "watch",
     "bought", "played", "ate", "home", "weekend", "day", "imagine",
     "pretend", "dream", "plan"])


#: The learning-standard ladder as the JSU words it for Years 4, 5 and 6, so
#: the same standard can be checked at every level of the upper primary.
#: Each record is keyed by its own code as well as by year, so a report can
#: name the standard without a second lookup.
JSU_STANDARDS = {
    "3.1.1": {
        "3.1.1": "Understand the main idea of longer texts",
        4: "Understand the main idea of simple longer texts.",
        5: "Understand the main idea of longer texts and of the main ideas of "
           "each paragraph.",
        6: "Understand the main idea and the main ideas of several paragraphs "
           "in longer texts.",
    },
    "3.1.2": {
        "3.1.2": "Understand specific information and details in simple "
                 "longer texts",
        4: "Understand specific information and details of short simple "
           "texts.",
        5: "Understand specific information and details of simple texts of "
           "one or two paragraphs.",
        6: "Understand specific information and details of two paragraphs or "
           "more.",
    },
    "3.1.3": {
        "3.1.3": "Guess the meaning of unfamiliar words from clues provided "
                 "by other known words and by context",
        4: "Guess the meaning of unfamiliar words from visuals and the topic.",
        5: "Guess the meaning of unfamiliar words from title and topic.",
        6: "Guess the meaning of unfamiliar words from other known words and "
           "by context.",
    },
    "3.2.1": {
        "3.2.1": "Understand the general meaning of short texts",
        4: "Understand the general meaning of short simple texts on familiar "
           "topics.",
        5: "Understand the general meaning of short texts and of one or two "
           "paragraphs on familiar topics.",
        6: "Understand the general meaning of short texts and of simple texts "
           "of two or more paragraphs on familiar topics.",
    },
    "3.2.2": {
        "3.2.2": "Understand specific information, details and the writer's "
                 "purpose",
        4: "Understand specific information, details and the writer's purpose "
           "in short simple texts.",
        5: "Understand specific information and details, and infer meaning in "
           "longer texts.",
        6: "Understand specific information and details, and infer meaning from "
           "a longer text with a range of structures.",
    },
    "3.2.3": {
        "3.2.3": "Guess unfamiliar words from the visuals, the topic and known "
                 "words",
        4: "Guess unfamiliar words from the visuals and the topic.",
        5: "Guess unfamiliar words from the title, the visuals and known words.",
        6: "Guess unfamiliar words from the title, the topic, the visuals and "
           "known words in the text.",
    },
    "4.2.1": {
        "4.2.1": "Give reasons and opinions",
        4: "Give reasons.",
        5: "Give reasons and opinions on a familiar topic.",
        6: "Give reasons, opinions and justifications in a longer text.",
    },
    "4.2.2": {
        "4.2.2": "Offer help, advice, invitations, and describe future plans "
                 "or events",
        4: "Offer help, advice and invitations.",
        5: "Give advice, and describe a simple plan or event.",
        6: "Describe future plans or events, and make arrangements with a "
           "range of structures.",
    },
    "4.2.3": {
        "4.2.3": "Describe routines, and narrate factual events and "
                 "experiences",
        4: "Describe daily routines and simple personal experiences.",
        5: "Describe routines, and narrate simple factual events and "
           "experiences.",
        6: "Narrate factual events and experiences of interest, and describe "
           "imagination and fantasy.",
    },
    "4.2.4": {
        "4.2.4": "Describe people, places and objects, and their personality",
        4: "Describe people, places and objects.",
        5: "Describe people, places and objects, and their personality.",
        6: "Describe people, places and objects, and compare their "
           "personality and qualities.",
    },
    "4.2.5": {
        "4.2.5": "Write a coherent paragraph or text of at least three "
                 "sentences",
        4: "Write a coherent paragraph of at least three sentences.",
        5: "Write a coherent paragraph of at least five sentences, using a "
           "range of conjunctions.",
        6: "Write a coherent text of at least two paragraphs, using a range of "
           "linkers and conjunctions.",
    },
    "4.3.1": {
        "4.3.1": "Use capital letters and punctuation correctly",
        4: "Use capital letters and full stops correctly in simple sentences.",
        5: "Use capital letters, full stops, commas and quotation marks "
           "correctly.",
        6: "Use capital letters, full stops, commas, apostrophes and "
           "quotation marks correctly in a longer text.",
    },
    "4.3.2": {
        "4.3.2": "Spell familiar words correctly and use correct word families",
        4: "Spell familiar words correctly.",
        5: "Spell familiar words and use correct word families.",
        6: "Spell familiar and less familiar words, and use correct word "
           "families.",
    },
    "4.3.3": {
        "4.3.3": "Produce a plan or draft of two paragraphs or more for a "
                 "familiar topic and modify this appropriately in response "
                 "to feedback",
        4: "Produce a plan or draft of one paragraph for a familiar topic "
           "and modify this appropriately in response to feedback.",
        5: "Produce a plan or draft of one or two paragraphs for a familiar "
           "topic and modify this appropriately in response to feedback.",
        6: "Produce a plan or draft of two paragraphs or more for a familiar "
           "topic and modify this appropriately in response to feedback.",
    },
}


# ---------------------------------------------------------------------------
# The Sheet 2 text-type and lexico-grammar lists
# ---------------------------------------------------------------------------
#: The nine Part 1 text types `JSU_Y4Y5Y6.xlsx` / Sheet 2 plots, in the sheet's
#: own order, so a JSU row names a genre the ministry recognises.
JSU_READING_GENRES = (
    "Notices", "Posters", "Labels / Signs / Charts", "Emails",
    "Advertisements", "Text Messages (SMS) / Post-it Notes", "Dialogues",
)
#: The eight Part 2 lexico-grammar focuses.  A Part 2 blank answered with a
#: *content* word is outside this list; `jsu.EXTRA_FOCUS` records the honest
#: extension the generator uses rather than mislabelling one.
JSU_GRAMMAR_FOCUS = (
    "Auxiliary Verbs", "Modal Verbs", "Determiners", "Pronouns",
    "Prepositions", "Conjunctions", "Adverbs", "Nouns",
)


# ---------------------------------------------------------------------------
# Round 33 (F3): difficulty shifts structure, not only vocabulary
# ---------------------------------------------------------------------------
# Before this round `difficulty` only re-ranked pool entries by lexical
# complexity, so an "easy" and a "hard" paper asked for the *same* writing
# length and the same passage shape.  These tables make the demand itself
# move.
#
# `WRITE_WORDS` gives a (min, max) word count per year and difficulty.  The
# published UPSA/UASA band is treated as `medium`; easy sits below it and hard
# above it, so a teacher asking for a "hard" paper really gets more writing.
WRITE_WORDS = {
    # Year 4 sits at the same A2 Low band as Year 5, and the school's own Y4
    # UASA 2025 asks for "about 30 - 50 words" and "60 to 80 words".
    4: {"easy": [25, 40], "medium": [30, 50], "hard": [50, 80]},
    1: {"easy": (10, 20), "medium": (15, 30), "hard": (25, 40)},
    2: {"easy": (15, 25), "medium": (20, 35), "hard": (30, 45)},
    3: {"easy": (20, 30), "medium": (30, 50), "hard": (45, 70)},
    5: {"easy": (25, 40), "medium": (30, 50), "hard": (50, 80)},
    6: {"easy": (30, 45), "medium": (40, 60), "hard": (60, 90)},
}

#: Ruled answer lines per writing part, scaled to the word count so a pupil
#: physically has room.  Keyed by difficulty band rather than by year, because
#: what matters is how much has to fit on the page.
WRITE_LINES = {"easy": 4, "medium": 6, "hard": 9}


def write_words(year: int, difficulty: str = "medium") -> tuple[int, int]:
    """Word band for a writing task; falls back to the published band."""
    table = WRITE_WORDS.get(int(year))
    if not table:
        return (30, 50)
    band = table.get(str(difficulty))
    return band or table.get("medium", (30, 50))


# Year 4 shares a few module names with Years 5-6 ("Getting Around"), and its
# modules are named after the Year 4 RPT document, so the two lists are unioned
# rather than one overwriting the other -- a themed Year 4 or Year 6 paper must
# both find their own on-theme questions and passages.
for _theme, _kws in _THEME_KEYWORDS_Y4.items():
    _existing = THEME_KEYWORDS.get(_theme) or []
    THEME_KEYWORDS[_theme] = list(dict.fromkeys(_kws + list(_existing)))


# ---------------------------------------------------------------------------
# Round 39: attainment objectives and performance levels
# ---------------------------------------------------------------------------
# The marking scheme could say what a question *tests* only in prose -- the JSU
# names the skill, but nothing said which attainment objective it served, and
# there was no mark weighting per objective at all.  A teacher auditing a paper
# against the DSKP had to add it up by hand from the part titles.
#
# AO1 recall of known language, AO2 comprehension of a given text, AO3 the
# pupil's own production.  Each part kind sits in exactly one, so the split is
# mechanical and nothing here is an opinion about a pupil's ability.
AOS = ("AO1", "AO2", "AO3")

AO_KIND = {
    # AO1 - recall: the pupil retrieves a known word, form or feature.
    "vocab": "AO1",
    "words": "AO1",
    "cloze": "AO1",
    # AO2 - comprehension: the answer is in, or is only reachable through, a
    # text the pupil is reading.  Matching and open comprehension are the
    # two ways this is asked at SJKC.
    "comprehension": "AO2",
    "match": "AO2",
    # AO3 - application: the pupil produces language of their own.
    "writing": "AO3",
}

AO_LABEL = {
    "AO1": "Recall of known words, forms and features",
    "AO2": "Comprehension of the given text",
    "AO3": "Application in the pupil's own writing",
}

#: Performance levels, lowest first.  A teacher marks a piece of writing by
#: finding the level that best describes it; the mark range is derived from the
#: part's own mark total so a 10-mark and a 15-mark part both get six usable
#: bands instead of one rounding to a single mark.
PL_LEVELS = (
    ("PL1", "Low", "The response is off-task or absent. Meaning is mostly not "
                    "communicated, and errors get in the way of reading it."),
    ("PL2", "Very limited", "Some relevant content, but the message is hard to "
                             "follow. Vocabulary and sentence control are well "
                             "below the level of the task."),
    ("PL3", "Limited", "The message can be followed. Content is thin, or the "
                       "language is inaccurate often enough to need the reader's "
                       "effort."),
    ("PL4", "Satisfactory", "A clear, relevant response that meets the task. "
                            "Grammar and vocabulary are mostly right, with "
                            "slips that do not obscure meaning."),
    ("PL5", "Good", "A relevant, well-organised response with a range of "
                    "appropriate vocabulary and structures. Errors are few and "
                    "do not distract."),
    ("PL6", "Excellent", "A confident response that develops the content and "
                         "organises it for the reader. Vocabulary and structures "
                         "are varied and accurate, and spelling and punctuation "
                         "are essentially correct."),
)

#: The note printed above the table.  Nothing in the ministry corpus supplied a
#: performance-level scale, so the levels are printed as teacher guidance to be
#: checked against the district scheme rather than presented as the official
#: wording -- a teacher marking real scripts must know which is which.
PL_CAVEAT = ("Performance levels below are teacher guidance for marking this "
             "paper. They are not the ministry wording - check them against "
             "your district marking scheme before using them to mark.")


def ao_for_kind(kind: str) -> str:
    """The attainment objective a part kind serves.

    An unlisted kind is treated as AO1 rather than raising: a new part kind
    should still be markable and still be auditable, and the marking scheme
    saying AO1 for something unclassified is safer than crashing a teacher's
    export.
    """
    return AO_KIND.get(str(kind or "").strip(), "AO1")


def pl_bands(total_marks: float) -> list[tuple[str, str, float, float, str]]:
    """Split a writing part's marks into the six performance levels.

    Returns ``[(code, name, low, high, descriptor)]`` from PL1 up, covering
    every mark from 0 to ``total_marks`` with no gap and no overlap.  The split
    is proportional, so the middle bands are the widest -- that is where a
    real cohort of Year 3-6 scripts actually sits, and it matches how a single
    mark is not enough to separate six levels on a 10-mark part.
    """
    total = max(1, int(round(float(total_marks or 0))))
    bands: list[tuple[str, str, float, float, str]] = []
    # Six bands as integer marks-per-level, largest remainder first so the
    # rounding error lands on the widest band rather than the last one.
    cuts = [round(total * (i + 1) / 6) for i in range(5)]
    low = 0
    for i, (code, name, desc) in enumerate(PL_LEVELS):
        high = cuts[i] if i < 5 else total
        bands.append((code, name, float(low), float(high), desc))
        low = high + 1
    return bands
