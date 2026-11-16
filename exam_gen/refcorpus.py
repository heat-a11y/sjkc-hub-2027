"""Reference-corpus miner for the official UPSA/UASA 2026 papers.

Round 14.  Reads the SJKC English exam .docx files (or pre-stripped .txt
dumps) that a teacher keeps on disk — e.g. ``~/Downloads/exam2026`` — and
extracts, per SJKC year, the vocabulary words and Part 5 picture-word boxes
each paper actually uses.  The result is a structured JSON "reference corpus"
under the app data dir that webfetch / question construction can draw on, so
new papers stay grounded in the official exams.

Pure stdlib: a .docx is a zipped OOXML package, so we read
``word/document.xml`` directly and strip the tags (no python-docx dependency).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from . import data as D
import zipfile

APP_DATA = None   # resolved lazily (XDG_DATA_HOME or ~/.local/share)

# The five UASA papers a teacher keeps are PDFs, not .docx.  A .docx is a
# zipped OOXML package we can read directly, but PDF needs poppler's
# ``pdftotext`` — a plain stdlib parse of the binary format would be far too
# fragile.  Resolved once at import; every call site treats a missing binary
# as "this file has no text", so mining stays hermetic and offline-safe.
PDFTOTEXT = shutil.which("pdftotext")

REFERENCE_NAME = "reference.json"

# Words that carry no vocabulary signal in an exam header/instructions.
_STOP = frozenset(
    "the a an and or of to in on for is are was were be been am at by with "
    "from as it its this that these those i you he she we they my your his "
    "her our their me him us them not no so do does did will would can could "
    "should must have has had may might then than there here about after "
    "before choose correct answer each read text questions part question "
    "based above below study words write name class paper test pupil pupils "
    "subject exam english malay ujian bahasa inggeris mark marks minimum "
    "maximum between into out what when who where why how which other each "
    "teacher school".split())

# Boilerplate phrases that sit in every paper header/lead and must never count.
_BOILER = (
    "questions to", "for each question", "on your answer sheet",
    "read the text", "read the notes", "choose the correct",
    "based on the", "mark the correct", "the first letter",
    "there is one space", "one space for", "between and", "study the",
    "write an", "short essay", "academic session", "answer the",
)


def app_dir() -> str:
    """The app-data directory used by the rest of the project."""
    global APP_DATA
    if APP_DATA is None:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            APP_DATA = os.path.join(xdg, "exam-gen")
        else:
            cand = os.path.join(os.path.expanduser("~"), ".local", "share", "exam-gen")
            bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "materials", "2027")
            APP_DATA = cand if os.path.exists(os.path.join(cand, REFERENCE_NAME)) else (bundled if os.path.isdir(bundled) else cand)
    return APP_DATA


def pdftotext_available() -> bool:
    """True when poppler's ``pdftotext`` is on PATH (PDF papers are minable)."""
    return bool(PDFTOTEXT)


def _pdf_text(path: str) -> str | None:
    """Run ``pdftotext -layout`` on ``path`` (None if unavailable or it fails)."""
    if not PDFTOTEXT:
        return None
    try:
        proc = subprocess.run([PDFTOTEXT, "-layout", path, "-"],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "ignore") or None


def docx_text(path: str) -> str | None:
    """Extract the visible text of a .docx / .pdf / .txt (None on failure)."""
    low = path.lower()
    if low.endswith(".docx"):
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
        except (OSError, zipfile.BadZipFile, KeyError):
            return None
        xml = xml.replace("<w:tab/>", "\t").replace("</w:p>", "\n")
        return re.sub(r"<[^>]+>", "", xml)
    if low.endswith(".pdf"):
        return _pdf_text(path)
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


_YEAR_PATTERNS = (
    re.compile(r"(?i)\byear\s*_?([1-6])(?!\d)"),
    re.compile(r"(?i)\btahun\s*[t]?\s*([1-6])(?!\d)"),
    re.compile(r"(?i)\by([1-6])(?!\d)"),
    re.compile(r"(?i)\bt([1-6])(?!\d)"),
)


def guess_year(name: str) -> int | None:
    """Map a file name onto a supported SJKC year, else ``None``.

    The combined ``T5&6`` file counts as Year 5.  Year 4 is supported from
    Round 36, and ``Y4_UASA_2025.docx`` is the Year 4 reference paper.
    """
    base = os.path.basename(name)
    for pat in _YEAR_PATTERNS:
        m = pat.search(base)
        if m:
            y = int(m.group(1))
            return y if y in D.YEARS else None
    return None


def _split_parts(text: str) -> dict[int, str]:
    """Split exam text into ``{part_num: part_text}`` by ``PART n`` headers."""
    m = re.search(r"(?im)^\s*part\s*([1-7])\b", text or "")
    if not m:
        return {}
    parts: dict[int, str] = {}
    heads = [h for h in re.finditer(r"(?im)^\s*part\s*([1-7])\b", text or "")]
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        parts[int(h.group(1))] = text[h.start():end]
    return parts


def _tokens(line: str) -> list[str]:
    return re.findall(r"[a-z']{3,}", line.lower())


def _is_wordlist_line(line: str) -> bool:
    """True for a line that looks like a Part 5 picture-word box, e.g.
    ``elephant   lizard   spider   frog   duck``."""
    toks = _tokens(line)
    if not 3 <= len(toks) <= 12:
        return False
    return not any(t in _STOP for t in toks)


def _top_words(text: str, cap: int = 24) -> list[str]:
    """Frequency-ranked vocabulary words in ``text`` (boilerplate removed)."""
    low = text.lower()
    for b in _BOILER:
        low = low.replace(b, " ")
    freq: dict[str, int] = {}
    order: list[str] = []
    for t in (_tokens(low)):
        tok = t.strip("'")
        if not tok or tok in _STOP:
            continue
        if tok.endswith("'s") and len(tok) > 3:
            tok = tok[:-2]
        if tok not in freq:
            freq[tok] = 0
            order.append(tok)
        freq[tok] += 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], order.index(kv[0])))
    return [w for w, _ in ranked[:cap]]


def mine_doc(path: str) -> dict | None:
    """Mine one paper file into a small per-part vocabulary summary."""
    text = docx_text(path)
    if not text:
        return None
    parts = _split_parts(text)
    mined: list[dict] = []
    for num, body in sorted(parts.items()):
        entry: dict = {"num": num, "words": _top_words(body)}
        if num == 5:
            # Part 5 picture-word boxes appear either as a spaced word list on
            # one line ("elephant  lizard  spider  frog  duck") or as one word
            # per line.  Instruction / question-number lines never qualify.
            pw: list[str] = []
            for line in body.splitlines():
                toks = _tokens(line)
                if not (1 <= len(toks) <= 12):
                    continue
                if any(t in _STOP for t in toks):
                    continue
                if re.match(r"^\s*[0-9(]", line):
                    continue
                for w in toks:
                    if w not in pw:
                        pw.append(w)
            entry["picture_words"] = pw[:12]
        mined.append(entry)
    return {"source": os.path.basename(path), "parts": mined}


_PAPER_EXTS = (".docx", ".pdf", ".txt")


def _paper_files(docs_dir: str) -> list[str]:
    """Every ``.docx`` / ``.pdf`` / ``.txt`` under ``docs_dir``, recursively.

    The scan recurses because a teacher organises the set by sub-folder
    (``exam2026/paper/``, ``exam2026/2025/``) rather than dumping every paper in
    one flat directory.  Deeper nesting is followed to a bounded depth so an
    accidental walk of a whole home directory cannot hang the GUI.
    """
    found: list[str] = []
    root = os.path.abspath(docs_dir)
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel.count(os.sep) >= 2:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.lower().endswith(_PAPER_EXTS):
                found.append(os.path.join(dirpath, name))
    return found


def mine_dir(docs_dir: str) -> dict:
    """Mine every ``*.docx`` / ``*.pdf`` / ``*.txt`` paper under ``docs_dir``.

    Returns ``{year: {"year": year, "source": fname, "parts": [...]}}``.  A
    year with several papers keeps the one with the most mined parts, so a
    thin or partly-OCR'd file cannot shadow a good one.
    """
    out: dict = {}
    if not os.path.isdir(docs_dir):
        return out
    for path in _paper_files(docs_dir):
        year = guess_year(os.path.basename(path))
        if year is None:
            continue
        info = mine_doc(path)
        if not info:
            continue
        info["year"] = year
        prev = out.get(year)
        if prev is None or _mine_rank(info) > _mine_rank(prev):
            out[year] = info
    return out


def _mine_rank(info: dict) -> tuple:
    """Sort key deciding which paper represents a year.

    A structured ``.docx`` is parsed from OOXML with real line breaks, so its
    Part 5 picture-word box comes out clean; ``pdftotext -layout`` output is
    column-formatted and its "word list" lines are prose, so a PDF must not
    shadow an equally-complete .docx for the same year.
    """
    parts = info.get("parts") or []
    pics = next((p.get("picture_words") for p in parts
                 if p.get("num") == 5), None) or []
    structured = 0 if str(info.get("source", "")).lower().endswith(".pdf") else 1
    return (len(parts), structured, min(len(pics), 5))


def save_report(data: dict, out_dir: str | None = None) -> str:
    """Persist the corpus under the app data dir (or ``out_dir``)."""
    path = os.path.join(out_dir or app_dir(), REFERENCE_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({str(k): v for k, v in data.items()},
                  fh, ensure_ascii=False, indent=2)
    return path


def load_report(path: str | None = None) -> dict:
    """Read a saved corpus, normalising year keys back to ``int``."""
    path = path or os.path.join(app_dir(), REFERENCE_NAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    out: dict = {}
    for k, v in data.items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            continue
    return out


def summarize(data: dict) -> str:
    """Human-readable accounting of a mined corpus."""
    lines: list[str] = []
    for year in sorted(data):
        info = data[year]
        parts = info.get("parts") or []
        words = sorted({w for p in parts for w in p.get("words", [])})
        pics = sorted({w for p in parts for w in p.get("picture_words", [])})
        lines.append(
            f"Year {year}: {info.get('source', '?')} — {len(parts)} parts, "
            f"{len(words)} vocab words, {len(pics)} picture words")
        if pics and year in (1, 2, 3):
            lines.append(f"Year {year} Part 5 pictures: {', '.join(pics)}")
    return "\n".join(lines) or "No usable papers found."