"""Pupil marks, class results and difficulty calibration (pure stdlib).

This module turns a teacher's per-question marks into per-part totals, whole
class averages, KSSR bands and a CSV export, and it feeds the difficulty
calibration data (Round 13/S3, S4) back into the question bank:

  * ``results_csv``  — per-pupil CSV (part columns + total/percent/grade/band).
  * ``pupils_from_csv`` — round-trip parser for that CSV / the marking window.
  * ``record_stats`` — counts asked/wrong per MCQ & word question so weak
    items can be rotated out of future papers (see ``bank`` calibration).
"""

from __future__ import annotations

import csv
import io
import re
from collections import OrderedDict

#: Part-label column group is fixed by the paper; these helpers apply evenly.
GRADE_THRESHOLDS = (
    (0.80, "A"),    # 40/50
    (0.60, "B"),    # 30/50
    (0.40, "C"),    # 20/50
    (0.20, "D"),    # 10/50
)

#: KSSR six-band performance levels (fraction of the total marks).
KSSR_BANDS = (
    (0.85, 6),     # 42.5/50
    (0.70, 5),     # 35/50
    (0.55, 4),     # 27.5/50
    (0.40, 3),     # 20/50
    (0.25, 2),     # 12.5/50
)


def part_columns(papers) -> list[tuple[str, float]]:
    """(label, max-marks) per part column, from the first paper's parts."""
    base = papers[0] if papers else None
    if base is None:
        return []
    cols = [(f"P{p.num}", float(p.marks)) for p in base.parts]
    total = float(base.marks_table[-1][1]) if base.marks_table else 50.0
    cols.append(("TOTAL", total))
    return cols


def part_of_question(papers, qno: int) -> int:
    """Return the part number that owns ``qno`` in the first paper."""
    for p in papers[0].parts:
        if p.qfirst <= int(qno) < p.qfirst + max(len(p.items), 1):
            return p.num
    return 0


def pupil_parts(pupil: dict, papers) -> dict[int, float]:
    """Per-part earned totals for one pupil (dict of part_no -> marks).
    Unknown questions are ignored; a part is 0.0 when nothing is recorded."""
    per = OrderedDict((p.num, 0.0) for p in papers[0].parts)
    for qno, earned in (pupil.get("marks") or {}).items():
        pno = part_of_question(papers, qno)
        if pno and pno in per:
            per[pno] += float(earned)
    return per


def total_mark(pupil: dict, papers) -> float:
    """Grand total across parts for one pupil."""
    return round(sum(pupil_parts(pupil, papers).values()), 2)


def out_of(papers) -> float:
    cols = part_columns(papers)
    return float(cols[-1][1]) if cols else 50.0


def grade(total: float, out: float) -> str:
    frac = (float(total) / float(out)) if float(out) else 0.0
    for th, letter in GRADE_THRESHOLDS:
        if frac >= th:
            return letter
    return "E"


def band(total: float, out: float) -> int:
    frac = (float(total) / float(out)) if float(out) else 0.0
    for th, b in KSSR_BANDS:
        if frac >= th:
            return b
    return 1


def pupil_row(pupil: dict, papers) -> list:
    """One CSV row for a pupil: name, per-part marks, total, grade, band."""
    name = (pupil.get("name") or "").strip()
    per = pupil_parts(pupil, papers)
    out = out_of(papers)
    tot = total_mark(pupil, papers)
    parts = [per[p.num] for p in papers[0].parts]
    return [name, *parts, tot, round((tot / out) * 100, 1) if out else 0.0,
            grade(tot, out), band(tot, out)]


def results_csv(papers, pupils) -> str:
    """Comma-separated class results: per-pupil rows + a class-average row."""
    cols = part_columns(papers)
    header = ["Pupil", *[c for c, _ in cols[:-1]], "TOTAL",
              "/{:.0f}".format(cols[-1][1]) if cols else "/50",
              "%", "Grade", "Band"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    ordered = sorted((p for p in pupils if (p.get("name") or "").strip()),
                     key=lambda p: p["name"].strip().casefold())
    for pupil in ordered:
        w.writerow(pupil_row(pupil, papers))
    if ordered:
        n = len(ordered)
        per_parts = [sum(pupil_parts(p, papers)[pn]
                         for p in ordered) / n for pn in (p.num for p in papers[0].parts)]
        avgs = [round(v, 2) for v in per_parts]
        out = out_of(papers)
        avgtot = round(sum(per_parts), 2)
        avgpct = round((avgtot / out) * 100, 1) if out else 0.0
        w.writerow(["Class average", *avgs, avgtot, "", avgpct, "", ""])
        count = OrderedDict()
        for pupil in ordered:
            b = band(total_mark(pupil, papers), out)
            count[int(b)] = count.get(int(b), 0) + 1
        legend = "KSSR band count: " + ", ".join(
            f"B{i}={count[i]}" for i in sorted(count))
        w.writerow([legend])
    return buf.getvalue()


def _col_to_part(h: str) -> int:
    """Map a CSV column header to a part number: ints and ``P1``/``part3``."""
    digits = re.sub(r"\D", "", h)
    if digits and 1 <= int(digits) <= 9:
        return int(digits)
    return 0


def pupils_from_csv(text: str) -> list[dict]:
    """Parse a results CSV back into pupil dicts (skips header/average rows).

    Accepts the shape produced by :func:`results_csv` (columns may vary) plus
    plain ``Pupil,marks-per-part...`` sheets; the TOTAL / % / Grade / Band
    columns are ignored on import because totals are recomputed from the
    per-part columns (``P1 .. P7`` or plain ``1 .. 7`` headers).
    """
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    skip = {"", "pupil", "name", "total", "%", "grade", "band", "no."}
    pupils: list[dict] = []
    for row in rows[1:]:
        if not row or not (row[0] or "").strip():
            continue
        name = row[0].strip()
        low = name.lower()
        if low.startswith("class average") or low.startswith("kssr band count"):
            continue
        marks = {}
        for i, h in enumerate(header):
            if i == 0 or h in skip or h.startswith("/"):
                continue
            pno = _col_to_part(h)
            if not pno:
                continue
            try:
                marks[pno] = float(row[i] or 0.0)
            except ValueError:
                pass
        pupils.append({"name": name, "marks": marks})
    return pupils


def record_stats(papers, pupils, stats: dict | None = None) -> dict:
    """Tally asked/wrong counts for every exact-grade question in the batch.

    Only MCQ / word (fill-the-word) questions that carry a definite answer are
    tracked — writing is subjective and is skipped.  ``stats`` is the
    bank's difficulty-stats dict (``{"q": {key: {"asked": n, "misses": m}}}``);
    it is mutated and returned so the caller can persist it.
    """
    from . import bank
    stats = stats if isinstance(stats, dict) else {}
    table: dict = stats.setdefault("q", {})
    for pupil in pupils:
        for paper in papers:
            for part in paper.parts:
                if part.kind == "writing":
                    continue
                for item, qno in zip(part.items, part.qnos()):
                    key = bank.qkey(item)
                    if not key:
                        continue
                    cell = table.setdefault(key, {"asked": 0, "misses": 0,
                                                  "kind": part.kind})
                    cell["asked"] += 1
                    earned = float((pupil.get("marks") or {}).get(qno, 0.0))
                    if earned <= 0.0:
                        cell["misses"] += 1
    return stats