"""Export pipeline: write .docx, then convert to .pdf via LibreOffice.

The .docx written by :mod:`docx` is the source of truth.  LibreOffice headless
renders an exact PDF (CJK-capable via Noto fonts).  ``libreoffice --headless``
is present on this machine; if it is ever missing we return None and the caller
shows a helpful message instead of failing.

LibreOffice startup dominates single-file conversion cost, so batch exports
(save all + PDF all) convert every .docx in a single ``soffice`` invocation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from . import docx as X


def _find_soffice() -> str | None:
    for name in ("libreoffice", "soffice"):
        p = shutil.which(name)
        if p:
            return p
    return None


def save_docx(paper, path: str, imgs: dict | None = None,
              allow_fetch: bool = True) -> str:
    """Write paper to ``path`` (.docx).  Returns the path."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = X.render_doc(paper, imgs=imgs, allow_fetch=allow_fetch)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def docx_to_pdf(docx_path: str, out_pdf: str | None = None) -> str | None:
    """Convert one .docx to .pdf, returning the PDF path or None on failure."""
    produced = _convert([docx_path])
    if not produced:
        return None
    path = produced[0]
    if out_pdf:
        os.makedirs(os.path.dirname(os.path.abspath(out_pdf)) or ".", exist_ok=True)
        shutil.move(path, out_pdf)
        return out_pdf
    return path


def _convert(docx_paths: list[str], out_dir: str | None = None) -> list[str] | None:
    """Convert several .docx files in a single headless LibreOffice run.

    Returns the produced PDF paths (same basenames, .pdf) or None on failure.
    """
    soffice = _find_soffice()
    if not soffice:
        return None
    docx_paths = [os.path.abspath(p) for p in docx_paths]
    tmpdir = out_dir or tempfile.mkdtemp(prefix="examgen-")
    try:
        cmd = [soffice, "--headless", "--convert-to", "pdf:writer_pdf_Export",
               "--outdir", tmpdir, *docx_paths]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300,
                       env={**os.environ, "HOME": os.path.expanduser("~")})
        bases = {os.path.splitext(os.path.basename(p))[0] for p in docx_paths}
        made = {os.path.splitext(f)[0]: f
                for f in os.listdir(tmpdir) if f.lower().endswith(".pdf")}
        paths = [os.path.join(tmpdir, made[b]) for b in bases if b in made]
        return paths or None
    except Exception:
        return None


def save_paper(paper, base_path: str, want_pdf: bool = True,
               imgs: dict | None = None, allow_fetch: bool = True) -> dict:
    """Write .docx (always) and .pdf (if possible).  Returns result dict."""
    docx_path = save_docx(paper, base_path + ".docx", imgs=imgs,
                          allow_fetch=allow_fetch)
    result = {"docx": docx_path, "pdf": None}
    if want_pdf:
        result["pdf"] = docx_to_pdf(docx_path, base_path + ".pdf")
    return result


def save_marksheet(paper, base_path: str, want_pdf: bool = False) -> dict:
    """Write the standalone marking sheet, optionally converting to PDF."""
    path = (base_path[:-5] if base_path.endswith(".docx")
            else base_path) + "_marksheet.docx"
    with open(path, "wb") as fh:
        fh.write(X.mark_sheet_doc(paper))
    result = {"docx": path, "pdf": None}
    if want_pdf:
        result["pdf"] = docx_to_pdf(path, os.path.splitext(path)[0] + ".pdf")
    return result


def save_teacher_copy(paper, base_path: str, want_pdf: bool = False,
                      imgs: dict | None = None,
                      allow_fetch: bool = True) -> dict:
    """Write the teacher document: the same paper plus the key and the JSU.

    Round 38.  The pupil paper is what ``--out`` produces, so the key and the
    table live in their own file -- ``<stem>_TEACHER.docx`` -- named so that
    it is obvious at a glance which one must not be photocopied.  The paper
    itself is not mutated: the two documents are the same content with the
    teacher pages switched on.
    """
    import copy as _copy
    stem, ext = os.path.splitext(base_path)
    if not ext:
        stem = base_path
    out = f"{stem}_TEACHER.docx"
    teacher = _copy.copy(paper)
    teacher.meta = dict(paper.meta)
    teacher.meta["answer_key"] = True
    teacher.meta["jsu"] = True
    with open(out, "wb") as fh:
        fh.write(X.render_doc(teacher, imgs=imgs, allow_fetch=allow_fetch))
    result = {"docx": out}
    if want_pdf:
        pdf = docx_to_pdf(out)
        if pdf:
            result["pdf"] = pdf
    return result


def save_mark_scheme(paper, base_path: str, want_pdf: bool = False,
                     conf: dict | None = None) -> dict:
    """Save the standalone teacher marking scheme (Round 31 F2).

    Written as ``<stem>_MARK_SCHEME.docx`` next to the paper so it is obvious
    at a glance which file is the teacher copy.
    """
    from . import docx as _docx
    stem, ext = os.path.splitext(base_path)
    if not ext:
        stem = base_path
    out = f"{stem}_MARK_SCHEME.docx"
    with open(out, "wb") as fh:
        fh.write(_docx.mark_scheme_doc(paper, conf=conf))
    result = {"docx": out}
    if want_pdf:
        pdf = docx_to_pdf(out)
        if pdf:
            result["pdf"] = pdf
    return result


def save_omr_sheet(paper, base_path: str, want_pdf: bool = False) -> dict:
    """Save the OMR bubble answer sheet (Round 32 F1) as ``<stem>_OMR.docx``."""
    from . import docx as _docx
    stem, ext = os.path.splitext(base_path)
    if not ext:
        stem = base_path
    out = f"{stem}_OMR.docx"
    with open(out, "wb") as fh:
        fh.write(_docx.omr_sheet_doc(paper))
    result = {"docx": out}
    if want_pdf:
        pdf = docx_to_pdf(out)
        if pdf:
            result["pdf"] = pdf
    return result


def save_with_extras(paper, base_path: str, want_pdf: bool = True,
                     marksheet: bool = False, imgs: dict | None = None,
                     allow_fetch: bool = True,
                     mark_scheme: bool = False,
                     conf: dict | None = None,
                     teacher: bool = False,
                     omr: bool = False) -> dict:
    """Save the paper + (optionally) the marking sheet.  Returns result dict."""
    result = save_paper(paper, base_path, want_pdf=want_pdf, imgs=imgs,
                        allow_fetch=allow_fetch)
    if teacher:
        tc = save_teacher_copy(paper, base_path, want_pdf=want_pdf, imgs=imgs,
                               allow_fetch=allow_fetch)
        result["teacher"] = tc.get("docx")
        if tc.get("pdf"):
            result["teacher_pdf"] = tc["pdf"]
    if marksheet:
        sm = save_marksheet(paper, base_path, want_pdf=want_pdf)
        result["marksheet"] = sm.get("docx")
        if sm.get("pdf"):
            result["marksheet_pdf"] = sm["pdf"]
    if mark_scheme:
        sc = save_mark_scheme(paper, base_path, want_pdf=want_pdf, conf=conf)
        result["mark_scheme"] = sc.get("docx")
        if sc.get("pdf"):
            result["mark_scheme_pdf"] = sc["pdf"]
    if omr:
        os_ = save_omr_sheet(paper, base_path, want_pdf=want_pdf)
        result["omr"] = os_.get("docx")
        if os_.get("pdf"):
            result["omr_pdf"] = os_["pdf"]
    return result


def save_bundle(papers, base_path: str, class_label: str = "",
                want_pdf: bool = True, bundle_marksheet: bool = True,
                imgs: dict | None = None, allow_fetch: bool = True) -> dict:
    """Save a class bundle: N variant papers + one merged marking sheet.

    Files are written next to ``base_path`` as ``<stem>_variant_01.docx`` …
    and ``<stem>_bundle_marksheet.docx``; every .docx is converted to .pdf in
    one LibreOffice pass.  Returns an outcome dict
    (``docx``, ``pdf``, ``bundle_marksheet``, ``bundle_marksheet_pdf``).
    """
    base_path = os.path.abspath(base_path)
    os.makedirs(os.path.dirname(base_path) or ".", exist_ok=True)
    stem = os.path.splitext(os.path.basename(base_path))[0]
    out_dir = os.path.dirname(base_path) or "."
    n = len(papers)
    pad = max(2, len(str(n)))
    docx_paths: list[str] = []
    result: dict[str, object] = {"docx": [], "pdf": []}
    for i, paper in enumerate(papers, 1):
        part = f"{stem}_variant_{i:0{pad}d}"
        path = save_docx(paper, os.path.join(out_dir, part + ".docx"),
                         imgs=imgs, allow_fetch=allow_fetch)
        docx_paths.append(path)
        result["docx"].append(path)                      # type: ignore[union-attr]
    sheet = None
    if bundle_marksheet:
        sheet = os.path.join(out_dir, f"{stem}_bundle_marksheet.docx")
        with open(sheet, "wb") as fh:
            fh.write(X.bundle_marksheet_doc(papers, class_label))
        docx_paths.append(sheet)
        result["bundle_marksheet"] = sheet
    if want_pdf:
        made = _convert(docx_paths) or []
        by_stem = {os.path.splitext(os.path.basename(p))[0]: p for p in made}
        pdfs: list[str] = []
        for i in range(1, n + 1):
            key = f"{stem}_variant_{i:0{pad}d}"
            if key in by_stem:
                target = os.path.join(out_dir, key + ".pdf")
                shutil.move(by_stem[key], target)
                pdfs.append(target)
        result["pdf"] = pdfs                           # type: ignore[assignment]
        if sheet:
            key = f"{stem}_bundle_marksheet"
            if key in by_stem:
                target = os.path.join(out_dir, key + ".pdf")
                shutil.move(by_stem[key], target)
                result["bundle_marksheet_pdf"] = target
    return result


def batch_save(entries: list[tuple[object, str, dict]], out_dir: str,
               want_pdf: bool = True) -> dict[str, list[str]]:
    """Save many papers (and their marksheets) with one LibreOffice pass.

    ``entries`` is ``[(paper, file_stem, extra_conf), ...]`` where ``file_stem``
    is the output filename without extension.  Returns
    ``{"docx": [...], "pdf": [...], "marksheet": [...], "marksheet_pdf": [...]}``.
    """
    os.makedirs(out_dir, exist_ok=True)
    docx_paths: list[str] = []
    sheet_paths: list[str] = []
    result: dict[str, list[str]] = {"docx": [], "pdf": [],
                                    "marksheet": [], "marksheet_pdf": []}
    for paper, stem, extra in entries:
        stem = os.path.splitext(stem)[0]
        base = os.path.join(out_dir, stem)
        save_docx(paper, base + ".docx", imgs=extra.get("imgs"),
                  allow_fetch=extra.get("allow_fetch", False))
        result["docx"].append(base + ".docx")
        docx_paths.append(base + ".docx")
        if extra.get("marksheet"):
            sm = save_marksheet(paper, base, want_pdf=False)
            result["marksheet"].append(sm["docx"])
            sheet_paths.append(sm["docx"])
    if want_pdf and (docx_paths or sheet_paths):
        pdfs = _convert(docx_paths + sheet_paths) or []
        by_stem = {os.path.splitext(os.path.basename(p))[0]: p for p in pdfs}
        for _paper, stem, extra in entries:
            stem = os.path.splitext(stem)[0]
            target = os.path.join(out_dir, stem)
            if stem in by_stem:
                shutil.move(by_stem[stem], target + ".pdf")
                result["pdf"].append(target + ".pdf")
            sheet_stem = stem + "_marksheet"
            if sheet_stem in by_stem:
                shutil.move(by_stem[sheet_stem], target + "_marksheet.pdf")
                result["marksheet_pdf"].append(target + "_marksheet.pdf")
    return result