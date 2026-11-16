"""QC watchdog (Round 20/F37).

The generator grades its own output the way a teacher would, and the teacher's
own reference copies (``~/Downloads/exam2026``) are the oracle: an issue code
that DOES appear in a real reference paper is tolerated for generated papers;
anything else is a hard failure. ``bank.generate_clean`` re-rolls parts
(corpus → no-textbook → no-web) until a paper carries **zero** hard issues,
and the CLI ``--check`` / ``--check-teacher`` audit a directory of saved
papers like a smoke door.

Per-kind scope (the teacher's papers decide what "hard" means):

* vocab / cloze  — options never re-invent stem words (no ``rain`` next to
  "Rain clouds gathered …"), are never mixed- or all-CAPS, and Y3/Y5 gaps offer
  the three forms of *one* verb ("cook / cooks / cooking", never a category
  flip "doctor / nurse / farmer").
* cloze / comprehension — the passage is declarative: no dialogues
  ("Did you see that documentary about eafing last night?"), no worksheet
  instructions ("Read and listen to the text again."), no OCR debris
  ("got up at & a.m.").
* comprehension / match / words — a stem may *legitimately* reuse passage
  words ("What does Mei Ling bring to school?" → "her school bag"), so the
  leak, casing and digit rules are deliberately scoped to vocab/cloze only.

Structural sanity (counts per part) is re-checked here so the watchdog is
self-contained; ``paper_compliance`` also surfaces this report.
"""

from __future__ import annotations

import glob
import html
import os
import re
import zipfile

from . import bank
from . import data as D

_INSTRUCTION_WORDS = {
    "read", "listen", "look", "match", "tick", "choose", "write", "draw",
    "colour", "color", "answer", "complete", "fill", "copy", "practise",
    "practice", "circle", "underline", "find", "name", "count", "unscramble",
    "study", "remember", "retell", "label", "number", "order", "sort",
    "trace", "repeat", "chant", "sing", "check", "both", "dictation",
    "follow", "retell",
}

_IRREG_BASES = {"has": "have", "having": "have", "had": "have",
                "is": "be", "am": "be", "are": "be", "was": "be",
                "were": "be", "been": "be", "being": "be",
                "does": "do", "doing": "do", "did": "do",
                "goes": "go", "going": "go", "went": "go", "gone": "go",
                "says": "say", "saying": "say", "said": "say",
                "gets": "get", "getting": "get", "got": "get",
                "makes": "make", "making": "make", "made": "make",
                "takes": "take", "taking": "take", "took": "take"}

# Rules enforced against parsed *reference* items.  Teacher papers bring their
# own licence (mixed-case cloze options, Title-Case phrases), so the
# casing/triplet/repeat rules never fire against a reference copy.
_REFERENCE_CODES = {"option-dup", "stem-empty", "stem-noise", "option-leak",
                    "digit", "blank-count", "count-mismatch",
                    "write-topic", "write-notes", "write-words",
                    "write-template"}

_WRITE_TOPIC_RE = re.compile(r"(?i)wants to know about\s+([^.]+?)\s*[.]"
                             r"|tell your friend about\s+([^.]+?)\s*[.,]")
_WRITE_WORDS_RE = re.compile(r"(?i)use the words?:\s*([^.]+?)[.]")
# required "use the words" that are function words, never content vocabulary
_WRITE_WORDS_WEAK = {"some", "every", "each", "still", "get", "got", "one",
                     "two", "three", "etc", "also", "very", "really", "just",
                     "more", "most", "new", "time", "people"}


def _verb_base(w):
    """Lemma shared by the three gap forms ("cook / cooks / cooking" → cook)."""
    w = str(w).lower().strip()
    if w in _IRREG_BASES:
        return _IRREG_BASES[w]
    w = re.sub(r"(ies)$", "y", w)
    w = re.sub(r"(ing|es|s)$", "", w)
    if len(w) > 2 and w[-1] == w[-2]:
        w = w[:-1]
    return w.rstrip("e")


def _bullet_text(item) -> str:
    """Flatten an item's bullet/notes list into a single string."""
    bullets = _get(item, "bullets") or []
    if isinstance(bullets, str):
        return " " + bullets
    return " " + " ".join(str(b) for b in bullets)


def _write_issues(text) -> list:
    """Part 6/7 writing-prompt rules (Round 21).

    A writing prompt is not an MCQ, so it is graded by text coherence:
    the topic must be a plain noun phrase (never "about Read A Newspaper
    Article"), a note must not ask the pupil to define a random word, and
    "Use the words: X, Y, Z." must list content vocabulary, never "some".
    """
    text = text or ""
    issues = []
    if ("wants to know about" in text.lower()
            or "why you chose the words" in text.lower()
            or "what word you chose" in text.lower()):
        issues.append(QCIssue(
            "write-template",
            "old Part 6/7 scaffold (\"wants to know about X ... why you "
            "chose the words\") — a writing prompt must be a concrete "
            "scenario with a notes table, like the official papers"))
    m = _WRITE_TOPIC_RE.search(text)
    if m:
        topic = (m.group(1) or m.group(2) or "").strip()
        if topic and not bank.valid_writing_topic(topic):
            issues.append(QCIssue(
                "write-topic",
                f"writing topic {topic!r} is a method/skill label, not a "
                "subject a pupil can write about"))
    if "what the word '" in text.lower():
        issues.append(QCIssue(
            "write-notes",
            "a note asks for the meaning of a random word "
            "(\"what the word 'X' means\") unrelated to the topic"))
    m = _WRITE_WORDS_RE.search(text)
    if m:
        for tok in re.split(r"[,/]", m.group(1)):
            tok = tok.strip(" .")
            if tok and (len(tok) < 3 or tok.lower() in _STOPWORDS
                        or tok.lower() in _WRITE_WORDS_WEAK):
                issues.append(QCIssue(
                    "write-words",
                    f"required writing word {tok!r} is not content "
                    "vocabulary"))
                break
    return issues


class QCIssue:
    __slots__ = ("code", "message", "hard")

    def __init__(self, code: str, message: str, hard: bool = True):
        self.code = code
        self.message = message
        self.hard = hard

    def __repr__(self):                      # pragma: no cover - debug aid
        return f"<QC {self.code}{'!' if self.hard else ':'} {self.message}>"


class QCReport:
    """Aggregated verdict: a ``score`` out of 10 plus the machine list."""

    def __init__(self, issues=None):
        self.issues = list(issues or [])

    @property
    def hard(self):
        return sum(1 for i in self.issues if i.hard)

    @property
    def soft(self):
        return sum(1 for i in self.issues if not i.hard)

    @property
    def score(self):
        s = 10.0 - 1.5 * self.hard - 0.5 * self.soft
        return round(max(0.0, min(10.0, s)), 1)

    def as_dict(self):
        return {"score": self.score, "hard": self.hard, "soft": self.soft,
                "issues": [(i.code, i.hard, i.message)
                           for i in self.issues]}


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _mcq_options(item):
    """Opts may be keyed ``options`` (MCQItem) or ``opts`` (raw bank dicts)."""
    if isinstance(item, dict):
        return item.get("opts", item.get("options", None))
    return getattr(item, "options", None)


_STOPWORDS = {"a", "an", "the", "it", "he", "she", "they", "we", "you", "i",
              "to", "on", "in", "at", "of", "and", "or", "for", "with",
              "by", "from", "have", "has", "do", "does", "did", "is", "am",
              "are", "was", "were", "be", "that", "this", "his", "her",
              "their", "there", "here", "my", "your", "its"}


def _first_alpha(s):
    m = re.search(r"[A-Za-z]", str(s or ""))
    return m.group() if m else ""


def _legit_caps(o):
    """True when an option's leading capital is a legitimate proper noun /
    festival / place / acronym from the pools (``D.LEGIT_OPTION_CAPS``) — the
    teacher prints ``Kuala Lumpur``, ``Chinese New Year`` and ``LRT`` beside
    lowercase distractors, so these never count toward a mixed-case failure."""
    o = str(o or "").strip()
    if o in D.LEGIT_OPTION_CAPS:
        return True
    # a bare all-caps acronym (LRT, KLIA) is allowed even without the list.
    if re.fullmatch(r"[A-Z]{2,6}", o or ""):
        return True
    # Round 26: a price written the way the teacher prints it — a currency
    # code then a number, "RM180", "USD2.50" — is a legitimate capital, not a
    # shouted option.  The code must be a known one so "ABC12" is still
    # caught.  "RM" is included although it is a symbol rather than an ISO
    # code, because it is how every Malaysian school paper writes ringgit.
    m = re.fullmatch(r"([A-Z]{2,3})\s?[\d.,]+", o or "")
    return bool(m) and m.group(1) in D.CURRENCY_CODES


def _int(year):
    try:
        return int(year)
    except (TypeError, ValueError):
        return None


def check_item(item, kind: str, year="", reference: bool = False,
               parsed: bool = False):
    """Grade one MCQ against the teacher's bar for that part kind.

    ``parsed`` marks items recovered from a .docx's page layout: a cloze
    "stem" there is really the whole gapped passage, so the leak/stem rules
    must not fire on presentation lines.
    """
    issues = []
    if isinstance(item, bank.WriteItem):
        return _write_issues(" ".join(str(_get(item, "prompt") or "")
                                    + _bullet_text(item)))
    if isinstance(item, bank.WordItem):
        clue = str(_get(item, "clue") or "").strip()
        if not clue:
            issues.append(QCIssue("stem-empty", "clue line is empty"))
        elif not bank._stem_admits(clue, _int(year)):
            issues.append(QCIssue("stem-noise", "clue reads like OCR debris"))
        return issues
    if kind == "writing":
        items = [str(_get(item, "stem") or ""),
                 str(_get(item, "prompt") or ""),
                 str(_get(item, "lead_text") or "")]
        return _write_issues(" ".join(t for t in items if t)
                             + _bullet_text(item))
    stem = str(_get(item, "stem") or "").strip()
    opts = [str(o).strip() for o in (list(_mcq_options(item) or []))]
    opts = [o for o in opts if o and not re.match(r"^[A-D]$", o)]
    y = _int(year)

    # -- scope-dependent rules ---------------------------------------------
    cloze_presentation = parsed and kind == "cloze" and len(stem) > 90
    if kind in ("vocab", "cloze") and not cloze_presentation:
        blanks = re.findall(r"_{2,}", stem)
        if blanks and len(blanks) != 1:
            issues.append(QCIssue(
                "blank-count", f"{len(blanks)} visible blanks; a gap has one"))
        # An option that is *nothing but* a digit is a subject-code / OCR
        # artifact.  A number inside an option is ordinary content and the
        # teacher prints it: "RM180", "3 km", "40 pages", "12 March".  The old
        # test joined the options and matched any whitespace-delimited digit,
        # so it failed every reading option that mentioned a quantity.
        if opts and any(re.fullmatch(r"[0-9]+", o.strip()) for o in opts):
            issues.append(QCIssue(
                "digit", "an option is a bare digit (subject-code or OCR "
                         "artifact)"))
    if stem and not cloze_presentation:
        # a leading blank is how a teacher writes a stem that starts with the
        # gap ("__________ is a good hobby…") — not OCR debris
        stem_noise_ok = bool(parsed and re.match(r"^_{2,}", stem))
        if not bank._stem_admits(stem, y) and not stem_noise_ok:
            issues.append(QCIssue("stem-noise", "stem reads like OCR debris"))
        if kind == "vocab" and not reference and not parsed:
            stem_toks = set(re.findall(
                r"[a-z']+", re.sub(r"_+", " ", stem).lower()))
            stem_toks -= _STOPWORDS
            for o in opts:
                if any(t in stem_toks
                       for t in set(re.findall(r"[a-z']+", o.lower()))
                       - _STOPWORDS):
                    issues.append(QCIssue(
                        "option-leak", f"option {o!r} reuses a stem word"))
    if not stem and opts:
        issues.append(QCIssue("stem-empty",
                              "question parsed with options but no stem"))
    if len({o.casefold() for o in opts}) != len(opts):
        issues.append(QCIssue("option-dup", "duplicate options offered"))
    if kind in ("vocab", "cloze") and not reference and opts:
        # legit heads: proper nouns / festivals / places / acronyms (teacher
        # papers use them), so only a *common word* whose first letter is
        # capitalised for no reason is a mixed-case hard failure.
        ups = sum(1 for o in opts
                  if _first_alpha(o).isupper()
                  and not _legit_caps(o))
        lows = sum(1 for o in opts if _first_alpha(o).islower())
        if ups and lows:
            issues.append(QCIssue(
                "option-case", "options mix upper- and lower-case styles"))
        elif ups and not lows and all(len(_first_alpha(o)) for o in opts) \
                and not any(re.search(r"[a-z]", o) for o in opts):
            issues.append(QCIssue(
                "option-case", "options are shouted in ALL-CAPS"))
    if kind == "cloze" and y in (3, 5) and len(opts) == 3 and not reference:
        if len({_verb_base(o) for o in opts}) > 1:
            issues.append(QCIssue(
                "gap-triplet", "the three options are not one verb's forms"))
    return issues


# Passage-level noise is deliberately narrower than bank._OCR_NOISE: a colon
# or bracket is ordinary English inside a reading text, and a PASSAGE is not an
# option line.  What is never teacher-like in a passage: OCR ellipses / fused
# doubled marks / ampersands / splash-dashes / the classic scanner residues.
_PASSAGE_NOISE = re.compile(
    r"…|\.{3,}|'{2,}|``|,{2,}|\||--|->|\u2014"
    r"|alot|doesmt|doesnt|dossent|donesn|&|\s-\s")


def _passage_issues(lead_text, issues):
    """A cloze / comprehension passage is declarative narrative: no dialogue,
    no worksheet instructions, no OCR debris (the teacher never prints those).
    Gap markers ``(6)______`` are stripped first so the blanks themselves are
    not misread as noise."""
    t = (lead_text or "").strip()
    if not t:
        return
    t = re.sub(r"\(\d+\)\s*_{2,}", "", t)
    t = re.sub(r"_{2,}\s*", "", t)
    if _PASSAGE_NOISE.search(t):
        issues.append(QCIssue("passage-ocr",
                              "the passage still carries OCR debris (dialogue "
                              "or scanned glue)"))
    for sent in re.split(r"(?<=[.!?])\s+", t):
        sent = sent.strip()
        if not sent:
            continue
        if "?" in sent or "!" in sent:
            issues.append(QCIssue(
                "passage-dialogue",
                f"passage line is a dialogue/instruction: {sent[:60]!r}"))
            continue
        m = re.match(r"[A-Za-z]+", sent)
        if m and m.group().lower() in _INSTRUCTION_WORDS:
            issues.append(QCIssue(
                "passage-dialogue",
                f"passage line starts like a worksheet drill: {sent[:60]!r}"))


def _spec(year, num):
    specs = {s["id"]: s for s in D.PARTS.get(_int(year) or 0, [])}
    return specs.get(num)


def mapping_balance_issues(part) -> list[str]:
    """How a Part 4 block's answers are spread over the letters A, B and C.

    Accepts a Part or anything with ``items`` whose ``options`` are the three
    letters, so it works on a generated paper and on a parsed .docx alike.
    """
    labels = []
    for it in list(_get(part, "items") or []):
        opts = list(_mcq_options(it) or [])
        if [str(o).strip().upper() for o in opts] != ["A", "B", "C"]:
            continue
        labels.append("ABC"[int(_get(it, "answer", 0) or 0)])
    return bank._answer_balance(labels)


def _part1_stimulus_issues(part, items) -> list[str]:
    """Part 1 must ask a question about a stimulus, and every option must be
    traceable to that stimulus (or be a declared confusion-set sibling).

    The pool authors each item with a ``set`` key from ``data.PART1_SETS``;
    at QC time we only have the rendered item, so the check is: the answer
    word appears in the stimulus, and every distractor is a real phrase (not
    a bare noun from an unrelated category).  An item that is a gap-fill
    cloze — which is what the "TRAVEL TIP / suitcase / planet / hotel" drift
    produced — has no stimulus and is reported.
    """
    out = []
    for i, it in enumerate(items, 1):
        stim = list(_get(it, "stimulus") or [])
        stem = str(_get(it, "stem") or "")
        if not stim:
            out.append(
                f"Q{i} has no stimulus — Part 1 is a short-text question, not "
                f"a gap-fill cloze (stem starts {stem[:40]!r})")
            continue
        opts = list(_mcq_options(it) or [])
        ans = _get(it, "answer", 0)
        if opts and isinstance(ans, int) and 0 <= ans < len(opts):
            answer = str(opts[ans])
            blob = " ".join(stim).casefold()
            if answer.casefold() not in blob:
                out.append(
                    f"Q{i} answer {answer!r} is nowhere in the stimulus — the "
                    f"question cannot be answered from the text")
    return out


def check_part(part, year="", reference: bool = False) -> QCReport:
    issues = []
    num = int(_get(part, "num") or 0)
    kind = str(_get(part, "kind") or "")
    items = list(_get(part, "items") or [])
    spec = _spec(year, num) if year else None
    if spec and len(items) != spec["count"]:
        issues.append(QCIssue(
            "count-mismatch",
            f"PART {num} has {len(items)} question(s); the format needs "
            f"{spec['count']}"))
    if kind in ("cloze", "comprehension"):
        _passage_issues(str(_get(part, "lead_text") or ""), issues)
    if kind == "match":
        for msg in mapping_balance_issues(part):
            issues.append(QCIssue("answer-balance", f"PART {num}: {msg}",
                                  hard=False))
    if kind == "vocab" and year >= 5:
        # Round 26: Years 5-6 Part 1 was rebuilt in the official short-stimulus
        # shape, so the hard rule applies there.  Years 1-3 still use the older
        # gap-fill shape (documented as a follow-up in SPEC.md) and are not
        # policed yet, so no existing junior paper is failed by this rule.
        for msg in _part1_stimulus_issues(part, items):
            issues.append(QCIssue("part1-stimulus", f"PART {num}: {msg}",
                                  hard=True))
    for item in items:
        issues += check_item(item, kind, year, reference, parsed=False)
    if len(items) >= 3:
        counts = {}
        for it in items:
            ap = str(_get(it, "ans_text") or "").strip()
            opts = list(_mcq_options(it) or [])
            if not ap and opts:
                ap = opts[_get(it, "answer", 0)]
            ap = re.sub(r"\W+", "", ap).casefold()
            if ap:
                counts[ap] = counts.get(ap, 0) + 1
        if counts and max(counts.values()) >= (len(items) + 1) // 2:
            issues.append(QCIssue(
                "answer-repeat",
                f"one answer ({max(counts, key=counts.get)!r}) is asked for "
                f"{max(counts.values())}× in the same part", hard=False))
    return QCReport(issues)


def check_paper(paper, reference: bool = False) -> QCReport:
    issues = []
    meta = _get(paper, "meta") or {}
    for p in _get(paper, "parts") or []:
        issues += check_part(p, meta.get("year"), reference).issues
    return QCReport(issues)


# ---------------------------------------------------------------------------
# Consuming real .docx files: the teacher's reference copies and saved papers.
# ---------------------------------------------------------------------------

def _docx_lines(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    lines = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, flags=re.S))
        t = html.unescape(t).replace("\u00a0", " ").strip()
        if t:
            lines.append(t)
    return lines


_HEADER_RE = re.compile(
    r"^(PART\s*\d|BAHAGIAN|MARKAH|JUMLAH|NAMA|KELAS|PEMERIKSA|UJIAN|"
    r"BAHASA|SESI|SULIT|SKEMA|UNTUK|INSTRUCTIONS)", re.I)


def _year_from(lines, path=""):
    m = re.search(r"(?:Year|Tahun|YEAR)?\s*[YT]\s*([1-6])", path, re.I)
    if m:
        return int(m.group(1))
    for ln in lines[:12]:
        m = re.search(r"\b([1-6])\b", ln)
        if m:
            return int(m.group(1))
    return None


def _split_parts(lines):
    parts, cur = [], []
    for ln in lines:
        if re.match(r"^PART\s*\d", ln, re.I):
            if cur:
                parts.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        parts.append(cur)
    return parts


_QNO_RE = re.compile(r"^\s*(?:\(\s*\d+\s*\)|\d+\s*[.)])\s*")
_OPTL_RE = re.compile(r"^\s*(?:[A-Da-d]\s*[.)]|\d+\s*[.)])\s*")
_OPT_R = re.compile(r"\s*[.)]\s*$")


def _strip_qno(s):
    return _QNO_RE.sub("", s) if s else s


def _clean_opt(s):
    for _ in range(4):
        t = _OPTL_RE.sub("", s)
        if t == s:
            break
        s = t
    return _OPT_R.sub("", s)


def _extract_part(blk):
    """One PART block → ``(num, kind, lead_text, items)``.

    Mirror of the reference layout (and of our own generation): a stem is a
    line carrying a blank or ending in ``?``; the short lines that follow up to
    the next stem are its three options.  A raw parsed cloze "stem" is actually
    the gapped passage, so it is long and reported as lead text instead.
    Item numbers (``(1)``, ``6.``) and option letters (``A.``) are layout, not
    content, so they are stripped before any rule judges the text.
    """
    num = None
    m = re.match(r"^PART\s*(\d+)", blk[0], re.I)
    if m:
        num = int(m.group(1))
    kind = {1: "vocab", 2: "cloze", 3: "comprehension",
            4: "match", 5: "words", 6: "writing",
            7: "writing"}.get(num, "vocab")
    stem, opts = None, []
    items, lead = [], []
    for raw in blk[1:]:
        s = str(raw or "").replace("\u00a0", " ").strip()
        if not s or "<" in s or ">" in s:
            continue
        if _HEADER_RE.match(s):
            continue
        if re.match(r"^[A-D]\s*\.?\s*$", s) or re.match(
                r"^\(?(\d+)\)?\s*[.)]\s*$", s):
            continue
        if "@" in s or re.match(r"^[_.]+$", s) or ".com" in s:
            continue
        has_letters = bool(re.search(r"[A-Za-z]", s))
        tail = s[-1] if s else ""
        body = _strip_qno(s)
        is_stem = (body.endswith("?") and has_letters) or (
            ("____" in body or "___" in body) and has_letters
            and tail in ".?")
        if is_stem:
            if stem and len(opts) >= 2:
                items.append({"stem": stem, "opts": list(opts)})
            stem, opts = body, []
        elif not stem:
            lead.append(s)
        elif (len(opts) < 3 and len(s) <= 60
              and re.search(r"[A-Za-z]", s)
              and not s.endswith((".", "?"))
              and not re.match(r"^\d+$", s)
              and not re.match(r"^[A-Za-z]\s+(?:_+\s*)+$", s)):
            opts.append(_clean_opt(s))
        else:
            lead.append(s)
    if stem and len(opts) >= 2:
        items.append({"stem": stem, "opts": list(opts)})
    return num, kind, " ".join(lead), items


def _parse_docx(path):
    lines = _docx_lines(path)
    year = _year_from(lines, path)
    parts = []
    for blk in _split_parts(lines):
        num, kind, lead, items = _extract_part(blk)
        if items or lead:
            parts.append({"num": num, "kind": kind, "lead_text": lead,
                          "items": items})
    return year, parts


def _audit_docx(path, reference=False):
    """QCReport for a saved .docx; items are plain dicts, so every parsed
    question is graded by the same per-kind rules (``reference=True`` relaxes
    casing/triplet and keeps only the invariant codes)."""
    year, parts = _parse_docx(path)
    issues = []
    for p in parts:
        for it in p["items"]:
            for i in check_item(it, p["kind"], year, reference=reference,
                                parsed=True):
                if reference and i.code not in _REFERENCE_CODES:
                    continue
                issues.append(i)
        if p["kind"] == "writing" and (p["items"] or p["lead_text"]):
            for i in _write_issues(p["lead_text"]):
                if reference and i.code not in _REFERENCE_CODES:
                    continue
                issues.append(i)
    return QCReport(issues)


def audit_dir(path):
    """``--check DIR`` — every saved paper inside must be QC-hard clean."""
    reports = []
    for f in sorted(glob.glob(os.path.join(path, "*.docx"))):
        reports.append((os.path.basename(f), _audit_docx(f, reference=False)))
    return reports


def reference_issues(path):
    """``--check-teacher`` — the oracle: a teacher's copies must pass 100%.

    Only the invariant item rules are enforced here (leak / stem hygiene /
    duplicates / digits); casing and verb-triplet rules the generator pays are
    deliberately NOT applied to the teacher's own licence.
    """
    issues = []
    for f in sorted(glob.glob(os.path.join(path, "*.docx"))):
        year, parts = _parse_docx(f)
        for p in parts:
            for it in p["items"]:
                for i in check_item(it, p["kind"], year, reference=True,
                                    parsed=True):
                    if i.code in _REFERENCE_CODES and i.hard:
                        i.message = f"{os.path.basename(f)}: {i.message}"
                        issues.append(i)
    return issues