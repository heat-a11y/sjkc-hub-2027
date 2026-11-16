"""Textbook corpus miner — the SJKC pupil's textbooks are the SOLE reference.

Round 17.  The scanned English textbook PDFs a teacher keeps on disk
(``~/Downloads/exam2026/textbook_year*.pdf``: Years 1&2, 3, 4, 5, 6) are
OCRed into a per-year ``textbook_corpus.json`` under the app data dir.  Every
generated question (``bank.py``) then draws its content from that corpus; the
old hand-written pools and the web passages become a spare wheel.

The 2026 SJKC PDFs are pure scans (no text layer), so the pipeline is:
  1. ``pdftotext`` first — digital PDFs with an embedded layer need no OCR;
  2. otherwise ``pdftoppm`` renders each page and ``tesseract`` OCRs it;
  3. page text is cached under ``<appdata>/textbook_ocr/`` so the next run is
     offline.
Pure stdlib + the poppler/tesseract external binaries (the codebase already
uses ``soffice`` the same way).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile

CORPUS_NAME = "textbook_corpus.json"
OCR_SUBDIR = "textbook_ocr"

# Filename keyword -> SJKC years the book serves.  The app generates Years
# 1/2/3/5/6 (never Year 4); the Year 4 textbook is mined but unused.
FILE_YEARS = {
    "textbook_year1&2": (1, 2),
    "textbook_year3": (3,),
    "textbook_year4": (4,),
    "textbook_year5": (5,),
    "textbook_year6": (6,),
}

# Words that carry no vocabulary signal in an exam / exercise.
_STOP = frozenset(
    "the a an and or of to in on for is are was were be been am at by with "
    "from as it its this that these those i you he she we they my your his "
    "her our their me him us them not no so do does did will would can could "
    "should must have has had may might then than there here about after "
    "before read write listen say colour color look match circle draw cut "
    "paste stick choose correct answer each text questions part question "
    "based above below study words name class page unit lesson pupil pupils "
    "teacher school exam english malay ujian bahasa inggeris mark marks "
    "minimum maximum between into out what when where who why how which "
    "other sing song play listen".split())

# Lines that are textbook exercise instructions routinely OCR'd as their own
# line and carry no vocabulary signal (kept out of the word list but harmless
# as reading sentences).
_INSTRUCTION_RE = re.compile(
    r"^(listen|say|sing|read|look|write|colour|color|match|circle|draw|"
    r"choose|complete|count|point|tick|move|cut|paste|follow|speak|practise|"
    r"practice|work|remember|talk|repeat)\b", re.I)

_UNIT_HEAD_RE = re.compile(r"(?im)^\s*(?:starter\s+)?unit\s*[1-9][0-9]?")

# CJK characters (the SJKC books carry Chinese glosses) and OCR junk.
_MIXED = re.compile(r"[^\x00-\x7f]")


def app_dir() -> str:
    """The app-data directory used by the rest of the project.

    Not memoised: the hermetic tests retarget ``XDG_DATA_HOME`` mid-process.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return os.path.join(xdg, "exam-gen")
    cand = os.path.join(os.path.expanduser("~"), ".local", "share", "exam-gen")
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "materials", "2027")
    if not os.path.exists(os.path.join(cand, CORPUS_NAME)) and os.path.isdir(bundled):
        return bundled
    return cand


def corpus_path(out_dir: str | None = None) -> str:
    """Where ``textbook_corpus.json`` lives (or will live)."""
    return os.path.join(out_dir or app_dir(), CORPUS_NAME)


def ocr_dir() -> str:
    d = os.path.join(app_dir(), OCR_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# OCR pipeline
# ---------------------------------------------------------------------------

def _run(args: list[str], timeout: int = 240):
    """Run an external binary, returning (rc, stdout).  Never raises."""
    try:
        cp = subprocess.run(args, capture_output=True, text=True,
                            timeout=timeout)
        return cp.returncode, cp.stdout
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def _has_text(text: str) -> bool:
    """True when ``text`` has enough real words to be usable without OCR."""
    return len(re.findall(r"[A-Za-z]{3,}", text or "")) >= 15


def _strip_unit_heads(text: str) -> str:
    """Drop whole ``Unit N…`` header lines (they are not sentences)."""
    return "\n".join(
        ln for ln in (text or "").split("\n") if not _UNIT_HEAD_RE.match(ln))


def _pdftotext(pdf: str, first: int | None, last: int | None) -> str:
    args = ["pdftotext"]
    if first is not None and last is not None:
        args += ["-f", str(first), "-l", str(last)]
    args += [pdf, "-"]
    rc, out = _run(args)
    return out if rc == 0 else ""


def _tesseract(png: str) -> str:
    rc, out = _run(["tesseract", png, "stdout", "--dpi", "150", "-l", "eng"])
    return out or ""


def _render_and_ocr(pdf: str, first: int, last: int) -> list[str]:
    """Rasterize pages ``first..last`` with pdftoppm (in bounded chunks so one
    slow image page can't blow the whole book) and OCR each with tesseract.
    Returns one text blob per page (never raises)."""
    out: list[str] = []
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return out
    total = _page_count(pdf)
    if total <= 0:
        total = max(int(first), 60)     # pdfinfo missing — bounded guess
    last = min(last, total)
    chunk = 20
    for start in range(first, last + 1, chunk):
        stop = min(start + chunk - 1, last)
        with tempfile.TemporaryDirectory(prefix="tb_ocr_") as td:
            prefix = os.path.join(td, "pg")
            rc, _ = _run(["pdftoppm", "-f", str(start), "-l", str(stop),
                          "-r", "150", "-png", pdf, prefix], timeout=600)
            if rc != 0:
                continue        # nothing from this chunk; keep going
            pages = sorted(f for f in os.listdir(td) if f.endswith(".png"))
            for page in pages:
                out.append(_tesseract(os.path.join(td, page)))
    return out


def _ocr_file(_pdf: str, first: int | None, last: int | None) -> str:
    # cache per PDF (the same book serves two years in the SJKC set, e.g.
    # textbook_year1&2.pdf → years 1 and 2); the year is parsed later.
    stem = re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(_pdf))
    if stem.endswith("_"):
        stem = stem[:-1]
    name = stem + (f"_p{first}-{last}" if first is not None else "_full")
    return os.path.join(ocr_dir(), name + ".txt")


def _wordcount(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{3,}", text or ""))


def _page_count(pdf: str) -> int:
    rc, out = _run(["pdfinfo", pdf])
    if rc != 0:
        return 0
    for line in out.splitlines():
        if line.lower().startswith("pages:"):
            p = line.split(":", 1)[1].strip()
            if p.isdigit():
                return int(p)
    return 0


def ocr_pdf(pdf: str, year: int, first: int | None = None,
            last: int | None = None, force: bool = False) -> str:
    """Return the text of a textbook PDF for ``year``.

    Tries the embedded layer first; scanned PDFs fall back to tesseract.  A
    sparse extract (scans whose front-matter carries a digital text layer) is
    still OCR'd.  The result is cached on disk so every later run is offline.
    Empty string when nothing usable is recovered.
    """
    if not pdf or not os.path.exists(pdf) or not os.path.isfile(pdf):
        return ""
    cache = _ocr_file(pdf, first, last)
    if not force and os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            pass
    text = _pdftotext(pdf, first, last)
    usable = (_has_text(text)
              and (first is not None or _wordcount(text) >= _page_count(pdf) * 80))
    if not usable:
        text = "\n\n".join(_render_and_ocr(pdf, first or 1,
                                           last or 10 ** 9)).strip()
        if last is None:
            # catch the huge-page count: pdftoppm stops at the last real page
            last = 0
    text = _clean(text)
    if _has_text(text):
        try:
            with open(cache, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass
    return text


def _clean(text: str) -> str:
    """Normalize raw OCR/page text: fix quotes, drop form feeds and junk."""
    text = (text or "").replace("\x0c", "\n").replace("\r\n", "\n")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" \u00a0") for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ---------------------------------------------------------------------------
# corpus parsing (pure)
# ---------------------------------------------------------------------------

def split_units(text: str, whole_title: str = "Textbook",
                year: int = 1) -> list[dict]:
    """Chunk OCR text by ``Unit N`` headings.  Without any heading the whole
    text becomes one unnamed unit.  Each unit carries its own clean
    ``sentences`` and ``words`` (the cleanliness gates from
    ``clean_sentences``/``pick_words`` are applied per unit)."""
    year = int(year)
    text = text or ""
    heads = [m for m in _UNIT_HEAD_RE.finditer(text)]
    units: list[dict] = []
    if not heads:
        sents = clean_sentences(text, year)
        return [{"title": whole_title, "text": text,
                 "sentences": sents, "words": pick_words(sents)}]
    for i, m in enumerate(heads):
        start = m.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        header = text[start:end].split("\n", 1)[0].strip()
        body = text[start:end]
        sents = clean_sentences(body, year)
        units.append({"title": header or f"Unit {i + 1}", "text": body,
                      "sentences": sents, "words": pick_words(sents)})
    return units


def clean_sentences(text: str, year: int) -> list[str]:
    """Sentences from ``text`` that pass the year's band + word gates.

    Garbage OCR lines, overly long sentences, sentences whose CEFR band
    overshoots the year's cap, and blocked content are dropped, never
    repaired (Round 17 decision 1).  Round 18: the final decision is the
    strict admission gate ``bank._sentence_admits`` (capital start, finite
    verb, no OCR debris), so OCR fragments like ``"1 have dinner with my
    family."`` or ``"s of people were leaving the station."`` can never
    become question sources.
    """
    from . import bank as B
    from . import data as D
    year = int(year)
    blob = _clean(_strip_unit_heads(text or ""))
    out: list[str] = []
    # sentences split on ., ! or ?, within ONE OCR line (a merged multi-line
    # run-on would smuggle column labels and word-lists past the gates).
    parts: list[str] = []
    for ln in blob.split("\n"):
        parts.extend(p for p in re.split(r"(?<=[.!?])\s+", ln))
    for part in parts:
        part = part.strip()
        part = re.sub(r"^(?:[a-d]\s+)+(?=[A-Z])", "", part)  # "(a) …" options
        if not part or _MIXED.search(part):
            continue
        stripped = B._LEAD_OCR.sub("", part).strip()
        if stripped and B._sentence_admits(stripped, year):
            out.append(stripped)
    # de-dup verbatim repeats (revision spreads OCR duplicates)
    seen: set[str] = set()
    kept: list[str] = []
    for s in out:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            kept.append(s)
    return kept


def pick_words(sentences: list[str], cap: int = 40) -> list[str]:
    """Frequency-ordered content words from ``sentences`` (stop words out)."""
    freq: dict[str, int] = {}
    order: list[str] = []
    for s in sentences:
        for tok in re.findall(r"[a-z']+", s.lower()):
            w = tok.strip("'")
            if not w or len(w) < 3 or w in _STOP or _MIXED.search(w):
                continue
            if not w.isalpha():
                continue
            if w not in freq:
                freq[w] = 0
                order.append(w)
            freq[w] += 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], order.index(kv[0])))
    return [w for w, _ in ranked[:cap]]


def chunk_sentences(sentences: list[str], year: int) -> list[str]:
    """Join sentences into reading passages bounded by the year's ceiling."""
    from . import data as D
    ceil = D.PASSAGE_WORD_CEIL.get(int(year), 150)
    lo = min(40, max(20, ceil // 3))
    out: list[str] = []
    cur: list[str] = []
    cur_w = 0
    for s in sentences:
        sw = len(s.split())
        if cur and cur_w + sw > ceil:
            out.append(" ".join(cur))
            cur, cur_w = [], 0
        cur.append(s)
        cur_w += sw
        if cur_w >= lo:
            out.append(" ".join(cur))
            cur, cur_w = [], 0
    if cur and cur_w >= 20:
        out.append(" ".join(cur))
    return out


def parse_text(text: str, year: int, source: str = "inline") -> dict:
    """Parse raw OCR text for ``year`` into one corpus entry (string key)."""
    year = int(year)
    units = []
    for u in split_units(text, year=year):
        sents = u.get("sentences") or []
        units.append({
            "title": u["title"],
            "words": pick_words(sents),
            "sentences": sents,
            "passages": chunk_sentences(sents, year),
        })
    all_sents = [s for u in units for s in u["sentences"]]
    entry = {
        "source": source,
        "pages": 0,
        "units": units,
        "words": pick_words(all_sents),
        "sentences": all_sents,
    }
    return {str(year): entry}


# ---------------------------------------------------------------------------
# mining + persistence
# ---------------------------------------------------------------------------

def find_textbooks(docs_dir: str) -> dict[int, str]:
    """Map supported SJKC years -> textbook PDF path inside ``docs_dir``."""
    out: dict[int, str] = {}
    if not docs_dir or not os.path.isdir(docs_dir):
        return out
    for name in sorted(os.listdir(docs_dir)):
        low = name.lower()
        if not low.endswith(".pdf"):
            continue
        stem = low[:-4]
        years = FILE_YEARS.get(stem)
        if not years:
            continue
        for y in years:
            if y in D.YEARS:
                out.setdefault(y, os.path.join(docs_dir, name))
    return out


def mine_dir(docs_dir: str) -> dict:
    """OCR every textbook in ``docs_dir`` and build the corpus.

    ``{year: {source, pages?, units, words, sentences}}`` with string keys.
    """
    out: dict = {}
    paths = find_textbooks(docs_dir)
    for year in sorted(paths):
        pdf = paths[year]
        text = ocr_pdf(pdf, year)
        if not text:
            continue
        entry = parse_text(text, year, source=os.path.basename(pdf))
        try:
            with __import__("zipfile").ZipFile(pdf) as _z:
                pass  # not a docx; ignore
        except Exception:
            pass
        entry[str(year)]["source"] = os.path.basename(pdf)
        # OCR page count from pdfinfo when available (best effort)
        rc, out_txt = _run(["pdfinfo", pdf])
        if rc == 0:
            for line in out_txt.splitlines():
                if line.lower().startswith("pages:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip().isdigit():
                        entry[str(year)]["pages"] = int(parts[1].strip())
        out[str(year)] = entry[str(year)]
    return out


def save_corpus(data: dict, out_dir: str | None = None) -> str:
    """Persist the corpus under the app data dir (or ``out_dir``)."""
    path = corpus_path(out_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({str(k): v for k, v in data.items()},
                  fh, ensure_ascii=False, indent=1)
    return path


def load_corpus(path: str | None = None) -> dict:
    """Read a saved corpus, normalising year keys back to ``int``.
    Missing/corrupt file returns {}.  String-keyed lookups work too."""
    path = path or corpus_path()
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
            out[k] = v
    return out


def usable_for_year(corpus: dict, year: int) -> int:
    """Clean sentences a year could actually use (for the GUI tooltip)."""
    from . import bank as B
    year = int(year)
    ent = corpus.get(year) or corpus.get(str(year))
    if not ent:
        return 0
    sents = ent.get("sentences") or []
    return sum(1 for s in sents if not B._passage_blocked(s))


def summarize(data: dict) -> str:
    """Human-readable accounting of a mined corpus."""
    lines: list[str] = []
    for year in sorted(data):
        info = data[year]
        units = info.get("units") or []
        sents = info.get("sentences") or []
        words = info.get("words") or []
        lines.append(
            f"Year {year}: {info.get('source', '?')} — {len(units)} units, "
            f"{len(words)} vocab words, {len(sents)} clean sentences")
        for u in units[:3]:
            lines.append(f"  Year {year}  {u.get('title', '?')}: "
                         f"{len(u.get('words', []))} words · "
                         f"{len(u.get('sentences', []))} sentences")
    return "\n".join(lines) or "No textbook corpus found."