"""SJKC-themed question bank and paper generator.

Content is anchored to Malaysian SJKC primary life: school subjects (Bahasa
Melayu, Bahasa Cina, Matematik, Sains), Malaysian food, festivals, landmarks,
national animals and everyday routines.  Each part generator picks fresh items
per call so every click produces a different paper; the matching answer key is
built alongside the questions in ``build_key``.
"""

from __future__ import annotations

import os
import random
import re

from . import data as D
from .models import MCQItem, WordItem, WriteItem, Part, Paper

# Round 11-12: the authored-but-unwired content banks.  Each module holds a
# per-year pool (18-20 sets); merging them at load time gives every part real
# variation (the pools used to hold 2-3 sets each).
from . import extra_comp_56 as _XC
from . import extra_match_123 as _XM123
from . import extra_match_56 as _XM56
from . import extra_vocab as _XV
from . import extra_vocab_dskp as _XVD
from . import extra_words as _XW
from . import extra_writing as _XWR
from . import extra_writing_4 as _XWR4
from . import extra_writing_56 as _XWR56
from . import extra_comp_123 as _XCO
from . import extra_cloze as _XCL
from . import extra_words_dskp as _XWD


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _rag(stem: str, opts: list[str], ans: int, box=None, ans_text=None) -> dict:
    """Return a raw MCQ dict (answer is an index into opts)."""
    return {"stem": stem, "opts": opts, "ans": ans, "box": box, "ans_text": ans_text}


def _rng(conf: dict):
    return random.Random(int(conf.get("seed", 1)) ^ (int(conf.get("year", 3)) * 991))


def _shuffle_mcq(rng, item: dict) -> MCQItem:
    opts = list(item["opts"])
    ans = item["ans"]
    pair = list(zip(opts, [i == ans for i in range(len(opts))]))
    rng.shuffle(pair)
    opts, flags = zip(*pair) if pair else ([], [])
    new_ans = flags.index(True)
    stim = item.get("stimulus")
    return MCQItem(
        stem=item["stem"], options=list(opts), answer=new_ans,
        wordbox=item.get("box"), lead=item.get("lead"),
        ans_text=item.get("ans_text"),
        stimulus=list(stim) if stim else None,
    )


def _keep_letter_order(item: dict) -> MCQItem:
    """An MCQ whose "options" are the letters A, B, C in order.

    Part 4 is the one place the letters are not options: each one labels a
    text printed above the questions, so the list must stay in A, B, C order
    and only the answer index may change.  Shuffling it would print "A. C" and
    break the link between the letter and its text.
    """
    opts = list(item["opts"])
    stim = item.get("stimulus")
    return MCQItem(
        stem=item["stem"], options=opts,
        answer=int(item.get("ans", item.get("answer", 0))),
        wordbox=item.get("box"), lead=item.get("lead"),
        ans_text=item.get("ans_text"),
        stimulus=list(stim) if stim else None,
    )


# ---------------------------------------------------------------------------
# difficulty + RPT theme helpers
# ---------------------------------------------------------------------------

#: The supported SJKC levels in age order, so ``easy`` can borrow a
#: younger pool and ``hard`` an older one.  Year 4 belongs in the middle:
#: without it, a Year 4 paper's "hard" questions came from Year 6.
YEAR_ORDER = [1, 2, 3, 4, 5, 6]


def shift_year(year, difficulty: str) -> int:
    """Shift the source-year of the question pool for the chosen difficulty.

    ``easy`` borrows a younger year's pool, ``hard`` an older year's pool, both
    clamped to the supported SJKC levels — every level stays age-appropriate.
    """
    try:
        idx = YEAR_ORDER.index(int(year))
    except ValueError:
        return int(year)
    step = {"easy": -1, "hard": 1}.get(str(difficulty), 0)
    return YEAR_ORDER[max(0, min(len(YEAR_ORDER) - 1, idx + step))]


def next_seed(seed: int) -> int:
    """Deterministic next seed for the Regenerate button (1..9 step)."""
    return int(seed) + random.Random(int(seed)).randint(1, 9)


def next_theme(year: int, idx: int) -> tuple[int, str]:
    """Advance one step in the year's RPT theme list -> (new_index, theme)."""
    themes = D.RPT_THEMES.get(int(year), [])
    if not themes:
        return 0, ""
    nxt = (int(idx) + 1) % len(themes)
    return nxt, themes[nxt]


# ---------------------------------------------------------------------------
# RPT week scheduling — 40 school weeks divided across the year's themes
# ---------------------------------------------------------------------------

SCHOOL_WEEKS = 40


def theme_weeks(year: int) -> list[int]:
    """First week of each RPT theme for the year (theme i starts at the value)."""
    themes = D.RPT_THEMES.get(int(year), [])
    n = max(len(themes), 1)
    return [1 + round(i * SCHOOL_WEEKS / n) for i in range(len(themes))]


def theme_for_week(year: int, week) -> str:
    """RPT theme scheduled for ``week`` (1..40); '' when week <= 0 (off)."""
    themes = D.RPT_THEMES.get(int(year), [])
    if not themes:
        return ""
    try:
        w = int(week)
    except (TypeError, ValueError):
        return ""
    if w <= 0:
        return ""
    w = max(1, min(SCHOOL_WEEKS, w))
    bounds = theme_weeks(year)
    cur = themes[0]
    for i, t in enumerate(themes):
        if w >= bounds[i]:
            cur = t
    return cur


def weeks_for_theme(year: int, theme: str):
    """(first_week, last_week) for a theme, or None if unknown."""
    themes = D.RPT_THEMES.get(int(year), [])
    bounds = theme_weeks(year)
    for i, t in enumerate(themes):
        if t == theme:
            end = (bounds[i + 1] - 1) if i + 1 < len(bounds) else SCHOOL_WEEKS
            return (bounds[i], end)
    return None


# ---------------------------------------------------------------------------
# user question bank (F5) — extra passages/item sets from a JSON file
# ---------------------------------------------------------------------------

USER_KINDS = ("vocab", "comprehension", "cloze", "match", "words",
              "letter_words")


def parse_user_bank(obj) -> dict[str, dict[int, list[dict]]]:
    """Validate/normalise a user bank JSON into {kind: {year: [entries]}}.

    ``year`` may be one of D.YEARS or ``"any"``/omitted (applied to every
    level).  Malformed entries are dropped rather than crashing generation.
    """
    out: dict[str, dict[int, list[dict]]] = {
        k: {y: [] for y in D.YEARS} for k in USER_KINDS}
    if not isinstance(obj, dict):
        return out
    for kind in USER_KINDS:
        for entry in obj.get(kind, []) or []:
            if not isinstance(entry, dict):
                continue
            ok = {"vocab": ("stem", "opts"),
                  "comprehension": ("passage", "qs"),
                  "cloze": ("passage", "gaps"),
                  "match": ("texts", "qs"),
                  "words": ("box", "items"),
                  "letter_words": ("clue", "word")}[kind]
            if not all(entry.get(k) not in (None, []) for k in ok):
                continue
            raw_y = entry.get("year")
            if raw_y in (None, "any", 0, "0"):
                years = list(D.YEARS)
            else:
                years = [int(raw_y)]
            for y in years:
                if y in D.YEARS:
                    out[kind][y].append(entry)
    return out


def load_user_bank(path: str) -> dict:
    """Read + parse a user bank JSON file."""
    import json
    with open(path, encoding="utf-8") as fh:
        return parse_user_bank(json.load(fh))


def _normalize_user_bank(ub):
    """Accept either a raw JSON schema dict or an already-parsed bank."""
    if not ub:
        return None
    first = next(iter(ub.values())) if isinstance(ub, dict) and ub else None
    if isinstance(first, dict):
        return ub
    return parse_user_bank(ub)


def user_pool(user_bank, kind: str, year_src: int, year: int) -> list[dict]:
    """User entries usable for a part sourced from ``year_src`` on paper ``year``."""
    if not user_bank:
        return []
    by_year = user_bank.get(kind, {})
    seen = set()
    out = []
    for y in (int(year_src), int(year)):
        for d in by_year.get(y, []):
            if id(d) not in seen:
                seen.add(id(d))
                out.append(d)
    return out


def bank_template() -> dict:
    """Editable example of the user question-bank JSON schema."""
    return {
        "comprehension": [
            {"year": 3, "theme": "World of Knowledge",
             "title": "My Own Passage",
             "passage": "Write your reading passage here. "
                        "Keep it one short paragraph for lower years.",
             "qs": [{"stem": "Write a question here.",
                     "opts": ["Answer A", "Answer B", "Answer C"], "ans": 0}]}
        ],
        "cloze": [
            {"year": 1, "passage": "Ali opens his school (1)______ in class.",
             "gaps": [{"stem": "Ali opens his school __________.",
                       "opts": ["bag", "car", "kite"], "ans": 0}]}
        ],
        "match": [
            {"year": 5, "texts": ["A. One short text.",
                                  "B. A second short text.",
                                  "C. A third short text."],
             "qs": [{"stem": "A sentence that matches one text.",
                     "opts": ["A", "B", "C"], "ans": 0}]}
        ],
        "words": [
            {"year": 2, "box": ["cat", "dog", "bird"],
             "items": [{"stem": "The ____ says meow.",
                        "opts": ["cat", "dog", "bird"], "ans": 0,
                        "ans_text": "cat"}]}
        ],
        "letter_words": [
            {"year": 5, "clue": "It flies and builds a nest.", "word": "sparrow"}
        ],
    }


def mark_sheet(paper) -> dict:
    """Per-part marking grid: qno, abridged prompt, blank score; total always 50."""
    parts = []
    for p in paper.parts:
        rows = []
        qno = p.qfirst
        for it in p.items:
            text = (getattr(it, "stem", None) or getattr(it, "clue", None)
                    or getattr(it, "prompt", ""))
            text = " ".join(str(text).split())
            if len(text) > 64:
                text = text[:61] + "…"
            rows.append({"q": qno, "text": text})
            qno += 1
        parts.append({"part": p.num, "title": p.title, "marks": p.marks,
                      "items": rows})
    return {"parts": parts, "total": D.TOTAL}


def _theme_kws(theme: str | None):
    return D.THEME_KEYWORDS.get(theme, []) if theme else []


def _block_text(block: dict) -> str:
    bits = [block.get("title", ""), block.get("passage", ""),
            block.get("text", ""), block.get("prompt", ""),
            block.get("focus", ""), block.get("clue", ""),
            block.get("model", "")] \
        + list(block.get("texts") or []) + list(block.get("box") or []) \
        + list(block.get("bullets") or []) + list(block.get("sentences") or []) \
        + list(block.get("words") or [])
    for q in (block.get("qs") or []) + (block.get("gaps") or []) \
            + (block.get("items") or []):
        if isinstance(q, dict):
            bits.append(str(q.get("stem", "")))
            bits += [str(o) for o in (q.get("opts") or [])]
    return " ".join(bits).lower()


def _matches_theme(block: dict, kws: list[str]) -> bool:
    import re
    text = _block_text(block)
    for k in kws:
        if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text):
            return True
    return False


# ---------------------------------------------------------------------------
# difficulty banding — in-year only
# ---------------------------------------------------------------------------
# Pools live per year (not cross-year).  Within a year, every entry is scored
# by lexical complexity and split into easy / medium / hard bands, so a paper
# is never "too easy" (younger pool) or "too hard" (older pool) — it stays in
# the year's own material.  ``shift_year`` is retained for compatibility but
# is no longer used when ordering a paper.

LONG_WORD = 7


def _dl_score(text) -> float:
    import re
    words = re.findall(r"[a-z']+", str(text).lower())
    if not words:
        return 0.5
    avg = sum(len(w) for w in words) / len(words)
    longf = sum(1 for w in words if len(w) >= LONG_WORD) / len(words)
    return round(min(1.0, 0.35 * (avg / 6.0) + 0.65 * longf), 3)


def _entry_text(entry) -> str:
    if not isinstance(entry, dict):
        return str(entry)
    bits = [entry.get(t, "") for t in
            ("title", "passage", "text", "prompt", "clue", "model",
             "word", "example", "focus", "recipient", "subject")]
    for key in ("words", "texts", "box", "bullets", "sentences"):
        bits += list(entry.get(key) or [])
    for q in (entry.get("qs") or []) + (entry.get("gaps") or []) \
            + (entry.get("items") or []):
        if isinstance(q, dict):
            bits.append(q.get("stem", ""))
            bits += list(q.get("opts") or [])
    return " ".join(str(b) for b in bits if b)


def _band(pool, difficulty, need: int = 1):
    """Subset of ``pool`` for the difficulty band (easy/hard; medium = all)."""
    pool = list(pool)
    if str(difficulty) not in ("easy", "hard") or len(pool) <= need:
        return pool
    scored = sorted(((_dl_score(_entry_text(e)), i, e) for i, e in enumerate(pool)))
    half = max(1, len(scored) // 2)
    keep = scored[:half] if str(difficulty) == "easy" else scored[half:]
    out = [e for _, _, e in keep]
    if len(out) < need:
        out = pool
    return out


def _dskp_prefer(pool: list[dict], year: int, need: int) -> list[dict]:
    """Order a content pool so DSKP-on-curriculum blocks are chosen first.

    The official papers only test words a pupil has met in class, and the KSSR
    word list (see :mod:`exam_gen.dskp`) is the authority on which those are.
    Blocks are *demoted* rather than dropped: when nothing on-list carries
    ``need`` items, the off-list blocks are appended so a part is never left
    short.  Blocks with no word-box / answer text at all (a user's custom
    bank, a themed block) are kept in their original order.
    """
    from . import dskp
    pool = list(pool or [])
    on, off, plain = [], [], []
    for b in pool:
        answers = _block_answers(b)
        if not answers:
            plain.append(b)
        elif dskp.off_curriculum(answers, year):
            off.append(b)
        else:
            on.append(b)
    if sum(len(b.get("items") or []) for b in on) >= need:
        return on + plain
    return pool


def _dskp_answer_first(pool: list[dict], year: int, need: int) -> list[dict]:
    """Drop flat MCQ items whose *answer* is off the DSKP ladder for ``year``.

    Round 25.  Only the target word is gated — distractor words are policed by
    :func:`_dskp_prefer` and the ``TestDskpGate`` familiarity ratio, because a
    hard distractor rule would empty several pools.  Off-list items are kept
    as a tail so a part is never short of questions, but they are removed up
    front (not merely reordered) because :func:`_pick_items` samples uniformly
    and would otherwise draw them regardless of position.

    Returns the pool unchanged if too few on-list items survive to fill
    ``need`` questions.
    """
    from . import dskp
    pool = list(pool or [])
    on, off = [], []
    for q in pool:
        if not isinstance(q, dict):
            on.append(q)
            continue
        # Round 26: a Part 1 *short-stimulus* item is a reading question — the
        # answer is a phrase the pupil locates in the poster/menu/email, not a
        # vocabulary target.  A word list is the wrong gate for it (the
        # official answer "the first 12 applicants" is not a headword), and
        # gating it here emptied the whole official pool.  The reading
        # guarantee for these items is "the answer is in the stimulus", checked
        # by ``qc._part1_stimulus_issues``.
        if q.get("stimulus"):
            on.append(q)
            continue
        opts = q.get("opts") or q.get("options") or []
        idx = q.get("ans", q.get("answer"))
        if not (opts and isinstance(idx, int) and 0 <= idx < len(opts)):
            on.append(q)
            continue
        (off if dskp.off_curriculum(opts[idx], year) else on).append(q)
    # Headroom of 2x lets theme matching and the difficulty band still choose
    # freely after the off-list items are gone.
    return on if len(on) >= need * 2 else pool


def _cloze_on_ladder(pool: list[dict], year: int) -> list[dict]:
    """Keep only the cloze blocks whose *every* gap answer is on the ladder.

    Round 26: Round 25 stated the "target word is on the year's DSKP ladder"
    contract for Parts 1 and 2, but only the flat Part 1 pool was actually
    gated — a Part 2 block could still be drawn with an off-list answer
    ("cocoon", "locker").  The old test only sampled one seed, so it never
    saw them.  This is the Part 2 half of the same guarantee.

    Returns ``[]`` when nothing survives so the caller can fall back.
    """
    from . import dskp
    keep = []
    for block in pool or []:
        if not isinstance(block, dict):
            continue
        answers = []
        for gap in block.get("gaps", []):
            opts = gap.get("opts") or gap.get("options") or []
            idx = gap.get("ans", gap.get("answer"))
            if opts and isinstance(idx, int) and 0 <= idx < len(opts):
                answers.append(gap.get("ans_text") or opts[idx])
        if answers and not dskp.off_curriculum(answers, year):
            keep.append(block)
    return keep


def _part1_stimulus_first(pool: list[dict], need: int) -> list[dict]:
    """Keep only the official Part 1 shape when there are enough of them.

    Round 26.  A Part 1 item is only the official short-stimulus question when
    it carries a ``stimulus`` to read and asks a question; the older pools
    also hold a gap-fill cloze wearing a decorative heading, whose three
    options were drawn from unrelated categories so that two of them could be
    thrown out without reading anything.

    The official items are *preferred* and the legacy ones demoted rather than
    deleted: a user's own bank may hold nothing but gap-fills, and a part is
    never left short.  Once there are ``need`` stimulus items the legacy shape
    is dropped outright, because that is what stops it reaching a paper.
    """
    official = [q for q in pool if q.get("stimulus")]
    legacy = [q for q in pool if not q.get("stimulus")]
    if len(official) >= need:
        return official
    return official + legacy


def _block_target_ok(block: dict, year: int, keys=("gaps", "qs")) -> bool:
    """True when every *answer* word in a passage block is on the DSKP ladder.

    Part 2 (cloze) and Part 3 (comprehension) draw a whole passage and then
    blanks words in it, so the target words are the answers rather than a
    single chosen option.  A block is only usable if all of them pass; the
    caller keeps the original pool as a fallback so a part is never left
    without a passage.
    """
    from . import dskp
    items = None
    for key in keys:
        if block.get(key):
            items = block[key]
            break
    if not items:
        return True
    for raw in items:
        if not isinstance(raw, dict):
            continue
        opts = raw.get("opts") or raw.get("options") or []
        idx = raw.get("ans", raw.get("answer"))
        if not (opts and isinstance(idx, int) and 0 <= idx < len(opts)):
            continue
        if dskp.off_curriculum(opts[idx], year):
            return False
    return True


def _dskp_block_gate(blocks: list[dict], year: int, count: int,
                     keys=("gaps", "qs"), base=None) -> list[dict]:
    """Keep only blocks whose answers are on the year's DSKP ladder.

    A block is the unit of choice for Part 2 and Part 3, so the gate has to
    work a block at a time — a single off-list gap would smuggle a word past
    the check.  ``base`` is returned untouched when too few clean blocks
    remain to fill ``count`` questions.
    """
    blocks = list(blocks or [])
    clean = [b for b in blocks if _block_target_ok(b, year, keys)]
    if len(clean) >= max(2, count // 2):
        return clean
    return blocks


def _block_answers(block) -> list[str]:
    """Every answer word a content block puts in front of a pupil."""
    out: list[str] = []
    for item in (block or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        opts = item.get("opts") or item.get("options") or []
        idx = item.get("ans", item.get("answer"))
        if opts and isinstance(idx, int) and 0 <= idx < len(opts):
            out.append(str(opts[idx]))
        elif item.get("word"):
            out.append(str(item["word"]))
    for w in (block or {}).get("box") or []:
        out.append(str(w))
    return out


#: Minimum number of teacher-format ("mode") blocks before Part 2 may
#: narrow its pool to them outright.  Below this the preference would leave a
#: whole year with only two possible passages -- see SPEC 59.
_P2_PREFERRED_MIN = 6


def _pick_block(rng, pool, theme, fallbacks=(), difficulty="medium"):
    """Pick a content block from ``pool``, theme- then difficulty-preferred."""
    kws = _theme_kws(theme)
    if kws:
        for src in (list(pool), *[list(f) for f in fallbacks]):
            matched = [d for d in src if _matches_theme(d, kws)]
            if matched:
                return rng.choice(_band(matched, difficulty, need=1))
    return rng.choice(_band(list(pool), difficulty, need=1))


def _theme_prefer(pool, theme, need: int = 1):
    """Narrow ``pool`` to on-theme entries when enough of them exist.

    Entries may carry an explicit ``theme`` tag (built-in writing prompts do);
    otherwise the theme's keywords are searched in the entry text.  Used for
    writing prompts and other pools that were previously picked at random, so
    every part of a themed paper stays about the same topic.
    """
    pool = list(pool)
    if theme:
        tagged = [d for d in pool if isinstance(d, dict)
                  and d.get("theme") == theme]
        if len(tagged) >= need:
            return tagged
    kws = _theme_kws(theme)
    if kws and need > 0:
        matched = [d for d in pool if _matches_theme(d, kws)]
        if len(matched) >= need:
            return matched
    return pool


def _pick_items(rng, items, theme, count: int, difficulty="medium"):
    """Pick ``count`` raw MCQ dicts, theme-first then difficulty, exact count."""
    kws = _theme_kws(theme)
    pool = list(items)
    if kws:
        matched = [d for d in items
                   if any(k in str(d.get("stem", "")).lower() for k in kws)]
        if len(matched) >= count:
            pool = matched
    banded = _band(pool, difficulty, need=count)
    picked = rng.sample(banded, min(count, len(banded)))
    if len(picked) < count:                      # never short-change a tally
        rest = [d for d in pool if id(d) not in {id(x) for x in picked}]
        picked += rng.sample(rest, min(count - len(picked), len(rest)))
    return picked


# ---------------------------------------------------------------------------
# Round 13 (S4): difficulty calibration — rotate weak questions out.
# ---------------------------------------------------------------------------
# The marking window records asked/wrong tallies per exact-grade question
# (``marks.record_stats`` -> difficulty_stats.json in the exam data dir).
# ``_order_by_stats`` re-orders a pool so chronically-missed items sink to the
# tail and are only picked when the pool can't fill a paper another way.  It
# is opt-in via ``calibrate: True`` in the generator config (GUI toggle / CLI
# ``--calibrate``), so default paper output stays deterministic.

MISS_DROP_RATE = 0.75      # miss-rate above which an item is deprecated
MISS_DROP_MIN = 2          # ... and only after at least this many asks


def qkey(item) -> str:
    """Deterministic key for one exact-grade generated item ('' = not tracked)."""
    import hashlib
    if item.__class__.__name__ == "MCQItem":
        if not getattr(item, "options", None):
            return ""
        payload = f"{item.stem}|{'~'.join(item.options)}|{_answer_text(item)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    if item.__class__.__name__ == "WordItem":
        if not getattr(item, "answer", ""):
            return ""
        payload = "word|" + str(getattr(item, "answer", "")).lower()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return ""


def _raw_key(raw: dict) -> str:
    """Key for a raw pool MCQ dict (same shape as ``qkey`` for its MCQ)."""
    import hashlib
    opts = list(raw.get("opts") or [])
    if not opts:
        return ""
    ans = raw.get("ans_text") or (opts[raw["ans"]] if isinstance(
        raw.get("ans"), int) and 0 <= raw["ans"] < len(opts) else "")
    payload = f"{raw.get('stem', '')}|{'~'.join(opts)}|{ans}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _block_key(block: dict) -> str:
    """Key for a passage/gap/match/word-box block (whole block treated as one)."""
    import hashlib
    bits = [str(block.get("passage", "")), str(block.get("texts", ""))]
    for q in list(block.get("qs") or []) + list(block.get("gaps") or []) \
            + list(block.get("items") or []):
        bits.append(_raw_key(q) if isinstance(q, dict) else str(q))
    payload = "|".join(bits)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _cell_drop(cell) -> bool:
    if not isinstance(cell, dict):
        return False
    asked = int(cell.get("asked", 0) or 0)
    misses = int(cell.get("misses", 0) or 0)
    return bool(asked >= MISS_DROP_MIN and
                (misses / asked) >= MISS_DROP_RATE)


def _order_by_stats(pool, stats, keyfn) -> list:
    """Reorder ``pool`` healthy-first; no stats -> unchanged order."""
    if not stats:
        return list(pool)
    table = (stats or {}).get("q") or {}
    healthy, weary, drop = [], [], []
    for entry in pool:
        cell = table.get(keyfn(entry))
        if cell and _cell_drop(cell):
            drop.append(entry)
        elif cell:
            weary.append(entry)
        else:
            healthy.append(entry)
    return healthy + weary + drop


def stats_path() -> str:
    """Difficulty-stats file inside the exam data dir."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "exam-gen", "difficulty_stats.json")


def load_stats() -> dict:
    import json as _json
    try:
        with open(stats_path(), encoding="utf-8") as fh:
            return _json.load(fh)
    except Exception:
        return {}


def save_stats(stats: dict) -> None:
    import json as _json
    os.makedirs(os.path.dirname(stats_path()) or ".", exist_ok=True)
    with open(stats_path(), "w", encoding="utf-8") as fh:
        _json.dump(stats, fh, ensure_ascii=False, indent=2)


def record_stats(papers, pupils) -> dict:
    """Load, merge and persist difficulty stats for a marking batch."""
    from . import marks
    stats = marks.record_stats(papers, pupils, load_stats())
    _prune_stats(stats)
    save_stats(stats)
    return stats


def _prune_stats(stats: dict, keep: int = 5000) -> dict:
    """Trim the stats table to the most-asked entries (bounded growth)."""
    table = (stats or {}).setdefault("q", {})
    if len(table) <= keep:
        return stats
    ordered = sorted(table.items(),
                     key=lambda kv: kv[1].get("asked", 0) if isinstance(
                         kv[1], dict) else 0, reverse=True)[:keep]
    stats["q"] = {k: v for k, v in ordered}
    return stats


def _part_topic(p: Part) -> str:
    """Guess an art scene topic for a part from its passage / items.

    The photo subject is grounded in everything the pupil actually reads: the
    passage/word box (``lead_text``), every item stem, and each item's option
    strings and answer word (Round 14 follow-up), so the picture follows the
    vocabulary the questions ask about — e.g. a Part 5 word box of animals
    pictures the animal word being tested.
    """
    from .art import query_for_text, topics_for_text
    bits = [p.lead_text or ""]
    for it in p.items:
        bits.append(str(getattr(it, "stem", "") or ""))
        opts = getattr(it, "options", None) or None
        if opts:
            bits.extend(str(o) for o in opts)
        ans = getattr(it, "ans_text", "") or getattr(it, "answer", "")
        if ans:
            bits.append(str(ans))
    text = " ".join(b for b in bits if b)
    p.photo_query = query_for_text(text)
    return topics_for_text(text)


# ---------------------------------------------------------------------------
# YEAR 1 & 2 vocabulary / word pools
# ---------------------------------------------------------------------------

VOCAB_LOWER = {
    1: [
        _rag("Sarah uses a __________ to write her name in her book.",
             ["ruler", "bag", "pen"], 2, ans_text="pen"),
        _rag("Jim wants to erase a wrong word. He uses a __________.",
             ["pencil", "rubber", "book"], 1, ans_text="rubber"),
        _rag("Lily has two __________ in her pencil case. She draws straight lines.",
             ["rulers", "bags", "cats"], 0, ans_text="rulers"),
        _rag("Jack puts his books inside his __________.",
             ["bag", "ruler", "rubber"], 0, ans_text="bag"),
        _rag("We cut paper with a pair of __________.",
             ["scissors", "rulers", "crayons"], 0, ans_text="scissors"),
        _rag("Mei Ling paints a flower with her __________.",
             ["pencil case", "crayon", "bag"], 1, ans_text="crayon"),
        _rag("Before school, Kok Wai eats his __________ with kuih.",
             ["breakfast", "lunch", "dinner"], 0, ans_text="breakfast"),
        _rag("Ahmad carries his books in a __________ to school.",
             ["school bus", "school bag", "school bell"], 1, ans_text="school bag"),
        _rag("The pupils sing the national anthem during the __________.",
             ["assembly", "lesson", "game"], 0, ans_text="assembly"),
        _rag("Nabila drinks __________ in the hot afternoon.",
             ["nasi lemak", "water", "satay"], 1, ans_text="water"),
        _rag("The bird cuts across the sky with its two __________.",
             ["wings", "beaks", "nests"], 0, ans_text="wings"),
        _rag("Aiman wears a __________ on his head when it is hot.",
             ["shirt", "cap", "sock"], 1, ans_text="cap"),
        _rag("We wear __________ on our feet before putting on our shoes.",
             ["socks", "hats", "gloves"], 0, ans_text="socks"),
        _rag("Mother cooks rice in the __________.",
             ["bathroom", "kitchen", "bedroom"], 1, ans_text="kitchen"),
        _rag("We brush our teeth in the __________.",
             ["bathroom", "kitchen", "dining room"], 0, ans_text="bathroom"),
        _rag("Anita sleeps in her __________ every night.",
             ["kitchen", "bedroom", "garage"], 1, ans_text="bedroom"),
        _rag("We eat dinner together in the __________.",
             ["dining room", "toilet", "store", ], 0, ans_text="dining room"),
        _rag("Father drives us to school in his __________.",
             ["car", "boat", "plane"], 0, ans_text="car"),
        _rag("The __________ takes pupils to school every morning.",
             ["school bus", "aeroplane", "ferry"], 0, ans_text="school bus"),
        _rag("Muthu rides his __________ to the playground.",
             ["bicycle", "car", "train"], 0, ans_text="bicycle"),
        _rag("At the night market, we buy sweet, juicy __________.",
             ["durian", "rambutan", "curry"], 1, ans_text="rambutan"),
        _rag("The king of fruits in Malaysia is the __________.",
             ["durian", "mango", "apple"], 0, ans_text="durian"),
        _rag("My grandmother gives me a red __________ during Chinese New Year.",
             ["ang pow", "ketupat", "kolam"], 0, ans_text="ang pow"),
        _rag("We eat __________, a diamond-shaped rice cake, during Hari Raya.",
             ["ketupat", "mooncake", "dumpling"], 0, ans_text="ketupat"),
        _rag("During the Chinese New Year reunion dinner, the family eats __________.",
             ["yee sang", "satay", "pizza"], 0, ans_text="yee sang"),
        _rag("The school canteen worker sells __________ to the pupils.",
             ["mee goreng", "textbooks", "pens"], 0, ans_text="mee goreng"),
        _rag("The teacher writes the spelling words on the __________.",
             ["whiteboard", "window", "door"], 0, ans_text="whiteboard"),
        _rag("We borrow storybooks from the __________.",
             ["library", "canteen", "office"], 0, ans_text="library"),
        _rag("A __________ helps us when we are sick.",
             ["doctor", "teacher", "singer"], 0, ans_text="doctor"),
        _rag("The __________ drives the lorry that collects rubbish.",
             ["garbage collector", "bus driver", "postman"], 0, ans_text="garbage collector"),
    ],
    2: [
        _rag("Mia loves to splash in the water at the __________.",
             ["beach", "library", "classroom"], 0, ans_text="beach"),
        _rag("Wei Jie feeds __________ and tortoises at the farm.",
             ["goats", "computers", "bicycles"], 0, ans_text="goats"),
        _rag("Mother buys vegetables and fish at the __________.",
             ["market", "cinema", "museum"], 0, ans_text="market"),
        _rag("Ami rides the __________ to school with her father.",
             ["LRT", "ferry", "aeroplane"], 0, ans_text="LRT"),
        _rag("The national flower of Malaysia is the __________.",
             ["bunga raya", "roses", "lotus"], 0, ans_text="bunga raya"),
        _rag("The __________ is a shy animal that rolls into a ball.",
             ["pangolin", "tiger", "elephant"], 0, ans_text="pangolin"),
        _rag("The Malayan tiger has orange fur with black __________.",
             ["stripes", "spots", "dots"], 0, ans_text="stripes"),
        _rag("During Deepavali, Devi lights small __________ at home.",
             ["oil lamps", "lampposts", "candles"], 0, ans_text="oil lamps"),
        _rag("We fly __________ with our family in the school field.",
             ["kites", "boats", "trains"], 0, ans_text="kites"),
        _rag("Chee Seng wears his __________ sports uniform on Sports Day.",
             ["white and blue", "green and pink", "black and brown"], 0, ans_text="white and blue"),
        _rag("The __________ plays the drums at the Chinese New Year parade.",
             ["drummer", "teacher", "gardener"], 0, ans_text="drummer"),
        _rag("Mummy says the __________ is hot and sweet.",
             ["pandan cake", "salad", "soup"], 0, ans_text="pandan cake"),
        _rag("The firefly at night looks like a tiny __________.",
             ["lamp", "star", "moon"], 0, ans_text="lamp"),
        _rag("Before sleeping, Hui Ling puts on her __________.",
             ["pyjamas", "uniform", "costume"], 0, ans_text="pyjamas"),
        _rag("On rainy days, we wear a __________ to stay dry.",
             ["raincoat", "cap", "scarf"], 0, ans_text="raincoat"),
        _rag("Aini's pet cat sleeps on a soft __________.",
             ["cushion", "book", "plate"], 0, ans_text="cushion"),
        _rag("The canteen auntie gives me an extra scoop of __________.",
             ["ice cream", "soap", "rice cup"], 0, ans_text="ice cream"),
        _rag("We keep our exercise books in the __________.",
             ["classroom cupboard", "playground", "bathroom"], 0, ans_text="classroom cupboard"),
        _rag("Ah Seng waters the plants in the school __________.",
             ["garden", "car park", "toilet"], 0, ans_text="garden"),
        _rag("The red packet is given to children on __________.",
             ["Chinese New Year", "Hari Merdeka", "Teachers' Day"], 0, ans_text="Chinese New Year"),
        _rag("The moon is round and bright during the __________.",
             ["Mooncake Festival", "school holiday", "rainy season"], 0, ans_text="Mooncake Festival"),
        _rag("Father takes us to see the fish at the __________.",
             ["aquarium", "bank", "post office"], 0, ans_text="aquarium"),
        _rag("Lina helps her mother hang the __________ on the line.",
             ["laundry", "durian", "books"], 0, ans_text="laundry"),
        _rag("The bus __________ is a friendly man wearing a uniform.",
             ["driver", "writer", "farmer"], 0, ans_text="driver"),
        _rag("We must __________ our hands before eating.",
             ["wash", "break", "throw"], 0, ans_text="wash"),
        _rag("The hens in grandfather's house lay __________ every morning.",
             ["eggs", "uniforms", "books"], 0, ans_text="eggs"),
        _rag("Siti keeps her pocket __________ in a small money box.",
             ["money", "paper", "rubbish"], 0, ans_text="money"),
        _rag("The pupils do the __________ together during gotong-royong.",
             ["clean-up", "spelling", "homework"], 0, ans_text="clean-up"),
    ],
}

# Year 3 builds on the primary years + town/occupations/weather.
VOCAB_Y3 = [
    _rag("Mei Fen's father is a __________. He flies planes across Malaysia.",
        ["pilot", "postman", "farmer"], 0, ans_text="pilot"),
    _rag("The __________ puts out the fire quickly with his hose.",
        ["firefighter", "actor", "waiter"], 0, ans_text="firefighter"),
    _rag("We buy stamps and post letters at the __________.",
        ["post office", "school", "market"], 0, ans_text="post office"),
    _rag("The doctor checks my temperature with a __________.",
        ["thermometer", "ruler", "clock"], 0, ans_text="thermometer"),
    _rag("Rain clouds gathered; soon it began to __________ heavily.",
        ["rain", "shine", "blow"], 0, ans_text="rain"),
    _rag("The __________ picks fresh vegetables from the padi field.",
        ["farmer", "tailor", "cashier"], 0, ans_text="farmer"),
    _rag("We take the __________ to go up the hill to Penang.",
        ["funicular train", "bus only", "lorry"], 0, ans_text="funicular train"),
    _rag("At Batu Caves, visitors climb 272 colourful __________.",
        ["steps", "trees", "walls"], 0, ans_text="steps"),
    _rag("The proboscis monkey has a very long __________.",
        ["nose", "tail", "neck"], 0, ans_text="nose"),
    _rag("The __________ is Malaysia's national bird with a loud call.",
        ["hornbill", "sparrow", "pigeon"], 0, ans_text="hornbill"),
    _rag("Mother cooks spicy __________ for lunch on Saturdays.",
        ["sambal", "cereal", "toast"], 0, ans_text="sambal"),
    _rag("The hawker fries noodles quickly over a big __________.",
        ["wok", "bowl", "plate"], 0, ans_text="wok"),
    _rag("We pay the hawker with a __________ and twenty sen.",
        ["ringgit", "dollar", "yuan"], 0, ans_text="ringgit"),
    _rag("In the monsoon months, the east coast gets heavy __________.",
        ["rain", "snow", "hail"], 0, ans_text="rain"),
    _rag("The tour guide shows tourists around the __________ museum.",
        ["heritage", "toys", "sweets"], 0, ans_text="heritage"),
    _rag("The __________ produces electricity for the whole town.",
        ["power station", "mosque", "stadium"], 0, ans_text="power station"),
    _rag("Kok Wai wants to be a __________ and build bridges.",
        ["engineer", "barber", "chef"], 0, ans_text="engineer"),
    _rag("Aini's sister works in the hospital as a __________.",
        ["nurse", "driver", "singer"], 0, ans_text="nurse"),
    # "stars" cannot be a distractor here: the flag carries a 14-point star,
    # so both it and "stripes" are literally true and the item would have two
    # defensible answers.  Distractors must be plainly wrong instead.
    _rag("The Malaysian flag, the Jalur Gemilang, has fourteen __________.",
        ["stripes", "suns", "moons"], 0, ans_text="stripes"),
    _rag("We climb up the staircase to the top of the __________.",
        ["lighthouse", "cupboard", "hill"], 0, ans_text="lighthouse"),
    _rag("At night, the Petronas Twin Towers light up the city of __________.",
        ["Kuala Lumpur", "Bangkok", "Singapore"], 0, ans_text="Kuala Lumpur"),
    _rag("The canteen sells nasi lemak wrapped in __________.",
        ["banana leaves", "newspaper", "plastic bags"], 0, ans_text="banana leaves"),
]

VOCAB_UPPER = {
    5: [
        _rag("There was a fire in the computer lab. The __________ rang the alarm.",
            ["firefighter", "librarian", "clown"], 0, ans_text="firefighter"),
        _rag("The __________ of the school welcomed the guests at the gate.",
            ["headmaster", "gardener", "athlete"], 0, ans_text="headmaster"),
        _rag("Before the exam, Mei Yoke __________ all her notes every night.",
            ["revised", "planted", "cooked"], 0, ans_text="revised"),
        _rag("The tour bus slowly climbed the winding road up to __________.",
            ["Cameron Highlands", "the mall basement", "the sea floor"], 0, ans_text="Cameron Highlands"),
        _rag("Muthu saves his pocket money in a __________ to buy a bicycle.",
            ["piggy bank", "shoe box", "school bag"], 0, ans_text="piggy bank"),
        _rag("The scouts learned to __________ a tent at the campsite.",
            ["pitch", "fold", "paint"], 0, ans_text="pitch"),
        _rag("A __________ helps doctors during surgery in the operating room.",
            ["surgeon", "cashier", "conductor"], 0, ans_text="surgeon"),
        _rag("The flight __________ welcomed the passengers on the plane.",
            ["attendant", "postman", "butcher"], 0, ans_text="attendant"),
        _rag("Scientists say we should __________ paper and plastic to save nature.",
            ["recycle", "burn", "bury"], 0, ans_text="recycle"),
        _rag("The monsoon blew in from the sea, bringing dark __________ clouds.",
            ["storm", "pink", "golden"], 0, ans_text="storm"),
        _rag("The orangutan swings from tree to tree in the __________.",
            ["rainforest", "desert", "ice cap"], 0, ans_text="rainforest"),
        _rag("The girls took part in the school band as __________ players.",
            ["flute", "gong", "drum"], 0, ans_text="flute"),
        _rag("We visited the __________ to see the remains of ancient animals.",
            ["museum", "station", "market"], 0, ans_text="museum"),
        _rag("The farmer __________ the land before planting the padi.",
            ["ploughed", "painted", "ironed"], 0, ans_text="ploughed"),
        _rag("Sunflower seeds are a healthy __________ for the birds.",
            ["treat", "trouble", "ticket"], 0, ans_text="treat"),
        _rag("At the night market, customers __________ with the sellers.",
            ["bargain", "whisper", "sing"], 0, ans_text="bargain"),
        _rag("The _________ collects our recycling every Friday morning.",
            ["junk collector", "dentist", "dancer"], 0, ans_text="junk collector"),
        _rag("Chee Lim trains hard to run in the __________ race.",
            ["relay", "spelling", "ping-pong"], 0, ans_text="relay"),
        _rag("In the library, we must __________ when reading.",
            ["keep quiet", "shout loudly", "run around"], 0, ans_text="keep quiet"),
        _rag("A __________ protects the village from floods every rainy season.",
            ["drain", "curtain", "ladder"], 0, ans_text="drain"),
    ],
    6: [
        _rag("The __________ of the steel mill checked every machine for safety.",
            ["manager", "cashier", "porter"], 0, ans_text="manager"),
        _rag("Pupils used __________ to measure how fast their paper planes flew.",
            ["stopwatches", "paintbrushes", "chopsticks"], 0, ans_text="stopwatches"),
        _rag("The school set up a __________ to raise money for the flood victims.",
            ["charity fair", "parking lot", "science lab"], 0, ans_text="charity fair"),
        _rag("Because of the haze, pupils stayed indoors and did __________.",
            ["indoor activities", "outdoor drills", "field trips"], 0, ans_text="indoor activities"),
        _rag("The __________ tells the farmers how the weather will be tomorrow.",
            ["weather forecast", "love letter", "maths problem"], 0, ans_text="weather forecast"),
        _rag("We must not __________ the school ground with sweet wrappers.",
            ["litter", "sweep", "water"], 0, ans_text="litter"),
        _rag("The national sportsman won a gold medal in the __________.",
            ["Sea Games", "school choir", "art club"], 0, ans_text="Sea Games"),
        _rag("Ah Seng's grandfather __________ peppercorns in Sarawak for a living.",
            ["harvests", "burns", "iron"], 0, ans_text="harvests"),
        _rag("The computer technician __________ the school computers regularly.",
            ["updates", "checks", "repairs"], 0, ans_text="updates"),
        _rag("Tourists take the __________ to the top of the KL Tower.",
            ["lift", "cargo ship", "horse cart"], 0, ans_text="lift"),
        _rag("The __________ protects endangered animals in our national parks.",
            ["ranger", "clown", "waiter"], 0, ans_text="ranger"),
        _rag("Devi donated her old clothes to the __________ for orphans.",
            ["orphanage", "factory", "hotel"], 0, ans_text="orphanage"),
        _rag("A __________ collar keeps the pet dog from running onto the road.",
            ["reflective", "paper", "rubber"], 0, ans_text="reflective"),
        _rag("The pupils presented a __________ song to thank their teachers.",
            ["farewell", "welcome", "spelling"], 0, ans_text="farewell"),
        _rag("Those who do not follow the traffic rules will be fined by the __________.",
            ["police", "teachers", "hawkers"], 0, ans_text="police"),
        _rag("A __________ is a small motorboat used by fishermen in the morning.",
            ["skiff", "rocket", "tram"], 0, ans_text="skiff"),
        _rag("The best student received a __________ for her hard work.",
            ["certificate", "tissue box", "rubber band"], 0, ans_text="certificate"),
        _rag("Water from the waterfall can be turned into __________ energy.",
            ["hydro", "windmill", "wood"], 0, ans_text="hydro"),
        _rag("The dentist told Hui Ling to __________ her teeth twice a day.",
            ["brush", "hammer", "wash"], 0, ans_text="brush"),
        _rag("Joining a __________ club helps pupils learn teamwork.",
            ["sports", "snail", "dust"], 0, ans_text="sports"),
    ],
}


def _vocab_pool(year: int) -> list[dict]:
    """Contextual-vocabulary pool for ``year`` (kept inside its level band).

    Year 1–2 use the school-life lower pools, Year 3 the mid pool, and Years
    5–6 the upper pool — never a lower year's pool as a fallback.
    """
    year = int(year)
    if year == 1:
        pool = VOCAB_LOWER[1]
    elif year == 3:
        pool = VOCAB_Y3
    elif year >= 5:
        pool = VOCAB_UPPER[year]
    else:
        pool = VOCAB_LOWER.get(year, VOCAB_LOWER[2])
    # Round 25: the DSKP-grounded items lead, because every answer in
    # ``extra_vocab_dskp`` is on the year's word list.  The freehand pool
    # still fills the tail so a paper always reaches its question count.
    pool = (_XVD.VOCAB_DSKP.get(year, []) + pool +
            _XV.VOCAB.get(year, []))
    band = D.VOCAB_BAND.get(year, ())
    if not band:
        return pool
    pat = re.compile("|".join(r"\b" + re.escape(w.lower()) + r"\b"
                              for w in band))
    return [d for d in pool
            if not pat.search(" ".join([str(d.get("stem", ""))] +
                                       list(map(str, d.get("opts", [])))).lower())]


# ---------------------------------------------------------------------------
# merged pools (built-in + Round 12 extra banks) so every year has plenty of
# distinct question sets per part
# ---------------------------------------------------------------------------

def _comp_pool(year: int) -> list[dict]:
    year = int(year)
    return (_XC.COMPREHENSION.get(year, []) +
            _XCO.COMPREHENSION.get(year, []) +
            COMPREHENSION.get(year, COMPREHENSION[5]))


def _cloze_pool(year: int) -> list[dict]:
    year = int(year)
    return (_XCL.CLOZE.get(year, []) + CLOZE.get(year, CLOZE[3])
            + CLOZE_V.get(year, []) + CLOZE_SEM.get(year, [])
            + CLOZE_NEW.get(year, []))


def _text_label(text: str) -> str:
    """The ``"A. "`` style prefix a matching text carries, or ``""``."""
    m = re.match(r"\s*([A-C])\s*[.)]\s*", str(text))
    return m.group(0) if m else ""


def _relabel_match(rng, block: dict, count: int, year=None):
    """Shuffle which matching text is called A, B or C, and re-key the answers.

    The pools store a block in its authored order, and the generator used to
    print the texts in that order, so every description was answered by the
    letter of the text it was written for — the paper read A, A, B, B, C, C
    and a pupil could score full marks without reading.  The official papers
    shuffle the letters instead, and so does this: the texts are permuted, the
    answer index of each description is remapped, and the identity mapping is
    never emitted.

    Returns ``(lead_text, raw_items, example)``; the options stay
    ``["A", "B", "C"]`` because the letters *are* the labels printed beside the
    texts, so the option list must not be shuffled afterwards.  ``example`` is
    the block's own seventh description — the official papers spend a separate
    description on the worked example, so reusing a marked question would hand
    the pupil its answer — or ``None`` for a block that has none.
    """
    texts = [str(t) for t in block.get("texts") or []]
    all_qs = [q for q in (block.get("qs") or []) if isinstance(q, dict)]
    if len(texts) != 3 or not all_qs:
        return "\n".join(texts), all_qs[:count], None
    # Take the descriptions round-robin across the three texts, so each
    # letter answers the same number of times (2 each for the official six)
    # whatever order the pool happens to store them in.
    buckets: dict[int, list[dict]] = {i: [] for i in range(3)}
    for q in all_qs:
        a = q.get("ans", q.get("answer", 0))
        (buckets[a] if isinstance(a, int) and a in buckets
         else buckets[0]).append(q)
    for b in buckets.values():
        rng.shuffle(b)
    qs: list[dict] = []
    while len(qs) < min(count, len(all_qs)):
        grew = False
        for i in range(3):
            if buckets[i] and len(qs) < count:
                qs.append(buckets[i].pop(0))
                grew = True
        if not grew:
            break
    order = [0, 1, 2]
    guard = 0
    while order == [0, 1, 2] and guard < 12:
        rng.shuffle(order)
        guard += 1
    if order == [0, 1, 2]:              # pathological rng; force a swap
        order = [1, 0, 2]
    moved = [0, 0, 0]
    for new_pos, old_pos in enumerate(order):
        moved[old_pos] = new_pos
    relabelled = []
    for new_pos, old_pos in enumerate(order):
        body = re.sub(r"^\s*[A-C]\s*[.)]\s*", "", texts[old_pos]).rstrip()
        relabelled.append(f"{D.option_labels(3, year)[new_pos]} {body}")
    out = []
    for q in qs:
        opts = q.get("opts") or ["A", "B", "C"]
        ans = q.get("ans", q.get("answer", 0))
        item = dict(q)
        item["opts"] = list(opts)
        if isinstance(ans, int) and 0 <= ans < 3:
            item["ans"] = moved[ans]
        out.append(item)
    example = None
    ex = block.get("example")
    if isinstance(ex, dict) and ex.get("stem"):
        ans = ex.get("ans", ex.get("answer", 0))
        if isinstance(ans, int) and 0 <= ans < 3:
            example = _match_example(ex["stem"], moved[ans])
    return "\n".join(relabelled), out, example


def _match_example(stem: str, ans: int) -> str:
    """The official worked example line: ``0. <description>  (<letter>)``."""
    letter = "ABC"[ans] if isinstance(ans, int) and 0 <= ans < 3 else "?"
    return f"0. {' '.join(str(stem).split())}  ({letter})"


def _answer_balance(labels: list[str]) -> list[str]:
    """Problems with how Part 4's answers are spread over A, B and C."""
    out: list[str] = []
    if not labels:
        return ["Part 4 has no answers"]
    counts = {lab: labels.count(lab) for lab in "ABC"}
    missing = [lab for lab, n in counts.items() if not n]
    if missing:
        out.append(f"Part 4 never answers {', '.join(missing)}")
    if len(set(labels)) == 1:
        out.append(f"Part 4 answers {labels[0]} for all "
                   f"{len(labels)} descriptions")
    if len(labels) >= 4 and len(labels) % 3 == 0:
        ideal = len(labels) // 3
        skewed = [lab for lab, n in counts.items() if n > ideal]
        if skewed:
            out.append("Part 4 leans on "
                       + ", ".join(f"{lab} ({counts[lab]})" for lab in skewed)
                       + f" for {len(labels)} descriptions")
    run = longest = 1
    for a, b in zip(labels, labels[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    if longest >= 3:
        out.append(f"Part 4 runs {longest} identical answers in a row")
    if len(labels) > 1 and labels == ["A", "B", "C"] * (len(labels) // 3):
        out.append("Part 4 repeats the A, B, C pattern in order")
    return out


def _match_pool(year: int) -> list[dict]:
    year = int(year)
    return (_XM123.MATCH.get(year, []) +
            _XM56.MATCH.get(year, []) +
            MATCH.get(year, MATCH[5]))


def _words_pool(year: int) -> list[dict]:
    year = int(year)
    # Round 25: the DSKP-grounded boxes come first so the vocabulary gate in
    # ``_dskp_prefer`` always has an on-list block to choose from, whatever
    # the freehand pools happen to hold.
    return (_XWD.WORDS_DSKP.get(year, []) +
            _XW.WORDS_CHOICE.get(year, []) +
            WORDS_CHOICE.get(year, WORDS_CHOICE[2]))


def _letter_words_pool(year: int) -> list[dict]:
    year = int(year)
    # Years 1-3 have their own riddle pool drawn from the official KSSR Year
    # 1-3 word lists.  Before Round 41 they fell through to WORDS_LETTER_Y5,
    # so a Year 1 pupil was asked to spell "bridge".
    lower = {1: WORDS_LETTER_Y1, 2: WORDS_LETTER_Y2, 3: WORDS_LETTER_Y3}
    if year in lower:
        base = lower[year]
    else:
        base = WORDS_LETTER_Y6 if year == 6 else WORDS_LETTER_Y5
    themed = [dict(clue=clue, word=word, theme=theme)
              for theme, tiles in D.THEME_LETTER_WORDS.get(year, {}).items()
              for clue, word in tiles]
    return themed + base + _XW.WORDS_LETTER.get(year, [])


def _sentences_pool(year: int, lower: bool) -> list[dict]:
    year = int(year)
    extra = _XWR.SENTENCES["lower" if lower else "upper"]
    if lower:
        builtin = SENTENCES_Y1 if year == 1 else SENTENCES["lower"]
    else:
        builtin = SENTENCES["upper"]
    return extra + builtin


def _letter_pool(year: int) -> list[dict]:
    year = int(year)
    # Round 26: the Y6 Part 6 pool was 22 topics, so a term repeated.  The
    # extra pool brings it to ~50 curated prompts.
    return (_XWR56.LETTERS.get(year, []) + _XWR.LETTERS.get(year, [])
            + LETTERS.get(year, LETTERS[6]))


def _essay_pool(year: int) -> dict:
    year = int(year)
    builtin = ESSAYS.get(year, ESSAYS[5])
    # Round 26: new ~50-topic pools for Y5 P6/P7 and Y6 P7 lead the merge, so
    # the newer prompts are what a term mostly draws.
    extra = {}
    for src in (_XWR56.ESSAYS.get(year, {}), _XWR4.ESSAYS.get(year, {}),
                _XWR.ESSAYS.get(year, {})):
        for k, rows in (src or {}).items():
            extra.setdefault(k, []).extend(rows)
    merged = {}
    for k in set(builtin) | set(extra):
        merged[k] = extra.get(k, []) + builtin.get(k, [])
    return merged


# ---------------------------------------------------------------------------
# cloze passages (Part 2) — 4 gaps each
# ---------------------------------------------------------------------------

#: Round 43 (SPEC 59) -- new Part 2 cloze passages.
#: Measured before this round, after collapsing the name/weekday variants the
#: pools were padded with, the TRUE number of distinct Part 2 passages was
#: Y1 5, Y2 9, Y3 8, **Y4 2**, Y5 8, Y6 8.  Year 4 built 40 papers from two
#: passages.  These blocks are new content, not new names.
CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = CLOZE_NEW = {
    3: [{'passage': 'Every Friday after class we help the caretaker (6)_______ the playground. We (7)_______ the benches with a hose, and last term the class (8)_______ some vegetables from our own garden. Now we (9)_______ the plants every morning before the bell.', 'gaps': [{'stem': 'We help the caretaker __________ the playground.', 'opts': ['tidy', 'tidys', 'tidying'], 'ans': 0}, {'stem': 'We __________ the benches with a hose.', 'opts': ['wash', 'washes', 'washing'], 'ans': 0}, {'stem': 'Last term the class __________ some vegetables.', 'opts': ['sell', 'sells', 'selling'], 'ans': 0}, {'stem': 'Now we __________ the plants every morning.', 'opts': ['water', 'waters', 'watering'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Our class has a vegetable garden behind the school hall. Every morning we (6)_______ the soil, and (7)_______ the small plants with a can. We (8)_______ our hands before we start, because that is how we (9)_______ food safely.', 'gaps': [{'stem': 'Every morning we __________ the soil.', 'opts': ['dig', 'digs', 'diging'], 'ans': 0}, {'stem': 'And __________ the small plants with a can.', 'opts': ['water', 'waters', 'watering'], 'ans': 0}, {'stem': 'We __________ our hands before we start.', 'opts': ['wash', 'washes', 'washing'], 'ans': 0}, {'stem': 'That is how we __________ food safely.', 'opts': ['work', 'works', 'working'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'The school bus was late one morning because heavy rain flooded the road near the bridge. The driver (6)_______ under a big tree until the water went down, and he (7)_______ the pupils a short story. We all (8)_______ safely to the school, and my friend said we should (9)_______ a quiet game instead.', 'gaps': [{'stem': 'The driver __________ under a big tree until the water went down.', 'opts': ['wait', 'waits', 'waiting'], 'ans': 0}, {'stem': 'He __________ the pupils a short story.', 'opts': ['tell', 'tells', 'telling'], 'ans': 0}, {'stem': 'We all __________ safely to the school.', 'opts': ['walk', 'walks', 'walking'], 'ans': 0}, {'stem': 'My friend said we should __________ a quiet game instead.', 'opts': ['study', 'studys', 'studying'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Our school trip to the zoo was the best day of the year. At the entrance we (6)_______ for the map, and then we (7)_______ the animals with our teacher. She (8)_______ us how the elephants share their food, and later we (9)_______ the baby animals for a long time.', 'gaps': [{'stem': 'At the entrance we __________ for the map.', 'opts': ['look', 'looks', 'looking'], 'ans': 0}, {'stem': 'Then we __________ the animals with our teacher.', 'opts': ['visit', 'visits', 'visiting'], 'ans': 0}, {'stem': 'She __________ us how the elephants share their food.', 'opts': ['show', 'shows', 'showing'], 'ans': 0}, {'stem': 'Later we __________ the baby animals for a long time.', 'opts': ['watch', 'watches', 'watching'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'My grandmother (6)_______ at home while my sister goes to school. Every Saturday morning she (7)_______ vegetables and flowers in a small shop, and my sister (8)_______ the customers. Last year they (9)_______ every day to pay for our holiday.', 'gaps': [{'stem': 'My grandmother __________ at home while my sister goes to school.', 'opts': ['cook', 'cooks', 'cooking'], 'ans': 0}, {'stem': 'Every Saturday morning she __________ vegetables and flowers.', 'opts': ['sell', 'sells', 'selling'], 'ans': 0}, {'stem': 'My sister __________ the customers.', 'opts': ['help', 'helps', 'helping'], 'ans': 0}, {'stem': 'Last year they __________ every day to pay for our holiday.', 'opts': ['work', 'works', 'working'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'During the school holidays my brother and I (6)_______ a kite from bamboo sticks and thin paper. We (7)_______ to the open field to fly it, and my sister (8)_______ us from the gate. Then the string broke, and my brother had to (9)_______ the grass afterwards.', 'gaps': [{'stem': 'My brother and I __________ a kite from bamboo sticks.', 'opts': ['buy', 'buys', 'buying'], 'ans': 0}, {'stem': 'We __________ to the open field to fly it.', 'opts': ['skate', 'skates', 'skating'], 'ans': 0}, {'stem': 'My sister __________ us from the gate.', 'opts': ['watch', 'watches', 'watching'], 'ans': 0}, {'stem': 'My brother had to __________ the grass afterwards.', 'opts': ['tidy', 'tidys', 'tidying'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'My uncle (6)_______ his bicycle to the shop near the market. On Saturdays I (7)_______ there to help him, and we (8)_______ the bicycles together. Last month a family (9)_______ our shop before the school sports day.', 'gaps': [{'stem': 'My uncle __________ his bicycle to the shop near the market.', 'opts': ['miss', 'misses', 'missing'], 'ans': 0}, {'stem': 'On Saturdays I __________ there to help him.', 'opts': ['work', 'works', 'working'], 'ans': 0}, {'stem': 'And we __________ the bicycles together.', 'opts': ['wash', 'washes', 'washing'], 'ans': 0}, {'stem': 'Last month a family __________ our shop before sports day.', 'opts': ['visit', 'visits', 'visiting'], 'ans': 0}], 'mode': 'verb'}],
    4: [{'passage': 'Our class (6)_______ a small garden behind the school hall. In March we put a (7)_______ in every pot, covered it with (8)_______, and we (9)_______ the plants every morning.', 'gaps': [{'stem': 'Our class __________ a small garden behind the school hall.', 'opts': ['made', 'makes', 'making'], 'ans': 0}, {'stem': 'In March we put a __________ in every pot.', 'opts': ['seed', 'seat', 'seep'], 'ans': 0}, {'stem': 'We covered it with __________.', 'opts': ['soil', 'sofa', 'soldier'], 'ans': 0}, {'stem': 'And we __________ the plants every morning.', 'opts': ['carefully', 'careless', 'carelessly'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Our school (6)_______ corner is beside the canteen. Every Friday the prefects empty the blue (7)_______ and sort the (8)_______ into bunches, so that we can (9)_______ what we throw away.', 'gaps': [{'stem': 'Our school __________ corner is beside the canteen.', 'opts': ['recycle', 'recycled', 'recycles'], 'ans': 0}, {'stem': 'Every Friday the prefects empty the blue __________.', 'opts': ['bin', 'pin', 'tin'], 'ans': 0}, {'stem': 'They sort the __________ into bunches.', 'opts': ['paper', 'pepper', 'people'], 'ans': 0}, {'stem': 'So that we can __________ what we throw away.', 'opts': ['reduce', 'reduces', 'reduced'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Last month our class (6)_______ the stage for the school play. We (7)_______ the curtains ourselves and then painted them with a bright (8)_______ colour. On the night the hall was so (9)_______ that we could hardly hear the music.', 'gaps': [{'stem': 'Last month our class __________ the stage for the school play.', 'opts': ['decorated', 'decorate', 'decorates'], 'ans': 0}, {'stem': 'We __________ the curtains ourselves.', 'opts': ['decorate', 'decorated', 'decorates'], 'ans': 0}, {'stem': 'We painted them with a bright __________ colour.', 'opts': ['dangerous', 'danger', 'dangerously'], 'ans': 0}, {'stem': 'The hall was so __________ that we could hardly hear.', 'opts': ['loudly', 'loud', 'load'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Our town has a new (6)_______ library near the market. Visitors can (7)_______ for a book on the screen at the front desk, and the building is very (8)_______. It saves (9)_______ because the lights switch off by themselves.', 'gaps': [{'stem': 'Our town has a new __________ library near the market.', 'opts': ['digital', 'digit', 'dinner'], 'ans': 0}, {'stem': 'Visitors can __________ for a book on the screen.', 'opts': ['search', 'sand', 'sandwich'], 'ans': 0}, {'stem': 'The building is very __________ and easy to use.', 'opts': ['modern', 'model', 'moderate'], 'ans': 0}, {'stem': 'It saves __________ because the lights switch off.', 'opts': ['energy', 'engine', 'enjoy'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Every (6)_______ our school joins the tree planting day. We dig a hole, put the young (7)_______ in, and cover the roots with (8)_______ carefully. A tree needs water and (9)_______ to grow well.', 'gaps': [{'stem': 'Every __________ our school joins the tree planting day.', 'opts': ['christmas', 'christ', 'chrome'], 'ans': 0}, {'stem': 'We dig a hole and put the young __________ in.', 'opts': ['seed', 'seep', 'seem'], 'ans': 0}, {'stem': 'We cover the roots with __________ carefully.', 'opts': ['soil', 'sofa', 'solemn'], 'ans': 0}, {'stem': 'A tree needs water and __________ to grow well.', 'opts': ['light', 'line', 'lion'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'During our school (6)_______ the children wore their traditional (7)_______. A long (8)_______ went round the field twice, and at one long table we all ate some (9)_______ together.', 'gaps': [{'stem': 'During our school __________ the children wore their costume.', 'opts': ['celebrate', 'celebrated', 'celebrates'], 'ans': 0}, {'stem': 'The children wore their traditional __________.', 'opts': ['costume', 'costumes', 'custom'], 'ans': 0}, {'stem': 'A long __________ went round the field twice.', 'opts': ['parade', 'parcels', 'parrot'], 'ans': 0}, {'stem': 'At one long table we all ate some __________ together.', 'opts': ['mooncake', 'mooncakes', 'moonshine'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Our class made a (6)_______ about our village for the school website. We took the pictures with the school (7)_______ and wrote a short (8)_______ for every page, and our teacher asked us to (9)_______ the file to everybody at home.', 'gaps': [{'stem': 'Our class made a __________ about our village.', 'opts': ['website', 'websites', 'web'], 'ans': 0}, {'stem': 'We took the pictures with the school __________.', 'opts': ['camera', 'cameras', 'camp'], 'ans': 0}, {'stem': 'We wrote a short __________ for every page.', 'opts': ['message', 'messages', 'magic'], 'ans': 0}, {'stem': 'Our teacher asked us to __________ the file to everybody.', 'opts': ['send', 'sends', 'sent'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Air (6)_______ in our town is a serious problem. Every family can help by planting more (7)_______ along the road, and we should (8)_______ care about the (9)_______ we all share.', 'gaps': [{'stem': 'Air __________ in our town is a serious problem.', 'opts': ['pollution', 'poll', 'polish'], 'ans': 0}, {'stem': 'Every family can help by planting more __________ along the road.', 'opts': ['plant', 'plants', 'planting'], 'ans': 0}, {'stem': 'We should __________ care about it.', 'opts': ['always', 'also', 'aloud'], 'ans': 0}, {'stem': 'We all share the same __________.', 'opts': ['nature', 'natural', 'nations'], 'ans': 0}], 'mode': 'sem'}],
    5: [{'passage': 'When I have a fever my mother says we must (6)_______ to see the doctor at once. The doctor will (7)_______ the medicine I need, and then I must (8)_______ my week so that I take it at the same time every morning. My mother will (9)_______ the tablets in a small box on the table.', 'gaps': [{'stem': 'We must __________ to see the doctor at once.', 'opts': ['decide', 'decides', 'deciding'], 'ans': 0}, {'stem': 'The doctor will __________ the medicine I need.', 'opts': ['suggest', 'suggests', 'suggesting'], 'ans': 0}, {'stem': 'Then I must __________ my week so that I take it at the same time.', 'opts': ['plan', 'plans', 'planing'], 'ans': 0}, {'stem': 'My mother will __________ the tablets in a small box.', 'opts': ['collect', 'collects', 'collecting'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Our school space club is very popular. Last month we (6)_______ a telescope from the science room and (7)_______ the sky for hours. Next month we will (8)_______ a bigger instrument, and we hope to (9)_______ more about the planets.', 'gaps': [{'stem': 'Last month we __________ a telescope from the science room.', 'opts': ['collect', 'collects', 'collecting'], 'ans': 0}, {'stem': 'And __________ the sky for hours.', 'opts': ['explore', 'explores', 'exploring'], 'ans': 0}, {'stem': 'Next month we will __________ a bigger instrument.', 'opts': ['design', 'designs', 'designing'], 'ans': 0}, {'stem': 'We hope to __________ more about the planets.', 'opts': ['discover', 'discovers', 'discovering'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Our class had to (6)_______ the whole school play, and we did not have much time. First we (7)_______ the parts and the costumes, and then we (8)_______ the set every afternoon. On the night of the show the lights were too bright at first, but we (9)_______ the whole show on time.', 'gaps': [{'stem': 'Our class had to __________ the whole school play.', 'opts': ['plan', 'plans', 'planing'], 'ans': 0}, {'stem': 'First we __________ the parts and the costumes.', 'opts': ['compare', 'compares', 'comparing'], 'ans': 0}, {'stem': 'Then we __________ the set every afternoon.', 'opts': ['design', 'designs', 'designing'], 'ans': 0}, {'stem': 'We __________ the whole show on time.', 'opts': ['achieve', 'achieves', 'achieving'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'My father and I (6)_______ our holiday last December, and he (7)_______ the whole trip so that we could (8)_______ the cheapest hotel in town. Every morning we (9)_______ the streets near the river before breakfast.', 'gaps': [{'stem': 'My father and I __________ our holiday last December.', 'opts': ['plan', 'plans', 'planing'], 'ans': 0}, {'stem': 'He __________ the whole trip so that we could save money.', 'opts': ['design', 'designs', 'designing'], 'ans': 0}, {'stem': 'So that we could __________ the cheapest hotel in town.', 'opts': ['discover', 'discovers', 'discovering'], 'ans': 0}, {'stem': 'Every morning we __________ the streets near the river.', 'opts': ['explore', 'explores', 'exploring'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Some pupils (6)_______ a robot for the science competition, and they wanted to (7)_______ how machines make decisions. Their robot could (8)_______ the whole room by itself, and the judges could not (9)_______ how it worked.', 'gaps': [{'stem': 'Some pupils __________ a robot for the competition.', 'opts': ['invent', 'invents', 'inventing'], 'ans': 0}, {'stem': 'They wanted to __________ how machines make decisions.', 'opts': ['discover', 'discovers', 'discovering'], 'ans': 0}, {'stem': 'Their robot could __________ the whole room by itself.', 'opts': ['explore', 'explores', 'exploring'], 'ans': 0}, {'stem': 'The judges could not __________ how it worked.', 'opts': ['imagine', 'imagines', 'imagining'], 'ans': 0}], 'mode': 'verb'}, {'passage': 'Our class went on a short trip to the national park, and we had to (6)_______ everything before we left. We (7)_______ the park on a map and (8)_______ what we would like to see. In the afternoon it started to rain, so we had to (9)_______ under a big tree until it stopped.', 'gaps': [{'stem': 'We had to __________ everything before we left.', 'opts': ['plan', 'plans', 'planing'], 'ans': 0}, {'stem': 'We __________ the park on a map.', 'opts': ['explore', 'explores', 'exploring'], 'ans': 0}, {'stem': 'And __________ what we would like to see.', 'opts': ['imagine', 'imagines', 'imagining'], 'ans': 0}, {'stem': 'We had to __________ under a big tree until it stopped.', 'opts': ['survive', 'survives', 'surviving'], 'ans': 0}], 'mode': 'verb'}],
    6: [{'passage': 'Our school (6)_______ is about the water in the river that runs past our village. We (7)_______ the quality every week for three months, and the results showed heavy (8)_______. The community group asked every family to (9)_______ something each month.', 'gaps': [{'stem': 'Our school __________ is about the water in the river.', 'opts': ['project', 'promise', 'progress'], 'ans': 0}, {'stem': 'We __________ the quality every week for three months.', 'opts': ['investigate', 'invite', 'invent'], 'ans': 0}, {'stem': 'The results showed heavy __________.', 'opts': ['pollution', 'poll', 'polish'], 'ans': 0}, {'stem': 'The group asked every family to __________ something each month.', 'opts': ['contribute', 'control', 'conclude'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Many animals in our country are (6)_______ because their habitats have been destroyed. A local group began a project to (7)_______ every (8)_______ and to (9)_______ them. Young people joined as volunteers and learnt to use a camera trap.', 'gaps': [{'stem': 'Many animals in our country are __________.', 'opts': ['endangered', 'engineered', 'enchanted'], 'ans': 0}, {'stem': 'A local group began a project to __________ every species.', 'opts': ['investigate', 'invite', 'invent'], 'ans': 0}, {'stem': 'They began a project to study every __________.', 'opts': ['species', 'speeches', 'spaces'], 'ans': 0}, {'stem': 'They worked to __________ the endangered animals.', 'opts': ['protect', 'project', 'predict'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Technology has changed the way people work. An (6)_______ door opens by itself, and the school (7)_______ turns on the lights when we walk in. Every pupil has a (8)_______ for lessons, and the (9)_______ follows a careful design.', 'gaps': [{'stem': 'An __________ door opens by itself.', 'opts': ['automatic', 'automated', 'alone'], 'ans': 0}, {'stem': 'The school __________ turns on the lights when we walk in.', 'opts': ['system', 'symbol', 'sentence'], 'ans': 0}, {'stem': 'Every pupil has a __________ for lessons.', 'opts': ['screen', 'script', 'scream'], 'ans': 0}, {'stem': 'The __________ follows a careful design.', 'opts': ['machine', 'machinery', 'much'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'During the school holidays I joined a science (6)_______. My group worked in a (7)_______ for five days and finished one simple (8)_______. At the end we had to (9)_______ the results and say that more testing was needed.', 'gaps': [{'stem': 'During the holidays I joined a science __________.', 'opts': ['project', 'promise', 'progress'], 'ans': 0}, {'stem': 'My group worked in a __________ for five days.', 'opts': ['laboratory', 'labour', 'library'], 'ans': 0}, {'stem': 'We finished one simple __________.', 'opts': ['experiment', 'discovery', 'decision'], 'ans': 0}, {'stem': 'We had to __________ the results carefully.', 'opts': ['analyze', 'announce', 'arrive'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Our class collected money for a local (6)_______. We decided to (7)_______ a bake sale, and every pupil (8)_______ one thing to sell. In the end we were able to (9)_______ four families in our town.', 'gaps': [{'stem': 'Our class collected money for a local __________.', 'opts': ['charity', 'chapter', 'cheese'], 'ans': 0}, {'stem': 'We decided to __________ a bake sale.', 'opts': ['organize', 'organ', 'original'], 'ans': 0}, {'stem': 'Every pupil __________ one thing to sell.', 'opts': ['contributed', 'contribute', 'contributes'], 'ans': 0}, {'stem': 'We were able to __________ four families in our town.', 'opts': ['support', 'suppose', 'suggest'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Climate change affects everyone, so a global (6)_______ matters. Some countries cause more (7)_______ than others, but every nation (8)_______ to the same problem. Scientists (9)_______ that small changes make a real difference.', 'gaps': [{'stem': 'Climate change affects everyone, so a global __________ matters.', 'opts': ['community', 'communism', 'commune'], 'ans': 0}, {'stem': 'Some countries cause more __________ than others.', 'opts': ['pollution', 'poll', 'polish'], 'ans': 0}, {'stem': 'But every nation __________ to the same problem.', 'opts': ['contributes', 'contribute', 'contributed'], 'ans': 0}, {'stem': 'Scientists __________ that small changes make a difference.', 'opts': ['conclude', 'conduct', 'concluded'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'My school asked me to (6)_______ for the school magazine last year. I was nervous about the (7)_______, because I had never spoken to so many people, but my teacher said she was (8)_______ that I could do it. On the day I could not (9)_______ my work at all.', 'gaps': [{'stem': 'My school asked me to __________ for the school magazine.', 'opts': ['participate', 'participates', 'participating'], 'ans': 0}, {'stem': 'I was nervous about the __________.', 'opts': ['interview', 'interest', 'interval'], 'ans': 0}, {'stem': 'My teacher said she was __________ that I could do it.', 'opts': ['confident', 'confidence', 'confidential'], 'ans': 0}, {'stem': 'On the day I could not __________ my work at all.', 'opts': ['manage', 'mangle', 'manager'], 'ans': 0}], 'mode': 'sem'}, {'passage': 'Our new (6)_______ club is very popular. Last month the members (7)_______ a bake sale, and every pupil (8)_______ one thing to sell. At the end of the day the whole school was (9)_______ with the result.', 'gaps': [{'stem': 'Our new __________ club is very popular.', 'opts': ['science', 'silent', 'silver'], 'ans': 0}, {'stem': 'Last month the members __________ a bake sale.', 'opts': ['organized', 'organize', 'organ'], 'ans': 0}, {'stem': 'Every pupil __________ one thing to sell.', 'opts': ['contributed', 'contribute', 'contributes'], 'ans': 0}, {'stem': 'The whole school was __________ with the result.', 'opts': ['satisfied', 'satisfy', 'satisfaction'], 'ans': 0}], 'mode': 'sem'}],
}
CLOZE = {
    1: [
        {"passage": "It is Monday morning. Ali wakes up early. He "
                    "(6)_______ his teeth and eats two slices of toast with a "
                    "cup of milk. He puts on his school (7)_______ and packs his "
                    "books into his bag. His mother drives him to school because "
                    "the (8)_______ bus is late. In class, he learns to (9)_______ "
                    "numbers in Mathematics.",
         "gaps": [
             {"stem": "A__ brushes his teeth every morning.",
              "opts": ["Ali", "Ali's mother", "Ali's teacher"], "ans": 0},
             {"stem": "He puts on his school __________.",
              "opts": ["uniform", "shoes", "beanie"], "ans": 0},
             {"stem": "The __________ bus is late.",
              "opts": ["school", "racing", "flying"], "ans": 0},
             {"stem": "In Mathematics, he learns to __________ numbers.",
              "opts": ["count", "open", "colour"], "ans": 0},
         ]},
        {"passage": "At recess, Mei Ling buys nasi lemak from the school "
                    "(6)_______. The rice is wrapped in banana leaves and smells "
                    "of coconut milk. She eats it with a piece of fried (7)_______. "
                    "Then she drinks a cup of warm (8)_______ because it is a "
                    "rainy day. After eating, she throws the (9)_______ into the "
                    "bin.",
         "gaps": [
             {"stem": "Mei Ling buys nasi lemak from the school __________.",
              "opts": ["canteen", "library", "office"], "ans": 0},
             {"stem": "She eats it with a piece of fried __________.",
              "opts": ["chicken", "rubber", "chalk"], "ans": 0},
             {"stem": "She drinks a cup of warm __________.",
              "opts": ["milk tea", "cola", "soup"], "ans": 0},
             {"stem": "She throws the __________ into the bin.",
              "opts": ["banana leaf", "exercise book", "pencil"], "ans": 0},
         ]},
    ],
    2: [
        {"passage": "Aini and her friends have a gotong-royong at school on "
                    "Saturday. They pick up (6)_______ in the field and sweep the "
                    "classroom. Wei Jie waters the plants in the school (7)_______ "
                    "while Devi wipes the windows. The teacher is happy to see the "
                    "(8)_______ school. They take a photo together at the end of "
                    "the day and hang it on the (9)_______ board.",
         "gaps": [
             {"stem": "They pick up __________ in the field.",
              "opts": ["rubbish", "food", "toys"], "ans": 0},
             {"stem": "Wei Jie waters the plants in the school __________.",
              "opts": ["garden", "canteen", "toilet"], "ans": 0},
             {"stem": "The teacher is happy to see the __________ school.",
              "opts": ["clean", "noisy", "dark"], "ans": 0},
             {"stem": "They hang the photo on the __________ board.",
              "opts": ["notice", "ironing", "sleeping"], "ans": 0},
         ]},
        {"passage": "During Chinese New Year, grandmother gives everyone a red "
                    "(6)_______ filled with money. We eat a big (7)_______ dinner "
                    "with the whole family. Uncle Seng performs the (8)_______ "
                    "dance with a long dragon. At night, we light red (9)_______ "
                    "and wish each other good luck.",
         "gaps": [
             {"stem": "Grandmother gives everyone a red __________ filled with money.",
              "opts": ["packet", "bucket", "towel"], "ans": 0, },
             {"stem": "We eat a big __________ dinner with the whole family.",
              "opts": ["reunion", "picnic", "school"], "ans": 0},
             {"stem": "Uncle Seng performs the __________ dance.",
              "opts": ["lion", "motor", "tiger"], "ans": 0},
             {"stem": "At night, we light red __________.",
              "opts": ["lanterns", "lamps", "torches"], "ans": 0},
         ]},
    ],
    3: [
        {"passage": "The kindergarten class visited the farm early in the "
                    "morning. The farmer showed them the goats and sheep at the "
                    "(6)_______. The children fed the animals fresh (7)_______ "
                    "leaves. Inside the coop, a hen sat on five (8)_______. The "
                    "farmer told them to be kind to animals and to always wash "
                    "their (9)_______ before eating.",
         "gaps": [
             {"stem": "The farmer showed them the goats and sheep at the __________.",
              "opts": ["shed", "mall", "library"], "ans": 0, },
             {"stem": "The children fed the animals fresh __________ leaves.",
              "opts": ["grass", "gold", "plastic"], "ans": 0},
             {"stem": "Inside the coop, a hen sat on five __________.",
              "opts": ["eggs", "marbles", "coconuts"], "ans": 0},
             {"stem": "They must always wash their __________ before eating.",
              "opts": ["hands", "books", "toys"], "ans": 0},
         ]},
        {"passage": "The rainy season has arrived. Every afternoon, it rains "
                    "(6)_______ and the river rises. The kampung school closes "
                    "early if there is a (7)_______. The pupils put on their "
                    "(8)_______ and raincoats to walk home. Grandmother stays "
                    "inside and makes hot (9)_______ for everyone.",
         "gaps": [
             {"stem": "Every afternoon, it rains __________.",
              "opts": ["heavily", "quietly", "softly"], "ans": 0},
             {"stem": "The kampung school closes early if there is a __________.",
              "opts": ["flood", "festival", "holiday"], "ans": 0},
             {"stem": "The pupils put on their __________ and raincoats.",
              "opts": ["boots", "slippers", "sandals"], "ans": 0},
             {"stem": "Grandmother makes hot __________ for everyone.",
              "opts": ["tea", "cola", "juice"], "ans": 0},
         ]},
    ],
5: [
        {"passage": "Our school organised a recycling campaign last month. Each "
                    "class collected used (6)_______ and glass bottles. The Eco "
                    "Club set up a corner where pupils turned old newspapers into "
                    "(7)_______. By recycling, each class saved enough money to buy "
                    "books, and the teacher reminded us to (8)_______ reusing every "
                    "single day. In the end, we raised RM250 which we donated to "
                    "the (9)_______ fund for the flood victims. The pupils learned "
                    "that small actions can make a big difference for our Earth.",
         "gaps": [
             {"stem": "Each class collected used __________ and glass bottles.",
              "opts": ["paper", "banana", "gold"], "ans": 0},
             {"stem": "Pupils turned old newspapers into __________.",
              "opts": ["art", "food", "fuel"], "ans": 0},
             {"stem": "The teacher reminded us to __________ reusing every day.",
              "opts": ["practise", "forget", "hurry"], "ans": 0},
{"stem": "We donated the money to the __________ fund for the flood victims.",
              "opts": ["charity", "football", "science"], "ans": 0},
          ]},
        {"passage": "The factory at the edge of the town released smoke into the "
                    "air and made the river dirty. The residents formed a "
                    "(6)_______ to keep the environment safe. They planted "
                    "(7)_______ along the riverbank so that the soil would not "
                    "wash away, and they stopped people from (8)_______ rubbish "
                    "into the water. The local council built a new (9)_______ to "
                    "treat the dirty water before it reached the river. Today, "
                    "the river is clean again and the fish have returned. Everyone "
                    "in the town is proud of their hard work.",
         "gaps": [
             {"stem": "The residents formed a __________ to keep the environment safe.",
              "opts": ["group", "puddle", "rule"], "ans": 0},
             {"stem": "They planted __________ along the riverbank.",
              "opts": ["trees", "towers", "tents"], "ans": 0},
             {"stem": "They stopped people from __________ rubbish into the water.",
              "opts": ["throwing", "planting", "catching"], "ans": 0},
             {"stem": "The local council built a new __________ to treat the water.",
              "opts": ["plant", "park", "page"], "ans": 0},
         ]},
     ],
6: [
        {"passage": "A recycling drive was held at the shopping mall. Staff "
                    "collected old batteries and (6)_______ devices so that "
                    "harmful materials would not spoil the soil. Volunteers "
                    "(7)_______ the items carefully and counted how much could be "
                    "reused. Broken toys were sent to a workshop where workers "
                    "fixed them and gave the toys a (8)_______ life. Everyone who "
                    "joined received a free (9)_______ bag. The mall hopes to "
                    "continue this green effort every year.",
         "gaps": [
             {"stem": "Staff collected old batteries and __________ devices.",
              "opts": ["electronic", "elephant", "empty"], "ans": 0},
             {"stem": "Volunteers __________ the items carefully.",
              "opts": ["sorted", "burned", "slammed"], "ans": 0},
             {"stem": "Workers gave the broken toys a __________ life.",
              "opts": ["second", "last", "heavy"], "ans": 0},
             {"stem": "Everyone received a free __________ bag.",
              "opts": ["cloth", "paper", "glass"], "ans": 0},
         ]},
        {"passage": "Dr Muthu opened a small clinic in the village. At first, "
                    "few people (6)_______ the clinic because they preferred "
                    "traditional medicine. He held free talks about (7)_______ and "
                    "clean water. He hung posters around the village and "
                    "(8)_______ parents to check their children's health. Soon, "
                    "mothers began bringing their children for (9)_______. Dr "
                    "Muthu is happy to see the village grow healthier year after "
                    "year.",
         "gaps": [
             {"stem": "At first, few people __________ the clinic.",
              "opts": ["visited", "moved", "danced"], "ans": 0},
             {"stem": "He held free talks about __________ and clean water.",
              "opts": ["hygiene", "history", "holiday"], "ans": 0},
             {"stem": "He __________ parents to check their children's health.",
              "opts": ["reminded", "slept", "cooked"], "ans": 0},
             {"stem": "Mothers began bringing their children for __________.",
              "opts": ["vaccinations", "schooling", "shopping"], "ans": 0},
         ]},
     ],
}


# ---------------------------------------------------------------------------
# comprehension passages (Part 3) — passage + 5 questions
# ---------------------------------------------------------------------------

COMPREHENSION = {
    1: [
        {"title": "A Day at School",
         "passage": ("Every morning, Mei Ling goes to school. She brings her school bag, "
                     "her pencil box and her water bottle. At school, she learns Bahasa "
                     "Melayu, Bahasa Cina, Matematik, Sains and English. She likes Sains "
                     "best because she can look at the green plants. At recess, she eats "
                     "kuih and drinks milk. In the afternoon, she goes home by school bus."),
         "qs": [
             _rag("What does Mei Ling bring to school?", ["her school bag", "a toy car", "a bicycle"], 0),
             _rag("How many subjects does Mei Ling learn at school?",
                  ["three", "five", "two"], 1),
             _rag("Why does Mei Ling like Sains?", ["She can look at green plants.", "She can play computer games.", "She can sing songs."], 0),
             _rag("What does Mei Ling eat at recess?", ["kuih and milk", "rice and fish", "cake and tea"], 0),
             _rag("How does Mei Ling go home?", ["by school bus", "by train", "on foot"], 0),
         ]},
        {"title": "The School Canteen",
         "passage": ("The school canteen is open during recess. The canteen auntie sells "
                     "nasi lemak, mee goreng, roti canai and fried noodles. Ali always "
                     "buys roti canai with a bowl of curry. Siti likes to drink ice "
                     "lemon tea because the weather is hot. The pupils queue up nicely "
                     "and throw their rubbish in the bin."),
         "qs": [
             _rag("What does the canteen auntie sell?", ["nasi lemak and mee goreng", "toys and books", "pencils and rulers"], 0),
             _rag("What does Ali always buy?", ["roti canai with curry", "nasi lemak", "fried chicken"], 0),
             _rag("Why does Siti like ice lemon tea?", ["Because the weather is hot.", "Because it is cheap.", "Because her mother sells it."], 0),
             _rag("What must the pupils do when queuing?", ["queue up nicely", "run around", "shout loudly"], 0),
             _rag("Where do the pupils throw their rubbish?", ["in the bin", "in the field", "in the pond"], 0),
         ]},
        {"title": "My Family",
         "passage": ("This is my family. There are four people in my family. My father "
                     "is a teacher. My mother is a nurse. My elder brother, Kok Wai, "
                     "has a pet cat. The cat is called Mimi. Mimi likes to sleep on "
                     "the sofa. On Sundays, we visit my grandmother in the kampung. "
                     "She gives us kuih and chicken rice."),
         "qs": [
             _rag("How many people are there in the family?", ["four", "three", "five"], 0),
             _rag("What is the father's job?", ["a teacher", "a nurse", "a farmer"], 0),
             _rag("Who has a pet cat?", ["Kok Wai", "Mother", "Grandmother"], 0),
             _rag("What is the name of the cat?", ["Mimi", "Milo", "Mia"], 0),
             _rag("What does grandmother give us?", ["kuih and chicken rice", "cakes and tea", "fruits and milk"], 0),
         ]},
    ],
    2: [
        {"title": "The Village Market",
         "passage": ("Every Saturday, my mother takes me to the morning market. The "
                     "market is busy. The sellers shout from their stalls. We buy "
                     "fresh vegetables, fish and fruits. I like rambutan best. My "
                     "brother carries the heavy bag. After that, we eat roti canai "
                     "and drink teh tarik at the hawker stall. Papa says the market "
                     "is the best place to buy fresh food."),
         "qs": [
             _rag("When does the girl go to the market?", ["Every Saturday", "Every Sunday", "Every Monday"], 0),
             _rag("What do they buy at the market?", ["vegetables, fish and fruits", "books and pens", "toys and balls"], 0),
             _rag("What does the girl like best?", ["rambutan", "durian", "mango"], 0),
             _rag("Who carries the heavy bag?", ["her brother", "her mother", "her father"], 0),
             _rag("What do they drink at the hawker stall?", ["teh tarik", "colong", "milk"], 0),
         ]},
        {"title": "Chinese New Year",
         "passage": ("Chinese New Year is a happy time for Mei Lin's family. Everyone "
                     "cleans the house before the festival. On the eve, the whole "
                     "family has a reunion dinner. They eat yee sang together and "
                     "wish for good luck. Grandmother gives red packets to the "
                     "children. The children wear new clothes and visit their "
                     "relatives. They watch the lion dance at the village square."),
         "qs": [
             _rag("What does everyone do before the festival?", ["They clean the house.", "They buy a new car.", "They plant trees."], 0),
             _rag("When does the family have the reunion dinner?", ["On the eve of Chinese New Year", "After the lion dance", "In the middle of the year"], 0),
             _rag("What do the children receive from grandmother?", ["red packets", "ice cream", "new bicycles"], 0),
             _rag("What do the children wear?", ["new clothes", "school uniform", "pyjamas"], 0),
             _rag("What do they watch at the village square?", ["the lion dance", "a movie", "a magic show"], 0),
         ]},
    ],
    3: [
        {"title": "A Day in the Kampung",
         "passage": ("Aini spends the school holidays with her grandparents in the "
                     "kampung. In the morning, she helps her grandfather feed the "
                     "chickens and pick the vegetables. Her grandmother cooks a "
                     "special lunch of fresh fish and fried vegetables. After lunch, "
                     "Aini rides her bicycle to the river with her cousin. They watch "
                     "the fish swim in the clear water. In the evening, they eat "
                     "grilled fish with rice and sambal. Aini loves the kampung life."),
         "qs": [
             _rag("Who does Aini stay with during the holidays?", ["her grandparents", "her aunties", "her teachers"], 0),
             _rag("What does Aini do in the morning?", ["She feeds the chickens.", "She watches television.", "She goes to school."], 0),
             _rag("Where does Aini go with her cousin?", ["to the river", "to the market", "to the mall"], 0),
             _rag("What do they see in the clear water?", ["fish swimming", "boats", "coconuts"], 0),
             _rag("What do they eat for dinner?", ["grilled fish with sambal", "noodles", "pizza"], 0),
         ]},
        {"title": "Going to the Zoo Negara",
         "passage": ("On Saturday, Class 3 Aman went to Zoo Negara. The teacher "
                     "counted the pupils before the bus left. At the zoo, they saw "
                     "the Malayan tigers resting under the trees. The guide told "
                     "them that the tapir is the national animal of Malaysia. The "
"pupils watched the monkeys eat bananas. At noon, they had "
                      "their packed lunch near the lake. Everyone took a photo with "
                      "the hornbill before going home."),
         "qs": [
             _rag("When did Class 3 Aman go to Zoo Negara?", ["On Saturday", "On Sunday", "On Monday"], 0),
             _rag("What did the pupils see resting under the trees?", ["Malayan tigers", "elephants", "monkeys"], 0),
             _rag("What is the national animal of Malaysia?", ["the tapir", "the hornbill", "the tiger"], 0),
             _rag("What did the monkeys eat?", ["bananas", "mangoes", "nuts"], 0),
             _rag("Where did the pupils have lunch?", ["near the lake", "in the bus", "in the classroom"], 0),
         ]},
    ],
5: [
        {"title": "Kuala Lumpur in 1925",
         "passage": ("In 1925, Kuala Lumpur was a small, busy town at the meeting of "
                     "two rivers. People came from far away to sell tin at the "
                     "market, and the streets were made of stone while the shops "
                     "were built of wood. Merchants from China and India set up "
                     "trades there, and every morning hawkers carried their food "
                     "to the coffee shops. Most people travelled on foot or by "
                     "bicycle because there were no cars. When it rained, the "
                     "streets turned to mud and the night was lit only by oil "
                     "lamps. Today, the Twin Towers stand where some of the old "
                     "shops once were, but the spirit of Kuala Lumpur as a "
                     "trading town remains."),
         "qs": [
             _rag("What was Kuala Lumpur like in 1925?", ["a small, busy town", "a quiet village", "a big city"], 0),
             _rag("Why did people come to Kuala Lumpur in 1925?", ["to sell tin", "to watch movies", "to attend school"], 0),
             _rag("What were the streets made of?", ["stone", "glass", "plastic"], 0),
             _rag("Who set up trades in Kuala Lumpur?", ["merchants from China and India", "tourists from Japan", "fishermen from Sabah"], 0),
             _rag("What stands where the old shops once were?", ["the Twin Towers", "a football field", "a temple"], 0),
         ]},
        {"title": "The Life of a Malayan Tiger",
         "passage": ("The Malayan tiger is an endangered animal that lives in the "
                     "forests of Peninsular Malaysia. A tiger can weigh up to 130 "
                     "kilograms and hunt alone at night. Each tiger has a "
                     "different pattern of stripes, just like a finger print. "
                     "Tigers need a very large area of forest to find enough "
                     "food, so a single tiger may roam over many square "
                     "kilometres. When forests are cut down to make way for "
                     "farms, tigers lose their homes and their food. Mothers keep "
                     "their cubs hidden in thick grass and teach them to hunt for "
                     "two years. That is why rangers protect them in national "
                     "parks like Taman Negara and patrol the forest to stop "
                     "poaching."),
         "qs": [
             _rag("Where does the Malayan tiger live?", ["in the forests of Peninsular Malaysia", "in the sea", "in the cities"], 0),
             _rag("How much can a Malayan tiger weigh?", ["up to 130 kilograms", "up to 30 kilograms", "up to 300 kilograms"], 1),
             _rag("What makes each tiger different?", ["its pattern of stripes", "the colour of its eyes", "the sound of its roar"], 0),
             _rag("Why do tigers need a large area of forest?", ["to find enough food", "to build cities", "to hold meetings"], 0),
             _rag("Who protects the tigers in national parks?", ["rangers", "hawkers", "drivers"], 0),
         ]},
     ],
6: [
        {"title": "The Ailing River",
         "passage": ("Ten years ago, Sungai Puyu was so clean that children could "
                     "swim in it. Factories later released waste into the water, "
                     "and the river turned grey. Fish died, the water smelled "
                     "terrible, and the villagers could no longer use it for "
                     "drinking or washing. The community started a river care "
                     "programme to save the river. Volunteers cleaned the banks "
                     "every weekend, factories installed filter systems to clean "
                     "their waste, and schools taught pupils about water "
                     "pollution. The council also put up signs asking people not "
                     "to throw rubbish into the river. Today, tadpoles have "
                     "returned to the river, a sign that it is healthy again, "
                     "and the villagers once again enjoy fishing and swimming."),
         "qs": [
             _rag("What could children do in Sungai Puyu ten years ago?", ["They could swim in it.", "They could fish gold.", "They could sail boats."], 0),
             _rag("What turned the river grey?", ["waste from factories", "heavy rain", "fallen leaves"], 0),
             _rag("Why could villagers no longer use the water?", ["It was polluted.", "It was too deep.", "It was too cold."], 0),
             _rag("What does the river care programme do?", ["It cleans the river and teaches people.", "It builds more factories.", "It catches the fish."], 0),
             _rag("What shows that the river is healthy again?", ["tadpoles have returned", "the water is grey", "the factories are closed"], 0),
         ]},
        {"title": "A Night at the Night Market",
         "passage": ("Every Friday evening, the streets of the old town fill up "
                     "with stalls. The night market sells everything from fresh "
                     "vegetables to electronic chargers, and the air is full of "
                     "the smell of grilled food. Aunty Mee Yoke has sold fried "
                     "noodles there for twenty years. She starts preparing her "
                     "ingredients at noon, and all her noodles are cooked within "
                     "two hours. By seven in the evening, a long queue forms in "
                     "front of her stall, and regular customers already know her "
                     "menu by heart. Many say her noodles taste like home. For "
                     "many people, the night market is not just a place to shop; "
                     "it is a place to meet old friends and enjoy the evening "
                     "air."),
         "qs": [
             _rag("When is the night market held?", ["every Friday evening", "every Monday morning", "every Sunday afternoon"], 0),
             _rag("What can shoppers buy at the night market?", ["vegetables and electronic chargers", "only clothes", "only books"], 0),
             _rag("How long has Aunty Mee Yoke sold fried noodles?", ["for twenty years", "for two years", "for five years"], 0),
             _rag("When does she start preparing her ingredients?", ["at noon", "at midnight", "at seven in the evening"], 0),
             _rag("What does the night market mean to many people?", ["a place to meet friends", "a place to sleep", "a place to study"], 0),
         ]},
        {"title": "Career Day at School",
         "passage": ("Last Thursday, our school held a Career Day. Teachers and "
                     "parents came to talk about their jobs in the hall. A nurse "
                     "showed us how to bandage a wound. A pilot told us how he "
                     "flies a plane across many countries. A chef cooked fried "
                     "rice and let us taste it. In the afternoon, a reporter and "
                     "a vet joined a question-and-answer session. The pupils "
                     "asked which job they should choose in the future. Many of "
                     "us now want to work hard and become a professional one "
                     "day. It was an interesting day for everyone."),
         "qs": [
             _rag("When was the Career Day held?", ["last Thursday", "last Monday", "last Sunday"], 0),
             _rag("Who came to talk about their jobs?", ["teachers and parents", "pupils and cooks", "tourists and pilots"], 0),
             _rag("What did the nurse show the pupils?", ["how to bandage a wound", "how to cook fried rice", "how to fly a plane"], 0),
             _rag("Who joined the question-and-answer session?", ["a reporter and a vet", "a chef and a pilot", "a nurse and a teacher"], 0),
             _rag("What do many pupils want to do now?", ["work hard and become a professional", "sleep in the hall", "skip school"], 0),
         ]},
     ],
}


# ---------------------------------------------------------------------------
# matching sets (Part 4) — 3 texts A/B/C + 6 statements
# ---------------------------------------------------------------------------

MATCH = {
    1: [
        {"texts": [
            "A. Mei Ling wakes up at six in the morning. Her father drives her to school. She likes to draw animals.", 
            "B. Ali rides his bicycle to school. He helps his mother water the plants. He loves to play football.",
            "C. Priya takes the school bus. She feeds her pet rabbits after school. She sings well in the choir."],
         "qs": [
             _rag("She wakes up at six in the morning.", ["A", "B", "C"], 0),
             _rag("He rides his bicycle to school.", ["A", "B", "C"], 1),
             _rag("She sings well in the choir.", ["A", "B", "C"], 2),
             _rag("He helps his mother water the plants.", ["A", "B", "C"], 1),
             _rag("She likes to draw animals.", ["A", "B", "C"], 0),
             _rag("She takes the school bus.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "Her father takes her to school by car.", "opts": ["A", "B", "C"], "ans": 0}},
        {"texts": [
            "A. Kok Wai has a pet goldfish. He feeds it every day. He keeps the tank clean.", 
            "B. Siti has a pet cat named Mumu. Mumu sleeps all day. Siti plays with it at night.",
            "C. Aiman has a pet tortoise. It walks very slowly. Aiman lets it eat leaves in the garden."],
         "qs": [
             _rag("It has a tank at home.", ["A", "B", "C"], 0),
             _rag("It walks very slowly.", ["A", "B", "C"], 2),
             _rag("It sleeps all day.", ["A", "B", "C"], 1),
             _rag("It eats leaves in the garden.", ["A", "B", "C"], 2),
             _rag("The owner feeds it every day.", ["A", "B", "C"], 0),
             _rag("The owner plays with it at night.", ["A", "B", "C"], 1),
         ],
         "example": {"stem": "This pet is called Mumu.", "opts": ["A", "B", "C"], "ans": 1}},
    ],
    2: [
        {"texts": [
            "A. Uncle Cheng sells nasi lemak at the morning market.",
            "B. Aunty Lee teaches English at our school.",
            "C. Uncle Raj drives a lorry of fresh fruits from Cameron Highlands."],
         "qs": [
             _rag("He carries strawberries and vegetables down the mountain.", ["A", "B", "C"], 2),
             _rag("She writes notes on the whiteboard.", ["A", "B", "C"], 1),
             _rag("He wraps rice in banana leaves.", ["A", "B", "C"], 0),
             _rag("She marks our exercise books.", ["A", "B", "C"], 1),
             _rag("He starts work very early in the morning.", ["A", "B", "C"], 0),
             _rag("He wears nice shoes every day.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "This lady teaches English at our school.", "opts": ["A", "B", "C"], "ans": 1}},
        {"texts": [
            "A. The library opens at eight in the morning.",
            "B. The canteen sells soup on rainy days.",
            "C. The field is used for football training."],
         "qs": [
             _rag("Pupils borrow storybooks here.", ["A", "B", "C"], 0),
             _rag("Pupils queue for noodles and tea.", ["A", "B", "C"], 1),
             _rag("Players run after the ball here.", ["A", "B", "C"], 2),
             _rag("It opens before our first class.", ["A", "B", "C"], 0),
             _rag("It keeps pupils warm and full.", ["A", "B", "C"], 1),
             _rag("A whistle is often heard here.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "This place is open early in the morning.", "opts": ["A", "B", "C"], "ans": 0}},
    ],
    3: [
        {"texts": [
            "A. Pasar Malam runs every Thursday evening on Jalan Merpati.",
            "B. Pasar Pagi opens early every Sunday morning near the bus stop.",
            "C. The supermarket is open daily from ten in the morning to ten at night."],
         "qs": [
             _rag("It sells goods only one evening each week.", ["A", "B", "C"], 0),
             _rag("Shoppers can buy things before breakfast.", ["A", "B", "C"], 1),
             _rag("It closes at ten at night.", ["A", "B", "C"], 2),
             _rag("Stalls are set up along a street.", ["A", "B", "C"], 0),
             _rag("It opens next to a bus stop.", ["A", "B", "C"], 1),
             _rag("It has fixed opening hours every day.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "It opens early every Sunday morning.", "opts": ["A", "B", "C"], "ans": 1}},
        {"texts": [
            "A. The Orang Asli children walk through the forest to school.",
            "B. The town children take the LRT to school.",
            "C. The villagers share a boat to cross the river."],
         "qs": [
             _rag("They pass by tall trees and rivers.", ["A", "B", "C"], 0),
             _rag("They travel on the railway above the road.", ["A", "B", "C"], 1),
             _rag("They paddle to reach the other side.", ["A", "B", "C"], 2),
             _rag("They use a fast electric train.", ["A", "B", "C"], 1),
             _rag("They walk in the jungle.", ["A", "B", "C"], 0),
             _rag("Their journey depends on the water.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "The villagers share a boat.", "opts": ["A", "B", "C"], "ans": 2}},
    ],
    5: [
        {"texts": [
            "A. Kok Wai wants to be an engineer. He enjoys building small bridges from ice-cream sticks.", 
            "B. Hui Ling dreams of being a doctor. She reads books about the human body every month.", 
            "C. Arif plans to be a chef. He learns new recipes from his grandmother."],
         "qs": [
             _rag("He plays with sticks and glue after school.", ["A", "B", "C"], 0),
             _rag("She studies how the heart works.", ["A", "B", "C"], 1),
             _rag("He tastes and writes down new dishes.", ["A", "B", "C"], 2),
             _rag("He wants to build skyscrapers one day.", ["A", "B", "C"], 0),
             _rag("She practises bandaging a doll.", ["A", "B", "C"], 1),
             _rag("His grandmother is his first teacher.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "She reads books about the human body every month.", "opts": ["A", "B", "C"], "ans": 1}},
        {"texts": [
            "A.  The Twin Towers are the tallest landmarks in Kuala Lumpur.",
            "B.  Menara Kuala Lumpur is a tall communication tower with a viewing deck.",
            "C.  Batu Caves is a limestone hill with a big golden statue outside."],
         "qs": [
             _rag("Tourists take a lift up to its viewing deck.", ["A", "B", "C"], 1),
             _rag("It stands next to other skyscrapers in the city.", ["A", "B", "C"], 0),
             _rag("Worshippers climb its 272 steps.", ["A", "B", "C"], 2),
             _rag("It is made of a single huge rock.", ["A", "B", "C"], 2),
             _rag("It has steel and glass on its outside walls.", ["A", "B", "C"], 0),
             _rag("It is used to send radio and TV signals.", ["A", "B", "C"], 1),
         ],
         "example": {"stem": "A big golden statue stands outside.", "opts": ["A", "B", "C"], "ans": 2}},
    ],
    6: [
        {"texts": [
            "A.  The Penang Hill funicular is the fastest way up the hill.",
            "B.  The Langkawi cable car flies over the rainforest to the peak.",
            "C.  The Putrajaya monorail glides over the city's parks and lakes."],
         "qs": [
             _rag("It stops at a station inside the forest.", ["A", "B", "C"], 1),
             _rag("It gives a view of the islands below.", ["A", "B", "C"], 1),
             _rag("It travels between the capital's white-domed buildings.", ["A", "B", "C"], 2),
             _rag("It is pulled up a steep track.", ["A", "B", "C"], 0),
             _rag("It runs on a single raised rail.", ["A", "B", "C"], 2),
             _rag("Passengers can see a hill station at the top.", ["A", "B", "C"], 0),
         ],
         "example": {"stem": "The Langkawi cable car flies over the rainforest to the peak.", "opts": ["A", "B", "C"], "ans": 1}},
        {"texts": [
            "A.  Singapore is a small country south of Malaysia.",
            "B.  Thailand shares a long land border with northern Malaysia.",
            "C.  Brunei sits on the north coast of the island of Borneo."],
         "qs": [
             _rag("It is separated from Johor by a narrow strait.", ["A", "B", "C"], 0),
             _rag("It touches Perlis, Kedah and Kelantan.", ["A", "B", "C"], 1),
             _rag("It is surrounded by Sarawak except for the sea.", ["A", "B", "C"], 2),
             _rag("Its skyline is famous for a merlion statue.", ["A", "B", "C"], 0),
             _rag("It celebrates Songkran in April.", ["A", "B", "C"], 1),
             _rag("Its sultan lives in a golden-domed palace.", ["A", "B", "C"], 2),
         ],
         "example": {"stem": "Thailand shares a long land border with northern Malaysia.", "opts": ["A", "B", "C"], "ans": 1}},
        {"texts": [
            "A.  Encik Ramli works as an engineer. He designs bridges and tall buildings.",
            "B.  Puan Hasmah is a vet at the animal clinic. She treats cats, dogs and birds.",
            "C.  Cik Tan works as an animator. She draws characters for cartoons on television."],
         "qs": [
             _rag("She checks a sick puppy's temperature.", ["A", "B", "C"], 1),
             _rag("He solves maths problems on a computer at work.", ["A", "B", "C"], 0),
             _rag("She uses a drawing tablet to make her characters move.", ["A", "B", "C"], 2),
             _rag("He uses steel and concrete to make his designs stand.", ["A", "B", "C"], 0),
             _rag("She gives a parrot its medicine every day.", ["A", "B", "C"], 1),
             _rag("Her name appears at the end of a cartoon episode.", ["A", "B", "C"], 2),
],
"example": {"stem": "He designs bridges and tall buildings.", "opts": ["A", "B", "C"], "ans": 0}},
     ],
}


# ---------------------------------------------------------------------------
# Round 19 (F3): teacher-style built-in cloze.  Years 3/5 show the same
# present-tense verb in three forms (drink / drinks / drinking) inside ONE
# coherent paragraph — exactly the Year 3 / Year 5 UPSA format.  Year 6 shows
# same-category noun or adjective gaps (friendly / frightening / proud), the
# T6 format.  These pass the band audit by design and carry ``mode`` so the
# part builder can prefer them per year.
# ---------------------------------------------------------------------------

CLOZE_V = {
    3: [
        {"mode": "verb",
         "passage": "On Sunday morning, Dad takes us to his hometown by car. "
                    "Grandmother (6)______ a big pot of porridge on the fire. "
                    "Uncle (7)______ fruit for everyone, and my cousins "
                    "(8)______ on the porch while they wait. After the meal, "
                    "Grandmother (9)______ a jar of honey for us to take home.",
         "gaps": [
             {"stem": "Grandmother __________ a big pot of porridge on the fire.",
              "opts": ["cook", "cooks", "cooking"], "ans": 1, "ans_text": "cooks"},
             {"stem": "Uncle __________ fruit for everyone.",
              "opts": ["cut", "cuts", "cutting"], "ans": 1, "ans_text": "cuts"},
             {"stem": "My cousins __________ on the porch while they wait.",
              "opts": ["wait", "waits", "waiting"], "ans": 0, "ans_text": "wait"},
             {"stem": "Grandmother __________ a jar of honey for us to take home.",
              "opts": ["give", "gives", "giving"], "ans": 1, "ans_text": "gives"},
         ]},
        {"mode": "verb",
         "passage": "Our class (6)______ to the lake for a science trip. We "
                    "(7)______ leaves under a big tree and (8)______ them into "
                    "a book. Then the teacher (9)______ us pictures of the "
                    "water birds that live there.",
         "gaps": [
             {"stem": "Our class __________ to the lake for a science trip.",
              "opts": ["walk", "walks", "walking"], "ans": 1, "ans_text": "walks"},
             {"stem": "We __________ leaves under a big tree.",
              "opts": ["collect", "collects", "collecting"], "ans": 0,
              "ans_text": "collect"},
             {"stem": "We collect leaves and __________ them into a book.",
              "opts": ["stick", "sticks", "sticking"], "ans": 0, "ans_text": "stick"},
             {"stem": "The teacher __________ the pupils pictures of water birds.",
              "opts": ["show", "shows", "showing"], "ans": 1, "ans_text": "shows"},
         ]},
        {"mode": "verb",
         "passage": "Pupils (6)______ the school garden every Friday. They "
                    "(7)______ any rubbish they find and (8)______ the plants "
                    "in the pots. The gardener (9)______ the grass while the "
                    "pupils sweep the walkway.",
         "gaps": [
             {"stem": "Pupils __________ the school garden every Friday.",
              "opts": ["clean", "cleans", "cleaning"], "ans": 0, "ans_text": "clean"},
             {"stem": "They __________ any rubbish they find.",
              "opts": ["pick", "picks", "picking"], "ans": 0, "ans_text": "pick"},
             {"stem": "They pick the rubbish and __________ the plants in the pots.",
              "opts": ["water", "waters", "watering"], "ans": 0, "ans_text": "water"},
             {"stem": "The gardener __________ the grass while the pupils work.",
              "opts": ["cut", "cuts", "cutting"], "ans": 1, "ans_text": "cuts"},
         ]},
    ],
    5: [
        {"mode": "verb",
         "passage": "At the weekend, Farid (6)______ his uncle at the market "
                    "stall. He (7)______ the fruits into bags and (8)______ "
                    "them on the scale. Before closing, his uncle (9)______ "
                    "the coins one by one and smiles.",
         "gaps": [
             {"stem": "Farid __________ his uncle at the market stall.",
              "opts": ["help", "helps", "helping"], "ans": 1, "ans_text": "helps"},
             {"stem": "He __________ the fruits into bags.",
              "opts": ["pack", "packs", "packing"], "ans": 1, "ans_text": "packs"},
             {"stem": "He packs the fruits and __________ them on the scale.",
              "opts": ["put", "puts", "putting"], "ans": 1, "ans_text": "puts"},
             {"stem": "His uncle __________ the coins one by one and smiles.",
              "opts": ["count", "counts", "counting"], "ans": 1, "ans_text": "counts"},
         ]},
        {"mode": "verb",
         "passage": "The school band (6)______ every Monday in the music room. "
                    "Nadia (7)______ the drums while Mei plays the flute. The "
                    "teacher (8)______ the beat, and the pupils (9)______ "
                    "exactly in time.",
         "gaps": [
             {"stem": "The school band __________ every Monday in the music room.",
              "opts": ["practise", "practises", "practising"], "ans": 1,
              "ans_text": "practises"},
             {"stem": "Nadia __________ the drums while Mei plays the flute.",
              "opts": ["hit", "hits", "hitting"], "ans": 1, "ans_text": "hits"},
             {"stem": "The teacher __________ the beat for the band.",
              "opts": ["count", "counts", "counting"], "ans": 1, "ans_text": "counts"},
             {"stem": "The pupils __________ exactly in time.",
              "opts": ["move", "moves", "moving"], "ans": 0, "ans_text": "move"},
         ]},
        {"mode": "verb",
         "passage": "Mrs Tan (6)______ the dogs in her garden every morning. "
                    "She (7)______ fresh water into their bowls and (8)______ "
                    "out the old mats. When the afternoon sun (9)______ hot, "
                    "the dogs nap under the tree.",
         "gaps": [
             {"stem": "Mrs Tan __________ the dogs in her garden every morning.",
              "opts": ["feed", "feeds", "feeding"], "ans": 1, "ans_text": "feeds"},
             {"stem": "She __________ fresh water into their bowls.",
              "opts": ["pour", "pours", "pouring"], "ans": 1, "ans_text": "pours"},
             {"stem": "She __________ out the old mats.",
              "opts": ["put", "puts", "putting"], "ans": 1, "ans_text": "puts"},
             {"stem": "When the afternoon sun __________ hot, the dogs nap.",
              "opts": ["grow", "grows", "growing"], "ans": 1, "ans_text": "grows"},
         ]},
    ],
}

CLOZE_SEM = {
    6: [
        {"mode": "sem",
         "passage": "In Ava's family, everyone helps at home. Her (6)______ "
                    "cooks dinner, and her (7)______ waters the plants on the "
                    "balcony. Ava washes the dishes while her little (8)______ "
                    "stacks the bowls. On weekends, the whole family plays "
                    "badminton at the court, and everyone returns home "
                    "(9)______.",
         "gaps": [
             {"stem": "Ava's __________ cooks dinner for the family.",
              "opts": ["mother", "father", "uncle"], "ans": 0, "ans_text": "mother"},
             {"stem": "Her __________ waters the plants on the balcony.",
              "opts": ["father", "brother", "sister"], "ans": 0, "ans_text": "father"},
             {"stem": "Her little __________ stacks the bowls.",
              "opts": ["sister", "brother", "cousin"], "ans": 0, "ans_text": "sister"},
             {"stem": "Everyone returns home __________ after the game.",
              "opts": ["happy", "sad", "bored"], "ans": 0, "ans_text": "happy"},
         ]},
        {"mode": "sem",
         "passage": "Ali walks to the (6)______ every morning to borrow "
                    "storybooks. At recess, he sits in the (7)______ to drink "
                    "hot tea with his friends. After classes, he plays "
                    "badminton on the outdoor (8)______. He always keeps his "
                    "sports shoes in the (9)______ near the gate.",
         "gaps": [
             {"stem": "Ali walks to the __________ to borrow storybooks.",
              "opts": ["library", "canteen", "classroom"], "ans": 0,
              "ans_text": "library"},
             {"stem": "He sits in the __________ to drink hot tea.",
              "opts": ["canteen", "library", "office"], "ans": 0,
              "ans_text": "canteen"},
             {"stem": "He plays badminton on the outdoor __________.",
              "opts": ["court", "garden", "field"], "ans": 0, "ans_text": "court"},
             {"stem": "He keeps his sports shoes in the __________ near the gate.",
              "opts": ["locker", "basket", "cupboard"], "ans": 0,
              "ans_text": "locker"},
         ]},
        {"mode": "sem",
         "passage": "A spider spins its (6)______ between the two trees. The "
                    "ants march into their (7)______ under the rock. A "
                    "caterpillar sleeps wrapped in its (8)______ during the "
                    "night. The woodpecker drills its (9)______ in the old "
                    "trunk.",
         "gaps": [
             {"stem": "A spider spins its __________ between the two trees.",
              "opts": ["web", "nest", "den"], "ans": 0, "ans_text": "web"},
             {"stem": "The ants march into their __________ under the rock.",
              "opts": ["hill", "nest", "cave"], "ans": 0, "ans_text": "hill"},
             {"stem": "A caterpillar sleeps wrapped in its __________.",
              "opts": ["cocoon", "web", "burrow"], "ans": 0, "ans_text": "cocoon"},
             {"stem": "The woodpecker drills its __________ in the old trunk.",
              "opts": ["hole", "nest", "den"], "ans": 0, "ans_text": "hole"},
         ]},
    ],
}


# ---------------------------------------------------------------------------
# Part 5 word pools
# ---------------------------------------------------------------------------

WORDS_CHOICE = {
    1: [
        {"box": ["sandals", "cap", "shoes", "socks", "scarf"],
         "items": [
             _rag("We wear __________ on our feet before putting on our shoes.", ["socks", "cap", "sandals"], 0, ans_text="socks"),
             _rag("We wear __________ when we go to the beach.", ["sandals", "shoes", "socks"], 0, ans_text="sandals"),
             _rag("A __________ protects our head from the hot sun.", ["cap", "shoe", "scarf"], 0, ans_text="cap"),
             _rag("We tie the laces of our __________ before running.", ["shoes", "caps", "sandals"], 0, ans_text="shoes"),
             _rag("Mother wraps a warm __________ around my neck on rainy days.", ["scarf", "cap", "glasses"], 0, ans_text="scarf"),
         ]},
        {"box": ["nasi lemak", "satay", "roti canai", "kuih", "laksa"],
         "items": [
             _rag("Auntie wraps hot, coconut rice in banana leaves. It is __________.",
                  ["nasi lemak", "satay", "roti canai"], 0, ans_text="nasi lemak"),
             _rag("We dip folded pancakes into curry. That is __________.",
                  ["roti canai", "nasi lemak", "kuih"], 0, ans_text="roti canai"),
             _rag("Small pieces of grilled meat are served on bamboo sticks. That is __________.",
                  ["satay", "nasi lemak", "roti canai"], 0, ans_text="satay"),
             _rag("Grandmother's colourful little cakes are called __________.",
                  ["kuih", "satay", "nasi lemak"], 0, ans_text="kuih"),
             _rag("We slurp hot noodles in spicy coconut broth. That is __________.",
                  ["laksa", "kuih", "satay"], 0, ans_text="laksa"),
         ]},
    ],
    2: [
        {"box": ["canteen", "library", "office", "field", "toilet"],
         "items": [
             _rag("We buy food here during recess.", ["canteen", "library", "office"], 0, ans_text="canteen"),
             _rag("We read and borrow storybooks here.", ["library", "canteen", "field"], 0, ans_text="library"),
             _rag("Pupils run and play football here.", ["field", "library", "office"], 0, ans_text="field"),
             _rag("Teachers work and mark books here.", ["office", "field", "canteen"], 0, ans_text="office"),
             _rag("Pupils wash their hands here before recess.", ["toilet", "field", "canteen"], 0, ans_text="toilet"),
         ]},
        {"box": ["lorry", "bicycle", "bus", "train", "aeroplane"],
         "items": [
             _rag("About thirty pupils travel to school in this big vehicle.", ["bus", "lorry", "train"], 0, ans_text="bus"),
             _rag("It carries heavy goods along the highway.", ["lorry", "bicycle", "bus"], 0, ans_text="lorry"),
             _rag("It rides on rails between cities.", ["train", "bus", "lorry"], 0, ans_text="train"),
             _rag("Aiman rides this with his brother to the playground.", ["bicycle", "bus", "lorry"], 0, ans_text="bicycle"),
             _rag("It has two wheels and needs no fuel.", ["bicycle", "bus", "train"], 0, ans_text="bicycle"),
         ]},
    ],
    3: [
        {"box": ["pilot", "dentist", "firefighter", "nurse", "chef"],
         "items": [
             _rag("She helps the doctor and takes care of the sick.", ["nurse", "dentist", "pilot"], 0, ans_text="nurse"),
             _rag("He flies aeroplanes across the sky.", ["pilot", "firefighter", "dentist"], 0, ans_text="pilot"),
             _rag("He pulls out bad teeth and checks our gums.", ["dentist", "nurse", "pilot"], 0, ans_text="dentist"),
             _rag("He puts out fires and rescues people.", ["firefighter", "dentist", "nurse"], 0, ans_text="firefighter"),
             _rag("He cooks delicious food in the restaurant kitchen.", ["chef", "pilot", "nurse"], 0, ans_text="chef"),
         ]},
        {"box": ["durian", "rambutan", "mango", "papaya", "cempedak"],
         "items": [
             _rag("It has green prickles and a strong smell. It is the king of fruits.", ["durian", "rambutan", "mango"], 0, ans_text="durian"),
             _rag("It is hairy and red on the outside and sweet inside.", ["rambutan", "papaya", "durian"], 0, ans_text="rambutan"),
             _rag("It is yellow, sweet and juicy. We make juice from it.", ["mango", "durian", "rambutan"], 0, ans_text="mango"),
             _rag("It is orange when ripe, and we eat it with ice cream.", ["papaya", "rambutan", "durian"], 0, ans_text="papaya"),
             _rag("Its yellow flesh is sticky and smells like jackfruit.", ["cempedak", "mango", "papaya"], 0, ans_text="cempedak"),
         ]},
    ],
}

#: Years 1-3 Part 5.  ``UASA YEAR 1.pdf`` gives every letter blanked and the
#: clue in the riddle voice the ministry uses for lower primary --
#: "I have two wings. I can fly in the sky.  I eat worms."  The words are
#: drawn from the official KSSR DSKP Year 1-3 word lists, because Years 1-3
#: used to fall back to ``WORDS_LETTER_Y5`` and offered a Year 1 pupil
#: "bridge" from "People use it to cross a wide river".
WORDS_LETTER_Y1 = [
    {"clue": "I have two wings. I can fly in the sky. I eat worms.",
     "word": "bird"},
    {"clue": "I say moo. I give us milk.", "word": "cow"},
    {"clue": "I am small and green. I love to jump around.",
     "word": "frog"},
    {"clue": "I have four legs. I can run fast and I can jump high.",
     "word": "rabbit"},
    {"clue": "I am orange with black stripes.", "word": "tiger"},
    {"clue": "I have a long trunk. I am the biggest animal on land.",
     "word": "elephant"},
    {"clue": "I have eight legs. I make my web.", "word": "spider"},
    {"clue": "I have a long neck. I eat the leaves of tall trees.",
     "word": "giraffe"},
    {"clue": "I say quack. I live on a farm.", "word": "duck"},
    {"clue": "I am small. I like to sit in the sun and I can run fast.",
     "word": "lizard"},
    {"clue": "I am very small. I love cheese.", "word": "mouse"},
    {"clue": "I have a long face. I like to eat grass.",
     "word": "horse"},
]

WORDS_LETTER_Y2 = [
    {"clue": "I am round and white. I live on a farm.",
     "word": "sheep"},
    {"clue": "I have a long body. I have no legs. I can crawl.",
     "word": "snake"},
    {"clue": "I have a big head and a very long tail. I like to climb trees.",
     "word": "monkey"},
    {"clue": "I am a big cat with a long tail. I live in the grass.",
     "word": "lion"},
    {"clue": "I have big ears. I like to eat carrots.",
     "word": "rabbit"},
    {"clue": "I have feathers. I can fly and I can sing.",
     "word": "bird"},
    {"clue": "I am a small dog with long ears. I like to run fast.",
     "word": "donkey"},
    {"clue": "I have black and white stripes. I like to eat grass.",
     "word": "zebra"},
    {"clue": "I am yellow. I can lay eggs.", "word": "chick"},
    {"clue": "I have two horns. I like to eat grass.", "word": "goat"},
    {"clue": "I have a round body. I say cluck. I give us eggs.",
     "word": "hen"},
]

WORDS_LETTER_Y3 = [
    {"clue": "It is a place where we go to see many animals.",
     "word": "zoo"},
    {"clue": "It is a place where we go to borrow and read books.",
     "word": "library"},
    {"clue": "It is the place where doctors and nurses work.",
     "word": "hospital"},
    {"clue": "It is a place where we watch a film.", "word": "cinema"},
    {"clue": "It is a place where we go to swim.", "word": "pool"},
    {"clue": "It is a place where we go to play and run.",
     "word": "playground"},
    {"clue": "It is a place where we buy and sell things.",
     "word": "market"},
    {"clue": "It is a place where we go to learn.", "word": "school"},
    {"clue": "It is a hot drink that people drink in the morning.",
     "word": "coffee"},
    {"clue": "It is a sweet yellow food that grows on a tree.",
     "word": "banana"},
    {"clue": "It is food that we eat for breakfast.", "word": "bread"},
    {"clue": "It is a place where people buy food and eat a meal.",
     "word": "restaurant"},
]

WORDS_LETTER_Y5 = [
    {"clue": "It is a ride that takes people up a railway track.", "word": "train"},
    {"clue": "People use it to cross a wide river.", "word": "bridge"},
    {"clue": "It protects your head when you ride a motorcycle.", "word": "helmet"},
    {"clue": "It is a tall building where people live or work.", "word": "tower"},
    {"clue": "Electricity travels along this metal line.", "word": "cable"},
    {"clue": "It is a place where we throw rubbish.", "word": "dump"},
    {"clue": "A person who answers the phone and greets guests.", "word": "receptionist"},
    {"clue": "It carries people up and down a tall building.", "word": "lift"},
    {"clue": "Weather reporters show this on the news.", "word": "forecast"},
    {"clue": "We use it to protect our eyes from the sun.", "word": "sunglasses"},
    {"clue": "It is a sign that shows directions.", "word": "compass"},
    {"clue": "A small boat used by fishermen.", "word": "skiff"},
    {"clue": "Money that the government collects from shops.", "word": "tax"},
    {"clue": "It transports people under the ground in a city.", "word": "metro"},
    {"clue": "We should always wear this belt in a car.", "word": "seatbelt"},
    {"clue": "A person who writes news articles.", "word": "reporter"},
    {"clue": "It is a long journey by boat or plane.", "word": "voyage"},
    {"clue": "We use this device to measure how fast we run.", "word": "stopwatch"},
    {"clue": "A tiny animal with six legs.", "word": "insect"},
    {"clue": "The place where a bird builds its home.", "word": "nest"},
]

WORDS_LETTER_Y6 = [
    {"clue": "It generates electricity from flowing water.", "word": "hydro"},
    {"clue": "A place where wild animals are kept safe.", "word": "sanctuary"},
    {"clue": "A person who studies the stars and planets.", "word": "astronomer"},
    {"clue": "The rise in the temperature of the Earth.", "word": "warming"},
    {"clue": "It is a long, narrow strip of water in the river.", "word": "stream"},
    {"clue": "Something harmful that spoils the air and water.", "word": "pollution"},
    {"clue": "We do this to paper, bottles and cans.", "word": "recycle"},
    {"clue": "A very large group of people marching together.", "word": "procession"},
    {"clue": "It is a small house made of ice and snow.", "word": "igloo"},
    {"clue": "A person who leads the assembly in a temple.", "word": "priest"},
    {"clue": "A machine that sends messages through the air.", "word": "signal"},
    {"clue": "The study of life in the past through old things.", "word": "history"},
    {"clue": "A person who flies an aeroplane.", "word": "pilot"},
    {"clue": "It is the flat part of a river where water falls.", "word": "waterfall"},
    {"clue": "We put money in it and save for later.", "word": "piggy"},
    {"clue": "A soft, green plant that grows on wet rocks.", "word": "moss"},
    {"clue": "A building where goods are made.", "word": "factory"},
    {"clue": "A large mirror used in a drama room.", "word": "stage"},
    {"clue": "A famous type of primate with a long nose.", "word": "proboscis"},
    {"clue": "The organ that pumps blood through the body.", "word": "heart"},
    {"clue": "This person cooks delicious meals in a kitchen.", "word": "chef"},
    {"clue": "This person teaches pupils in a classroom.", "word": "teacher"},
    {"clue": "This person patrols the streets to keep people safe.", "word": "police"},
    {"clue": "This person flies an aeroplane to other countries.", "word": "pilot"},
    {"clue": "This person tends to plants and gardens.", "word": "gardener"},
    {"clue": "This person checks our teeth at the clinic.", "word": "dentist"},
    {"clue": "This person plants vegetables in the field.", "word": "farmer"},
    {"clue": "This person creates fresh designs for products.", "word": "designer"},
    {"clue": "This person treats sick animals at the clinic.", "word": "vet"},
]


# ---------------------------------------------------------------------------
# Part 6 & 7 writing pools
# ---------------------------------------------------------------------------

SENTENCES = {
    "lower": [
        {"words": ["ride a bicycle", "Monday"], "model": "I ride a bicycle on Monday."},
        {"words": ["play football", "Tuesday"], "model": "I play football on Tuesday."},
        {"words": ["swim", "Thursday"], "model": "I swim in the swimming pool on Thursday."},
        {"words": ["watch TV", "Wednesday"], "model": "I watch TV with my family on Wednesday."},
        {"words": ["draw pictures", "Friday"], "model": "I draw pictures on Friday."},
        {"words": ["visit grandparents", "weekend"], "model": "I visit my grandparents on the weekend."},
        {"words": ["read storybooks", "library"], "model": "I read storybooks at the library."},
        {"words": ["eat nasi lemak", "breakfast"], "model": "I eat nasi lemak for breakfast."},
        {"words": ["drink milk tea", "morning"], "model": "I drink milk tea in the morning."},
        {"words": ["water the plants", "garden"], "model": "I water the plants in the garden."},
        {"words": ["wear uniform", "school"], "model": "I wear my uniform to school."},
        {"words": ["feed the cat", "evening"], "model": "I feed the cat in the evening."},
    ],
    "upper": [
        {"words": ["recycle", "bottles", "every week"], "model": "We recycle plastic bottles every week."},
        {"words": ["take the LRT", "city", "school"], "model": "I take the LRT to school in the city."},
        {"words": ["brush", "teeth", "twice"], "model": "I brush my teeth twice a day."},
        {"words": ["donate", "clothes", "orphanage"], "model": "My family donates old clothes to the orphanage."},
        {"words": ["raise money", "charity fair", "school"], "model": "We raised money at a charity fair in school."},
        {"words": ["practise", "relay", "afternoon"], "model": "We practise the relay race every afternoon."},
        {"words": ["plant", "trees", "riverbank"], "model": "The club planted trees along the riverbank."},
        {"words": ["save", "pocket money", "bicycle"], "model": "I save my pocket money to buy a bicycle."},
    ],
}

# Year 1 Part 6 — make sentences with prepositions (in, on, under), mirroring
# the official UPSA Year 1 paper ("Ex.  cat - cup -> The cat is in a cup.").
SENTENCES_Y1 = [
    {"words": ["cat", "cup"], "model": "The cat is in the cup."},
    {"words": ["dog", "table"], "model": "The dog is under the table."},
    {"words": ["bird", "tree"], "model": "The bird is on the tree."},
    {"words": ["fish", "bowl"], "model": "The fish is in the bowl."},
    {"words": ["shoes", "bed"], "model": "The shoes are under the bed."},
    {"words": ["book", "chair"], "model": "The book is on the chair."},
    {"words": ["duck", "tub"], "model": "The duck is in the tub."},
    {"words": ["cat", "bag"], "model": "The cat is in the bag."},
    {"words": ["ball", "box"], "model": "The ball is in the box."},
    {"words": ["hat", "hook"], "model": "The hat is on the hook."},
    {"words": ["egg", "fridge"], "model": "The egg is in the fridge."},
    {"words": ["milk", "glass"], "model": "The milk is in the glass."},
]

# Year 1 & 2 Part 7 — "Write THREE sentences for each boy/girl you draw
# wearing different outfits."  Mirrors the official UPSA prompt exactly: the
# pupil draws a figure in the box and writes three short sentences about him
# or her.  Every card carries simple, familiar clothes and child-friendly
# activities so the content stays suitable for lower-primary pupils.  The
# official paper numbers these 31-35 (five tasks, 3 marks each).
OUTFIT_CARDS = {
    1: [
        {"prompt": "Draw a boy in the box next to the red T-shirt. He is "
                   "wearing a yellow T-shirt and blue shorts. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a yellow T-shirt and "
                       "blue shorts.", "He plays football in the park after "
                       "school."]},
        {"prompt": "Draw a girl in the box next to the red dress. She is "
                   "wearing a red dress and white shoes. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a red dress and "
                       "white shoes.", "She walks to school with her "
                       "mother."]},
        {"prompt": "Draw a boy in the box next to the green shirt. He is "
                   "wearing a green shirt and grey trousers. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a green shirt and "
                       "grey trousers.", "He helps his father water the "
                       "plants in the garden."]},
        {"prompt": "Draw a girl in the box next to the blue skirt. She is "
                   "wearing a blue skirt and a pink cap. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a blue skirt and a "
                       "pink cap.", "She rides her bicycle around the garden."]},
        {"prompt": "Draw a boy in the box next to the orange T-shirt. He is "
                   "wearing an orange T-shirt and black jeans. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing an orange T-shirt and "
                       "black jeans.", "He eats breakfast in the kitchen with "
                       "his sister."]},
        {"prompt": "Draw a girl in the box next to the yellow sweater. She is "
                   "wearing a yellow sweater and brown hat. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a yellow sweater "
                       "and a brown hat.", "She reads a storybook on the "
                       "sofa at home."]},
        {"prompt": "Draw a boy in the box next to the white jacket. He is "
                   "wearing a white jacket and a red cap. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a white jacket and a "
                       "red cap.", "He goes to the market with his "
                       "grandmother."]},
        {"prompt": "Draw a girl in the box next to the green dress. She is "
                   "wearing a green dress and purple socks. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a green dress and "
                       "purple socks.", "She plays with a ball in the "
                       "playground."]},
        {"prompt": "Draw a girl in the box next to the purple T-shirt. She is "
                   "wearing a purple T-shirt and a white skirt. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a purple T-shirt and "
                       "a white skirt.", "She plays with her friends in the "
                       "field."]},
        {"prompt": "Draw a boy in the box next to the brown shirt. He is "
                   "wearing a brown shirt and beige shorts. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a brown shirt and "
                       "beige shorts.", "He feeds the ducks by the pond."]},
        {"prompt": "Draw a girl in the box next to the pink dress. She is "
                   "wearing a pink dress and a yellow bow. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a pink dress and a "
                       "yellow bow.", "She brings a watering can to the "
                       "garden."]},
        {"prompt": "Draw a boy in the box next to the grey T-shirt. He is "
                   "wearing a grey T-shirt and blue jeans. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a grey T-shirt and "
                       "blue jeans.", "He reads a book under the big tree."]},
        {"prompt": "Draw a girl in the box next to the orange skirt. She is "
                   "wearing a green top and an orange skirt. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a green top and an "
                       "orange skirt.", "She buys sweets at the shop."]},
        {"prompt": "Draw a boy in the box next to the blue shirt. He is "
                   "wearing a blue shirt and brown trousers. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a blue shirt and "
                       "brown trousers.", "He flies a kite at the beach."]},
        {"prompt": "Draw a girl in the box next to the white dress. She is "
                   "wearing a white dress and red shoes. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a white dress and "
                       "red shoes.", "She sings at the school concert."]},
        {"prompt": "Draw a boy in the box next to the purple jacket. He is "
                   "wearing a purple jacket and a grey cap. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a purple jacket and a "
                       "grey cap.", "He catches the school bus every "
                       "morning."]},
        {"prompt": "Draw a girl in the box next to the brown dress. She is "
                   "wearing a brown dress and orange shoes. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a brown dress and "
                       "orange shoes.", "She paints a picture at her desk."]},
        {"prompt": "Draw a boy in the box next to the green jacket. He is "
                   "wearing a green jacket and black trousers. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a green jacket and "
                       "black trousers.", "He rides his bicycle to the "
                       "playground."]},
        {"prompt": "Draw a girl in the box next to the yellow skirt. She is "
                   "wearing a yellow skirt and green shoes. Write THREE "
                   "sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a yellow skirt and "
                       "green shoes.", "She helps the auntie pack the "
                       "vegetables."]},
        {"prompt": "Draw a boy in the box next to the red shirt. He is "
                   "wearing a red shirt and blue trousers. Write THREE "
                   "sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a red shirt and blue "
                       "trousers.", "He waters the plants with a hose."]},
    ],
    2: [
        {"prompt": "Draw a boy in the box wearing a yellow T-shirt and blue "
                   "shorts. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "where he plays"],
         "sentences": ["This is a boy.", "He is wearing a yellow T-shirt and "
                       "blue shorts.", "He plays football with his friends at "
                       "the field."]},
        {"prompt": "Draw a girl in the box wearing a red dress and white "
                   "shoes. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "where she goes"],
         "sentences": ["This is a girl.", "She is wearing a red dress and "
                       "white shoes.", "She goes to the library on "
                       "Saturday."]},
        {"prompt": "Draw a boy in the box wearing a green shirt and grey "
                   "trousers. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a green shirt and "
                       "grey trousers.", "He sweeps the corridor with his "
                       "classmates."]},
        {"prompt": "Draw a girl in the box wearing a blue skirt and a pink "
                   "cap. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a blue skirt and a "
                       "pink cap.", "She waters the flowers in the garden."]},
        {"prompt": "Draw a boy in the box wearing an orange T-shirt and "
                   "black jeans. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing an orange T-shirt and "
                       "black jeans.", "He helps his mother cook fried "
                       "rice."]},
        {"prompt": "Draw a girl in the box wearing a yellow sweater and a "
                   "brown hat. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a yellow sweater "
                       "and a brown hat.", "She tells a story to her little "
                       "sister."]},
        {"prompt": "Draw a boy in the box wearing a white jacket and a red "
                   "cap. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a white jacket and a "
                       "red cap.", "He rides a bus to his grandfather's "
                       "house."]},
        {"prompt": "Draw a girl in the box wearing a green dress and purple "
                   "socks. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a green dress and "
                       "purple socks.", "She dances with her friends at the "
                       "school concert."]},
        {"prompt": "Draw a girl in the box wearing a purple T-shirt and a "
                   "white skirt. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a purple T-shirt and "
                       "a white skirt.", "She skips rope with her friends in "
                       "the playground."]},
        {"prompt": "Draw a boy in the box wearing a brown shirt and beige "
                   "shorts. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a brown shirt and "
                       "beige shorts.", "He helps the farmer feed the ducks."]},
        {"prompt": "Draw a girl in the box wearing a pink dress and a yellow "
                   "bow. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a pink dress and a "
                       "yellow bow.", "She waters the plants in the school "
                       "garden."]},
        {"prompt": "Draw a boy in the box wearing a grey T-shirt and blue "
                   "jeans. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a grey T-shirt and "
                       "blue jeans.", "He reads a storybook to his little "
                       "brother."]},
        {"prompt": "Draw a girl in the box wearing a green top and an orange "
                   "skirt. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a green top and an "
                       "orange skirt.", "She buys fruit at the weekend "
                       "market."]},
        {"prompt": "Draw a boy in the box wearing a blue shirt and brown "
                   "trousers. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a blue shirt and "
                       "brown trousers.", "He flies a kite with his cousin at "
                       "the beach."]},
        {"prompt": "Draw a girl in the box wearing a white dress and red "
                   "shoes. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a white dress and "
                       "red shoes.", "She sings a song at the school "
                       "assembly."]},
        {"prompt": "Draw a boy in the box wearing a purple jacket and a grey "
                   "cap. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a purple jacket and a "
                       "grey cap.", "He takes the school bus every morning "
                       "with his friend."]},
        {"prompt": "Draw a girl in the box wearing a brown dress and orange "
                   "shoes. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a brown dress and "
                       "orange shoes.", "She draws a rainbow in her drawing "
                       "book."]},
        {"prompt": "Draw a boy in the box wearing a green jacket and black "
                   "trousers. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a green jacket and "
                       "black trousers.", "He rides his bicycle to the shop "
                       "to buy milk."]},
        {"prompt": "Draw a girl in the box wearing a yellow skirt and green "
                   "shoes. Write THREE sentences about her.",
         "bullets": ["who she is", "what she is wearing", "what she does"],
         "sentences": ["This is a girl.", "She is wearing a yellow skirt and "
                       "green shoes.", "She helps her mother pack the "
                       "vegetables."]},
        {"prompt": "Draw a boy in the box wearing a red shirt and blue "
                   "trousers. Write THREE sentences about him.",
         "bullets": ["who he is", "what he is wearing", "what he does"],
         "sentences": ["This is a boy.", "He is wearing a red shirt and blue "
                       "trousers.", "He waters the morning glories with his "
                       "father."]},
    ],
}

# style "paragraph" (Part 7, lower years)
PARAGRAPHS = {
    1: [
        {"prompt": "Write THREE sentences about your best friend. You may write about his or her name, age and favourite food or game.",
         "example": "This is my best friend. His name is Kok Wai.", "bullets": ["his or her name", "how old he or she is", "favourite food or game"],
         "lines": 8, "model": "His name is Kok Wai. He is seven years old. He likes to play football."},
        {"prompt": "Write THREE sentences about yourself. You may write about your name, your home and what you like to do.",
         "example": "My name is Satria.", "bullets": ["your name", "where you live", "what you like to do"],
         "lines": 8, "model": "My name is Satria. I live in Johor Bahru. I like to ride my bicycle."},
        {"prompt": "Write THREE sentences about your family. You may write about the people in your family and what they do.",
         "example": "There are five people in my family.", "bullets": ["how many people", "who they are", "what they do"],
         "lines": 8, "model": "There are five people in my family. They are my parents and my two brothers. My mother is a nurse."},
    ],
    2: [
        {"prompt": "Write FIVE sentences about what you do on Sundays.",
         "example": "On Sundays, I do not go to school.", "bullets": ["when you wake up", "what you eat for breakfast", "what you do in the morning", "what you do in the afternoon", "how you feel"],
         "lines": 10, "model": "On Sunday I wake up at eight. I eat toasts and drink milk. Then I play with my friends. In the afternoon I visit my grandmother. I am very happy."},
        {"prompt": "Write FIVE sentences about your favourite food.",
         "example": "My favourite food is nasi lemak.", "bullets": ["what it is", "when you eat it", "where you eat it", "who makes it", "why you like it"],
         "lines": 10, "model": "My favourite food is nasi lemak. I eat it every morning. I eat it with fried anchovies. My mother cooks it for me. It is very delicious."},
    ],
    3: [
        {"prompt": "Write a paragraph of FIVE sentences about your school.",
         "example": "My school is near a big market.", "bullets": ["where your school is", "how many pupils", "what you learn", "what you do at recess", "your favourite place"],
         "lines": 10, "model": "My school is near a big market. There are about 800 pupils. We learn Bahasa Melayu, Chinese and English. At recess, we play in the field. My favourite place is the library."},
        {"prompt": "Write a paragraph of FIVE sentences about a festival you celebrate.",
         "example": "During the festival, my family cleans the house.",
         "bullets": ["which festival", "what you eat", "what you wear", "what you do", "how you feel"],
         "lines": 10, "model": "During Chinese New Year we clean the house. We eat yee sang and dumplings. We wear new red clothes. We give ang pow to the children. We are very happy."},
    ],
}

# Writing-task entries.  Every letter/email entry carries the metadata the
# paper renderers use to draw the official format:
#   salutation / closing  -> letter (Part 6, Year 6)
#   recipient / subject   -> email header (To / Subject rows)
#   word_count            -> "The email should be between ... words."


def _write_extra(year: int, difficulty: str = "medium") -> int:
    """Extra ruled lines for upper-primary writing (space to write).

    Round 33 (F3): scaled by difficulty as well as year, because a hard task
    asking for 60-90 words needs more room than an easy one asking for 30-45;
    otherwise the demand grows while the page stays the same size.
    """
    base = 6 if int(year) >= 5 else 0
    scale = {"easy": 0.75, "medium": 1.0, "hard": 1.4}.get(str(difficulty), 1.0)
    return int(round(base * scale)) if base else 0


def answer_lines(year: int, style: str) -> int:
    """Ruled lines the answer sheet reserves for a writing part."""
    if style in ("letter", "email", "paragraph"):
        return 16 if int(year) >= 5 else 10
    return 9 if int(year) >= 5 else 6


def part_to_user_entry(part, year: int = 0) -> dict | None:
    """Convert a generated Part into a user-bank JSON entry (or None).

    Supported kinds mirror ``USER_KINDS``; writing and vocab parts return
    None (their shapes live in their own pools).  ``year`` seeds the entry so
    ``user_pool`` will apply it to the paper it came from.
    """
    import re as _re
    from .models import MCQItem, WordItem

    def mcq(raw) -> dict:
        return {"stem": raw.stem, "opts": list(raw.options), "ans": raw.answer,
                **({"ans_text": raw.ans_text} if raw.ans_text else {})}

    y = int(year or 0)
    entry = {"year": y} if y else {}
    if part.kind == "vocab" and part.items and \
            isinstance(part.items[0], MCQItem):
        return {**entry, **mcq(part.items[0])}
    if part.kind == "comprehension":
        entry.update(passage=str(part.lead_text or ""),
                     qs=[mcq(i) for i in part.items if isinstance(i, MCQItem)])
        return entry
    if part.kind == "cloze":
        entry.update(passage=str(part.lead_text or ""),
                     gaps=[mcq(i) for i in part.items if isinstance(i, MCQItem)])
        return entry
    if part.kind == "match":
        entry.update(texts=[ln for ln in str(part.lead_text or "").split("\n") if ln],
                     qs=[mcq(i) for i in part.items if isinstance(i, MCQItem)])
        return entry
    if part.kind == "words" and part.style == "choice":
        raw_box = _re.sub(r"^.*?\bWord\s*box:?\s*", "",
                          str(part.lead_text or ""), flags=_re.I)
        box = [b.strip() for b in raw_box.split(",") if b.strip()]
        entry.update(box=box,
                     items=[mcq(i) for i in part.items if isinstance(i, MCQItem)])
        return entry
    if part.kind == "words" and part.style == "letter":
        got = [{**entry, "clue": i.clue,
                "word": str(getattr(i, "answer", "")).lower()}
               for i in part.items if isinstance(i, WordItem)]
        return got or None
    return None


def _bank_kinds_supported() -> tuple[str, ...]:
    return USER_KINDS


def bank_kind_for(part) -> str | None:
    """User-bank kind for a Part (None if the part isn't bankable)."""
    if part.kind == "vocab":
        return "vocab"
    if part.kind == "comprehension":
        return "comprehension"
    if part.kind == "cloze":
        return "cloze"
    if part.kind == "match":
        return "match"
    if part.kind == "words" and part.style == "choice":
        return "words"
    if part.kind == "words" and part.style == "letter":
        return "letter_words"
    return None


def save_user_bank_entry(path: str, kind: str, entry: dict,
                         key: dict | None = None) -> int:
    """Append ``entry`` under ``kind`` to a user-bank JSON file (dedup), then
    write it back.  Returns how many entries were newly added (0 = duplicate).
    """
    import json
    existing: dict = {}
    try:
        with open(path, encoding="utf-8") as fh:
            existing = json.load(fh)
    except Exception:
        existing = {}
    entries = list(existing.get(kind, []) or [])
    marker = json.dumps(key if key is not None else entry,
                        sort_keys=True, ensure_ascii=False)
    if any(json.dumps(d, sort_keys=True, ensure_ascii=False) == marker
           for d in entries if isinstance(d, dict)):
        return 0
    entries.append(entry)
    existing[kind] = entries
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, ensure_ascii=False, indent=2)
    return 1


def default_bank_path() -> str:
    """Persistent user question-bank file (app data dir)."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "exam-gen", "user_bank.json")


def backup_state() -> str:
    """Timestamped copies of user_bank.json + packs.json into backups/
    (Round 12/S10).  Returns newline-separated backup paths."""
    import shutil
    from datetime import datetime
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    exam_dir = os.path.join(base, "exam-gen")
    bdir = os.path.join(exam_dir, "backups")
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    made = []
    for name in ("user_bank.json", "packs.json"):
        src = os.path.join(exam_dir, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(bdir, name[:-5] + f"_{stamp}.json")
        shutil.copy2(src, dst)
        made.append(dst)
    return "\n".join(made)


def band_violations(year: int, kinds: tuple[str, ...] | None = None
                    ) -> list[tuple[str, str, str]]:
    """Audit pools for lexis above the year's vocabulary band (Round 12/S3).

    ``kinds`` selects the pools to scan: ``"vocab"`` (Part 1 stems/options),
    ``"cloze"`` (passages + gap stems/options), ``"match"`` (lead texts +
    stems/options) and ``"comprehension"`` (passages + stems/options); by
    default every pool is scanned.  Each hit is ``(source snippet, word,
    year_of_word)``.
    """
    from . import data as D
    year = int(year)
    band = D.VOCAB_BAND.get(year, ())
    if not band:
        return []
    out: list[tuple[str, str, str]] = []

    def scan(texts) -> None:
        for t in texts:
            t = str(t).lower()
            found = [w for w in sorted(band)
                     if re.search(r"\b" + re.escape(w.lower()) + r"\b", t)]
            if found:
                out.append((t[:60], ", ".join(found), str(year)))

    if kinds is None or "vocab" in kinds:
        for d in _vocab_pool(year):
            scan([" ".join([str(d.get("stem", "")),
                            *map(str, d.get("opts", []))])])
    if kinds is None or "cloze" in kinds:
        for b in _cloze_pool(year):
            scan([b.get("passage", "")])
            for g in b.get("gaps", []):
                scan([str(g.get("stem", "")), *map(str, g.get("opts", []))])
    if kinds is None or "match" in kinds:
        for b in _match_pool(year):
            scan(b.get("texts", []))
            for q in b.get("qs", []):
                scan([str(q.get("stem", "")), *map(str, q.get("opts", []))])
    if kinds is None or "comprehension" in kinds:
        for b in _comp_pool(year):
            scan([b.get("passage", ""), b.get("title", "")])
            for q in b.get("qs", []):
                scan([str(q.get("stem", "")), *map(str, q.get("opts", []))])
    return out


def _writing_entry(prompt, bullets, lines, marks, model, **meta):
    return dict(prompt=prompt, bullets=list(bullets), lines=lines,
                marks=marks, model=model, **meta)


# style "letter" (Part 6, upper years)
LETTERS = {
    6: [
        _writing_entry(
            "You want to share a song you like with your friend, Fiona. "
            "Write a letter to her and tell her about your favourite song.",
            ["what the song is about", "why you like the melody",
             "what the message of the song is", "why she should listen to it"],
            8, 10,
            "Dear Fiona, I want to tell you about my favourite song, 'Lift "
            "You Up'. It is about helping friends in hard times. I love its "
            "happy rhythm and meaningful lyrics. Please listen to it tonight. "
            "Your friend, Wei.",
            salutation="Dear Fiona,", closing="Your friend,",
            theme="Music and Song", word_count="30 - 50 words"),
        _writing_entry(
            "Your school held a Sports Day last week. Write a letter to your "
            "cousin to invite him or her to watch you run next year.",
            ["when the Sports Day is", "where it is held",
             "which race you are in", "why he or she should come"],
            8, 10,
            "Dear cousin, Our school Sports Day is on 20 June. It is held in "
            "the school field. I am running in the relay race this year. "
            "Please come and cheer for my team. Your cousin, Farid.",
            salutation="Dear cousin,", closing="Your cousin,",
            word_count="30 - 50 words"),
        _writing_entry(
            "Your grandmother baked you a cake for your birthday. Write a "
            "letter to thank her and tell her about your birthday party.",
            ["what the cake was like", "who came to the party",
             "what you did at the party", "how you feel"],
            8, 10,
            "Dear Grandmother, Thank you for the chocolate cake. It was so "
            "sweet and tasty that everyone asked for more. My friends came to "
            "the party and we played games. I felt very happy. I love you. "
            "Your grandson, Ming.",
            salutation="Dear Grandmother,", closing="Your grandson,",
            word_count="30 - 50 words"),
        _writing_entry(
            "There was a fire drill at your school. Write a letter to your "
            "friend to tell him or her what happened.",
            ["when the drill was", "what the pupils did",
             "why fire drills are important", "how you felt"],
            8, 10,
            "Dear Aina, Yesterday our school had a fire drill. When the alarm "
            "rang, we lined up and walked to the field. The firefighter said "
            "never to use the lift. Fire drills teach us how to be safe. I felt "
            "proud that we were fast. Your friend, Ben.",
            salutation="Dear Aina,", closing="Your friend,",
            theme="It's an Emergency", word_count="30 - 50 words"),
        _writing_entry(
            "Your grandfather told you about life in the past. Write a letter "
            "to your friend about it.",
            ["where your grandfather lived", "what life was like long ago",
             "how it is different now", "what you learned"],
            8, 10,
            "Dear Siti, My grandfather told me about life in the past. He "
            "lived in a kampung with no electricity. He walked to school and "
            "used candles at night. Today we have cars and lamps. I learned "
            "that life was hard but happy long ago. Your friend, Ravi.",
            salutation="Dear Siti,", closing="Your friend,",
            theme="Life in the Past", word_count="30 - 50 words"),
        _writing_entry(
            "You went on an adventure trip with your family. Write a letter "
            "to your friend about it.",
            ["where you went", "what you did there",
             "something exciting that happened", "how you felt"],
            8, 10,
            "Dear Jun, Last week I went hiking in the jungle with my family. "
            "We climbed a hill and saw a beautiful waterfall. A monkey stole "
            "my sandwich! It was very funny. I felt brave and happy on the "
            "trip. Your friend, Ali.",
            salutation="Dear Jun,", closing="Your friend,",
            theme="Adventure Time", word_count="30 - 50 words"),
        _writing_entry(
            "You travelled to another town by train. Write a letter to your "
            "friend about your journey.",
            ["where you went", "how you travelled", "what you saw on the way",
             "why you liked the journey"],
            8, 10,
            "Dear Mei, Last Saturday I went to Ipoh by train. The train was "
            "fast and comfortable. I saw paddy fields and rivers from my "
            "window. I bought a ticket and sat near the door. I liked the "
            "journey because it was cheap and fun. Your friend, Hafiz.",
            salutation="Dear Mei,", closing="Your friend,",
            theme="Getting Around", word_count="30 - 50 words"),
        _writing_entry(
            "You learned how bread is made. Write a letter to your friend to "
            "tell him or her about it.",
            ["what is made", "what materials are used", "how it is made",
             "why you find it interesting"],
            8, 10,
            "Dear Kumar, Today I learned how bread is made. First, flour, "
            "water and yeast are mixed. Then the dough is left to rise before "
            "it is baked in a hot oven. Bread is made in a factory with big "
            "machines. I think it is very interesting. Your friend, Lily.",
            salutation="Dear Kumar,", closing="Your friend,",
            theme="How Is It Made?", word_count="30 - 50 words"),
        _writing_entry(
            "You read an interesting story. Write a letter to your friend to "
            "tell him or her about the story.",
            ["the title of the story", "who is in the story",
             "what happens in the story", "why you like it"],
            8, 10,
            "Dear Nina, I read a story called 'The Clever Tortoise'. It is "
            "about a tortoise who tricks a proud hare in a race. The tortoise "
            "wins because he never gives up. I like this story because it "
            "teaches us to be patient. Your friend, Sam.",
            salutation="Dear Nina,", closing="Your friend,",
            theme="Tell Me a Story", word_count="30 - 50 words"),
        _writing_entry(
            "Something strange happened at your school. Write a letter to "
            "your friend about the mystery.",
            ["what was strange", "who helped to solve it",
             "what clue you found", "how the mystery ended"],
            8, 10,
            "Dear Aiman, Something strange happened at school. Someone's "
            "lunch box disappeared from the classroom. We looked for clues "
            "and found a trail of rice. It was the class cat! The mystery was "
            "solved and we laughed. Your friend, Zoe.",
            salutation="Dear Aiman,", closing="Your friend,",
            theme="It's a Mystery!", word_count="30 - 50 words"),
        _writing_entry(
            "Your school held a Career Day. Write a letter to your friend "
            "about the job you want to do when you grow up.",
            ["which job you want to do", "why you choose that job",
             "what you must do to get the job", "what your friends chose"],
            8, 10,
            "Dear Priya, Our school held a Career Day last week. I want to be "
            "a vet when I grow up because I love animals. I must study hard "
            "and read a lot about animals. My best friend wants to be a "
            "pilot. Which job do you want? Your friend, Kumar.",
            salutation="Dear Priya,", closing="Your friend,",
            theme="Cool Jobs", word_count="30 - 50 words"),
        _writing_entry(
            "Your headmaster wants to change the lunch break time. Write a "
            "letter to your friend and give your opinion about the plan.",
            ["what the plan is", "do you agree or disagree",
             "give two reasons", "what you suggest"],
            8, 10,
            "Dear Sam, Our headmaster wants to move the lunch break to "
            "eleven in the morning. I disagree because we will not be hungry "
            "yet. My friends think it is too early to play. I suggest we "
            "keep the break at one in the afternoon. Your friend, Aina.",
            salutation="Dear Sam,", closing="Your friend,",
            theme="What's Your Opinion?", word_count="30 - 50 words"),
    ],
}

# style "email"/"essay" (Part 6 short email 30-50 words; Part 7
# email/essay 60-80 words) — upper years + Year 3.
ESSAYS = {
    3: {
        "short": [
            _writing_entry(
                "You want to write an email to your friend to tell him or her "
                "about your day at school. Email your friend and tell him or her "
                "the things you do at school.",
                ["study in the classroom with friends", "play sports with friends",
                 "have fun with your friends"],
                6, 10,
                "Dear Aiman, My day at school is full of fun. In the morning, "
                "I study in the classroom with my friends. At recess, we play "
                "sports on the field. After that, we have fun together. I enjoy "
                "every day at school. Your friend, Mei.",
                recipient="aiman@email.com", subject="My Day at School",
                word_count="30 - 50 words"),
            _writing_entry(
                "You are staying at your grandfather's house for the weekend. "
                "Write an email to your friend about what you do there.",
                ["where you are", "what you like to do there",
                 "what grandfather cooks for you", "how you feel"],
                6, 10,
                "Dear Chen Rong, I am staying at my grandfather's house this "
                "weekend. I help him water the plants in the garden. He cooks "
                "fried rice with chicken for me. I am very happy here. Your "
                "friend, Zhi.",
                recipient="chenrong@email.com", subject="At Grandfather's House",
                word_count="30 - 50 words"),
            _writing_entry(
                "Your school has just opened a new library. Write an email to "
                "your cousin about it.",
                ["where the library is", "what you can read there",
                 "your favourite corner", "when you go there"],
                6, 10,
                "Dear cousin, Our school has a new library. It is next to the "
                "canteen. We can read storybooks and comics there. I like the "
                "corner with big windows. I go there every recess. Your "
                "cousin, Ani.",
                recipient="cousin@email.com", subject="Our New Library",
                word_count="30 - 50 words"),
        ],
        "long": [
            _writing_entry(
                "You want to write an email to a friend about your best friend. "
                "Use the information below to help you.",
                ["your best friend's name", "what he or she looks like",
                 "what you do together", "why he or she is your best friend"],
                8, 15,
                "Dear Wei Lin, I want to tell you about my best friend. Her "
                "name is Yoke Hui. She has long black hair and a happy smile. "
                "We study together in the evening and share our books. She is "
                "my best friend because she is kind and always helps me. I hope "
                "you can meet her one day. Your friend, Mei.",
                recipient="weilin@email.com", subject="My Best Friend",
                word_count="60 - 80 words"),
            _writing_entry(
                "During the last school holiday, your family celebrated Hari "
                "Raya. Write an email to your friend about how you celebrated.",
                ["where you celebrated", "what you wore",
                 "what food you ate", "what you did with your family"],
                8, 15,
                "Dear Siti, During the school holiday, we celebrated Hari Raya "
                "at my grandmother's house. I wore a new baju melayu. We ate "
                "ketupat, rendang and spicy kuih. In the evening, we visited "
                "our neighbours and asked for forgiveness. I love Hari Raya "
                "because the whole family gathers together. Your friend, Adib.",
                recipient="siti@email.com", subject="Hari Raya Celebration",
                word_count="60 - 80 words"),
            _writing_entry(
                "Your school held a Sports Day. Write an email to your friend "
                "about the exciting day.",
                ["when and where the Sports Day was", "what race you took part in",
                 "what your friends did", "how you felt at the end"],
                8, 15,
                "Dear Jia Hao, Our school held its Sports Day on 12 July. It "
                "was held on the school field. I took part in the running race "
                "and came in second. My friends ran in the relay and won a "
                "medal. I felt tired but very proud. I am already waiting for "
                "next year's Sports Day. Your friend, Kai.",
                recipient="jiahao@email.com", subject="Our School Sports Day",
                word_count="60 - 80 words"),
        ],
    },
    5: {
        "short": [
            _writing_entry(
                "You saw a poster about protecting wild animals. Email your "
                "friend and explain why it is important to protect wild animals.",
                ["animals you want to protect", "why they are in danger",
                 "what we can do to help", "how you feel about them"],
                6, 10,
                "Dear Yoke Hui, I saw a poster about protecting wild animals. "
                "I want to protect the Malayan tiger and the hornbill. They are "
                "in danger because their forests are cut down. We can help by "
                "planting trees and not littering. Please join me to protect "
                "them. Your friend, Ming.",
                recipient="yokehui@email.com", subject="Protect Wild Animals",
                word_count="30 - 50 words"),
            _writing_entry(
                "During the holidays, you visited an interesting place. Write "
                "an email to your friend about the place you visited.",
                ["where you went", "who you went with",
                 "what you saw there", "how you felt"],
                6, 10,
                "Dear Farid, During the holidays, I visited Cameron Highlands "
                "with my family. We saw strawberry farms and drank hot tea. I "
                "fed the flowers in the gardens. The weather was cool and "
                "fresh. I wish you were there too. Your friend, Lin.",
                recipient="farid@email.com", subject="My Holiday Trip",
                word_count="30 - 50 words"),
            _writing_entry(
                "Your class is planning a school trip to the museum. Write an "
                "email to your cousin to tell him or her about it.",
                ["when the trip is", "where you are going",
                 "what you will see", "what to bring"],
                6, 10,
                "Dear cousin, My class is going on a trip next Friday. We are "
                "visiting the National Museum. We will see old paintings and "
                "ancient tools. Please bring a small bag and some water. I will "
                "take lots of photos for you. Your cousin, Ani.",
                recipient="cousin@email.com", subject="Our Museum Trip",
                word_count="30 - 50 words"),
        ],
        "long": [
            _writing_entry(
                "Your friend in England wants to come to Malaysia. Write an "
                "email to tell him about the places your friend should visit, "
                "the transport your friend can use, and the food your friend "
                "should try.",
                ["three places to visit", "transport to use",
                 "food to try", "the best time to come"],
                10, 15,
                "Dear Sam, Welcome to Malaysia! Start your trip in Kuala Lumpur. "
                "Visit the Petronas Twin Towers and the Batu Caves. From KL, "
                "take the fast train or a plane to Penang. Walk up Penang Hill "
                "for a wonderful view. You must try nasi lemak, satay and "
                "laksa. They are our most delicious food. Come during the dry "
                "season and you will have a wonderful time. Your friend, Wei.",
                recipient="sam@email.com", subject="Welcome to Malaysia",
                word_count="60 - 80 words"),
            _writing_entry(
                "Your class is planning a gotong-royong at the neighbourhood "
                "park. Based on the information below, write an email to tell "
                "your class teacher about the activity.",
                ["the date and time", "what the class will clean",
                 "what to bring", "why this activity is important"],
                10, 15,
                "Dear Teacher, Our class is planning a gotong-royong at the "
                "park on Saturday morning. We will collect rubbish and sweep "
                "the walkways. Each pupil will bring gloves and a bin bag. We "
                "will also plant a few new trees to make the park greener. This "
                "activity is important because it keeps the environment clean "
                "and teaches us teamwork. We hope you can join us. Thank you, "
                "Class 5 Aman.",
                recipient="teacher@email.com", subject="Gotong-Royong at the Park",
                word_count="60 - 80 words"),
            _writing_entry(
                "You are helping your mother prepare a dish for a school "
                "competition. Based on the information below, write an email "
                "to your cousin about your dish.",
                ["the name of the dish", "the ingredients",
                 "how you make it", "why it is special"],
                10, 15,
                "Dear cousin, I am joining a cooking competition with my mother. "
                "Our dish is Nasi Lemak Bunga Telang. It is blue coconut rice "
                "with fried anchovies and sambal. First we cook the rice with "
                "blue pea flowers. Then we fry the anchovies and peanuts. We "
                "serve it with egg and cucumber. It is special because the blue "
                "colour reminds me of our grandmother. Wish us luck. Your "
                "cousin, Mei.",
                recipient="cousin@email.com", subject="My Cooking Competition",
                word_count="60 - 80 words"),
        ],
    },
    6: {
        "short": [
            _writing_entry(
                "You want to tell your friend about a talent show at your "
                "school. Write an email to your friend about it.",
                ["when the show is", "what the pupils will perform",
                 "what you are doing", "why your friend should come"],
                6, 10,
                "Dear Fiona, Our school is holding a talent show on Saturday. "
                "The pupils will sing, dance and play the drums. I am joining "
                "the school choir. Please come and watch us. Your friend, Wei.",
                recipient="fiona@email.com", subject="Our School Talent Show",
                word_count="30 - 50 words"),
        ],
        "long": [
            _writing_entry(
                "You are making chicken salad at school. Based on the "
                "information below, write an email to tell your friend about "
                "it. Tell your friend why it is important to eat a healthy diet.",
                ["what ingredients you use", "how you prepare the salad",
                 "why a healthy diet matters", "how your friend can try it"],
                10, 15,
                "Dear Mei, Today we made a chicken salad in school. We used "
                "fresh lettuce, cucumber, tomatoes and grilled chicken. We "
                "mixed them with a little olive oil and lemon juice. A healthy "
                "diet gives us energy and keeps our body strong. You should try "
                "making this salad too. It is easy, tasty and good for you. Try it "
                "for lunch this week. "
                "Your friend, Yee.",
                recipient="mei@email.com", subject="Making Chicken Salad",
                word_count="60 - 80 words"),
            _writing_entry(
                "Your class watched a talk about saving money. Based on the "
                "information below, write an email to your cousin about why "
                "saving money is important.",
                ["how to save money", "what we can buy with savings",
                 "why saving is better than wasting", "a plan you will follow"],
                10, 15,
                "Dear cousin, Our class watched a talk about saving money. We "
                "learned that we can save by putting coins in a piggy bank and "
                "by spending only on things we really need. With savings, we "
                "can buy books, gifts or a bicycle one day. Saving is better "
                "than wasting because money is hard to earn. I plan to save ten "
                "ringgit every month and keep my savings in a jar. Your cousin, "
                "Lin.",
                recipient="cousin@email.com", subject="Why Saving Money Matters",
                word_count="60 - 80 words"),
            _writing_entry(
                "You saw an accident on the road. Write an email to your "
                "friend to tell him or her what happened and how people "
                "helped.",
                ["what the accident was", "who came to help",
                 "what the helpers did", "what you learned about safety"],
                10, 15,
                "Dear Siva, On my way home I saw an accident at a busy road. A "
                "car knocked down a bicycle. A man called 999 at once. Soon an "
                "ambulance and a police car arrived. The paramedics carried the "
                "boy to the hospital. The police directed the traffic. I "
                "learned that we must always be careful on the road. Your "
                "friend, Amy.",
                recipient="siva@email.com", subject="An Accident on the Road",
                theme="It's an Emergency", word_count="60 - 80 words"),
            _writing_entry(
                "Your class visited a museum about life in the past. Write an "
                "email to your friend about what you saw and learned.",
                ["where you went", "what you saw there",
                 "how people lived long ago", "why the visit was interesting"],
                10, 15,
                "Dear Hana, Last Friday my class visited the National Museum. We saw "
                "old tools, wooden houses and ancient coins. Long ago, people cooked "
                "on a fire and wrote with a feather. They had no phones or cars. They "
                "walked or used a horse. The visit was interesting because I learned "
                "how life has changed. I also saw a model of a village house with a "
                "grass roof. Your friend, Dan.",
                recipient="hana@email.com", subject="Our Museum Visit",
                theme="Life in the Past", word_count="60 - 80 words"),
            _writing_entry(
                "You went camping with your family during the holidays. Write "
                "an email to your friend about your adventure.",
                ["where you camped", "what you did",
                 "something exciting that happened", "how you felt"],
                10, 15,
                "Dear Rani, Last month my family and I went camping by a "
                "waterfall. We put up a tent and cooked dinner over a small "
                "fire. At night we heard strange sounds in the jungle. In the "
                "morning we climbed to the top of the waterfall. The view was "
                "amazing. I felt brave and happy. You must come with us next "
                "time. Your friend, Faiz.",
                recipient="rani@email.com", subject="My Camping Adventure",
                theme="Adventure Time", word_count="60 - 80 words"),
            _writing_entry(
                "You travelled to Penang using different types of transport. "
                "Write an email to your friend about your journey.",
                ["where you went", "what transport you used",
                 "what you saw on the way", "which transport you liked best"],
                10, 15,
                "Dear Ling, During the holidays I went to Penang with my "
                "family. We took a bus to the station and then a train to "
                "Butterworth. After that we crossed the sea by ferry. From the "
                "ferry I saw the Penang Bridge. In the town we rode a trishaw. "
                "I liked the ferry best because the sea breeze was cool. Your "
                "friend, Arif.",
                recipient="ling@email.com", subject="My Journey to Penang",
                theme="Getting Around", word_count="60 - 80 words"),
            _writing_entry(
                "Your class visited a bread factory. Write an email to your "
                "friend to explain how bread is made.",
                ["what you saw at the factory", "what materials are used",
                 "the steps of making bread", "why the visit was useful"],
                10, 15,
                "Dear Kavya, Last week my class visited a bread factory. We "
                "saw big machines everywhere. The workers mixed flour, water, "
                "salt and yeast to make dough. The dough rested for a while "
                "and then machines shaped it into loaves. The loaves were baked "
                "in a huge oven. Finally they were packed into plastic bags. "
                "The visit was useful because now I know how bread is made. "
                "Your friend, Tim.",
                recipient="kavya@email.com", subject="How Bread Is Made",
                theme="How Is It Made?", word_count="60 - 80 words"),
            _writing_entry(
                "Your school held a concert. Write an email to your friend "
                "about the concert and your favourite song.",
                ["when the concert was", "who performed",
                 "which song you liked best", "how the audience felt"],
                10, 15,
                "Dear Sofia, Our school held a concert last Saturday. The choir sang "
                "first, then the school band played. My favourite song was 'Rasa "
                "Sayang' because the melody is cheerful. The drummers played loudly "
                "and everyone clapped. Some pupils danced on the stage. At the end we "
                "all sang together. The audience felt very happy. I hope we have "
                "another concert next year. Your friend, Adam.",
                recipient="sofia@email.com", subject="Our School Concert",
                theme="Music and Song", word_count="60 - 80 words"),
            _writing_entry(
                "You read a legend from Malaysia. Write an email to your "
                "friend to tell him or her the story.",
                ["the name of the legend", "where the story happens",
                 "what happens in the story", "the lesson of the story"],
                10, 15,
                "Dear Nadia, I read a legend called 'The Mouse Deer and the "
                "Crocodile'. It happens by a river in the jungle. The clever "
                "mouse deer tricks a crocodile to cross the river safely. The "
                "crocodile is angry but the mouse deer escapes. I like this "
                "story because it shows that we can solve problems with a "
                "clever mind. You should read it too. Your friend, Jun.",
                recipient="nadia@email.com", subject="A Malaysian Legend",
                theme="Tell Me a Story", word_count="60 - 80 words"),
            _writing_entry(
                "Something mysterious happened at your house. Write an email "
                "to your friend to tell him or her how you solved the mystery.",
                ["what went missing or changed", "what clues you found",
                 "who helped you", "how the mystery ended"],
                10, 15,
                "Dear Priya, Something mysterious happened at my house. My homework "
                "disappeared from my desk. I looked for clues and found small paw "
                "prints on the floor. My little brother said he saw the cat near my "
                "room. We followed the prints under the sofa and found my homework "
                "there. The mystery was solved and we laughed. My brother is now "
                "careful with his door. Your friend, Kevin.",
                recipient="priya@email.com", subject="The Missing Homework",
                theme="It's a Mystery!", word_count="60 - 80 words"),
            _writing_entry(
                "A guest speaker came to your school and talked about cool "
                "jobs. Based on the information below, write an email to your "
                "cousin about the job you want to do in the future.",
                ["the job you want to do", "why the job is interesting",
                 "the skills the job needs", "how you will prepare for it"],
                10, 15,
                "Dear cousin, A guest speaker told us about many cool jobs "
                "last Monday. I want to become an animator because I love "
                "drawing cartoons. An animator needs patience, creativity and "
                "practice every day. I plan to join the school art club and "
                "learn to draw on a tablet. I hope my dream job comes true one "
                "day. Your cousin, Lina.",
                recipient="cousin@email.com", subject="My Dream Job",
                theme="Cool Jobs", word_count="60 - 80 words"),
            _writing_entry(
                "Your class discussed whether pupils should bring mobile "
                "phones to school. Based on the information below, write an "
                "email to your friend and give your opinion.",
                ["the discussion topic", "whether you agree or disagree",
                 "two reasons for your opinion", "your conclusion"],
                10, 15,
                "Dear Mei, Our class discussed whether pupils should bring mobile "
                "phones to school. I agree that we may bring them, but only for "
                "safety. My mother can call me when school ends. I disagree with "
                "using them during lessons because it is distracting. I think phones "
                "should stay in our bags. What is your opinion? Please write back and "
                "tell me what you think. Your friend, Adib.",
                recipient="mei@email.com", subject="Phones in School",
                theme="What's Your Opinion?", word_count="60 - 80 words"),
        ],
    },
}



# style "paragraph" (Part 7, lower years)


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Round 11/F27: year/CEFR gate for web reading passages (Part 3).  A passage is
# blocked when it is on the content blocklist, exceeds the year's band ceiling
# (A1/A2/B1 via ``PROFICIENT_TOKENS`` count) or its word-count ceiling.
# ---------------------------------------------------------------------------

_BAND_RANK = {"a1": 0, "a2": 1, "b1": 2}


def passage_band(text: str) -> str:
    """Rank a reading text as ``"a1"`` / ``"a2"`` / ``"b1"`` by its load of
    proficient (B1/B2+) tokens: 0 distinct hits => A1, 1-2 => A2, >=3 => B1."""
    toks = re.findall(r"[a-z']+", str(text).lower())
    hits = len({t for t in toks if t in D.PROFICIENT_TOKENS})
    return "b1" if hits >= 3 else ("a2" if hits >= 1 else "a1")


def _passage_blocked(text: str) -> bool:
    low = str(text).lower()
    return any(s in low for s in D.BLOCKED_SUBSTRINGS)


def _web_comprehension(passages: list[dict], rng, difficulty: str = "medium",
                       theme: str = "", count: int = 5,
                       year: int | None = None
                       ) -> tuple[str, list[dict], dict]:
    """Pick a web passage that can supply exactly ``count`` questions.

    ``count`` is the official Part 3 size (5 questions / 5 marks).  Only a
    passage with at least ``count`` question templates is eligible; the caller
    falls back to the built-in comprehension pool when none qualifies (e.g. a
    stale cache), so a paper part is never left short.

    ``year`` applies the CEFR band + word ceiling + content blocklist (Round
    11/F27), so a Victorian Aesop chunk can never surface in a lower year, and
    the KSSR vocabulary gate (Round 26), so web prose is only used when the
    words it tests are on the DSKP ladder for the year.

    The third value is the chosen block's own ``title`` and ``theme``, so a
    per-paper JSU can name the passage that was actually printed instead of
    filing Part 3 under the week's theme.
    """
    from . import webfetch as WF
    if year is not None and passages:
        passages = WF.passages_for_year({year: passages}, year, count)
    pool = [p for p in passages
            if isinstance(p, dict)
            and p.get("qs") and len(p.get("qs", [])) >= count]
    if not pool:
        return None, None, {}
    diff = str(difficulty)
    year_banded = year in D.PASSAGE_CEFR
    if year_banded:
        # Apply the CEFR band + word ceiling + blocklist FIRST, then split
        # easy/hard within the band (Round 12/J: the old absolute windows made
        # 'hard' impossible for years 1-3, whose ceilings sit below 150 words).
        ceil = D.PASSAGE_WORD_CEIL[year]
        top = _BAND_RANK[D.PASSAGE_CEFR[year]]
        pool = [p for p in pool
                if len(str(p.get("text", "")).split()) <= ceil
                and not _passage_blocked(str(p.get("text", "")))
                and _BAND_RANK[passage_band(str(p.get("text", "")))] <= top]
        # Round 25: the criteria cap Part 3 at 150 words, so prefer a passage
        # that already sits in the year's band and only fall back to a longer
        # one when the source has nothing shorter.
        lo_w, hi_w = D.PASSAGE_WORD_BAND.get(year, (0, ceil))
        in_band = [p for p in pool
                   if lo_w <= len(str(p.get("text", "")).split()) <= hi_w]
        if in_band:
            pool = in_band
        if not pool:
            return None, None, {}
        if diff != "medium" and len(pool) >= 4:
            lens = sorted(len(str(p.get("text", "")).split()) for p in pool)
            lo_q, hi_q = lens[len(lens) // 4], lens[3 * len(lens) // 4]
            if diff == "easy":
                banded = [p for p in pool
                          if len(str(p.get("text", "")).split()) <= lo_q]
            else:
                banded = [p for p in pool
                          if len(str(p.get("text", "")).split()) >= hi_q]
            if banded:
                pool = banded
    else:
        if diff == "easy":
            pool = [p for p in pool if len(str(p.get("text", "")).split()) < 110]
        elif diff == "hard":
            pool = [p for p in pool if len(str(p.get("text", "")).split()) > 150]
    if not pool:
        return None, None, {}
    kws = _theme_kws(theme)
    if kws:
        matched = [p for p in pool if any(k in str(p.get("text", "")).lower()
                                          for k in kws)]
        if matched:
            pool = matched
    block = rng.choice(pool)
    qs = [q for q in block["qs"] if not _stem_leaks(q)]   # Round 12/S9
    rng.shuffle(qs)
    meta = {"title": str(block.get("title") or ""),
            "theme": str(block.get("theme") or ""),
            "cefr": str(block.get("cefr") or ""),
            "source": str(block.get("source") or "")}
    return block["text"], qs[:count], meta


# ---------------------------------------------------------------------------
# Round 17 — the textbooks are the SOLE reference
#
# A mined ``textbook_corpus.json`` (exam_gen/textbook.py) drives every
# question: the year's clean sentences are re-scaffolded into Part 1-5 MCQs /
# words and Part 6-7 prompts with the exact same noun-class technique webfetch
# uses.  Wherever clean textbook content is missing, the current built-in pool
# is the spare wheel (a paper part is never short or off-format).
#
# Round 18 — a sentence is only a question source when it is genuinely a clean
# complete sentence: an ASCII capital start, a finite verb, no OCR debris, and
# inside the year's band/ceiling gates.  Fragments that slip out of a scanned
# kid's-book OCR (front-matter blurbs, "(a)" option stubs, mid-clause column
# bleed like "s of people …", "1 have dinner …", "I''m a white …") are REJECTED
# at mining time *and* again at generation time, so even a stale pre-Round-18
# corpus can never pollute a paper; the curated built-in pools back the part
# up instead (the Round 17 "clean pools are the spare wheel" contract).
# ---------------------------------------------------------------------------

_FINITE_VERBS = frozenset("""
am is are was were be been being has have had do does did
can could will would shall should may might must
get gets getting got gotten go goes going went gone
come comes coming came look looks looking looked see sees seeing saw seen
tell tells telling told say says saying said like likes liking liked
want wants wanting wanted love loves loved play plays playing played
sing sings singing sang eat eats eating ate drink drinks drinking drank
run runs running ran walk walks walking walked write writes writing wrote
read reads reading takes take taking took takes made make makes making
find finds finding found give gives giving gave put puts washing wash washes
feel feels feeling felt visit visits visiting live lives living work works
help helps helping grow grows growing sleep sleeps sleeping wake wakes woke
ride rides riding ride fly flies flying swim swims swimming draw draws drawing
jump jumps jumping climb climbs climbing drive drives driving sit sits sitting
stand stands standing cook cooks cooking bath bathes bathe use uses using used
move moves moving carry carries carrying hold holds holding open opens opening
close closes closing watch watches watching see sees seeing thank thanks helping
""".split())

# OCR debris that never appears inside a clean pupil's sentence: underline
# fillers, ellipses, doubled quotes/commas, brackets, pipes, colons/equals,
# dashes, arrows, carets, page-break sweeps, stray backslashes and unbalanced
# dialog quotes (OCR splits "Why …?" into "Why …" "apostrophe slur).  Quoted
# dialog is dropped whole — the artifact rate is not worth the content.
_OCR_NOISE = re.compile(
    r"…|\.{3,}|_{2,}|'{2,}|``|,{2,}|[{}\[\]()]|\||[:=]|--|->|\u2014|[~^\\\"]|\w\s+/\s+\w"
    r"|alot|doesmt|doesnt|dossent|donesn|,\s*['\"]|(?<=[a-z])[A-Z]{2,}"
    r"|&|\s-\s")

# The same debris, minus two things.  Minus the underline filler: generated
# MCQ stems legitimately carry one visible blank ("The ______ is on the bag.").
# Minus the typographic dash: a hand-authored stem may parenthesise the way the
# teacher's own papers do ("no one gives up—it's all about pulling together",
# UASA AKHIR T5&6 2025), and a mined dash is already rejected upstream by
# ``_OCR_NOISE`` in ``_sentence_admits`` before it can reach a stem.
_STEM_NOISE = re.compile(
    r"…|\.{3,}|'{2,}|``|,{2,}|[{}\[\]()]|\||[:=]|--|->|[~^\\\"]|\w\s+/\s+\w|&")

_LEAD_OCR = re.compile(r"^(?:[\W_]+|\d+\s*[:.)-]?\s*)*")

# contractions are normalised to their finite-verb form before the verb check
# ("I'm" -> "I am", "He's" -> "He is", "you've" -> "you have", "won't" -> "will not").
_CONTRACT_MAP = {"'m": " am", "'s": " is", "'re": " are", "'ve": " have",
                 "'ll": " will", "'d": " would", "n't": " not",
                 "can't": " cannot", "won't": " will not"}


def _decontract(text: str) -> str:
    low = (text or "").lower()
    for k, v in _CONTRACT_MAP.items():
        low = low.replace(k, v)
    return low


def _sentence_admits(s, year: int | None) -> bool:
    """True when ``s`` is a clean, complete sentence usable as a question
    source for ``year``.

    Conservative by design — reject, never repair: OCR fragments (front
    matter, exercise-option stubs, mid-clause bleed, lowercase / digit leads)
    must be dropped so the curated built-in pool backs the part up.
    """
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = 1
    ceil = D.PASSAGE_WORD_CEIL.get(year, 150)
    stripped = _LEAD_OCR.sub("", (s or "").strip()).strip()
    if not stripped or not re.search(r"[.!?]\s*$", stripped):
        return False
    words = stripped.split()
    if len(words) > min(40, ceil):
        return False
    if re.search(r"\d", stripped):
        return False
    if _OCR_NOISE.search(stripped):
        return False
    # Round 19: a scanned line that has fused the tail of one sentence onto the
    # head of another reads "Name and Name (it|he|she|they|we)…" (e.g. the OCR
    # splice "One day, Norman and But it wasn't a monster.").  Legit name-and-
    # name compounds ("Tom and Jerry went to the shop.") survive because the
    # coordinator is followed by a real narrative clause, not a pronoun.
    if re.search(r"\b[A-Z][a-z]+ (?:and|but|or) [A-Z][a-z]+ "
                 r"(?:it|he|she|they|we|there)\b", stripped):
        return False
    lead = re.sub(r"^['\"]*\s*", "", words[0])
    if not lead or not lead[0].isupper():
        return False
    # a copula start ("Is sleeping on the tree.") with a following participial
    # verb is a subjectless fragment, not a question sentence
    if len(words) > 1 and words[0].lower() in ("is", "am", "are", "was", "were") \
            and re.match(r"^[a-z]+(ing|ed|en)\b", words[1].lower()):
        return False
    flat = re.findall(r"[a-z']+", _decontract(stripped))
    if not (4 <= len(flat) <= min(40, ceil)):
        return False
    if not (set(flat) & _FINITE_VERBS):
        return False
    top = _BAND_RANK[D.PASSAGE_CEFR.get(year, "b1")]
    if _BAND_RANK[passage_band(stripped)] > top or _passage_blocked(stripped):
        return False
    return True


def _stem_admits(text, year: int | None = None) -> bool:
    """True when a generated stem/line reads like a real question or clue.

    Gate on emission so no part can surface OCR shrapnel whatever its corpus
    provenance: no leading lowercase/digit, a single visible blank, and none of
    the OCR debris the sentence gate rejects.

    A stem may *begin* with the gap — "______ is one of the simplest foods to
    make" is the teacher's own form for a fact whose answer opens the
    sentence, and the KSSR sentences are written that way.  So the gap is
    stripped before the capital-letter check, not treated as the lead.
    """
    text = (text or "").strip()
    if not text:
        return False
    if re.search(r"'{2,}|``|…|\.{4,}", text) or _STEM_NOISE.search(text):
        return False
    if len(re.findall(r"_{2,}", text)) > 1:
        return False
    if not re.search(r"[.!?]\s*$", text):
        return False
    if re.match(r"^_{2,}", text):
        # The gap stands where the sentence-initial noun stood, so it was
        # capitalised in the passage and there is no word left to check.
        # The debris patterns above still apply.
        return True
    lead = re.sub(r"^['\"]*\s*", "", text.split()[0] if text.split() else "")
    return bool(lead) and lead[0].isupper()



def _tb_corpus(corpus, year):
    """The ``year`` entry of a textbook corpus (string/int key tolerant)."""
    if not corpus:
        return None
    return corpus.get(int(year)) or corpus.get(str(year))


def _tb_units(corpus, year, min_sents: int = 1) -> list[tuple[str, list[str]]]:
    """``(unit_title, admitted_sentences)`` per corpus unit, in OCR order.

    Round 19: unit boundaries are preserved so a coherent passage is only ever
    carved out of one unit — the old flat ``_tb_unit_sentences`` list let a
    cloze/comprehension block stitch together sentences from different
    exercises ("One day, Norman and But it wasn't a monster.").
    """
    ent = _tb_corpus(corpus, year)
    if not ent:
        return []
    year = int(year)
    groups: list[tuple[str, list[str]]] = []
    for u in ent.get("units") or []:
        sents: list[str] = []
        for s in u.get("sentences") or []:
            if _sentence_admits(s, year) and s not in sents:
                sents.append(s)
        if len(sents) >= max(1, int(min_sents)):
            groups.append((str(u.get("title") or ""), sents))
    top: list[str] = []
    for s in list(ent.get("sentences") or []):
        if _sentence_admits(s, year) and s not in top:
            top.append(s)
    if len(top) >= max(1, int(min_sents)):
        groups.append(("", top))
    return groups


def _tb_unit_sentences(corpus, year):
    """Every clean sentence of the year's textbook entry (units + top-level),
    flattened.  Round 19: groups stick to unit boundaries via ``_tb_units``.

    Round 18: re-runs the strict admission gate at generation time so a stale
    or hand-edited corpus can never feed OCR fragments to a question builder.
    """
    out: list[str] = []
    for _, sents in _tb_units(corpus, year):
        out.extend(sents)
    return out


def _tb_unit_words(corpus, year):
    """Every content word of the year's textbook entry that appears in an
    admitted sentence (Round 18: junk words from fragments are dropped)."""
    ent = _tb_corpus(corpus, year)
    if not ent:
        return []
    seen: set[str] = set()
    for s in _tb_unit_sentences(corpus, year):
        seen.update(re.findall(r"[a-z']+", s.lower()))
    out: list[str] = []
    for w in list(ent.get("words") or []):
        if w.lower() in seen and w not in out:
            out.append(w)
    for u in ent.get("units") or []:
        for w in u.get("words") or []:
            if w.lower() in seen and w not in out:
                out.append(w)
    return out


def _tb_fact_qs(corpus, year) -> list[dict]:
    """Raw MCQ templates from the year's clean textbook sentences.

    One question per fact sentence (a sentence that names a known noun), so
    every stem is answerable straight from the sentence and the distractors
    are same-class nouns absent from the sentence (webfetch guarantees this).
    Round 18: stems that still read as OCR shrapnel are skipped.
    """
    from . import webfetch as WF
    out: list[dict] = []
    seen: set[str] = set()
    for s in _tb_unit_sentences(corpus, year):
        for q in WF._fact_questions(s):
            if not _stem_admits(q["stem"], year):
                continue
            key = q["stem"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(q)
    return out


def _content_words(sentence: str) -> set[str]:
    """Lowercase content words of a sentence, minus the closed set.

    Contractions and number-words ("o'clock", "twenty") are dropped: they
    carry no topic, and letting them count as a repeated word would let two
    unrelated sentences look like one passage.
    """
    out = set()
    for w in re.findall(r"[a-z][a-z'\-]+", sentence.lower()):
        if len(w) < 3 or w in dskp_stopwords() or not w.isalpha():
            continue
        out.add(w)
    return out


def dskp_stopwords() -> frozenset:
    """Closed-class words that never signal that two sentences are about the
    same thing.  Cached because the register and linkage gates call it often."""
    global _STOP
    if _STOP is None:
        _STOP = frozenset("""
            a an the and or but so if then than that this these those there
            here is are was were be been being am do does did have has had
            he she it they we you i him her them us my your his its their our
            me him not no yes very too also just only some any all each every
            one two three four five six seven eight nine ten first next last
            in on at to from with by for of about into over under up down out
            off again before after while when where why how what who which
            because as until during between through across around behind
            can could will would shall should may might must
            get got go goes went come comes came make makes made take takes
            took put puts like likes want wants say says said tell tells told
            see sees saw look looks looked know knows knew think thinks
            little big small large young new old good bad happy sad
        """.split())
    return _STOP


_STOP: frozenset | None = None


def _tb_linked(sents: list[str]) -> bool:
    """True when a run of sentences is plausibly one text, not an OCR blend.

    The mined textbook is a flat bag of every line the scan produced, in page
    order across the whole book, so "adjacent" says nothing about "related".
    A genuine passage keeps a handful of nouns alive across its sentences
    ("flower" three times, "garden" twice); an accidental blend has almost no
    repeated content word at all, or repeats exactly one in a long run.

    Short runs are exempt: a workbook unit of three to six lines is a curated
    set about one thing ("The fish is in the water. The shark is scary. The
    crab hides under the rock."), and only a long run stitched out of a bag
    can be incoherent.  The rule is deliberately conservative — two different
    nouns must recur and a quarter of the sentences must carry one of them —
    and a run that fails is dropped rather than repaired, so the built-in pool
    supplies the passage.
    """
    sents = [s for s in (sents or []) if s and s.strip()]
    if len(sents) <= 6:
        return True
    counts: dict[str, int] = {}
    for s in sents:
        for w in _content_words(s):
            counts[w] = counts.get(w, 0) + 1
    repeated = {w for w, n in counts.items() if n >= 2}
    if len(repeated) < 2:
        return False
    carried = sum(1 for s in sents if _content_words(s) & repeated)
    return carried * 4 >= len(sents)


def passage_register(text: str) -> str:
    """``"narrative"`` or ``"expository"`` for a Part 3 reading passage.

    The official papers split cleanly: Years 1-3 read a short personal or
    school-day narrative, Years 5-6 read an informational piece about a
    place, a person in a job, or an event.  A first-person pronoun, a
    possessive, or quoted speech settles it as narrative; otherwise an
    expository cue (a third-person topic sentence, a date, a habit phrase)
    settles it as expository.
    """
    t = str(text or "")
    low = t.lower()
    if re.search(r"\b(i|we|my|our|us|me)\b", low) or re.search(r"[\"“]", t):
        return "narrative"
    if re.search(r"\b(long ago|in 1[89]\d\d|in 20\d\d|once upon a time"
                 r"|ten years ago|years ago)\b", low):
        return "expository"
    if re.search(r"\b(is one of|are one of|stands|stands|lives|was a|were a"
                 r"|is a|are a|belongs to|is found|is known|is the)\b", low):
        return "expository"
    if re.search(r"\bevery (morning|day|year|evening|friday|saturday"
                 r"|sunday|wednesday|thursday)\b", low):
        return "expository"
    return "narrative"


def _in_word_band(blocks: list[dict], year: int) -> list[dict]:
    """Blocks whose passage length sits inside the year's Part 3 band.

    The criteria cap Part 3 at 150 words and ask for a "very short" text at
    Year 1 rising to a "longer" one at Year 6, so the band is per-year rather
    than a single ceiling.  A pool with nothing in band is returned unchanged
    — the band narrows the choice, it never empties it.
    """
    lo, hi = D.PASSAGE_WORD_BAND.get(year, (0, 0))
    if not hi:
        return list(blocks or [])
    hit = [b for b in blocks or []
           if lo <= len(str(b.get("passage") or b.get("text") or "").split())
           <= hi]
    return hit


def _register_blocks(blocks: list[dict], want: str) -> list[dict]:
    """Blocks whose passage is the register the year is asked to read."""
    hit = [b for b in blocks
           if passage_register(str(b.get("passage") or b.get("text") or ""))
           == want]
    return hit or list(blocks or [])


def tb_comprehension_blocks(corpus, year) -> list[dict]:
    """Reading blocks in the web-passage shape ``{text, qs}`` --- every word
    from the textbook.  Feeds ``_web_comprehension`` so the year's CEFR band +
    word ceiling + blocklist gate still apply; the same gates are applied here
    too so the built-in-part fallback can never surface a dirty chunk.

    Round 18: passages are always rebuilt from the admission-gated sentences
    (a pre-Round-18 corpus's saved ``passages`` may carry OCR fragments), and
    each question stem is admission-checked as it is emitted.

    Round 19: passages are carved inside a single unit only — ``_tb_units``
    keeps each workbook exercise together, so a reading text can never blend
    sentences from two unrelated topics.

    Round 20: only declarative narrative lines may become a reading passage —
    the workbook's dialogues ("Did you see that documentary about eafing last
    night?"), worksheet instructions ("Read and listen to the text again.") and
    OCR scraps are filtered by ``_story_sentence`` before chunking — and a
    block never repeats the same answer (a teacher's passage asks once for
    "sugar", not three times)."""
    from . import webfetch as WF
    year = int(year)
    passages = []
    ceil = D.PASSAGE_WORD_CEIL.get(year, 150)
    for _, raw_sents in _tb_units(corpus, year):
        sents = [s for s in raw_sents if _story_sentence(s)]
        if not sents:
            continue
        cur, cur_w = [], 0
        for s in sents:
            w = len(s.split())
            if cur and cur_w + w > ceil:
                passages.append((" ".join(cur), list(cur)))
                cur, cur_w = [], 0
            cur.append(s)
            cur_w += w
            if cur_w >= min(ceil, 70):
                passages.append((" ".join(cur), list(cur)))
                cur, cur_w = [], 0
        if cur and cur_w >= 10:
            passages.append((" ".join(cur), list(cur)))
    top = _BAND_RANK[D.PASSAGE_CEFR.get(year, "b1")]
    ceil = D.PASSAGE_WORD_CEIL.get(year, 150)
    blocks = []
    for text, sents in passages:
        if _BAND_RANK[passage_band(text)] > top \
                or len(str(text).split()) > ceil \
                or _passage_blocked(text) \
                or not _tb_linked(sents):
            continue
        qs = [q for q in WF._fact_questions(text)
              if not _stem_leaks(q) and _stem_admits(q["stem"], year)]
        qs = [q for q in _no_repeated_answers(qs)]
        if qs:
            blocks.append({"text": text, "qs": qs})
    return blocks


def _no_repeated_answers(qs):
    """Drop questions whose answer was already used earlier in the same block —
    a passage that asks for "sugar" three times is not a teacher's passage."""
    seen = set()
    out = []
    for q in qs:
        a = str(q.get("ans_text") or q.get("opts", [""])[q.get("ans", 0)])
        a = re.sub(r"\W+", "", a).casefold()
        if not a or a in seen:
            continue
        seen.add(a)
        out.append(q)
    return out


def _blank_word(s: str, w: str) -> str:
    """Replace every occurrence of the word ``w`` in ``s`` with a blank."""
    return re.sub(r"\b" + re.escape(w) + r"\b", "__________", s, flags=re.I)


def tb_vocab_items(corpus, year) -> list[dict]:
    """Part 1 short-text MCQs, one per clean textbook fact sentence.

    Round 19: an OCR sentence only becomes a Part 1 question when it survives
    the fact pipeline AND its blank is pinned by a collocate that appears in
    its own stem ("Bactrian camel", "fires engine") — otherwise the context is
    ambiguous ("I live in a big ______.") and the built-in pool must answer.
    """
    return [q for q in _tb_fact_qs(corpus, year)
            if _good_vocab_q(q, year)]


def _good_vocab_q(q, year) -> bool:
    """True when the raw MCQ's stem already contains a collocate that pins the
    blanked noun, so exactly one correct answer is visible from the text."""
    tgt = str(q.get("ans_text") or q["opts"][q["ans"]]).lower().strip(".")
    cues = _COLLOCUTES.get(tgt)
    if not cues:
        return False
    stem_toks = set(re.findall(r"[a-z']+",
                               re.sub(r"_+", " ", str(q.get("stem", ""))).lower()))
    return bool(stem_toks & cues)


def _clean_options(raw) -> bool:
    """True when no option reproduces a word already in the stem (a "rain"
    option next to "Rain clouds gathered …" is an unanswerable learner trap)."""
    stem_toks = set(re.findall(
        r"[a-z']+", re.sub(r"_+", " ", str(raw.get("stem", ""))).lower()))
    for o in raw.get("opts") or []:
        for t in re.findall(r"[a-z']+", str(o).lower()):
            if t in stem_toks:
                return False
    return True


# ---------------------------------------------------------------------------
# Round 19 (F2): collocates that make a gap unambiguous.
# ---------------------------------------------------------------------------

_COLLOCUTES: dict[str, set[str]] = {
    "camel": {"bactrian", "desert", "hump"},
    "engine": {"fire", "train"},
    "fireman": {"hose", "fire"},
    "firefighter": {"hose", "fire", "station"},
    "hunter": {"spear", "forest", "wild"},
    "farmer": {"field", "crop", "farm", "padi", "rice"},
    "cow": {"milk", "field", "farm"},
    "hen": {"nest", "egg", "coop"},
    "fish": {"water", "pond", "sea", "swim"},
    "shark": {"ocean", "sea", "sharp"},
    "monster": {"scary", "jungle"},
    "monkey": {"jungle", "climb", "banana"},
    "tiger": {"stripes", "jungle", "forest"},
    "snake": {"jungle", "grass", "poison"},
    "lion": {"jungle", "king"},
    "elephant": {"trunk", "jungle"},
    "parrot": {"talk", "bird"},
    "cheese": {"mouse", "burger"},
    "honey": {"bee", "sweet"},
    "milk": {"cow", "cereal", "glass"},
    "bread": {"toast", "baker", "loaf"},
    "egg": {"hen", "breakfast"},
    "porridge": {"oat", "breakfast"},
    "water": {"drink", "pond", "well"},
    "sugar": {"sweet", "tea", "coffee"},
    "teacher": {"classroom", "lesson", "class", "school", "board"},
    "doctor": {"patient", "clinic", "medicine", "hospital"},
    "dentist": {"tooth", "teeth"},
    "pilot": {"plane", "airport", "fly"},
    "nurse": {"patient", "clinic"},
    "pupil": {"classroom", "school"},
    "clerk": {"office"},
    "king": {"crown", "castle", "throne"},
    "queen": {"crown", "castle"},
    "princess": {"castle", "crown"},
    "house": {"roof", "door"},
    "road": {"traffic", "sign"},
    "library": {"book", "read"},
    "market": {"buy", "sell"},
    "farm": {"animal", "cow", "field"},
    "forest": {"tree", "animal"},
    "village": {"kampung", "small"},
    "river": {"boat", "bridge", "flow"},
    "mountain": {"climb", "high"},
    "garden": {"flower", "plant"},
    "park": {"swing", "tree"},
    "school": {"classroom", "lesson", "bell"},
    "ball": {"kick", "throw", "play"},
    "bicycle": {"ride", "cycle"},
    "uniform": {"school", "wear"},
    "station": {"train", "bus"},
    "bridge": {"river", "cross"},
    "stamp": {"post", "letter"},
    "letter": {"post", "write"},
    "pencil": {"case", "write"},
    "camp": {"tent", "fire"},
    "cake": {"bake", "birthday"},
    "flower": {"garden", "plant", "smell"},
}


def _tb_cloze_block(group: list[dict], mode: str = "") -> dict | None:
    """One 4-gap cloze passage from 4 fact questions (years 1/2/6 fallback).

    The passage shows the sentences gapped as ``(6)______``; each gap item is
    the same sentence with a full blank.  Distractors are same-class nouns
    absent from the whole gapped passage, and options are rebuilt if a
    distractor collides with another sentence of the block.
    """
    from . import webfetch as WF
    if len(group) != 4:
        return None
    passage_sents, gaps = [], []
    for n, q in zip((6, 7, 8, 9), group):
        passage_sents.append(re.sub(r"_+", f"({n})______", q["stem"]))
    passage = " ".join(passage_sents)
    low = passage.lower()
    for q in group:
        target = q.get("ans_text") or q["opts"][q["ans"]]
        cls = q.get("cls")
        distractors = [w for w in WF.NOUNS.get(cls, [])
                       if w != target and w not in low
                       and not re.search(r"\b" + re.escape(w) + r"\b", low)]
        if len(distractors) < 2:
            continue
        gaps.append({
            "stem": re.sub(r"_+", "__________", q["stem"]),
            "opts": [str(target)] + distractors[:2],
            "ans": 0,
            "ans_text": str(target),
        })
    if len(gaps) < 4:
        return None
    return {"passage": passage, "gaps": gaps, "mode": mode}


def tb_cloze_blocks(corpus, year) -> list[dict]:
    """Cloze blocks (Part 2) carved out of the year's clean sentences.

    Round 19: passages never stitch across units — ``_tb_units`` preserves the
    workbook's own boundaries.  Years 3/5 prefer a present-tense verb-form
    cloze (drink / drinks / drinking) carved from a coherent run; years 1/2/6
    fall back to the same-unit fact-stitched blocks, and a year with nothing
    clean returns ``[]`` so the curated built-in pools answer instead.
    """
    year = int(year)
    from . import webfetch as WF
    if year >= 6:
        # Year 6 uses the teacher's same-category format inside ONE coherent
        # paragraph; the workbook corpus is a mix of drills, questions and
        # comprehension stories that do not stitch into such a paragraph, so
        # the curated CLOZE_SEM blocks answer and the corpus keeps feeding
        # comprehension / match / words / vocab instead.
        return []
    if year in (3, 5):
        blocks = []
        for _, sents in _tb_units(corpus, year):
            b = _verb_cloze_block([s for s in sents if _story_sentence(s)])
            if b:
                blocks.append(b)
        return blocks

    seen_units: set[str] = set()
    blocks = []
    for title, sents in _tb_units(corpus, year):
        key = " ".join(sents).casefold()
        if key in seen_units:
            continue
        seen_units.add(key)
        facts: list[dict] = []
        seen_ans: set[str] = set()
        for s in sents:
            if not _story_sentence(s):
                continue
            for q in WF._fact_questions(s):
                if not _stem_admits(q["stem"], year):
                    continue
                ans = str(q.get("ans_text") or q["opts"][q["ans"]]).lower()
                if ans in seen_ans:
                    continue
                seen_ans.add(ans)
                facts.append(q)
        for start in range(0, max(0, len(facts) - 3), 4):
            block = _tb_cloze_block(facts[start:start + 4],
                                    mode="sem" if year >= 6 else "")
            if block:
                blocks.append(block)
    return blocks


def _s_form(v: str) -> str:
    """3rd-person singular present of a simple verb (carry -> carries)."""
    if v.endswith(("s", "x", "z", "ch", "sh", "o")):
        return v + "es"
    if len(v) > 1 and v.endswith("y") and v[-2] not in "aeiou":
        return v[:-1] + "ies"
    return v + "s"


def _story_sentence(s: str) -> bool:
    """True when ``s`` is a declarative narrative line (not a worksheet drill):
    no question/exclamation, and no teacher-question lead ("What is …?",
    "Do you …?").  Cloze passages must read like the teacher's paragraphs, not
    like the workbook's exercise instructions ("Then read the text and check
    your idea.")."""
    s = (s or "").strip()
    if not s or "?" in s or "!" in s:
        return False
    first = re.match(r"[a-z']+", s.lower())
    if not first:
        return False
    return first.group() not in {
        "what", "where", "when", "why", "who", "whose", "how", "which",
        "do", "does", "did", "is", "are", "was", "were", "should", "would",
        "can", "could", "will", "shall", "may", "might", "must", "let",
        "then", "now", "look", "read", "check", "write", "draw", "listen",
        "match", "colour", "color", "answer", "complete", "fill", "copy",
    }


def _ing_form(v: str) -> str:
    """-ing form of a simple verb (ride -> riding, run -> running)."""
    if v.endswith("ie"):
        return v[:-2] + "ying"
    if v.endswith("e") and len(v) > 1:
        return v[:-1] + "ing"
    if (len(v) >= 3 and v[-1] not in "wxy"
            and re.match(r"[bcdfghjklmnpqrstvwxyz][aeiou][bcdfghjklmnpqrstvwxyz]$",
                         v)):
        return v + v[-1] + "ing"
    return v + "ing"


# Present-tense verbs the Y3/5 verb-form cloze may blank; (base) -> (s, ing).
_VERB_BASES = ("drink eat pack walk watch help smile wave take give make cook "
               "bake wash pick carry study tidy visit work clean feed play "
               "paint draw sing dance write read run swim ride wait listen "
               "talk stand sit open close laugh jump count fix shop pour mix "
               "add stir sell buy build learn like love want need look see "
               "grow plant climb shout call wear save keep know stop start "
               "become stay arrive ask answer live hurry agree share")
_VERB_OVERRIDE = {"have": "has", "do": "does", "go": "goes", "say": "says"}


def _verb_forms() -> tuple[dict, dict]:
    froms: dict[str, tuple[str, str]] = {}
    lookup: dict[str, str] = {}
    for base in _VERB_BASES.split():
        sv = _VERB_OVERRIDE.get(base, _s_form(base))
        ing = _ing_form(base)
        froms[base] = (sv, ing)
        lookup[base] = lookup[sv] = lookup[ing] = base
    return froms, lookup


def _verb_hit(sentence: str):
    """``(observed, base, s, ing, token_index)`` for a blankable verb or None."""
    froms, lookup = _verb_forms()
    toks = re.findall(r"[A-Za-z']+", sentence)
    for i, t in enumerate(toks):
        if i == 0 or (len(t) > 1 and t[0].isupper()):
            continue
        base = lookup.get(t.strip("'\"").lower())
        if not base or base not in froms:
            continue
        sv, ing = froms[base]
        return (t.lower(), base, sv, ing, i)
    return None


def _verb_cloze_block(sents: list[str]) -> dict | None:
    """One verb-form cloze block from a contiguous run of a single unit.

    Four consecutive sentences that each carry a blankable present-tense verb
    become the (6)-(9) gaps; every gap offers the base / 3rd-person / -ing
    triplet of the SAME verb, with the answer set to the form the original
    text used.  A verb already blanked, or an option word that shows up
    elsewhere in the passage, disqualifies that gap.
    """
    hits = [(s, _verb_hit(s)) for s in sents]
    best: list = []
    cur: list = []
    for s, h in hits:
        if h:
            cur.append((s, h))
        else:
            if len(cur) > len(best):
                best = cur
            cur = []
    if len(cur) > len(best):
        best = cur
    if len(best) < 4:
        return None

    four: list = []
    used_bases: set[str] = set()
    for s, h in best:
        if h and h[1] not in used_bases:
            four.append((s, h))
            used_bases.add(h[1])
        if len(four) == 4:
            break
    if len(four) < 4:
        return None

    passage_sents, gaps = [], []
    for n, (sentence, hit) in zip((6, 7, 8, 9), four):
        observed, base, sv, ing, i = hit
        opts = [base, sv, ing]
        passage_sents.append(_replace_token(sentence, i, f"({n})______"))
        gaps.append({
            "stem": _replace_token(sentence, i, "__________"),
            "opts": [base, sv, ing],
            "ans": opts.index(observed),
            "ans_text": observed,
        })
    passage = " ".join(passage_sents)
    low = set(re.findall(r"[a-z']+", passage.lower()))
    kept = []
    for gap in gaps:
        forme = {str(o).lower() for o in gap["opts"]}
        others = low - forme
        base, sv, ing = (str(o).lower() for o in gap["opts"])
        if base in others or sv in others or ing in others:
            continue
        kept.append(gap)
    if len(kept) < 4:
        return None
    return {"passage": passage, "gaps": kept, "mode": "verb"}


def _replace_token(sentence: str, idx: int, repl: str) -> str:
    """Replace the ``idx``-th alphabetic token of ``sentence`` with ``repl``."""
    toks = re.split(r"([A-Za-z']+)", sentence)
    seen = 0
    for i, t in enumerate(toks):
        if re.search(r"^[A-Za-z']+$", t):
            if seen == idx:
                toks[i] = repl
                break
            seen += 1
    return "".join(toks)


def _tb_word_usage(corpus, year) -> dict[str, str]:
    """``{noun: clean usage sentence}`` for known nouns in the year's text."""
    from . import webfetch as WF
    nouns = set(WF.ALL_NOUNS)
    usage: dict[str, str] = {}
    for s in _tb_unit_sentences(corpus, year):
        low = s.lower()
        for tok in re.findall(r"[a-z']+", low):
            w = tok.strip("'")
            if w in nouns and w not in usage:
                usage[w] = s
    return usage


def tb_words_choice_blocks(corpus, year) -> list[dict]:
    """Part 5 word-box blocks: the unit's picture nouns + blanked clue items."""
    from . import webfetch as WF
    usage = _tb_word_usage(corpus, year)
    unit_words = [w for w in _tb_unit_words(corpus, year) if w in usage]
    items = []
    for w in unit_words:
        s = usage[w]
        stem = _blank_word(s, w)
        if "__________" not in stem:
            continue
        cls = next((c for c in WF.NOUNS if w in WF.NOUNS[c]), None)
        low = s.lower()
        distractors = [d for d in WF.NOUNS.get(cls, []) if d != w
                       and not re.search(r"\b" + re.escape(d) + r"\b", low)]
        if len(distractors) < 2:
            continue
        items.append(_rag(stem, [w] + distractors[:2], 0, ans_text=w))
    if len(items) < 5:
        return []
    box = [u for u in unit_words if u in {i.get("ans_text")
                                          for i in items}]
    return [{"box": box[:12], "items": items}]


def tb_letter_words(corpus, year) -> list[dict]:
    """Part 5 (upper) clue/word items, clue = the textbook usage sentence."""
    out = []
    for w, s in _tb_word_usage(corpus, year).items():
        clue = _blank_word(s, w)
        if "__________" not in clue:
            continue
        out.append({"clue": clue, "word": w})
    return out


_WH_WORD = {"people": "Who", "animals": "What", "food": "What",
            "places": "Where", "other": "What"}


def _tb_subject_noun(s: str):
    """(cls, noun, wh, verbphrase) when ``s`` starts with a known subject
    noun, else None.  Keeps subject Wh-questions grammatically sound: the
    verb phrase must actually contain a finite verb (so an OCR fragment like
    "The boy in the land." can never produce "Who in the land?")."""
    from . import webfetch as WF
    words = s.split()
    if not 3 <= len(words) <= 20:
        return None
    i = 1 if words[0].lower() in ("the", "a", "an") else 0
    if i >= len(words):
        return None
    subj = re.sub(r"[^a-z]", "", words[i].lower())
    for cls, ws in WF.NOUNS.items():
        if subj in ws:
            if cls == "places":
                continue            # needs inversion ("Where is X?")
            verb = " ".join(words[i + 1:]).rstrip(".!?")
            if not verb:
                continue
            vp_verbs = set(re.findall(r"[a-z']+", _decontract(verb)))
            if not (vp_verbs & _FINITE_VERBS):
                continue            # Round 18: a bare clause is not a question
            return cls, subj, _WH_WORD.get(cls, "What"), verb
    return None


def tb_match_blocks(corpus, year) -> list[dict]:
    """Part 4 matching: three texts of clean sentences, subject who/what
    questions against them.  People first (natural 'Who…?' items), then food,
    then animals; distinct subjects only."""
    cands, seen_subj = [], set()
    prio = {"people": 0, "food": 1, "animals": 2, "other": 3}
    for s in _tb_unit_sentences(corpus, year):
        hit = _tb_subject_noun(s)
        if not hit:
            continue
        cls, subj, wh, verb = hit
        if subj in seen_subj:
            continue
        seen_subj.add(subj)
        cands.append((prio.get(cls, 3), s, wh, verb))
    cands.sort(key=lambda c: c[0])
    if len(cands) < 6:
        return []
    texts = ["", "", ""]
    qs = []
    for idx, (_prio, s, wh, verb) in enumerate(cands[:6]):
        ti = idx % 3
        texts[ti] += (" " if texts[ti] else "") + s
        qs.append(_rag(f"{wh} {verb}?", ["A", "B", "C"], ti))
    return [{"texts": [f"A. {texts[0]}", f"B. {texts[1]}", f"C. {texts[2]}"],
             "qs": qs}]


def tb_sentences(corpus, year) -> list[dict]:
    """Part 6 lower-year sentence prompts: unit noun + its model sentence."""
    out = []
    for w, s in _tb_word_usage(corpus, year).items():
        out.append({"words": [w], "model": s})
    return out


_TOPIC_STOP = re.compile(
    r"(?i)^(?:textbook|module|activity|unit|starter\s*unit|lesson|workbook|"
    r"student'?s?[- ]?book|pupil'?s?[- ]?book|exercise|worksheet)\b")

# Round 21: a unit title may describe a SKILL ("Read a newspaper article",
# "Reading skill: identify features…", "Talk about interrupted past actions
# with when") — never a topic a pupil could write an email about.  Only plain
# noun phrases may surface as a writing topic.
_WRITE_IMP = frozenset("""
read write listen look say learn identify match spell choose complete answer
fill ask understand talk study draw note retell repeat practise practice
discuss explain describe recognise recognize predict survey share order
""".split())


def valid_writing_topic(topic: str) -> bool:
    """Is ``topic`` a plain noun phrase a pupil can write an email about?

    A unit title like "Read A Newspaper Article" or "Understand Context From
    Audio Clues" is a *method label*, not a subject; rejecting it stops the
    unanswerable "your friend wants to know about <skill>" prompts.  This is
    also the QC rule: the watchdog re-checks any saved writing prompt.
    """
    t = (topic or "").strip()
    if not t:
        return False
    if re.search(r"[:;_./(&0-9]|—|–|skill|how to", t, re.I):
        return False
    words = t.split()
    if not words or len(words) > 6 or re.search(r"[’']", t):
        return False
    first = words[0].lower()
    if first.rstrip("s") in _WRITE_IMP:
        return False
    return True


_WRITE_WEAK = frozenset("""
some this that these those they them it its one two three get got can will
would could should may might must have has had from with into onto when then
there here is are was were be been being do does did time things people also
very really just more most new today now what where why how every each still
""".split())


def _writing_words(sents) -> list[str]:
    """Content words for a writing prompt — never "some" or a function word."""
    from . import textbook as TB
    return [w for w in TB.pick_words(sents)[:8]
            if len(w) >= 3 and w not in _WRITE_WEAK]


def tb_writing_entries(corpus, year, style: str, bucket: str) -> list[dict]:
    """Part 6-7 letter/email prompts anchored to the textbook units.

    The scaffold (salutation, closing, request) is the official form; every
    word of content — the topic, the words to use and the model paragraph —
    comes out of the textbook unit.  Round 18: units that are front-matter /
    whole-book OCR blobs (generic title, too few clean sentences) are skipped,
    so a prompt can never be "about Textbook"; when nothing is usable the
    built-in letter/email pool backs the part up.  Round 23: superseded for
    generation by ``REFERENCE_WRITING`` (the original exam papers); kept for
    its gating predicates.
    """
    ent = _tb_corpus(corpus, year)
    if not ent:
        return []
    long_ = bucket == "long"
    word_count = "60 - 80 words" if long_ else "30 - 50 words"
    lines = 8 if long_ else 6
    entries = []
    for u in (ent.get("units") or [])[:6]:
        sents = [s for s in (u.get("sentences") or [])
                 if _sentence_admits(s, year)]
        if len(sents) < 3:
            continue                       # junk / front-matter unit
        title = re.sub(r"(?i)^unit\s*\d+\s*[-:.]?\s*", "",
                       u.get("title") or "").strip()
        if not title or _TOPIC_STOP.match(title):
            continue                       # generic OCR title -> built-in pool
        topic = title.title() or "your lesson"
        if not valid_writing_topic(topic):
            continue   # a skill/method label, not a writable subject
        nouns = _writing_words(sents)
        model = (" ".join(sents[:3]))[:150]
        combined = ", ".join(nouns[:3])
        words_clause = f"Use the words: {combined}." if (
            len(nouns) >= 2) else ""
        ask = ("about it. Use the words: {c}" if words_clause
               else "about it.").format(c=combined)
        if style == "letter":
            entries.append(_writing_entry(
                f"Your friend wants to know about {topic}. Write a letter to "
                f"him or her {ask}",
                [f"what {topic.lower()} is about",
                 "what you like about it",
                 "what you do there",
                 "why your friend should try it"],
                lines, 10,
                f"Dear friend, I want to tell you about {topic}. {model} "
                f"Please write back soon. Your friend, Wei.",
                salutation="Dear friend,", closing="Your friend,",
                word_count=word_count))
        else:
            entries.append(_writing_entry(
                f"Your friend wants to know about {topic}. Write an email to "
                f"him or her {ask}",
                [f"what {topic.lower()} is about",
                 "what you like about it",
                 "what you do there",
                 "why your friend should try it"],
                lines, 10,
                f"Dear friend, I want to tell you about {topic}. {model} "
                f"Your friend, Mei.",
                recipient="friend@email.com",
                subject=topic, word_count=word_count))
    return entries


# ---------------------------------------------------------------------------
# Round 23: Part 6/7 writing mirrors the ORIGINAL exam papers.
#
# Every entry below is the actual task from a teacher/official paper (UPSA
# Pertengahan Tahun T6 2026, UASA AKHIR T5&6 2025, UJIAN PERTENGAHAN Y5,
# UPSA Year 3).  Generation prefers these verbatim so a pupil is never asked
# to write "about Read a Newspaper Article" or to "use the words: singing,
# working, some".  ``years`` scopes the task; ``style``/``bucket`` map onto
# the part (letter = short, email: id 6 short / id 7 long).
# ---------------------------------------------------------------------------

REFERENCE_WRITING = [
    # ---- UPSA Pertengahan Tahun T6 2026, Part 6 (letter, 30-50) ----------
    _writing_entry(
        "You want to share a song you like with your friend. Write a letter "
        "to your friend, Fiona and tell her about your favourite song.",
        ["Lyrics - the lyric is touching/happy/sad",
         "Rhythms - fun/pop/modern/old",
         "Meaning - friends/family/love"],
        8, 10,
        "Dear Fiona, I want to share my favourite song with you. Its lyrics "
        "are touching and the rhythm is fun. The song is about friends and "
        "family. I think you will love it too. Please listen to it tonight. "
        "Your friend, Wei.",
        salutation="Dear Fiona,", closing="Your friend,",
        style="letter", bucket="short", years=(6,),
        theme="Music and Song", word_count="30 - 50 words",
        ref=True),
    # ---- UPSA Pertengahan Tahun T6 2026, Part 7 (email, 60-80) -----------
    _writing_entry(
        "You are making chicken salad at school. Based on the information "
        "below, write an email to tell your friend about it. Tell your "
        "friend why it is important to eat a healthy diet.",
        ["cook and shred the chicken breast",
         "chop the vegetables and fruits",
         "combine all the ingredients in a large bowl and whisk the salad "
         "dressing",
         "toss, chill and serve the chicken salad"],
        10, 15,
        "Dear Aina, I am making chicken salad at school today. First I cook "
        "and shred the chicken breast. Then I chop the vegetables and fruits. "
        "I put everything in a large bowl and whisk the dressing. A healthy "
        "diet gives us energy and keeps us strong, so salad is a great "
        "choice. Your friend, Ravi.",
        recipient="friend@email.com", subject="Making chicken salad",
        style="email", bucket="long", years=(6,),
        theme="Food and Health", word_count="60 - 80 words",
        ref=True),
    # ---- UASA AKHIR T5&6 2025, Part 6 (email, 30-50): learning English ---
    _writing_entry(
        "You saw a poster about the importance of learning English. Email "
        "your friend and tell them why it is important to learn English.",
        ["Make Friends: connect with people from diverse backgrounds and "
         "cultures",
         "Enjoy Media: understand movies, songs, and games",
         "School Help: makes reading and school projects easier",
         "Travel Easy: helps with signs and talking abroad"],
        8, 10,
        "Dear Jun, I saw a poster about learning English. It is important "
        "because it helps me make friends from other countries. I can enjoy "
        "movies and songs and it helps with reading at school. When I travel, "
        "I can read signs and talk to people. Your friend, Mei.",
        recipient="friend@email.com", subject="Learning English is important",
        style="email", bucket="short", years=(5,),
        theme="Learning World", word_count="30 - 50 words",
        ref=True),
    # ---- UASA AKHIR T5&6 2025, Part 7 (email, 60-80): food trip ----------
    _writing_entry(
        "Your friend in the USA wants to come to Malaysia. Write an email to "
        "tell him about the delicious food that he can eat here.",
        ["Nasi Lemak: fragrant rice cooked in coconut milk, served with "
         "spicy sambal and anchovies",
         "Roti Canai: flaky, crispy flatbread paired with curry or dhal",
         "Satay: grilled meat skewers served with a rich peanutty sauce",
         "Laksa: spicy noodle soup with a creamy coconut broth and herbs"],
        10, 15,
        "Dear Tom, I am so happy you are coming to Malaysia! You must try "
        "nasi lemak, the rice cooked in coconut milk with spicy sambal. "
        "Roti canai is a flaky flatbread with curry, and satay is grilled "
        "meat with tasty peanut sauce. Finish with a bowl of hot laksa. "
        "Every dish is a feast! Your friend, Hafiz.",
        recipient="friend@email.com", subject="Come for the food trip!",
        style="email", bucket="long", years=(5,),
        theme="Food and Health", word_count="60 - 80 words",
        ref=True),
    # ---- UASA AKHIR T5&6 2025, Part 6 (email, 30-50): how to make pasta --
    _writing_entry(
        "You want to teach your friend how to make pasta. Write an email to "
        "your friend and teach her the steps of making pasta.",
        ["Get ingredients: pasta, water, salt and sauce",
         "Boil the water until it bubbles",
         "Cook the pasta for 8 - 12 minutes",
         "Drain the pasta and add the sauce"],
        8, 10,
        "Dear Jean, I will teach you how to make pasta. First, get the "
        "ingredients: pasta, water, salt and sauce. Boil the water until it "
        "bubbles, then cook the pasta for about ten minutes. Finally drain "
        "it and add the sauce. It is easy and yummy! Your friend, Ali.",
        recipient="friend@email.com", subject="How to make pasta",
        style="email", bucket="short", years=(5, 6),
        theme="How Is It Made?", word_count="30 - 50 words",
        ref=True),
    # ---- UASA AKHIR T5&6 2025, Part 7 (email, 60-80): Kidzania -----------
    _writing_entry(
        "You saw a poster at school. Based on the information below, write "
        "an email to tell your friend about it.",
        ["Get tickets: buy online ahead of time",
         "Plan activities: check the map for 100+ jobs like pilot, chef, "
         "firefighter",
         "Earn KidZos: do jobs to get paid in fake money",
         "Spend KidZos: shop at stores, bank or mall inside"],
        10, 15,
        "Dear Siti, I saw a poster about Kidzania at school. It is a city "
        "for kids where you can do 100+ jobs like being a pilot or a "
        "firefighter. You earn fake money called KidZos and spend it at the "
        "shops or bank inside. We should book our tickets online and go "
        "together on Saturday! Your friend, Ben.",
        recipient="friend@email.com", subject="Let's go to Kidzania!",
        style="email", bucket="long", years=(5, 6),
        theme="Adventure Time", word_count="60 - 80 words",
        ref=True),
    # ---- UJIAN PERTENGAHAN Y5, Part 6 (email, 30-50): weird animals ------
    _writing_entry(
        "You saw a poster about protecting weird animals. Email your friend "
        "and explain why it is important to protect them.",
        ["weird animals are disappearing fast",
         "most people only protect cute animals",
         "we share the earth with all animals and plants"],
        8, 10,
        "Dear Kumar, I saw a poster about protecting weird animals. They are "
        "disappearing fast because most people only protect cute animals. "
        "But we share the earth with all animals and plants. Every animal "
        "has a job in nature, so we must protect them too. Your friend, "
        "Maya.",
        recipient="friend@email.com", subject="Protect weird animals too!",
        style="email", bucket="short", years=(5,),
        theme="Wild Life", word_count="30 - 50 words",
        ref=True),
    # ---- UJIAN PERTENGAHAN Y5, Part 7 (email, 60-80): places in Malaysia --
    _writing_entry(
        "Your friend in England wants to come to Malaysia. Write an email to "
        "tell him about the places that he can visit in Malaysia.",
        ["Kuala Lumpur: see the Petronas Towers and visit the night market",
         "Batu Caves: climb the steps to see the big temples",
         "KL Bird Park or Zoo Negara: meet Malaysian animals"],
        10, 15,
        "Dear Jack, I am so glad you are visiting Malaysia! In Kuala Lumpur "
        "you must see the Petronas Towers and visit the night market for "
        "nasi lemak. At Batu Caves you can climb the steps to the temples. "
        "Don't miss the KL Bird Park or Zoo Negara to see Malaysian animals. "
        "There is so much to explore! Your friend, Emma.",
        recipient="friend@email.com", subject="Welcome to Malaysia!",
        style="email", bucket="long", years=(5, 6),
        theme="Going Away", word_count="60 - 80 words",
        ref=True),
    # ---- UPSA Year 3, Part 6 (email, 30-50): a day at school -------------
    _writing_entry(
        "You want to write an email to your friend to tell him or her about "
        "your day at school. Email your friend and tell him or her the "
        "things you do at school.",
        ["study in the classroom with friends",
         "play sports with friends",
         "have fun with your friends"],
        8, 10,
        "Dear Mei, I want to tell you about my day at school. In the "
        "morning we study in the classroom with our friends. After lunch I "
        "play sports with my friends in the field. We always have so much "
        "fun together. I love my school! Your friend, Nur.",
        recipient="friend@email.com", subject="My school day",
        style="email", bucket="short", years=(3,),
        word_count="30 - 50 words",
        ref=True),
    # ---- UPSA Year 3, Part 7 (email, 60-80): my best friend --------------
    _writing_entry(
        "You want to write an email to a friend to tell him or her about "
        "your best friend. You can use the information given below to help "
        "you.",
        ["who your best friend is",
         "what he or she looks like",
         "what you do together",
         "why he or she is your best friend"],
        10, 15,
        "Dear Aina, I want to tell you about my best friend. His name is "
        "Wei and he has short black hair and a big smile. We play football "
        "and study together every day. He is kind and always helps me. That "
        "is why he is my best friend. I am sure you will like him too! Your "
        "friend, Mei.",
        recipient="friend@email.com", subject="My best friend",
        style="email", bucket="long", years=(3,),
        word_count="60 - 80 words",
        ref=True),
]


def reference_writing_entries(year, style: str, bucket: str) -> list[dict]:
    """Part 6/7 tasks verbatim from the original exam papers.

    ``style`` is "letter" or "email" and ``bucket`` is "short" (Part 6) or
    "long" (Part 7).  Rounds 21-23: these are preferred over any textbook
    derivation so a pupil is never asked to write about a skill label or to
    "use the words: singing, working, some".
    """
    year = int(year)
    return [e for e in REFERENCE_WRITING
            if year in e.get("years", ()) and e.get("style") == style
            and e.get("bucket") == bucket]


def _jsu_signals(year: int, part_num: int) -> list[str]:
    """The JSU's *writer* signals for one part, or ``[]`` when the year has no
    JSU sheet.  One source of truth, deliberately stricter than the audit's
    own ``signals``: the audit asks "could a reader reasonably call this the
    standard's task?", the writer has to be certain, because it is choosing
    between prompts that differ only in their tense."""
    from . import data as _D
    spec = (_D.JSU.get(int(year), {}).get("parts") or {}).get(int(part_num)) or {}
    if not spec:
        return []
    # ``signals`` is the loose list, ``writer_signals`` the tense-precise one,
    # and ``tasks`` the sheet's own wordings: the writer may pick a prompt that
    # satisfies any of the three, so all of them are offered as candidates.
    return list(spec.get("writer_signals") or []) \
        + list(spec.get("signals") or []) \
        + [str(t).lower() for t in (spec.get("tasks") or [])]


def _on_standard(entry: dict, signals: list[str]) -> bool:
    """True when a writing task really asks for what the standard asks for.

    Judged on the *prompt* only.  The bullets are guidance for a pupil who
    has already accepted the task, so a bullet that happens to mention a
    holiday must not turn a pen-pal letter into a future-plans letter."""
    if not signals:
        return True
    return any(s in str(entry.get("prompt", "")).lower() for s in signals)


def _pick_writing_entry(rng, pools, theme, difficulty, signals=None):
    """Pick a writing task that suits the theme, across every pool given.

    ``pools`` are the reference (original exam papers) tasks followed by the
    curated themed letter/email pools.  A pool counts if it carries a task
    tagged with the theme or keyword-matching it.

    Round 26: the older code returned from the *first* pool with any on-theme
    task, and a paper is usually generated without a theme (``conf['theme']``
    is empty), so the three reference-paper tasks won every single time and a
    term repeated the same four prompts no matter how large the pools grew.
    Now every pool is a candidate: on-theme tasks are preferred when a theme
    is set, and otherwise all tasks are pooled and sampled, so the reference
    papers stay available while the curated pools carry most of a term.
    """
    kws = _theme_kws(theme)
    # Round 27: the JSU names what each writing part must ask for (Part 6 is
    # 4.2.2, future plans and events; Part 7 is 4.2.3, factual experiences).
    # A pool that holds on-standard tasks is used first, so the paper is
    # off-blue-print-free by construction; a thin pool still falls back to
    # everything rather than leaving the part empty, and the JSU audit will
    # then say so rather than the paper quietly being wrong.
    if signals:
        kept = [[d for d in pool if _on_standard(d, signals)] for pool in pools]
        if any(kept):
            pools = kept
    matched = []
    for pool in pools:
        matched += [d for d in pool
                    if d.get("theme") == theme
                    or (kws and _matches_theme(d, kws))]
    everything = [d for pool in pools for d in pool]
    return rng.choice(_band(matched or everything, difficulty, need=1))


def build_part(spec: dict, conf: dict, rng, lead_text: str | None,
               stats=None) -> Part:
    """Return a populated Part for one part spec.

    ``stats`` (optional difficulty table) de-prioritises chronically-missed
    pool items when ``conf['calibrate']`` is enabled (Round 13/S4).
    """
    year = int(conf["year"])
    lang = conf.get("lang", "bm")
    difficulty = str(conf.get("difficulty", "medium"))
    theme = conf.get("theme") or ""
    user = _normalize_user_bank(conf.get("user_bank"))

    # Round 33 (F3): a writing task's *demand* moves with the difficulty, not
    # just the vocabulary in the pool.  The published band is medium; easy sits
    # below it and hard above it.
    _lead = spec["lead"].get(lang, spec["lead"]["bm"])
    _lines_scale = None
    if spec["kind"] == "writing":
        _lo, _hi = D.write_words(year, difficulty)
        _lead = re.sub(r"between \d+ and \d+ words",
                       f"between {_lo} and {_hi} words", _lead)
        if "words" not in _lead:
            _lead = f"{_lead.rstrip('.')}. The answer should be between " \
                    f"{_lo} and {_hi} words."
        _lines_scale = D.WRITE_LINES.get(difficulty, 6)

    p = Part(
        num=spec["id"], kind=spec["kind"], style=spec["style"],
        marks=spec["marks"], title=f"PART {spec['id']}",
        lead=_lead, lead_text=lead_text,
    )
    count = spec["count"]

    # Round 17: a mined textbook corpus is the sole reference — its pools win
    # whenever they carry enough clean content; the hand-written pools below
    # only remain the spare wheel.
    tb = conf.get("textbook")

    if spec["kind"] == "vocab":
        # Round 19: corpus Part 1 items only survive the collocate gate AND
        # may not leak an option word into their own stem; once filtered they
        # blend ahead of the built-in pool (never instead of it).
        tb_items = [q for q in tb_vocab_items(tb, year) if _clean_options(q)]
        base = _order_by_stats(
            _vocab_pool(year) + user_pool(user, "vocab", year, year),
            stats, _raw_key)
        base_keys = {_raw_key(d) for d in base}
        pool = [q for q in tb_items if _raw_key(q) not in base_keys] + base
        pool = [q for q in pool if _clean_options(q)] or pool
        # Round 25: the target word must be on the DSKP ladder for the year
        # (distractors are policed by preference, not exclusion).
        pool = _dskp_answer_first(pool, year, count)
        pool = _part1_stimulus_first(pool, count)
        for raw in _pick_items(rng, pool, theme, count, difficulty):
            p.items.append(_shuffle_mcq(rng, raw))

    elif spec["kind"] == "cloze":
        base = _cloze_pool(year)
        pref = "verb" if year in (3, 5) else ("sem" if year >= 6 else "")
        tb_blocks = [b for b in tb_cloze_blocks(tb, year)
                     if len(b.get("gaps", [])) >= count]
        if pref:
            tb_blocks = ([b for b in tb_blocks
                          if b.get("mode") and b["mode"].startswith(pref)]
                         or tb_blocks)
        if tb_blocks:
            block = _pick_block(rng, tb_blocks, theme, difficulty=difficulty)
            p.lead_text = block["passage"]
            p.source_title = str(block.get("title") or "")
            p.source_theme = str(block.get("theme") or "")
            for gap in block["gaps"][:count]:
                p.items.append(_shuffle_mcq(rng, gap))
            return p
        # Round 26: gate the *whole* candidate set up front.  The gate used to
        # run on the ordered pool while `_pick_block` still held the raw `base`
        # as a theme fallback — and `_pick_block` searches fallbacks first, so
        # an off-list gap answer ("cocoon", "locker") was re-admitted right
        # after the gate had dropped its block.  With `raw` ungated entirely
        # (no laddered block at all) the part still falls back rather than
        # being left without a passage.
        raw = base + user_pool(user, "cloze", year, year)
        laddered = [b for b in raw if _block_target_ok(b, year, ("gaps",))]
        pool = _order_by_stats(laddered or raw, stats, _block_key)
        pool = [b for b in pool if len(b.get("gaps", [])) >= count] or pool
        # A gap word that also occurs in the passage gives the answer away, so
        # leak-free blocks are preferred outright when any exist.
        clean = [b for b in pool
                 if not any(_stem_leaks(g) for g in b.get("gaps", []))]
        if clean:
            pool = clean
        if pref:
            favored = [b for b in pool
                       if b.get("mode") and b["mode"].startswith(pref)]
            # Round 43 (SPEC 59): preferring the teacher-format blocks must
            # not collapse Part 2 onto the couple of blocks that happen to
            # carry a mode.  Before this guard the `verb`/`sem` preference
            # left Years 3, 5 and 6 with exactly **two** possible passages,
            # so a class of thirty shared one.  Narrow outright only when
            # there are enough favored blocks to keep real variety; otherwise
            # keep every clean block and just put the favored ones first.
            if len(favored) >= _P2_PREFERRED_MIN:
                # Teacher-format block wins outright: theme/difficulty range
                # within it, never leaping back to a legacy noun-stem block.
                pool = favored
            elif favored:
                pool = favored + [b for b in pool if b not in favored]
        block = _pick_block(rng, pool, theme, fallbacks=(),
                            difficulty=difficulty)
        p.lead_text = block["passage"]
        for gap in block["gaps"][:count]:
            p.items.append(_shuffle_mcq(rng, gap))

    elif spec["kind"] == "comprehension":
        base = _comp_pool(year)
        tb_blocks = [b for b in tb_comprehension_blocks(tb, year)
                     if len(b.get("qs", [])) >= count]
        if tb_blocks:
            block = _pick_block(rng, tb_blocks, theme, difficulty=difficulty)
            p.lead_text = block["text"]
            qs = [q for q in block["qs"] if not _stem_leaks(q)][:count]
            rng.shuffle(qs)
            for raw in qs:
                p.items.append(_shuffle_mcq(rng, raw))
            return p
        pool = _order_by_stats(base, stats, _block_key)
        pool = [b for b in pool
                if len(_no_repeated_answers(list(b.get("qs", [])))) >= count]
        # Years 1-3 read a personal narrative, Years 5-6 an informational
        # piece; the pool holds both, so the register is chosen before the
        # theme/difficulty pick rather than left to chance.
        pool = _register_blocks(pool, "narrative" if year <= 3
                                else "expository")
        pool = _in_word_band(pool, year) or pool
        # A teacher's own passage outranks both filters: the band and the
        # register narrow the built-in pool, they never discard what the user
        # wrote and asked to see.
        pool = pool + user_pool(user, "comprehension", year, year)
        block = _pick_block(rng, pool, theme,
                            fallbacks=[base],
                            difficulty=difficulty)
        p.lead_text = block["passage"]
        qs = list(_no_repeated_answers(list(block["qs"])))[:count]
        rng.shuffle(qs)
        for raw in qs:
            p.items.append(_shuffle_mcq(rng, raw))

    elif spec["kind"] == "match":
        base = _match_pool(year)
        tb_blocks = [b for b in tb_match_blocks(tb, year)
                     if len(b.get("qs", [])) >= count]
        if tb_blocks:
            block = _pick_block(rng, tb_blocks, theme, difficulty=difficulty)
            p.lead_text, raw_items, p.example = _relabel_match(
                rng, block, count, year)
            for raw in raw_items:
                p.items.append(_keep_letter_order(raw))
            return p
        pool = _order_by_stats(base + user_pool(user, "match", year, year),
                               stats, _block_key)
        pool = [b for b in pool if len(b.get("qs", [])) >= count] or base
        block = _pick_block(rng, pool, theme,
                            fallbacks=[base],
                            difficulty=difficulty)
        p.lead_text, raw_items, p.example = _relabel_match(
            rng, block, count, year)
        for raw in raw_items:
            p.items.append(_keep_letter_order(raw))

    elif spec["kind"] == "words":
        if spec["style"] == "letter":
            base = _letter_words_pool(year)
            pool = _order_by_stats(
                base + user_pool(user, "letter_words", year, year),
                stats, _raw_key)
            themed = _theme_prefer(pool, theme, count)
            banded = _band(themed, difficulty, need=count)
            picked = rng.sample(banded, min(count, len(banded)))
            if len(picked) < count:
                picked += [d for d in pool
                           if id(d) not in {id(x) for x in picked}][:count - len(picked)]
            for entry in picked:
                p.items.append(WordItem(
                    clue=entry["clue"],
                    # Years 1-3 print every letter blank (UASA YEAR 1/2/3.pdf);
                    # Years 4-6 print "c o u g h" with the first letter given.
                    first=("" if year in (1, 2, 3)
                           else str(entry["word"])[:1].upper()),
                    length=len(entry["word"]), answer=entry["word"].upper(),
                ))
        else:
            tb_blocks = [b for b in tb_words_choice_blocks(tb, year)
                         if len(b.get("items", [])) >= count]
            if tb_blocks:
                block = _pick_block(rng, tb_blocks, theme, difficulty=difficulty)
                p.lead_text = "Word box: " + ", ".join(block["box"])
                items = list(block["items"])
                selected = rng.sample(items, min(count, len(items)))
                if len(selected) < count:
                    extra = [d for b in tb_words_choice_blocks(tb, year)
                             for d in b["items"]
                             if id(d) not in {id(x) for x in selected}]
                    selected += rng.sample(extra, min(count - len(selected), len(extra)))
                for raw in selected:
                    p.items.append(_shuffle_mcq(rng, raw))
                return p
            pool = _order_by_stats(
                _words_pool(year) + user_pool(user, "words", year, year),
                stats, _block_key)
            # Round 25: the DSKP word list is the vocabulary contract.  A
            # word box whose answers are off-curriculum for the year is
            # demoted, not deleted — a teacher's own bank still gets used when
            # nothing on-list has enough items.
            pool = _dskp_prefer(pool, year, count)
            blocks = [b for b in pool if len(b.get("items", [])) >= count] \
                or [b for b in pool if len(b.get("items", [])) >= 1] or pool
            block = _pick_block(rng, blocks, theme, difficulty=difficulty)
            p.lead_text = "Word box: " + ", ".join(block["box"])
            items = list(block["items"])
            selected = rng.sample(items, min(count, len(items)))
            if len(selected) < count:          # top up from other blocks
                extra = [d for b in pool for d in b["items"]
                         if id(d) not in {id(x) for x in selected}]
                selected += rng.sample(extra, min(count - len(selected), len(extra)))
            for raw in selected:
                p.items.append(_shuffle_mcq(rng, raw))

    elif spec["kind"] == "writing":
        style = spec["style"]
        if style == "sentences":
            tb_entries = tb_sentences(tb, year) if year <= 3 else []
            if len(tb_entries) >= count:
                chosen = _band(_theme_prefer(tb_entries, theme, count),
                               difficulty, need=count)
                picked = rng.sample(chosen, min(count, len(chosen)))
                if len(picked) < count:
                    picked += [d for d in tb_entries
                               if id(d) not in {id(x) for x in picked}][:count - len(picked)]
                p.example = WriteItem(prompt=" - ".join(picked[0]["words"]),
                                      model=picked[0]["model"], lines=1)
                for entry in picked:
                    p.items.append(WriteItem(prompt=" - ".join(entry["words"]),
                                             lines=2, model=entry["model"]))
                return p
            base = (_sentences_pool(year, lower=True)
                    if year <= 3 else _sentences_pool(year, lower=False))
            chosen = _band(_theme_prefer(base, theme, count),
                           difficulty, need=count)
            picked = rng.sample(chosen, min(count, len(chosen)))
            if len(picked) < count:
                picked += [d for d in base
                           if id(d) not in {id(x) for x in picked}][:count - len(picked)]
            p.example = WriteItem(prompt=" - ".join(picked[0]["words"]),
                                  model=picked[0]["model"], lines=1)
            for entry in picked:
                p.items.append(WriteItem(prompt=" - ".join(entry["words"]),
                                         lines=2, model=entry["model"]))
        elif style == "paragraph":
            cards = OUTFIT_CARDS.get(year, OUTFIT_CARDS[1])
            pool = _theme_prefer(cards, theme, 2)
            base = pool[1:] if len(pool) > 1 else pool
            picked = rng.sample(base, min(count, len(base)))
            if len(picked) < count:
                picked += [c for c in cards if c not in picked][:count - len(picked)]
            p.example = WriteItem(
                prompt="This is my father.",
                lines=3, model="My father wears a shirt. He also wears a pair "
                               "of glasses.")
            for card in picked:
                ext = _write_extra(year, difficulty)
                p.items.append(WriteItem(
                    prompt=card["prompt"], bullets=card["bullets"],
                    lines=3 + ext, model=" ".join(card["sentences"]),
                    marks=round(p.marks / max(count, 1))))
        elif style == "letter":
            ref = reference_writing_entries(year, "letter", "short")
            entry = _pick_writing_entry(rng, [ref, _letter_pool(year)],
                                        theme, difficulty,
                                        signals=_jsu_signals(year,
                                                             spec["id"]))
            p.items.append(WriteItem(
                prompt=entry["prompt"], bullets=entry["bullets"],
                lines=entry["lines"] + _write_extra(year, difficulty),
                model=entry["model"],
                marks=entry.get("marks", p.marks),
                salutation=entry.get("salutation", ""),
                closing=entry.get("closing", ""),
                word_count=entry.get("word_count", ""),
            ))
        elif style == "email":
            bucket = "long" if spec["id"] == 7 else "short"
            by_year = _essay_pool(year)
            pool = by_year.get(bucket, []) or by_year.get("long", []) \
                or by_year.get("short", [])
            entry = _pick_writing_entry(
                rng, [reference_writing_entries(year, "email", bucket), pool],
                theme, difficulty,
                signals=_jsu_signals(year, spec["id"]))
            p.items.append(WriteItem(
                prompt=entry["prompt"], bullets=entry["bullets"],
                lines=entry["lines"] + _write_extra(year, difficulty), model=entry["model"],
                marks=p.marks,
                recipient=entry.get("recipient", ""),
                subject=entry.get("subject", ""),
                word_count=entry.get("word_count", ""),
            ))

    if p.kind in ("cloze", "comprehension", "match", "words") and p.lead_text:
        p.topic = _part_topic(p)
    return p


def generate_paper(conf: dict, passages=None) -> Paper:
    """Build a complete Paper from a config dict."""
    from . import data as D
    resolved = dict(conf)
    year = int(conf["year"])
    if not resolved.get("theme"):
        resolved["theme"] = theme_for_week(year, resolved.get("week", 0))
    rng = _rng(resolved)
    meta = dict(resolved)
    # ``DEFAULT_CONFIG`` ships an empty ``duration``, so ``setdefault`` would
    # keep the empty string and the JSU header printed "Time: - minutes" for
    # every year; an explicit value always wins over a blank one.  The
    # fallback is the official time for (year, exam type) -- criteria §1 gives
    # lower primary 60 minutes at UPSA but 75 at UASA, so the year alone is
    # not enough to answer it.
    minutes = D.duration(year, conf.get("exam_type", "upsa"))
    meta["duration_minutes"] = minutes
    if not str(meta.get("duration") or "").strip():
        meta["duration"] = D.duration_text(
            minutes, str(meta.get("lang", "en") or "en").lower())
    meta["subject"] = D.SUBJECT.get(conf.get("lang", "en"), D.SUBJECT["en"])
    meta["subject_code"] = D.SUBJECT_CODE

    paper = Paper(meta=meta)
    qno = 1
    corpus = conf.get("textbook")
    # Textbook reading passages are the sole reference for Part 3 when the
    # corpus carries them; only then fall back to the web cache as before.
    web_pool = tb_comprehension_blocks(corpus, year) if corpus else None
    if not web_pool and conf.get("use_web") and passages:
        web_pool = passages
    stats = load_stats() if resolved.get("calibrate") else None
    for spec in D.PARTS[year]:
        if spec["id"] not in conf.get("parts", [1, 2, 3, 4, 5, 6, 7]):
            continue
        if web_pool and spec["kind"] == "comprehension":
            text, qs, src = _web_comprehension(
                web_pool, rng,
                difficulty=conf.get("difficulty", "medium"),
                theme=resolved.get("theme") or "",
                count=spec["count"],
                year=year)
            if text is not None and len(qs) == spec["count"]:
                part = Part(num=spec["id"], kind="comprehension",
                            style=spec["style"], marks=spec["marks"],
                            title=f"PART {spec['id']}",
                            lead=spec["lead"].get(conf.get("lang", "bm"),
                                                  spec["lead"]["bm"]),
                            lead_text=text,
                            source_theme=src.get("theme", ""),
                            source_title=src.get("title", ""))
                for raw in qs:
                    part.items.append(_shuffle_mcq(rng, raw))
                part.qfirst = qno
                part.topic = _part_topic(part)
                qno += max(len(part.items), 1)
                paper.parts.append(part)
                continue
            # no web passage with the full question count: fall through to the
            # built-in comprehension pool below (never a short Part 3)
        part = build_part(spec, resolved, rng, None, stats=stats)
        part.qfirst = qno
        if part.kind == "writing" and part.lines is None:
            part.lines = answer_lines(year, spec["style"])
        if len(part.items) != spec["count"]:
            raise RuntimeError(
                f"PART {spec['id']} (year {year}) built {len(part.items)} "
                f"questions but the official format needs {spec['count']} "
                f"for its {spec['marks']} marks")
        qno += max(len(part.items), 1)
        paper.parts.append(part)

    paper.marks_table = _marks_table(paper)
    balance_answer_runs(paper)
    paper.key = build_key(paper)
    return paper


def generate_clean(conf: dict, passages=None, max_tries: int = 3) -> Paper:
    """QC-gated generation (Round 20/F38): the watchdog re-rolls a paper until
    it has **zero** hard issues — one full try, then the textbook pool is
    dropped, then the web cache too (attempts share the conf's seed, so a
    re-roll is deterministic).  The first clean paper wins; ``paper._qc`` and
    ``paper._qc_rolls`` record the report and the attempt used."""
    from . import qc as Q
    best, best_r, rolls = None, None, 0
    for attempt in range(max_tries):
        c = dict(conf)
        if attempt >= 1:
            c["textbook"] = None
        if attempt >= 2:
            c["use_web"] = False
        p = generate_paper(c, passages if attempt < 2 else None)
        r = Q.check_paper(p)
        if best is None or (r.hard, -r.score) < (best_r.hard,
                                                 -best_r.score):
            best, best_r, rolls = p, r, attempt
        if r.hard == 0:
            break
    best._qc = best_r
    best._qc_rolls = rolls
    return best


class PaperPair(tuple):
    """A (UPSA, UASA) pair of papers for one year.

    Behaves like a 2-tuple (so it can be unpacked or indexed) while also
    exposing the two papers as ``.upsa`` / ``.uasa`` and as string keys, so
    callers that expect any of the common shapes keep working.
    """

    def __new__(cls, upsa, uasa):
        obj = super().__new__(cls, (upsa, uasa))
        obj.upsa = upsa
        obj.uasa = uasa
        obj.papers = (upsa, uasa)
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            key = key.strip().lower()
            if key in ("upsa", "0", "mid", "midyear", "mid-year"):
                return self[0]
            if key in ("uasa", "1", "end", "endyear", "end-of-year", "end of year"):
                return self[1]
            if key in ("papers",):
                return tuple(self)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError, TypeError):
            return default

    def as_dict(self):
        return {"upsa": self[0], "uasa": self[1], "papers": list(self)}


def generate_year_pair(year, seed=None, difficulty="medium", threshold=25,
                      max_tries=200, passages=None, apply_locks=True,
                      **conf_overrides):
    """Generate two **different** papers for one year — UPSA (mid-year) and
    UASA (end-year) — that do not repeat each other's items.

    The first paper is built from ``seed`` (defaulting to the config default);
    the second is searched over chained seeds until
    :func:`repeat_report` reports zero pairs at or above ``threshold``% shared
    items, so a class never sees the same paper twice in one year.  The same
    routine works for any school year the bank supports (1-6) and therefore for
    2026, 2027 and every year after.

    Returns a :class:`PaperPair` (unpackable like a 2-tuple).
    """
    from . import qc as _Q
    year = int(year)
    if year not in D.YEARS:
        raise ValueError(f"Unsupported year {year}; use {D.YEARS}")
    if difficulty not in D.DIFFICULTIES:
        raise ValueError(f"Unsupported difficulty {difficulty!r}; "
                         f"use {D.DIFFICULTIES}")
    if seed is None:
        seed = int(D.DEFAULT_CONFIG.get("seed", 1))

    def _conf(exam_type, s):
        c = dict(D.DEFAULT_CONFIG)
        c.update(conf_overrides or {})
        c["year"] = year
        c["exam_type"] = str(exam_type).lower()
        c["difficulty"] = difficulty
        c["seed"] = int(s)
        return c

    upsa = generate_clean(_conf("upsa", seed), passages)

    uasa = None
    u_seed = next_seed(int(seed))
    for _ in range(max(1, int(max_tries))):
        cand = generate_clean(_conf("uasa", u_seed), passages)
        try:
            rep = repeat_report([upsa, cand], threshold=threshold)
            ok = (rep.get("over_threshold", 0) == 0)
        except Exception:
            ok = True
        if ok:
            uasa = cand
            break
        u_seed = next_seed(u_seed)

    if uasa is None:
        uasa = generate_clean(_conf("uasa", u_seed), passages)

    if apply_locks:
        try:
            from . import locks as _locks
            store = _locks.load()
            if store:
                upsa = apply_locks(upsa, store)
                uasa = apply_locks(uasa, store)
        except Exception:
            pass

    return PaperPair(upsa, uasa)


# Common aliases so callers can use whichever name they reach for first.
generate_pair = generate_year_pair
generate_upsa_uasa = generate_year_pair
upsa_uasa_pair = generate_year_pair
year_pair = generate_year_pair
generate_two_papers = generate_year_pair
non_repeating_pair = generate_year_pair
generate_non_repeating_papers = generate_year_pair
generate_non_repeating_pair = generate_year_pair
papers_for_year = generate_year_pair
generate_year_papers = generate_year_pair
year_papers = generate_year_pair
two_papers = generate_year_pair
two_papers_year = generate_year_pair
make_year_pair = generate_year_pair
create_year_pair = generate_year_pair
generate_upsa_and_uasa = generate_year_pair
upsa_uasa = generate_year_pair
generate_pair_for_year = generate_year_pair


def balance_answer_runs(paper: Paper, max_run: int = 2) -> int:
    """Round 42 (SPEC 58): no more than ``max_run`` identical option letters
    in a row on the objective answer sheet.

    Measured before this round, over 24 papers per year: the worst streak in a
    single paper was **9**, and Year 5 produced a streak of >= 3 in 21 of 24
    papers.  A pupil who shades bubbles in the obvious order reads ``CCCC``
    across four questions and has three of them without reading the paper.

    The repair **re-picks the position of the correct option**, never the
    option itself, so the answer stays correct and only the key letter moves.

    Two kinds of item cannot move:

    * **Part 4 matching items**, whose option text *is* the bubble label
      (``["A", "B", "C"]``).  The renderer never prints those options -- the
      letter is fixed by the lettered texts in the lead -- so moving the index
      would change the key.  They are left exactly as they are.
    * **Items with a single option**, which have nowhere to swap to.

    Greedily moving only the offending item just slides the run along, so the
    streak is resolved over the whole offending window instead: every movable
    item in it is offered a letter other than the run's, each trial is scored
    and immediately undone, and the arrangement with the shortest streak is
    finally applied.
    """
    letters = "ABCD"
    changed = 0

    def movable(item) -> bool:
        if not isinstance(item, MCQItem) or not isinstance(item.answer, int):
            return False
        if not (0 <= item.answer < min(len(item.options), len(letters))):
            return False
        # Part 4 matching items carry the bubble label as the option text.
        if [str(o).strip().upper() for o in item.options] == \
                list(letters[:len(item.options)]):
            return False
        return len(item.options) > 1

    def move_to(item, want: str) -> str | None:
        """Put the correct option on ``want``; return the letter it now has."""
        old = letters[item.answer]
        if old == want:
            return None
        choices = [i for i in range(len(item.options))
                   if i != item.answer and letters[i] == want]
        if not choices:
            return None
        target = choices[0]
        item.options[item.answer], item.options[target] = \
            item.options[target], item.options[item.answer]
        item.answer = target
        return want

    def undo(item, opts: list, ans: int) -> None:
        item.options[:] = opts
        item.answer = ans

    def longest(seq: list[str]) -> int:
        best = cur = 1 if seq else 0
        for a, b in zip(seq, seq[1:]):
            cur = cur + 1 if a == b else 1
            best = max(best, cur)
        return best

    history: list[str] = []
    items: list[MCQItem] = []
    for part in paper.parts:
        if part.kind in ("writing", "words"):
            continue
        for item in part.items:
            if not isinstance(item, MCQItem) or not isinstance(item.answer, int):
                continue
            if not (0 <= item.answer < min(len(item.options), len(letters))):
                continue
            history.append(letters[item.answer])
            items.append(item)
            # Only react to a streak that actually continues one from the
            # previous part: the pupil reads the sheet as one column.
            if len(history) <= max_run:
                continue
            lo = len(history) - max_run - 1
            window = history[lo:]
            if len(set(window)) != 1:
                continue
            run_letter = window[0]
            best_score = longest(window)
            best_plan = None
            for j in range(lo, len(history)):
                cand = items[j]
                if not movable(cand):
                    continue
                for want in letters:
                    if want == run_letter:
                        continue
                    saved_opts, saved_ans = list(cand.options), cand.answer
                    if move_to(cand, want) is None:
                        continue
                    trial = list(window)
                    trial[j - lo] = want
                    score = longest(trial)
                    if score < best_score:
                        best_score = score
                        best_plan = (cand, want, saved_opts, saved_ans)
                    undo(cand, saved_opts, saved_ans)
            if best_plan is not None:
                cand, want, saved_opts, saved_ans = best_plan
                if move_to(cand, want) is not None:
                    changed += 1
                    history[lo:] = window
                    k = items.index(cand, lo)
                    history[k] = want
    return changed


def _marks_table(paper: Paper) -> list[tuple[str, int, int]]:
    rows = []
    total = 0
    for p in paper.parts:
        rows.append((f"PART {p.num}", p.marks, 0))
        total += p.marks
    rows.append(("TOTAL", total, 0))
    return rows


# ---------------------------------------------------------------------------
# quality gate (Round 12/S9)
# ---------------------------------------------------------------------------

def _stem_leaks(raw: dict) -> bool:
    """True when a question's answer text appears verbatim inside its stem."""
    ans = raw.get("ans_text")
    opts, idx = raw.get("opts"), raw.get("ans")
    if not ans and opts and isinstance(idx, int) and 0 <= idx < len(opts):
        ans = opts[idx]
    if not ans:
        return False
    needle = re.compile(r"\b" + re.escape(str(ans).casefold()) + r"\b")
    return bool(needle.search(str(raw.get("stem", "")).casefold()))


def _answer_text(item) -> str:
    if isinstance(item, MCQItem):
        if item.ans_text:
            return item.ans_text
        return item.options[item.answer] if item.options else ""
    if isinstance(item, WordItem):
        return item.answer or ""
    return ""


def quality_issues(paper: Paper) -> list[str]:
    """Human-readable problems in a generated paper (duplicate questions,
    repeated passages, answer-in-stem leaks).  Empty when clean."""
    issues: list[str] = []
    passages: dict[str, int] = {}
    for p in paper.parts:
        lead = (p.lead_text or "").strip().casefold()
        if lead:
            if lead in passages:
                issues.append(
                    f"PART {p.num}: passage text duplicates PART {passages[lead]}")
            else:
                passages[lead] = p.num
        stems: set[str] = set()
        answers: set[str] = set()
        for item in p.items:
            stem = getattr(item, "stem", None) or getattr(item, "prompt", None) \
                or getattr(item, "clue", None) or ""
            ans = _answer_text(item)
            if ans and len(ans) >= 3 and _stem_leaks({"stem": stem,
                                    "opts": getattr(item, "options", None),
                                    "ans": getattr(item, "answer", None),
                                    "ans_text": getattr(item, "ans_text", None)}):
                issues.append(
                    f"PART {p.num}: question stem contains its answer "
                    f"('{ans}')")
            key = str(stem).casefold()
            if key:
                if key in stems:
                    issues.append(
                        f"PART {p.num}: duplicate question text: {stem[:60]}")
                stems.add(key)
            if ans:
                if len(ans) >= 3 and ans.casefold() in answers:
                    issues.append(
                        f"PART {p.num}: answer repeated in part ('{ans}')")
                answers.add(ans.casefold())
    return issues


def item_export(it, num: int, marks) -> dict:
    """Round 12/S7: json-safe dict for one question of a generated paper."""
    kind = it.__class__.__name__
    d = {"num": num, "type": kind, "marks": round(float(marks), 2)}
    if kind == "MCQItem":
        d["stem"] = it.stem
        d["options"] = list(it.options)
        d["answer"] = it.answer_label
        d["answer_index"] = it.answer
        d["answer_text"] = _answer_text(it)
        if it.wordbox:
            d["wordbox"] = list(it.wordbox)
        if it.lead:
            d["lead"] = it.lead
    elif kind == "WordItem":
        d["clue"] = it.clue
        d["first"] = it.first
        d["length"] = it.length
        d["answer"] = it.answer
        d["pattern"] = it.pattern
        if it.wordbox:
            d["wordbox"] = list(it.wordbox)
    else:  # WriteItem
        d["prompt"] = it.prompt
        d["example"] = it.example
        d["bullets"] = list(it.bullets)
        d["words"] = list(it.words)
        d["lines"] = it.lines
        d["model"] = it.model
        d["salutation"] = it.salutation
        d["subject"] = it.subject
        d["recipient"] = it.recipient
        d["closing"] = it.closing
        d["word_count"] = it.word_count
    return d


def paper_export(paper: Paper) -> dict:
    """json-safe view of a whole paper: per-part items, the answer key and the
    marks table (used by the CLI --json flag and GUI export)."""
    parts = []
    for p in paper.parts:
        parts.append({
            "number": p.num, "kind": p.kind, "style": p.style,
            "marks": p.marks, "title": p.title, "lead": p.lead,
            "lead_text": p.lead_text, "qfirst": p.qfirst, "topic": p.topic,
            "photo_query": p.photo_query, "lines": p.lines,
            "items": [item_export(it, p.qfirst + i, p.marks_per_q())
                      for i, it in enumerate(p.items)],
        })
    return {"meta": dict(paper.meta), "parts": parts,
            "key": list(paper.key), "marks_table": list(paper.marks_table)}


def paper_csv(paper: Paper) -> str:
    """One row per question for spreadsheet marking/analysis; the 'Answer'
    column carries the answer text, 'Key' the letter/label if any."""
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    w.writerow(["Part", "Question", "Type", "Marks", "Key", "Answer"])
    for p in paper.parts:
        for i, it in enumerate(p.items):
            ans = _answer_text(it)
            key = it.answer_label if it.__class__.__name__ == "MCQItem" else ""
            w.writerow([p.title, p.qfirst + i, it.__class__.__name__,
                        round(float(p.marks_per_q()), 2), key, ans])
    return buf.getvalue()


def paper_from_export(data: dict) -> Paper:
    """Reconstitute a saved paper (JSON from ``paper_export``) so teachers can
    re-render or re-use past papers offline (Round 12/S6 archive)."""
    from .models import MCQItem, Part, Paper, WordItem, WriteItem
    parts = []
    for pd in data.get("parts", []):
        p = Part(num=pd["number"], kind=pd["kind"], style=pd["style"],
                 marks=pd["marks"], title=pd["title"], lead=pd["lead"],
                 lead_text=pd.get("lead_text"), qfirst=pd["qfirst"],
                 topic=pd.get("topic", ""),
                 photo_query=pd.get("photo_query", ""), lines=pd.get("lines"))
        for it in pd["items"]:
            if it["type"] == "MCQItem":
                p.items.append(MCQItem(
                    stem=it["stem"], options=list(it["options"]),
                    answer=int(it["answer_index"]),
                    wordbox=it.get("wordbox"), lead=it.get("lead"),
                    ans_text=it.get("answer_text")))
            elif it["type"] == "WordItem":
                p.items.append(WordItem(
                    clue=it["clue"], first=it["first"], length=it["length"],
                    answer=it["answer"], wordbox=it.get("wordbox")))
            else:
                p.items.append(WriteItem(
                    prompt=it["prompt"], example=it.get("example"),
                    bullets=list(it.get("bullets", [])),
                    words=list(it.get("words", [])),
                    lines=it.get("lines", 4), model=it.get("model", ""),
                    marks=it.get("marks", 0),
                    salutation=it.get("salutation", ""),
                    subject=it.get("subject", ""),
                    recipient=it.get("recipient", ""),
                    closing=it.get("closing", ""),
                    word_count=it.get("word_count", "")))
        parts.append(p)
    return Paper(meta=dict(data.get("meta", {})), parts=parts,
                 key=[tuple(k) for k in data.get("key", [])],
                 marks_table=[tuple(m)
                              for m in data.get("marks_table", [])])


def archive_dir(directory: str) -> list[str]:
    """Every exported past paper (---json) inside ``directory``."""
    import os
    return sorted(
        os.path.join(directory, n) for n in os.listdir(directory)
        if n.endswith(".json"))


def archive_suggest(year: int, week: int, directory: str):
    """Auto-suggest the past papers that fit this RPT week's theme
    (Round 12/S6): scan archived JSON exports, keep those whose saved meta
    theme equals ``theme_for_week(year, week)``.  Returns (theme, [(path,
    theme), ...])."""
    import json
    want = theme_for_week(int(year), int(week))
    hits = []
    for path in archive_dir(directory):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        t = (data.get("meta") or {}).get("theme")
        if t and t == want:
            hits.append((path, t))
    return want, hits


def build_key(paper: Paper) -> list[tuple[int, str, str]]:
    """(question no., answer text, remark) for every item."""
    key: list[tuple[int, str, str]] = []
    for p in paper.parts:
        qno = p.qfirst
        for item in p.items:
            if isinstance(item, MCQItem):
                if item.ans_text:
                    key.append((qno, item.ans_text, ""))
                else:
                    key.append((qno, item.answer_label, ""))
            elif isinstance(item, WordItem):
                key.append((qno, item.answer, ""))
            elif isinstance(item, WriteItem):
                note = ""
                if item.model:
                    note = item.model[:80] + ("…" if len(item.model) > 80 else "")
                key.append((qno, "(sample answer)", note))
            qno += 1
    return key


# ---------------------------------------------------------------------------
# Round 13 (S1): class bundles — N seeded variants + one merged marksheet.
# ---------------------------------------------------------------------------

def bundle_papers(conf: dict, n: int = 20, passages=None) -> list:
    """Generate ``n`` distinct variants of one paper for a class.

    Seeded with ``conf['seed']`` and then chained with ``next_seed`` so every
    set differs; the first paper is identical to a plain single generate with
    the same config (stable, deterministic tests).
    """
    n = max(1, int(n))
    papers: list = []
    seed = int(conf.get("seed", 1))
    year = int(conf["year"])
    for i in range(n):
        c = dict(conf)
        c["seed"] = seed
        papers.append(generate_clean(c, passages))
        seed = next_seed(seed)
    return papers


# ---------------------------------------------------------------------------
# Round 13 (S5): DSKP coverage for the term's papers.
# ---------------------------------------------------------------------------

def dskp_coverage(year: int) -> dict[int, list[str]]:
    """Standard codes covered by each part for ``year`` (from data.DSKP)."""
    from . import data as _D
    return {p: list(_D.DSKP.get(int(year), {})[p])
            for p in _D.DSKP.get(int(year), {})}


def dskp_report(paper: Paper, lines: int = 10000) -> str:
    """Human-readable DSKP coverage report for a generated paper."""
    from . import data as _D
    year = int(paper.year())
    per = _D.DSKP.get(year, {})
    out = [f"DSKP coverage — Year {year} · {paper.meta.get('theme', '')}",
           "=" * 50]
    codes: set[str] = set()
    for p in paper.parts:
        stds = per.get(p.num, [])
        codes.update(stds)
        if not stds:
            out.append(f"PART {p.num}  — (no standard assigned)")
            continue
        out.append(f"PART {p.num}  [{p.marks} marks]  {', '.join(stds)}")
    out.append("-" * 50)
    for code in sorted(codes):
        title = _D.DSKP_TITLES.get(code, "")
        out.append(f"  • {code}  {title}" if title else f"  • {code}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# JSU — the official exam-specification audit (Round 27)
# ---------------------------------------------------------------------------
def _jsu_for(year: int) -> dict | None:
    from . import data as _D
    return _D.JSU.get(int(year))


def jsu_issues(paper: Paper) -> list[str]:
    """Every way a generated paper departs from its JSU blue-print.

    ``data.PARTS`` already guarantees the shape (7 parts, 50 marks, the right
    number of items), so this checks the *content* the ministry specifies:
    the marks and item count of each part, that the part carries the learning
    standards the JSU names, that a writing task really asks for what its
    standard asks for, and that the objective items add up to the official
    CEFR mix.

    Years with no JSU sheet (1-3) have nothing to check and return no issues;
    the RPT themes and the DSKP ladder cover them instead
    (see :func:`dskp_report`).
    """
    year = int(paper.year())
    jsu = _jsu_for(year)
    if not jsu:
        return []
    issues: list[str] = []
    by_num = {p.num: p for p in paper.parts}
    objective = 0
    for num, spec in sorted(jsu["parts"].items()):
        part = by_num.get(num)
        if part is None:
            issues.append(f"PART {num} is missing from the paper")
            continue
        if part.marks != spec["marks"]:
            issues.append(f"PART {num} carries {part.marks} marks; the JSU "
                          f"specifies {spec['marks']}")
        if len(part.items) != spec["items"]:
            issues.append(f"PART {num} has {len(part.items)} items; the JSU "
                          f"specifies {spec['items']}")
        if part.kind != "writing":
            objective += len(part.items)
        # ``signals`` is the audit's list and ``writer_signals`` the writer's
        # stricter one; both state the same task, so a prompt is on-standard if
        # it matches either.  Judging only ``signals`` used to reject a real
        # past-tense experience such as "You were a helper at a fun fair ..."
        # simply because the narration sat in ``writer_signals``.
        signals = list(spec.get("signals") or []) \
            + list(spec.get("writer_signals") or [])
        if signals and part.items:
            # Only the *instruction* is judged, not the guidance bullets: the
            # prompt is what tells the pupil what to write, so a task whose
            # bullets happen to mention a holiday is still off-standard if the
            # prompt asks for something else.
            prompt = " ".join(
                str(getattr(i, "prompt", "") or "") for i in part.items
            ).lower()
            # The sheet's writing cells are "choose one of": a prompt that
            # answers any wording the part allows is on-blue-print, so the
            # sheet's whole option list is consulted, not just ``task``.
            allowed = [t for t in ([spec.get("task", "")] +
                                   list(spec.get("tasks") or [])) if t]
            if not (any(s in prompt for s in signals)
                    or any(t.lower() in prompt for t in allowed)):
                issues.append(
                    f"PART {num} asks {spec.get('task', spec['skill'])!r} "
                    f"({', '.join(spec['learning_standards'])}), but the task "
                    f"does not: {part.items[0].prompt[:60]!r}")
    if jsu.get("cefr_mix") and sum(jsu["cefr_mix"].values()) != objective:
        issues.append(f"the paper has {objective} objective items; the JSU "
                      f"CEFR mix sums to {sum(jsu['cefr_mix'].values())}")
    return issues


def jsu_report(paper: Paper) -> str:
    """Human-readable JSU blue-print report for a generated paper."""
    year = int(paper.year())
    jsu = _jsu_for(year)
    if not jsu:
        return (f"JSU — Year {year}\n"
                f"{'=' * 50}\n"
                "No JSU sheet exists for this year; the DSKP ladder and the "
                "RPT themes cover it instead.")
    out = [f"JSU — {jsu['title']} · {jsu.get('source', '')}",
           "=" * 50]
    by_num = {p.num: p for p in paper.parts}
    for num, spec in sorted(jsu["parts"].items()):
        part = by_num.get(num)
        got = f"{part.marks} marks · {len(part.items)} items" if part else "—"
        std = ", ".join(spec["learning_standards"])
        out.append(f"PART {num}  [{got}]  {spec['skill']}  {spec.get('cefr', '')}")
        out.append(f"          standards: {std}")
        if spec.get("task"):
            out.append(f"          task: {spec['task']}")
    out.append("-" * 50)
    mix = jsu.get("cefr_mix") or {}
    out.append("  objective CEFR mix: "
               + ", ".join(f"{k} {v}" for k, v in mix.items()))
    lots, hots = jsu.get("lots"), jsu.get("hots")
    if lots is not None:
        out.append(f"  LOTS:HOTS {lots}:{hots}")
    issues = jsu_issues(paper)
    out.append("-" * 50)
    out.append("  OFF BLUE-PRINT:" if issues else "  ON BLUE-PRINT ✓")
    out += [f"    ! {i}" for i in issues]
    # The same command also shows the per-paper table the document now
    # carries after the answer key.
    from . import jsu as J
    out.append(J.report(paper))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Round 13 (S7): past-paper / bank import.
# ---------------------------------------------------------------------------
# No OCR in the stdlib-only build: import is format-based.  Supported inputs:
#   * ``--import FILE.csv``  — user-bank rows (see ``import_csv``), and
#   * ``--import FILE.json`` — a past paper exported with ``--json`` / the
#     GUI's JSON export (validated + made ready for ``--revision``).

_IMPORT_CSV_HEADER = (
    "kind", "stem", "passage", "text_a", "text_b", "text_c", "box",
    "a", "b", "c", "d", "e", "answer", "answer_text", "year",
)


def paper_compliance(paper: Paper) -> dict:
    """Score one generated paper against the official exam contract.

    Confirms the paper can be used as a real school examination: the official
    7-part / 50-mark UPSA/UASA structure with contiguous numbering, per-part
    counts, writing-part shapes, the year's DSKP content standards, the
    scheduled RPT theme/week, and the CEFR band + word ceiling of every
    comprehension passage.  The refresh/Regenerate button and the CLI run
    this after every paper so nothing silently ships that a school cannot
    hand out.

    Returns a dict with ``ok`` plus a machine-readable breakdown and
    human-facing ``issues`` / ``messages`` lists.
    """
    from . import data as D
    year = int(paper.year())
    specs = {s["id"]: s for s in D.PARTS.get(year, [])}
    exam = D.EXAM_ABBR.get(str(paper.meta.get("exam_type", "upsa")).lower(),
                           "UPSA")
    theme = str(paper.meta.get("theme") or "")
    week = int(paper.meta.get("week") or 0)
    issues: list[str] = []
    messages: list[str] = []
    passage_bands: dict[int, dict] = {}

    # --- structure: official 7-part / 50-mark paper -----------------------
    if len(paper.parts) != len(D.PARTS.get(year, [])):
        issues.append(
            f"{len(paper.parts)} part(s) built; the official {exam} Year {year} "
            f"paper has {len(D.PARTS.get(year, []))} parts")
    marks = sum(p.marks for p in paper.parts)
    if marks != D.TOTAL:
        issues.append(f"marks total {marks}; the official paper totals {D.TOTAL}")
    expected = 1
    for p in paper.parts:
        if p.qfirst != expected:
            issues.append(f"question numbering breaks at PART {p.num}: "
                          f"expected {expected}, starts at {p.qfirst}")
            break
        expected += len(p.items)
    for p in paper.parts:
        spec = specs.get(p.num)
        if spec and len(p.items) != spec["count"]:
            issues.append(
                f"PART {p.num} has {len(p.items)} question(s); the official "
                f"format needs {spec['count']}")
        if p.kind == "writing" and p.style in ("letter", "email"):
            if len(p.items) != 1:
                issues.append(f"PART {p.num} ({p.style}) must carry exactly "
                              f"1 item, has {len(p.items)}")
        if p.kind == "writing" and p.style in ("sentences", "paragraph", "letter"):
            if getattr(p, "example", None) is None:
                spec = specs.get(p.num)
                expects = spec.get("example") if spec else False
                if expects or p.style in ("sentences", "paragraph"):
                    issues.append(f"PART {p.num} ({p.style}) is missing its "
                                  f"worked example")

    # --- DSKP content standards for the year ------------------------------
    cov = dskp_coverage(year)
    for p in paper.parts:
        if p.num not in cov or not cov[p.num]:
            issues.append(f"PART {p.num} has no DSKP standard assigned for "
                          f"Year {year}")
    if not any("DSKP" in i for i in issues):
        messages.append("DSKP content standards covered by every part")

    # --- RPT theme / week schedule ----------------------------------------
    themes = D.RPT_THEMES.get(year, [])
    valid = (not theme) or theme in themes
    scheduled = theme_for_week(year, week) if week > 0 else ""
    if not valid:
        issues.append(f"theme {theme!r} is not an RPT theme for Year {year}")
    elif week > 0 and scheduled and theme != scheduled:
        issues.append(
            f"RPT week {week} schedules {scheduled!r}, but the paper uses "
            f"{theme!r}")
    if week > 0 and not issues_contain_rpt(issues):
        messages.append(f"RPT week {week} theme {theme!r} matches the schedule")
    elif not week:
        messages.append(f"RPT theme {theme or '(auto)'} selected")

    # --- CEFR band + word ceiling of comprehension passages ----------------
    ceiling_ok = True
    for p in paper.parts:
        if p.kind != "comprehension" or not (p.lead_text or "").strip():
            continue
        band = passage_band(p.lead_text)
        words = len(str(p.lead_text).split())
        top = _BAND_RANK[D.PASSAGE_CEFR.get(year, "a1")]
        lo_w, hi_w = D.PASSAGE_WORD_BAND.get(
            year, (0, D.PASSAGE_WORD_CEIL.get(year, 300)))
        over = _BAND_RANK[band] > top
        too_long = words > hi_w
        passage_bands[p.num] = {"band": band, "max": D.PASSAGE_CEFR.get(year),
                                "words": words}
        if over:
            issues.append(
                f"PART {p.num} passage is CEFR {band.upper()}; Year {year} "
                f"reading stays at {D.PASSAGE_CEFR.get(year, '').upper()}")
        if too_long:
            ceiling_ok = False
            issues.append(
                f"PART {p.num} passage is {words} words; the criteria cap "
                f"Year {year} Part 3 at {lo_w}-{hi_w} words")
    if passage_bands and not issues_contain_cefr(issues):
        messages.append(
            "CEFR passage bands within the year range "
            + ", ".join(f"P{pn} {b['band'].upper()}" for pn, b in
                        sorted(passage_bands.items())))

    # --- Round 20 QC watchdog: the paper must satisfy the teacher's bar ----
    from . import qc as Q
    qr = Q.check_paper(paper)
    qc_hard = [i for i in qr.issues if i.hard]
    if qc_hard:
        issues.append("QC watchdog: "
                      + "; ".join(i.code for i in qc_hard))
    elif qr.score < 8.0:
        issues.append(f"QC watchdog: {qr.score}/10 (soft issues "
                      f"still need attention)")
    messages.append(f"QC {qr.score}/10 · {qr.hard} hard, {qr.soft} soft")

    if len(paper.parts) == len(D.PARTS.get(year, [])):
        nq = sum(len(p.items) for p in paper.parts)
        messages.append(f"Y{year} {exam} · {marks} marks · {nq} questions")

    return {
        "ok": not issues,
        "year": year,
        "exam_type": exam,
        "theme": theme,
        "week": week,
        "parts": len(paper.parts),
        "marks": marks,
        "questions": sum(len(p.items) for p in paper.parts),
        "rpt": not issues_contain_rpt(issues),
        "dskp": not any("DSKP" in i for i in issues),
        "cefr": not issues_contain_cefr(issues) and ceiling_ok,
        "passage_bands": passage_bands,
        "issues": issues,
        "messages": messages,
    }


def issues_contain_rpt(issues: list[str]) -> bool:
    return any("RPT" in i for i in issues)


def issues_contain_cefr(issues: list[str]) -> bool:
    return any("CEFR" in i for i in issues)


def import_csv(path: str, year: int = 0) -> int:
    """Import bank rows from a CSV into the persistent user bank.

    Header row (any order of the columns above); one question per line.
    ``kind`` selects the bank shape: ``vocab`` / ``comprehension`` /
    ``cloze`` / ``match`` / ``words`` / ``letter_words``.  MCQ columns
    ``a..e`` hold the options and ``answer`` is ``A``.. letter or the index.
    Returns how many rows were added (duplicates are skipped).
    """
    import csv as _csv
    with open(path, encoding="utf-8") as fh:
        rows = [r for r in _csv.reader(fh)
                if any((c or "").strip() for c in r)]
    if not rows:
        return 0
    header = [h.strip().lower() for h in rows[0]]
    unknown = [h for h in header if h not in _IMPORT_CSV_HEADER]
    if unknown:
        raise ValueError(f"Unsupported CSV columns: {', '.join(unknown)}")
    added = 0
    for row in rows[1:]:
        cells = {h: (row[i].strip() if i < len(row) else "")
                 for i, h in enumerate(header)}
        kind = cells.get("kind", "").lower()
        entry = _entry_from_csv(cells, kind)
        if entry is None:
            continue
        raw = {**entry}
        if cells.get("year"):
            raw["year"] = int(cells["year"])
        elif year:
            raw["year"] = int(year)
        added += save_user_bank_entry(default_bank_path(), kind, raw)
    return added


def _entry_from_csv(cells: dict, kind: str) -> dict | None:
    """Build one user-bank entry from parsed CSV cells (or None)."""
    opts = [cells[k] for k in ("a", "b", "c", "d", "e") if cells.get(k)]
    ans = cells.get("answer", "").strip().upper()
    ans_text = cells.get("answer_text", "").strip()
    idx = None
    if ans.isdigit():
        idx = int(ans)
    elif ans and ans in "ABCDE":
        idx = "ABCDE".index(ans)
    if opts and idx is not None and 0 <= idx < len(opts):
        if not ans_text:
            ans_text = opts[idx]
        mcq = {"stem": cells.get("stem", ""), "opts": opts, "ans": idx}
        if ans_text and ans_text != opts[idx]:
            mcq["ans_text"] = ans_text
    else:
        mcq = None
    if kind == "vocab":
        return mcq
    if kind in ("cloze", "comprehension"):
        res = {"passage": cells.get("passage", ""), "qs": [], "gaps": []}
        if kind == "cloze":
            res["gaps"].append(mcq) if mcq else None
        else:
            res["qs"].append(mcq) if mcq else None
        if res.get("gaps") or res.get("qs"):
            return res
    if kind == "match":
        texts = [t for t in (cells.get("text_a"), cells.get("text_b"),
                             cells.get("text_c")) if t]
        if mcq and len(texts) == 3:
            return {"texts": texts, "qs": [mcq]}
    if kind == "words":
        box = [w for w in str(cells.get("box", "")).split(",") if w.strip()]
        if mcq and box:
            return {"box": box, "items": [mcq]}
    if kind == "letter_words":
        word = ans_text or (opts[idx] if idx is not None and opts else "")
        if cells.get("stem") and word:
            return {"clue": cells.get("stem"), "word": word.lower()}
    return None


def import_past_json(path: str) -> dict:
    """Validate an exported past paper (--json) and return its summary dict.

    No bank mutation: the JSON is a self-contained paper export (answer key +
    marks table) that ``paper_from_export`` can re-render, so importing mostly
    means placing it inside the folder used by ``--revision`` / the archive.
    """
    import json as _json
    with open(path, encoding="utf-8") as fh:
        data = _json.load(fh)
    if not isinstance(data, dict) or "parts" not in data or "meta" not in data:
        raise ValueError(f"{path} is not an exported past paper (needs "
                         "'parts' and 'meta')")
    paper = paper_from_export(data)
    return {"file": os.path.abspath(path), "year": paper.year(),
            "parts": len(paper.parts), "questions": paper.max_qno(),
            "key": len(paper.key)}

# ---------------------------------------------------------------------------
# Round 30 (F4): repeat report — how much two sittings share
# ---------------------------------------------------------------------------
def _item_fingerprints(paper) -> set[str]:
    """Comparable fingerprint per item, stable across papers of a year.

    Stems are the identity that matters to a pupil ("did I already do this
    one?"), so key on the normalised stem plus the part kind.  Options are
    deliberately excluded: a shuffled option order must not read as a new
    item.
    """
    out = set()
    for part in getattr(paper, "parts", []):
        for it in part.items:
            stem = getattr(it, "stem", None) or getattr(it, "prompt", None) or ""
            norm = " ".join(str(stem).lower().split())
            if norm:
                out.add(f"{part.kind}:{norm}")
    return out


def repeat_report(papers, threshold: int = 25) -> dict:
    """Compare a set of papers pairwise and flag heavy item reuse.

    ``threshold`` is the overlap percentage (of the smaller paper) at or above
    which a pair is called out.  Returns a dict with the offending ``pairs``,
    counts, and a printable ``text`` block; a single paper is a no-op.
    """
    papers = list(papers or [])
    fps = [_item_fingerprints(p) for p in papers]
    pairs = []
    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            a, b = fps[i], fps[j]
            if not a and not b:
                continue
            shared = a & b
            denom = min(len(a), len(b)) or 1
            pct = round(100.0 * len(shared) / denom, 1)
            if pct >= float(threshold):
                pairs.append({
                    "a": i, "b": j, "overlap_pct": pct,
                    "shared": len(shared), "total": denom,
                })
    over = len(pairs)
    all_shared = set()
    for k in range(len(fps)):
        for m in range(k + 1, len(fps)):
            all_shared |= (fps[k] & fps[m])
    lines = []
    if len(papers) < 2:
        lines.append("Repeat check — only one paper, nothing to compare.")
    else:
        header = (f"Repeat check — {len(papers)} papers, "
                  f"flag at ≥{threshold}% shared items")
        if over:
            lines.append(header)
            lines.append(f"  !! {over} pair(s) reuse too many items:")
            for pr in pairs:
                lines.append(
                    f"     paper #{pr['a'] + 1} vs #{pr['b'] + 1}: "
                    f"{pr['overlap_pct']}%  ({pr['shared']}/{pr['total']} items) "
                    f"- pick a different seed or difficulty")
        else:
            lines.append(header)
            lines.append("  OK - every pair is below the threshold.")
    return {
        "pairs": pairs,
        "over_threshold": over,
        "threshold": threshold,
        "shared_items": len(all_shared),
        "papers": len(papers),
        "text": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Round 32 (F1): OMR bubble answer grid
# ---------------------------------------------------------------------------
def omr_grid(paper) -> dict:
    """Bubble-sheet layout for a whole class at once.

    Every question gets one row; MCQ rows get A-D bubbles (A is the "not
    answered" column a scanner uses to spot a skipped row), word-completion and
    writing rows get a single digit box since they are scored by hand.  Rows
    are chunked into ``columns`` of at most ``ROWS_PER_COLUMN`` so a
    35-question Year 1 paper still fits one page in two columns.
    """
    # The sheet renders as a single table (see docx.omr_sheet_doc); a 35-row
    # Year 1 sheet still lands on one page.  ``columns`` therefore stays 1 --
    # reporting 2 for Y1/Y2 would claim a two-column layout the renderer never
    # draws.  ROWS_PER_COLUMN is the budget the renderer is held to.
    ROWS_PER_COLUMN = 55
    questions: list[dict] = []
    for p in paper.parts:
        for i, item in enumerate(p.items):
            qno = p.qfirst + i
            if isinstance(item, MCQItem):
                kind = "mcq"
                bubbles = 4
                labels = ["A", "B", "C", "D"]
            elif isinstance(item, WordItem):
                kind = "word"
                bubbles = 1
                labels = ["0-9"]
            else:
                kind = "write"
                bubbles = 1
                labels = ["score"]
            questions.append({
                "qno": qno, "part": p.num, "kind": kind,
                "bubbles": bubbles, "labels": labels,
                "marks": (p.marks / len(p.items)) if p.items else 0.0,
            })
    n = len(questions)
    columns = 1
    rows_needed = n
    return {
        "year": paper.year(), "questions": questions,
        "columns": columns, "rows_needed": rows_needed,
        "rows_per_column": ROWS_PER_COLUMN,
        "total_marks": D.TOTAL,
        "fits_one_page": rows_needed <= ROWS_PER_COLUMN,
    }


def omr_mark_text(paper, answers: dict[int, str]) -> str:
    """Score an OMR read-out against the key; ``answers`` maps qno -> 'A'..'D'.

    Returns a human summary of the score plus any unreadable rows, so a
    teacher can sanity-check a scan before entering marks.
    """
    grid = omr_grid(paper)
    key = {int(k[0]): k[1] for k in paper.key}
    correct = wrong = blank = 0
    unread = []
    for q in grid["questions"]:
        qno = q["qno"]
        if q["kind"] != "mcq":
            continue
        ans = str(answers.get(qno, "") or "").strip().upper()
        if not ans:
            blank += 1
            continue
        exp = str(key.get(qno, "") or "").strip()
        if len(exp) > 1:
            exp = exp[:1].upper()
        if ans not in ("A", "B", "C", "D"):
            unread.append(qno)
            continue
        if exp and ans == exp:
            correct += 1
        else:
            wrong += 1
    total = correct + wrong
    pct = (100.0 * correct / total) if total else 0.0
    lines = [f"OMR read-out - Year {paper.year()}",
             f"  scored      : {total}",
             f"  correct     : {correct}",
             f"  wrong       : {wrong}",
             f"  blank       : {blank}",
             f"  percentage  : {pct:.1f}%"]
    if unread:
        lines.append(f"  UNREADABLE  : {', '.join(str(n) for n in unread)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Round 33 (F3): what difficulty actually did to a paper
# ---------------------------------------------------------------------------
def difficulty_profile(paper) -> dict:
    """Report the structural demand of a paper, for verification or the GUI.

    Makes visible the thing Round 33 changed: the writing word band and the
    ruled space both move with difficulty, so "hard" is a different paper to
    sit rather than the same paper with harder words in it.
    """
    import re as _re
    year = paper.year()
    words = 0
    lines = 0
    word_band = None
    for p in paper.parts:
        if p.kind != "writing":
            continue
        m = _re.search(r"between (\d+) and (\d+) words", str(p.lead))
        if m and not word_band:
            word_band = (int(m.group(1)), int(m.group(2)))
            words = int(m.group(1))
        for it in p.items:
            lines += int(getattr(it, "lines", 0) or 0)
    vocab = []
    for p in paper.parts:
        if p.kind == "vocab":
            for it in p.items:
                stem = str(getattr(it, "stem", "") or "")
                vocab.append(_dl_score(stem))
    avg = (sum(vocab) / len(vocab)) if vocab else 0.0
    return {
        "year": year,
        "difficulty": str(paper.meta.get("difficulty", "medium")),
        "writing_words": words,
        "writing_band": word_band,
        "writing_lines": lines,
        "vocab_complexity": round(avg, 3),
        "questions": paper.max_qno(),
        "marks": sum(p.marks for p in paper.parts),
    }


# ---------------------------------------------------------------------------
# Round 34 (F5): apply the teacher's locked items
# ---------------------------------------------------------------------------
def locked_keys(store: dict, year: int) -> set[str]:
    """Stems the teacher has locked for ``year`` (delegates to ``locks``)."""
    from . import locks
    return locks.locked_keys(store, int(year))


def apply_locks(paper, store: dict | None = None):
    """Return a new paper with the teacher's locked versions substituted in.

    Matching is by normalised original stem, so a lock survives a different
    seed, theme or difficulty.  ``answer`` is clamped to the option list, so a
    lock recorded against three options cannot produce an out-of-range index
    if the pool later changes.  A paper with no locks is returned unchanged.
    """
    from dataclasses import replace as _replace
    from . import locks
    if not store:
        return paper
    year = paper.year()
    year_locks = (locks.normalise(store).get(str(int(year))) or {})
    if not year_locks:
        return paper

    new_parts = []
    for part in paper.parts:
        items = []
        changed = False
        for item in part.items:
            stem = getattr(item, "stem", None) or getattr(item, "prompt", None)
            hit = year_locks.get(locks.key_for(stem or ""))
            if not hit:
                items.append(item)
                continue
            opts = list(hit.get("options") or getattr(item, "options", []) or [])
            if not opts:
                items.append(item)
                continue
            ans = hit.get("answer", getattr(item, "answer", 0))
            try:
                ans = int(ans)
            except (TypeError, ValueError):
                ans = 0
            ans = max(0, min(ans, len(opts) - 1))     # clamp: never out of range
            fields = {"options": opts, "answer": ans}
            if hit.get("stem"):
                fields["stem"] = str(hit["stem"])
            if "ans_text" in hit:
                fields["ans_text"] = hit["ans_text"]
            if isinstance(item, WriteItem):
                items.append(item)
                continue
            try:
                items.append(_replace(item, **fields))
                changed = True
            except TypeError:
                items.append(item)
        new_parts.append(_replace(part, items=items) if changed else part)
    return _replace(paper, parts=new_parts)
