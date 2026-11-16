"""Headless command-line generation for testing / scripting.

    python3 main.py --cli --year 3 --out /tmp/Exam --seed 5 --pdf
"""

from __future__ import annotations

import json
import os
import re
import sys


def _slug(theme: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", theme).strip("_") or "Auto"


def _print_compliance(paper) -> None:
    """Print the refresh/Regenerate compliance verdict for one paper."""
    from . import bank
    pc = bank.paper_compliance(paper)
    det = (f"w{pc['week']} {pc['theme']}" if pc["week"]
           else (pc["theme"] or "auto"))
    flag = "REFRESH ✓ exam-ready" if pc["ok"] else "REFRESH ✗ NOT exam-ready"
    print(f"    {flag}  Y{pc['year']} {pc['exam_type']} · {pc['marks']} marks · "
          f"{pc['questions']} Q · RPT {det} · DSKP {'✓' if pc['dskp'] else '✗'} · "
          f"CEFR {'✓' if pc['cefr'] else '✗'}")
    qr = getattr(paper, "_qc", None)
    if qr is not None:
        rolls = getattr(paper, "_qc_rolls", 0)
        extra = f" (re-rolled ×{rolls + 1})" if rolls else ""
        print(f"    QC    {qr.score}/10 · {qr.hard} hard · {qr.soft} soft"
              f"{extra}")
    if not pc["ok"]:
        print("    REFRESH:", file=sys.stderr)
        for issue in pc["issues"]:
            print(f"    REFRESH: - {issue}", file=sys.stderr)


def _run_qc_check(path: str) -> int:
    """``--check DIR`` — audit every saved paper in the directory; any hard
    issue fails the door."""
    from . import qc
    reports = qc.audit_dir(path)
    bad = 0
    for name, r in reports:
        tag = "✓" if r.hard == 0 else "✗"
        print(f"    QC {tag} {name}: {r.score}/10 · {r.hard} hard · "
              f"{r.soft} soft")
        if r.hard:
            bad += 1
            for i in r.issues:
                if i.hard:
                    print(f"    QC  - {i.code} {i.message}", file=sys.stderr)
    if not reports:
        print(f"QC: no papers (.docx) found under {path}", file=sys.stderr)
    print(f"QC: {len(reports)} paper(s), {bad} failing the teacher's bar")
    return 1 if bad else 0


def _run_qc_teacher() -> int:
    """``--check-teacher`` — the reference copies oracle must pass 100%."""
    from . import qc
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "materials", "2027", "past-papers")
    legacy = os.path.expanduser("~/Downloads/exam2026")
    path = bundled if os.path.isdir(bundled) else legacy
    issues = qc.reference_issues(path)
    for i in issues:
        print(f"    QC ✗ {i.code}: {i.message}", file=sys.stderr)
    if not issues:
        print(f"QC: teacher reference copies under {path} pass the watchdog ✓")
        return 0
    print(f"QC: {len(issues)} reference issue(s) — a real paper must be clean",
          file=sys.stderr)
    return 1


def _run_term(conf, passages, out: str, weeks: int, marksheet: bool,
              want_pdf: bool, repeat_check: bool = False,
              coverage: bool = False) -> int:
    """Batch-generate one paper per RPT week (Round 12/S5).  Papers land in
    ``out/`` as ``UPSA_Y{year}_W{week:02d}_{theme}.docx`` with a week-keyed
    seed, so a whole term is ready in one command."""
    from . import bank, pdfmake, dskp as _dskpmod
    os.makedirs(out, exist_ok=True)
    n = min(int(weeks), bank.SCHOOL_WEEKS)
    done = 0
    made = []
    for w in range(1, n + 1):
        wconf = dict(conf)
        wconf["week"] = w
        wconf["theme"] = bank.theme_for_week(int(conf["year"]), w)
        wconf["seed"] = int(conf.get("seed", 1)) + w * 977
        paper = bank.generate_clean(wconf, passages)
        made.append(paper)
        base = os.path.join(out, f"UPSA_Y{conf['year']}_W{w:02d}_{_slug(wconf['theme'])}")
        res = pdfmake.save_with_extras(paper, base, want_pdf=want_pdf,
                                       marksheet=marksheet)
        print(f"OK  year={conf['year']} week={w:02d} theme={wconf['theme']} "
              f"questions={paper.max_qno()}  key={len(paper.key)}")
        print(f"    DOCX: {res['docx']}")
        if res.get("pdf"):
            print(f"    PDF: {res['pdf']}")
        if coverage:
            print(_dskpmod.coverage_report(paper)["text"])
        done += 1
    if repeat_check and len(made) > 1:
        print()
        print(bank.repeat_report(made)["text"])
    print(f"Generated {done} papers for {conf['year']} in {out}")
    return 0


USAGE = """\
Penjana Kertas Ujian — SJKC Bahasa Inggeris exam paper generator

  python3 main.py --cli --year 3 --out /tmp/Paper.docx [options]
  python3 main.py                      # GTK4 GUI

Paper
  --year N            1-6 (Year 4 shares the Year 5 blueprint)
  --exam-type T       UPSA (mid-year) or UASA (end-of-year)  [alias --exam]
  --difficulty D      easy | medium | hard
  --seed N            integer seed; the same seed gives the same paper
  --theme T           RPT weekly theme; --week N / --term N pick it by number
  --week N / --term N weekly or term index for the theme

Content
  --textbook FILE     use a textbook corpus instead of the built-in bank
  --bank FILE         extra JSON question bank
  --template FILE     .docx template for styling
  --import FILE       import a question bank (--import-ref / --import-textbook)
  --calibrate         re-fit difficulty against the corpus

Output
  --out PATH          .docx file or output directory
  --pdf               also convert to .pdf (needs LibreOffice)
  --marksheet         pupil mark sheet
  --no-sheet          omit the bubble answer sheet (official format)
  --mark-scheme       teacher mark scheme (AO columns, PL1-PL6)
  --teacher-copy      answers + JSU appendix (never photocopy)
  --teacher NAME      teacher name printed on the paper
  --school NAME / --crest PATH   school name and crest
  --csv / --json      machine-readable tally
  --bundle N / --class NAME       generate N papers for one class
  --pair                          generate non-repeating UPSA + UASA for the year

Checking
  --check PATH        audit a saved .docx (or a directory of them)
  --qc-check          QC the generated paper only
  --qc-teacher        QC as a teacher copy (relaxed option rules)
  --qc-json PATH      write the QC report as JSON
  --dskp              DSKP word-list report
  --jsu               print the JSU learning outcomes
  --coverage          print syllabus coverage
  --stats             print bank statistics
  --repeat-check      report duplicate items across seeds

  -h, --help          show this message and exit
"""


def run_cli(args: list[str], want_pdf: bool = False) -> int:
    # ``--help`` must answer the question and stop.  Checked before any
    # generation so it can never write a paper as a side effect.
    if any(a in ("-h", "--help") for a in args):
        print(USAGE, end="")
        return 0
    from . import bank, data as D, pdfmake
    from . import webfetch

    conf = dict(D.DEFAULT_CONFIG)
    out = None
    _marksheet = False
    _no_sheet = False
    _mark_scheme = False
    _teacher = False
    _omr = False
    _no_locks = False
    _ab = False
    _pair = False
    _week = 0
    _term = 0
    bank_path = None
    template_path = None
    _csv_out = False
    _json_out = False
    _revision = None
    _backup = False
    _out_given = False
    _bundle = 0
    _class = ""
    _dskp = False
    _jsu = False
    _coverage = False
    _repeat_check = False
    _import_file = None
    _import_ref = None
    _import_textbook = None
    _use_tb = None
    _calibrate = False
    _results_file = None
    _stats = False
    _qc_check = None
    _qc_teacher = False
    _qc_json = None
    for i, a in enumerate(args):
        if a == "--cli":
            continue
        if a.startswith("--year"):
            conf["year"] = int(args[i + 1])
        elif a.startswith("--seed"):
            conf["seed"] = int(args[i + 1])
        elif a == "--difficulty":
            conf["difficulty"] = args[i + 1]
        elif a in ("--exam-type", "--exam"):
            # UPSA (mid-year) or UASA (end-of-year).  The two differ in more
            # than the caption: Years 1-3 are a 60-minute UPSA paper and a
            # 75-minute UASA paper (criteria §1).
            want = str(args[i + 1]).lower()
            if want not in D.EXAM_ABBR:
                print(f"Unknown --exam-type {args[i + 1]!r}; "
                      f"expected one of {', '.join(sorted(D.EXAM_ABBR))}")
                return 2
            conf["exam_type"] = want
        elif a == "--theme":
            conf["theme"] = args[i + 1]
        elif a == "--school":
            conf["school"] = args[i + 1]
        elif a == "--teacher":
            conf["teacher"] = args[i + 1]
        elif a == "--crest":
            conf["crest"] = args[i + 1]
        elif a == "--pupil-id":
            conf["pupil_id"] = args[i + 1]
        elif a == "--qr":
            conf["qr"] = True
        elif a == "--calibrate":
            _calibrate = True
            conf["calibrate"] = True
        elif a == "--class":
            _class = args[i + 1]
        elif a == "--dskp":
            _dskp = True
        elif a == "--jsu":
            _jsu = True
        elif a == "--coverage":
            _coverage = True
        elif a == "--repeat-check":
            _repeat_check = True
        elif a == "--stats":
            _stats = True
        elif a == "--check":
            _qc_check = args[i + 1]
        elif a == "--check-teacher":
            _qc_teacher = True
        elif a == "--qc-json":
            _qc_json = args[i + 1]
        elif a == "--import":
            _import_file = args[i + 1]
        elif a == "--import-ref":
            _import_ref = args[i + 1]
        elif a == "--import-textbook":
            _import_textbook = args[i + 1]
        elif a == "--textbook":
            _use_tb = True
        elif a == "--no-textbook":
            _use_tb = False
        elif a == "--results":
            _results_file = args[i + 1]
        elif a == "--bundle":
            _bundle = max(1, int(args[i + 1]))
        elif a in ("--no-pictures", "--pictures"):
            conf["pictures"] = (a == "--pictures")
        elif a == "--no-locks":
            _no_locks = True
        elif a == "--omr":
            _omr = True
        elif a == "--mark-scheme":
            _mark_scheme = True
        elif a == "--marksheet":
            _marksheet = True
        elif a == "--ab":
            _ab = True
        elif a == "--pair":
            _pair = True
        elif a == "--week":
            _week = int(args[i + 1])
        elif a == "--term":
            _term = int(args[i + 1])
        elif a == "--bank":
            bank_path = args[i + 1]
        elif a == "--bank-template":
            template_path = args[i + 1]
        elif a.startswith("--out"):
            _out_given = True
            out = args[i + 1]
        elif a == "--no-key":
            conf["answer_key"] = False
            conf["jsu"] = False
        elif a == "--no-sheet":
            _no_sheet = True
            conf["answer_sheet"] = False
        elif a == "--teacher-copy":
            # Write the teacher document (answer key + JSU) beside the pupil
            # paper.  A plain --out is a pupil paper (Round 38).  Not named
            # --teacher: that already takes the *teacher's name* (line 172).
            _teacher = True
        elif a == "--csv":
            _csv_out = True
        elif a == "--json":
            _json_out = True
        elif a == "--revision":
            _revision = args[i + 1]
        elif a == "--backup":
            _backup = True
        elif a == "--web":
            conf["use_web"] = True

    if template_path:
        with open(template_path, "w", encoding="utf-8") as fh:
            json.dump(bank.bank_template(), fh, ensure_ascii=False, indent=2)
        print(f"Bank template written: {template_path}")
        return 0

    if _import_ref:
        from . import refcorpus
        data = refcorpus.mine_dir(_import_ref)
        if not data:
            print(f"Import-ref: no usable papers found in {_import_ref}",
                  file=sys.stderr)
            return 2
        path = refcorpus.save_report(data)
        print("Reference corpus (per-year vocab / picture words):")
        print(refcorpus.summarize(data))
        print(f"    saved: {path}")
        return 0

    if _import_textbook:
        from . import textbook as TB
        data = TB.mine_dir(_import_textbook)
        if not data:
            print(f"Import-textbook: no textbook PDFs found in {_import_textbook}",
                  file=sys.stderr)
            return 2
        path = TB.save_corpus(data)
        print("Textbook corpus (the sole reference):")
        print(TB.summarize(data))
        print(f"    saved: {path}")
        return 0

    if conf["difficulty"] not in D.DIFFICULTIES:
        print(f"Unsupported difficulty '{conf['difficulty']}'; "
              f"use {D.DIFFICULTIES}", file=sys.stderr)
        return 2

    if conf["year"] not in D.YEARS:
        print(f"Unsupported year {conf['year']}; use {D.YEARS}", file=sys.stderr)
        return 2
    if out is None:
        out = os.path.join(os.getcwd(), f"UPSA_Year{conf['year']}_BI")
    elif not _term:
        # Single-paper modes treat --out as a file stem and append their own
        # extension, so drop a document extension the user already typed to
        # avoid "Paper.docx.docx".  --term treats --out as a directory.
        out = os.path.splitext(out)[0]

    passages = None
    if conf.get("use_web"):
        cache = webfetch.load_cache()
        passages = [p for name in cache for p in cache.get(name, [])]
        if not passages:
            print("No web passages cached yet; run the GUI 'Fetch web' first or "
                  "seed the cache.", file=sys.stderr)

    # Round 17: the mined textbooks are the sole reference.  A saved corpus is
    # used automatically unless --no-textbook; --textbook requires one (falls
    # back gracefully, never blocks offline generation).
    if _use_tb is not False:
        from . import textbook as TB
        corpus = TB.load_corpus()
        if corpus:
            conf["textbook"] = corpus
        elif _use_tb:
            print("Textbook corpus not found; run `--import-textbook DIR` first. "
                  "Falling back to the built-in pools.", file=sys.stderr)

    if bank_path:
        conf["user_bank"] = bank.load_user_bank(bank_path)
    conf["week"] = _week

    if _import_file:
        if _import_file.lower().endswith(".json"):
            try:
                verdict = bank.import_past_json(_import_file)
            except ValueError as exc:
                print(f"Import: {exc}", file=sys.stderr)
                return 2
            print(f"Imported past paper: {verdict['file']}  "
                  f"year={verdict['year']} parts={verdict['parts']} "
                  f"questions={verdict['questions']}")
            return 0
        try:
            n = bank.import_csv(_import_file, year=int(conf["year"]))
        except (ValueError, OSError) as exc:
            print(f"Import: {exc}", file=sys.stderr)
            return 2
        print(f"Imported {n} question(s) into the user bank from "
              f"{_import_file}")
        return 0

    if _stats:
        st = bank.load_stats()
        table = (st or {}).get("q") or {}
        flagged = [v for v in table.values()
                   if isinstance(v, dict) and v.get("asked", 0) >= 2
                   and v.get("misses", 0) / v["asked"] >= bank.MISS_DROP_RATE]
        print(f"Difficulty stats: {len(table)} question(s) tracked, "
              f"{len(flagged)} chronically missed")
        for i, v in enumerate(sorted(table.values(),
                                     key=lambda c: -(c.get('misses', 0)
                                                     or 0))[:8], 1):
            print(f"  {i}. asked={v.get('asked', 0)} miss={v.get('misses', 0)}"
                  f" ({round(100 * v.get('misses', 0) / v['asked']) if v.get('asked') else 0}%)"
                  f"  kind={v.get('kind', '?')}")
        return 0

    if _revision:
        want, hits = bank.archive_suggest(conf["year"], _week or 1,
                                          _revision)
        print(f"  RPT theme for week {_week or 1}: {want!r}")
        if hits:
            print(f"  Past papers to revise with ({len(hits)}):")
            for path, t in hits:
                print(f"    - {path}  ({t})")
        else:
            print("  (no archived paper on this theme yet; export papers with "
                  "--json to build an archive)", file=sys.stderr)

    if _backup and not _out_given:
        made = bank.backup_state()
        if made:
            print("Backups written:")
            for line in made.splitlines():
                print(f"    - {line}")
            return 0
        print("Backup: no user_bank.json/packs.json yet.", file=sys.stderr)
        return 2

    if _backup:
        made = bank.backup_state()
        if made:
            print("Backups written:")
            for line in made.splitlines():
                print(f"    - {line}")

    if _qc_teacher:
        return _run_qc_teacher()

    if _qc_check:
        return _run_qc_check(_qc_check)

    if _term:
        return _run_term(conf, passages, out, _term, _marksheet, want_pdf,
                          repeat_check=_repeat_check, coverage=_coverage)

    if _pair:
        from . import pdfmake as _pm
        _overrides = {k: v for k, v in conf.items()
                      if k not in ("year", "seed", "difficulty")}
        pair = bank.generate_year_pair(
            conf["year"], seed=conf.get("seed", 1),
            difficulty=conf.get("difficulty", "medium"),
            passages=passages, **_overrides)
        upsa, uasa = pair
        # apply locks handled inside generate_year_pair
        r1 = _pm.save_with_extras(upsa, out + "_UPSA", want_pdf=want_pdf,
                                   marksheet=_marksheet, mark_scheme=_mark_scheme,
                                   conf=conf, teacher=_teacher, omr=_omr)
        r2 = _pm.save_with_extras(uasa, out + "_UASA", want_pdf=want_pdf,
                                   marksheet=_marksheet, mark_scheme=_mark_scheme,
                                   conf=conf, teacher=_teacher, omr=_omr)
        print(f"OK  year-pair  year={conf['year']} seed={conf['seed']} "
              f"parts={len(upsa.parts)} questions={upsa.max_qno()}")
        print(f"    UPSA DOCX: {r1['docx']}")
        print(f"    UASA DOCX: {r2['docx']}")
        if r1.get("pdf"):
            print(f"    UPSA PDF : {r1['pdf']}")
        if r2.get("pdf"):
            print(f"    UASA PDF : {r2['pdf']}")
        print()
        print(bank.repeat_report([upsa, uasa])["text"])
        return 0

    if _results_file:
        return _run_results(conf, passages, _results_file, _calibrate)

    if _bundle:
        papers = bank.bundle_papers(conf, _bundle, passages)
        from . import pdfmake as _pm
        res = _pm.save_bundle(papers, out, class_label=_class,
                              want_pdf=want_pdf)
        first = papers[0]
        _print_compliance(first)
        print(f"OK  class bundle  year={conf['year']} seed={conf['seed']} "
              f"variants={len(papers)} parts={len(first.parts)} "
              f"questions={first.max_qno()} key={len(first.key)}")
        for p in res.get("docx", []):
            print(f"    DOCX: {p}")
        for p in res.get("pdf", []):
            print(f"    PDF : {p}")
        print(f"    MARKSHEET: {res.get('bundle_marksheet', '(none)')}")
        if res.get("bundle_marksheet_pdf"):
            print(f"    MARKSHEET PDF: {res['bundle_marksheet_pdf']}")
        if _dskp:
            print(bank.dskp_report(first))
        if _jsu:
            print(bank.jsu_report(first))
        return 0

    paper = bank.generate_clean(conf, passages)
    if not _no_locks:
        from . import locks as _locks
        _store = _locks.load()
        if _store:
            paper = bank.apply_locks(paper, _store)
            n = len(bank.locked_keys(_store, paper.year()))
            if n:
                print(f"    LOCKED: {n} teacher-locked item(s) for Year "
                      f"{paper.year()} applied")
    issues = bank.quality_issues(paper)
    if issues:
        print("    QC:", file=sys.stderr)
        for issue in issues:
            print(f"    QC: - {issue}", file=sys.stderr)
    if _qc_json:
        from . import qc
        qr = getattr(paper, "_qc", None) or qc.check_paper(paper)
        with open(_qc_json, "w", encoding="utf-8") as fh:
            json.dump(qr.as_dict(), fh, ensure_ascii=False, indent=2)
        print(f"    QC report: {_qc_json}")
    _print_compliance(paper)
    if _dskp:
        print(bank.dskp_report(paper))
    if _jsu:
        print(bank.jsu_report(paper))
    if _coverage:
        from . import dskp as _dskpmod
        print(_dskpmod.coverage_report(paper)["text"])
    if _csv_out or _json_out:
        _write_exports(paper, out, _csv_out, _json_out)
    res = pdfmake.save_with_extras(paper, out, want_pdf=want_pdf,
                                   marksheet=_marksheet,
                                   mark_scheme=_mark_scheme, conf=conf,
                                   teacher=_teacher, omr=_omr)
    extra = []
    if _ab:
        bconf = dict(conf)
        bconf["seed"] = bank.next_seed(int(conf["seed"]))
        b_paper = bank.generate_clean(bconf, passages)
        br = pdfmake.save_paper(b_paper, out + "B", want_pdf=want_pdf)
        extra.append(br["docx"])
    n_mcq = sum(1 for p in paper.parts for it in p.items if it.__class__.__name__ == "MCQItem")
    print(f"OK  year={conf['year']} seed={conf['seed']} parts={len(paper.parts)} "
          f"questions={paper.max_qno()} key={len(paper.key)}")
    print(f"    DOCX: {res['docx']}")
    for p in extra:
        print(f"    DOCX: {p}")
    if res.get("marksheet"):
        print(f"    MARKSHEET: {res['marksheet']}")
    if res.get("teacher"):
        print(f"    TEACHER (answers + JSU - do not photocopy): "
              f"{res['teacher']}")
    if res["pdf"]:
        print(f"    PDF : {res['pdf']}")
    else:
        print("    PDF : (LibreOffice unavailable or conversion failed)",
              file=sys.stderr)
    return 0


def _write_exports(paper, out: str, do_csv: bool, do_json: bool) -> None:
    """Round 12/S7: side-by-side .key.csv / .json next to the .docx."""
    from . import bank
    if do_csv:
        with open(out + ".key.csv", "w", encoding="utf-8") as fh:
            fh.write(bank.paper_csv(paper))
        print(f"    CSV: {out}.key.csv")
    if do_json:
        with open(out + ".json", "w", encoding="utf-8") as fh:
            json.dump(bank.paper_export(paper), fh, ensure_ascii=False,
                      indent=2)
        print(f"    JSON: {out}.json")


def _run_results(conf, passages, results_file: str,
                 do_calibrate: bool) -> int:
    """Round 13/S3: read a marking CSV of pupil marks, print the class
    summary (*.summary.csv), and optionally feed difficulty stats (S4)."""
    from . import bank, marks as M
    try:
        with open(results_file, encoding="utf-8") as fh:
            pupils = M.pupils_from_csv(fh.read())
    except OSError as exc:
        print(f"Results: cannot read {results_file}: {exc}",
              file=sys.stderr)
        return 2
    if not pupils:
        print("Results: no pupil rows found.", file=sys.stderr)
        return 2
    paper = bank.generate_clean(conf, passages)
    summary = M.results_csv([paper], pupils)
    base = os.path.splitext(results_file)[0] + ".summary.csv"
    with open(base, "w", encoding="utf-8") as fh:
        fh.write(summary)
    out_tot = M.out_of([paper])
    grades: dict[str, int] = {}
    for p in pupils:
        t = M.total_mark(p, [paper])
        g = M.grade(t, out_tot)
        grades[g] = grades.get(g, 0) + 1
    print(f"Results: {len(pupils)} pupil(s); class summary written: {base}")
    print(f"    grade spread: " +
          ", ".join(f"{g}={grades[g]}" for g in sorted(grades)))
    if do_calibrate:
        st = bank.record_stats([paper], pupils)
        print(f"    difficulty stats updated "
              f"({len((st or {}).get('q', {}))} questions tracked)")
    return 0