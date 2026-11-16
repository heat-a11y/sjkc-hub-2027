"""Data model for a generated exam paper.

A Paper is a list of Parts.  Each Part holds typed items; the DOCX and HTML
renderers and the answer-key builder all consume this same model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MCQItem:
    """Multiple-choice item (Parts 1-4 and choice-style Part 5).

    For matching (Part 4) the options are simply the letters A/B/C and the
    three short texts are carried in ``part.lead_text``.  For a cloze part the
    gapped passage is carried in ``part.lead_text`` and each item targets one
    blank.  ``wordbox`` shows a bank of words above the question.

    Part 1 is the official short-stimulus format: ``stimulus`` holds the
    poster / menu / email / form the pupil reads, one string per printed line,
    and ``stem`` is the question asked about it.  Every Part 1 option is the
    same kind of thing (see ``data.PART1_SETS``), so the question is decided by
    reading the stimulus rather than by spotting an absurd distractor.
    """
    stem: str
    options: list[str]
    answer: int                       # index into options
    wordbox: list[str] | None = None
    lead: str | None = None           # optional per-question text
    ans_text: str | None = None       # override for the key (e.g. the word)
    stimulus: list[str] | None = None  # Part 1: the short text being read

    @property
    def answer_label(self) -> str:
        return ("ABCDEFGH"[self.answer] if self.answer < 8 else str(self.answer + 1))


@dataclass
class WordItem:
    """Fill-the-word item (Part 5, the ministry spelling task).

    The clue describes the word and the pupil writes it out, one underscore per
    letter.  Year 4-6 give the first letter ("c o u g h"); Year 1-3 blank every
    letter, so ``first`` is empty there -- see SPEC 57.
    """
    clue: str
    first: str
    length: int
    answer: str
    wordbox: list[str] | None = None

    @property
    def pattern(self) -> str:
        if not self.first:
            return " _ " * self.length
        return self.first + " _ " * (self.length - 1)


@dataclass
class WriteItem:
    """Writing item (Parts 6-7): sentences, letters, essays or emails."""
    prompt: str
    example: str | None = None
    bullets: list[str] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    lines: int = 4
    model: str = ""
    marks: int = 0
    salutation: str = ""     # letter opener, e.g. "Dear Fiona,"
    subject: str = ""        # email subject line, e.g. "My Hobby"
    recipient: str = ""      # email address, e.g. "fiona@email.com"
    closing: str = ""        # letter sign-off, e.g. "Your friend,"
    word_count: str = ""     # e.g. "30 - 50 words" (rendered as an instruction)


@dataclass
class Part:
    num: int
    kind: str
    style: str
    marks: int
    title: str                # "PART 1"
    lead: str                 # BM/EN instruction sentence(s)
    items: list = field(default_factory=list)   # list[MCQItem | WordItem | WriteItem]
    lead_text: str | None = None                # passage / matching texts / word box
    qfirst: int = 1            # question number of the first item
    topic: str = ""            # art topic id for the part illustration ('' = none)
    photo_query: str = ""      # Wikimedia Commons subject for the part photo ('' = SVG)
    lines: int | None = None   # answer-sheet ruled lines ('' = year default, writing parts)
    example: str | None = None  # worked example line (Part 4 shows one, "0. ...")
    source_theme: str = ""     # RPT theme of the passage actually used (P3)
    source_title: str = ""     # that passage's own title, for the JSU (P3)

    def qnos(self) -> list[int]:
        return list(range(self.qfirst, self.qfirst + len(self.items)))

    def marks_per_q(self) -> float:
        if not self.items:
            return 0.0
        return self.marks / len(self.items)


@dataclass
class Paper:
    meta: dict
    parts: list[Part] = field(default_factory=list)
    key: list[tuple[int, str, str]] = field(default_factory=list)  # (qno, answer, note)
    marks_table: list[tuple[str, int, int]] = field(default_factory=list)  # (label, marks, got)

    def max_qno(self) -> int:
        return max((p.qfirst + len(p.items) - 1 for p in self.parts), default=0)

    def year(self) -> int:
        return int(self.meta.get("year", 1))

    def duration(self) -> str:
        from . import data as D
        return self.meta.get("duration") or D.DURATION.get(self.year(), "")