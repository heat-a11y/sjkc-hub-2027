"""Pure-stdlib .docx writer for the exam papers.

Implements a minimal but fully valid Office Open XML document (A4, Arial)
using only ``zipfile`` and string building — no third-party dependency,
mirroring the pure-stdlib philosophy of Penjana RPH Mingguan.  The layout
follows the official UPSA 2026 SJKC Bahasa Inggeris papers:

    header (exam title / year / subject / duration)
    Nama · Kelas  |  Untuk Kegunaan Pemeriksa marks grid
    ARAHAN
    PART 1..7 with questions
    optional OMR-style answer sheet
    optional SKEMA JAWAPAN (answer key)
"""

from __future__ import annotations

import html
import os
import zipfile

from . import art, data as D
from .models import MCQItem, WordItem, WriteItem, Part, Paper

XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _rpr(bold=False, italic=False, underline=False, sz=22, color=None):
    out = ["<w:rPr>"]
    if color:
        out.append(f'<w:color w:val="{color}"/>')
    out.append('<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>')
    if bold:
        out.append("<w:b/>")
    if italic:
        out.append("<w:i/>")
    if underline:
        out.append("<w:u w:val=\"single\"/>")
    out.append(f'<w:sz w:val="{sz}"/>')
    out.append(f'<w:szCs w:val="{sz}"/>')
    out.append("</w:rPr>")
    return "".join(out)


def run(text, bold=False, italic=False, underline=False, sz=22, color=None,
        font=None) -> str:
    rp = _rpr(bold, italic, underline, sz, color)
    if font:
        rp = rp.replace("Arial", font, 1)
    return (f"<w:r>{rp}<w:t xml:space=\"preserve\">{_esc(text)}</w:t></w:r>")


def _para(children: list[str] | str, *, align=None, before=0, after=60,
          left=None, hanging=None, bold_all=False, sz=22) -> str:
    if isinstance(children, str):
        children = [children]
    ppr = ["<w:pPr>"]
    ppr.append(f'<w:spacing w:before="{before}" w:after="{after}" '
               f'w:line="276" w:lineRule="auto"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if left is not None or hanging is not None:
        ppr.append(f'<w:ind w:left="{left or 0}" w:hanging="{hanging or 0}"/>')
    ppr.append("</w:pPr>")
    if bold_all:
        children = [run(_children_text(c), bold=True, sz=sz) if isinstance(c, str)
                    else c for c in children]
    return "<w:p>" + "".join(ppr) + "".join(children) + "</w:p>"


def _children_text(c) -> str:
    import re
    return re.sub(r"<[^>]+>", "", c)


def para(text, *, bold=False, italic=False, underline=False, align=None,
         before=0, after=60, left=None, hanging=None, sz=22, color=None):
    return _para([run(text, bold=bold, italic=italic, underline=underline,
                      sz=sz, color=color)],
                 align=align, before=before, after=after, left=left,
                 hanging=hanging)


def page_break() -> str:
    return ('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            '<w:r><w:br w:type="page"/></w:r></w:p>')


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------

def _borders(args: dict) -> str:
    out = ["<w:tblBorders>"]
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        val = args.get(edge, "single")
        if val == "none":
            out.append(f'<w:{edge} w:val="none"/>')
        else:
            out.append(f'<w:{edge} w:val="true" w:sz="4" w:space="0" '
                       f'w:color="000000"/>')
    out.append("</w:tblBorders>")
    return "".join(out)


def _cell_borders(bottom_only=False) -> str:
    if not bottom_only:
        return ""
    b = ('<w:tcBorders><w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
         '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
         f'<w:bottom w:val="true" w:sz="6" w:space="0" w:color="000000"/>'
         '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
         '</w:tcBorders>')
    return b


Cell = list  # list of block strings (paragraphs / tables)


def table(rows: list[list[Cell]], widths: list[float] | None = None,
          grid: list[str] | None = None, grid_span: list[list[int]] | None = None,
          header_shade: str | None = None, bottom_rules: list[list[bool]] | None = None) -> str:
    """Build a table.  ``grid`` is the gridCol units list (twips); when absent it
    is derived from ``widths`` (fractions).  ``grid_span[j][i]`` may override row
    cell spans (ints >= 1)."""
    if grid is None:
        if widths is None:
            widths = [1.0 / len(rows[0])] * len(rows[0])
        total = 0
        for r in rows[:-1] if len(rows) > 1 else rows:
            if len(r) > len(widths):
                widths = list(widths) + [1.0] * (len(r) - len(widths))
        total = sum(widths)
        grid = [int(min(w / total * 9638, 9638)) for w in widths]
    tw = sum(grid)
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{tw}" w:type="dxa"/>',
           '<w:tblLayout w:type="fixed"/>', _borders({}),
           '<w:tblLook w:val="04A0"/>', "</w:tblPr>",
           '<w:tblGrid>' + "".join(f'<w:gridCol w:w="{g}"/>' for g in grid) +
           "</w:tblGrid>"]
    for ri, row in enumerate(rows):
        spans = (grid_span[ri] if grid_span and ri < len(grid_span)
                 else [1] * len(row))
        out.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>")
        for ci, cell in enumerate(row):
            span = spans[ci] if ci < len(spans) else 1
            bottom = (bottom_rules[ri][ci] if bottom_rules and
                      ri < len(bottom_rules) and ci < len(bottom_rules[ri])
                      else False)
            tcpr = ["<w:tcPr>"]
            tcpr.append(f'<w:tcW w:w="{grid[ci] * span}" w:type="dxa"/>')
            if span > 1:
                tcpr.append(f'<w:gridSpan w:val="{span}"/>')
            tcpr.append('<w:vAlign w:val="center"/>')
            if bottom:
                tcpr.append(_cell_borders(bottom_only=True))
            tcpr.append("</w:tcPr>")
            out.append("<w:tc>" + "".join(tcpr))
            blocks = cell if isinstance(cell, list) else [cell]
            for block in blocks:
                if block:
                    out.append(block)
            out.append("</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    out.append(para("", before=0, after=0))   # trailing paragraph (spec)
    return "".join(out)


# ---------------------------------------------------------------------------
# full document
# ---------------------------------------------------------------------------

def _content_types() -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            "<Default Extension=\"rels\" "
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "<Default Extension=\"xml\" "
            'ContentType="application/xml"/>'
            "<Default Extension=\"png\" "
            'ContentType="image/png"/>'
            "<Default Extension=\"jpeg\" "
            'ContentType="image/jpeg"/>'
            "<Override PartName=\"/word/document.xml\" "
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/>'
            "<Override PartName=\"/word/styles.xml\" "
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.styles+xml"/>'
            "<Override PartName=\"/docProps/core.xml\" "
            'ContentType="application/vnd.openxmlformats-package.'
            'core-properties+xml"/>'
            "</Types>")


def _root_rels() -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/'
            'relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>")


def _doc_rels() -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/styles" Target="styles.xml"/>'
            "</Relationships>")


def _styles() -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
            '<w:docDefaults><w:rPrDefault><w:rPr>'
            '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>'
            '<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr/></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
            "</w:styles>")


def _core(school: str) -> str:
    s = _esc(school or "SJKC EXAM")
    return (XML + "<cp:coreProperties "
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
f"<dc:title>{s} - Exam Paper</dc:title>"
             "<dc:creator>Exam Paper Generator</dc:creator>"
            "</cp:coreProperties>")


# ---------------------------------------------------------------------------
# paper renderer
# ---------------------------------------------------------------------------

def _para_with_number(qno: int, stem: str, *, bold_stem=False, sz=22) -> str:
    num = run(f"{qno}.", bold=True, sz=sz)
    body = run(" " + stem, bold=bold_stem, sz=sz)
    return _para([num, body], after=40, left=0)


def _option_lines(options: list[str], answer: int | None = None, sz=22,
                  year=None) -> list[str]:
    blocks = []
    labels = D.option_labels(len(options), year)
    for i, opt in enumerate(options):
        label = run(labels[i], bold=True, sz=sz)
        body = run(" " + opt, sz=sz)
        blocks.append(_para([label, body], after=20, left=567, hanging=283))
    return blocks


def _cloze_option_lines(qno: int, options: list[str], sz=22,
                        year=None) -> list[str]:
    """Options-only cloze row, e.g. ``6.  A. drink`` / ``    B. drinks``.

    Mirrors the real UPSA Part 2 layout: the passage keeps its numbered
    blanks inline and each question is just the lettered options after the
    question number (no restated sentence, no "Choose the correct answer").
    """
    blocks = []
    labels = D.option_labels(len(options), year)
    for i, opt in enumerate(options):
        label = run(labels[i], bold=True, sz=sz)
        body = run(" " + opt, sz=sz)
        if i == 0:
            num = run(f"{qno}.", bold=True, sz=sz)
            blocks.append(_para([num, run("  ", sz=sz), label, body],
                                after=20, left=0))
        else:
            blocks.append(_para([label, body], after=20, left=567, hanging=283))
    return blocks


def _topic_hint_line(p: Part) -> list[str]:
    topic = getattr(p, "topic", "") or ""
    word = art.hint_for_topic(topic)
    if not word:
        return []
    return [para(word, bold=True, after=40, sz=24)]


def _marks_table_cell(rows: list[tuple[str, int, int]]) -> Cell:
    head = [para("For Examiner Use", bold=True, align="center",
                 after=40, sz=18)]
    head.append(para("Examiner's Name :", after=20, sz=18))
    cells: list[list[Cell]] = [
        [[para("Part", bold=True, align="center", after=10, sz=18)],
         [para("Full Marks", bold=True, align="center", after=10, sz=18)],
         [para("Marks Obtained", bold=True, align="center", after=10, sz=18)]],
    ]
    for label, marks, _got in rows:
        cells.append([[para(label, bold=(label == "TOTAL"), align="center", after=10, sz=18)],
                      [para(str(marks), align="center", after=10, sz=18)],
                      [para("", after=10, sz=18)]])
    return head + [table(cells, widths=[0.42, 0.26, 0.32])]


def _crest_emus(data: bytes) -> tuple[int, int]:
    """(cx, cy) EMUs for a school-crest image fitted in a 3.2 x 3.2 cm box."""
    dims = art.image_dims(data)
    w_cm, h_cm = 3.2, 3.2
    if dims and dims[0] > 0 and dims[1] > 0:
        iw, ih = dims
        s = min(3.2 / iw, 3.2 / ih) * 320
        w_cm, h_cm = iw * s / 320, ih * s / 320
    return int(w_cm * art.EMU_CM), int(h_cm * art.EMU_CM)


def _crest_image(meta: dict, img_refs: dict, pic_no: int = 9001) -> str:
    path = str(meta.get("crest") or "").strip() or D.default_crest_path()
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except Exception:
        return ""
    if not art.image_dims(data):
        return ""
    fname = os.path.basename(path)
    img_refs["crest"] = ("rIdCrest", fname, data)
    cx, cy = _crest_emus(data)
    return _picture_block("rIdCrest", pic_no, fname, cx, cy)


def _qr_image(meta: dict, img_refs: dict, pic_no: int = 9002) -> str:
    """Register + return the pupil-ID QR drawing XML ('' when unused)."""
    pupil = str(meta.get("pupil_id") or "").strip()
    if not pupil or not meta.get("qr"):
        return ""
    try:
        from . import qr as _qr
        data = _qr.qr_png(pupil)
    except (ValueError, ImportError):
        return ""
    img_refs["qr"] = ("rIdQr", "qr.png", data)
    scale = 3 if min(max(len(pupil), 4), 60) > 28 else 3
    side_cm = 2.4
    cx = int(side_cm * art.EMU_CM)
    return _picture_block("rIdQr", pic_no, "qr.png", cx, cx)


def _header_block(paper: Paper, img_refs: dict | None = None) -> list[str]:
    meta = paper.meta
    lang = meta.get("lang", "en")
    exam_type = meta.get("exam_type", "upsa")
    year, session = meta.get("year"), meta.get("session")
    img_refs = img_refs if img_refs is not None else {}
    blocks = []
    crest = _crest_image(meta, img_refs)
    if crest:
        # The school crest sits above everything, centred, on the first page
        # (_picture_block already emits its own centred paragraph).
        blocks.append(crest)
    cap = D.EXAM_CAPTION.get(exam_type, D.EXAM_CAPTION["upsa"])
    blocks.append(para("  \u00b7  ".join(cap[l] for l in ("en", "ms", "zh")),
                       align="center", before=0, after=10, sz=20))
    blocks += [para(D.EXAM_ABBR.get(exam_type, "UP SA"), bold=True,
                    align="center", before=0, after=20, sz=34),
               para(f"YEAR {year} SESSION {session}", bold=True, align="center",
                    after=20, sz=28),
               para(f"{meta.get('subject', 'English Language')} "
                    f"({meta.get('subject_code', '013')})", bold=True,
                    align="center", after=10, sz=24),
               para(paper.duration(), align="center", after=120, sz=22)]

    identity = []
    school = str(meta.get("school") or "").strip()
    teacher = str(meta.get("teacher") or "").strip()
    if school or teacher:
        identity.append("  •  ".join(
            [part for part in
             ((f"School: {school}" if school else ""),
              (f"Teacher: {teacher}" if teacher else "")) if part]))
    pupil = str(meta.get("pupil_id") or "").strip()
    if pupil:
        identity.append(f"Pupil ID: {pupil}")
    if identity:
        blocks.append(para("\n".join(identity), align="center", after=60,
                           sz=20))

    name = para("Name:", sz=22)
    line1 = para("_" * 52, sz=22, after=120)
    klas = para("Class:", sz=22)
    line2 = para("_" * 52, sz=22, after=20)

    left_cell: Cell = [name, line1, klas, line2]
    right_cell: Cell = _marks_table_cell(paper.marks_table)
    header_tbl = table([[left_cell, right_cell]], widths=[0.5, 0.5])
    blocks.append(header_tbl)
    qr = _qr_image(meta, img_refs)
    if qr:
        blocks.append(qr)
        blocks.append(para(f"Pupil ID: {pupil}", align="center", after=20,
                           sz=18))
    blocks.append(para("", after=60))
    return blocks


def _arahan_block(conf: dict) -> str:
    lang = conf.get("lang", "en")
    head = para("INSTRUCTIONS:", bold=True, after=60, sz=24)
    items = "".join(para(f"{i}. {t}", after=30) for i, t in
                    enumerate(D.ARAHAN.get(lang, D.ARAHAN["en"]), 1))
    return head + items


def _part_heading(p: Part, page_break: bool = False) -> str:
    ppr = ['<w:pPr>',
           '<w:spacing w:before="120" w:after="40" w:line="276" '
           'w:lineRule="auto"/>']
    if page_break:
        ppr.append("<w:pageBreakBefore/>")
    ppr.append("<w:keepNext/>")
    ppr.append("</w:pPr>")
    return ("<w:p>" + "".join(ppr) +
            run(f"PART {p.num} [{p.marks} marks]", bold=True, sz=24) + "</w:p>")


def _questions_range(p: Part) -> str:
    qs = p.qnos()
    if not qs:
        return ""
    lab = "Questions" if len(qs) > 1 or qs[0] != p.qfirst else "Question"
    if len(qs) == 1:
        return para(f"{lab} {qs[0]}", after=40)
    return para(f"{lab} {qs[0]} to {qs[-1]}", after=40)


def _lead_text_block(p: Part) -> list[str]:
    if not p.lead_text:
        return []
    lines = str(p.lead_text).split("\n")
    out = []
    for ln in lines:
        out.append(para(ln, italic=False, after=60, left=0))
    return out


def _picture_block(r_id: str, pic_id: int, name: str, cx: int, cy: int) -> str:
    part = (f'<w:p><w:pPr><w:spacing w:before="40" w:after="80" '
            f'w:line="276" w:lineRule="auto"/><w:keepNext/>'
            f'<w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0" '
            f'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{pic_id}" name="{name}"/>'
            f'<wp:cNvGraphicFramePr>'
            f'<a:graphicFrameLocks noChangeAspect="1" '
            f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'
            f'</wp:cNvGraphicFramePr>'
            f'<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{pic_id}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill>'
            f'<a:blip r:embed="{r_id}" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
            f'<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            f'</pic:pic></a:graphicData></a:graphic></wp:inline>'
            f'</w:drawing></w:r></w:p>')
    return part


def _img_emus(data: bytes) -> tuple[int, int]:
    """Return (cx, cy) EMUs for ``data`` fitted inside a 10.5 x 9 cm box."""
    dims = art.image_dims(data)
    w_cm, h_cm = 10.5, 10.5 * 200 / 320    # default keeps the SVG 320x200 aspect
    if dims:
        iw, ih = dims
        if iw > 0 and ih > 0:
            scale = min(10.5 / iw, 9.0 / ih) * 320          # fit to the box
            w_cm, h_cm = iw * scale / 320, ih * scale / 320
    return int(w_cm * art.EMU_CM), int(h_cm * art.EMU_CM)


def _paragraph_blocks(p: Part, conf: dict, imgs: dict | None = None,
                      img_refs: dict | None = None,
                      page_break: bool = False,
                      pic_no: int = 1) -> list[str]:
    blocks: list[str] = []
    blocks.append(_part_heading(p, page_break=page_break))
    blocks.append(_questions_range(p))
    blocks.append(para(p.lead, italic=True, after=80))

    if imgs and p.topic in imgs:
        ref = img_refs.get(p.topic) if img_refs else None
        if ref is None:
            fname, _mime, data = imgs[p.topic]
            ref = (f"rIdImg{len(img_refs or {}) + 1}", fname, data)
            if img_refs is not None:
                img_refs[p.topic] = ref
        r_id, fname, data = ref
        cx, cy = _img_emus(data)
        blocks.append(_picture_block(r_id, pic_no, fname, cx, cy))

    has_passage = p.kind in ("cloze", "comprehension") and p.lead_text
    if has_passage:
        blocks.extend(_topic_hint_line(p))

    blocks.extend(_lead_text_block(p))

    is_sentences = p.kind == "writing" and p.style == "sentences"
    is_paragraph = p.kind == "writing" and p.style == "paragraph"
    if (is_sentences or is_paragraph) and p.example:
        ex = p.example
        blocks.append(para("Example:", bold=True, after=20))
        blocks.append(para(f"   {ex.prompt}   →   {ex.model}", italic=True, after=120))
    elif p.kind == "match" and p.example:
        # Part 4's worked example, numbered 0 so it is not a marked question.
        blocks.append(para(p.example, italic=True, after=80, left=567))

    qno = p.qfirst
    for item in p.items:
        if isinstance(item, MCQItem):
            if p.kind == "vocab" and item.stimulus:
                # Part 1: the short stimulus is printed first, then the
                # question, exactly as the official papers lay it out.
                for i, ln in enumerate(item.stimulus):
                    blocks.append(para(ln, bold=(i == 0), after=20, left=283))
                blocks.append(para("", after=20))
            if p.kind == "cloze":
                blocks.extend(_cloze_option_lines(qno, item.options,
                                                 year=conf.get("year")))
            elif p.kind == "match":
                # Part 4 gives the lettered texts above and asks the pupil to
                # pick a letter; printing "A. C / B. A / C. B" under the
                # description would mislabel them.
                blocks.append(_para_with_number(qno, item.stem))
            else:
                blocks.append(_para_with_number(qno, item.stem))
                blocks.extend(_option_lines(item.options,
                                            year=conf.get("year")))
        elif isinstance(item, WordItem):
            blocks.append(para(f"{qno}.  {item.clue}", after=30))
            blocks.append(para(f"       {item.pattern}", bold=False, after=20,
                               sz=20))
            blocks.append(para("", after=20))
        elif isinstance(item, WriteItem):
            blocks.append(_para_with_number(qno, item.prompt))
            for i, b in enumerate(item.bullets, 1):
                blocks.append(para(f"      {i}.  {b}", after=20, left=283))
            if item.word_count:
                kind_word = "email" if p.style == "email" else "letter"
                blocks.append(para(f"The {kind_word} should be between "
                                   f"{item.word_count}.", italic=True, after=80))
            if p.style == "email":
                if item.recipient:
                    blocks.append(para(f"To:  {item.recipient}", bold=True,
                                       after=20, sz=21))
                if item.subject:
                    blocks.append(para(f"Subject:  {item.subject}", bold=True,
                                       after=60, sz=21))
            elif p.style == "letter" and item.salutation:
                blocks.append(para(item.salutation, bold=True, after=60))
            if item.lines:
                line_rows = []
                for _ in range(item.lines):
                    line_rows.append([[para("", sz=22)]])
                blocks.append(table(line_rows, widths=[1.0],
                                    bottom_rules=[[True]] * item.lines))
            if p.style == "letter" and item.closing:
                blocks.append(para(item.closing, bold=True, before=80, after=20))
                blocks.append(para("_" * 28, after=20))
        qno += 1
    return blocks


def _answer_sheet(paper: Paper) -> list[str]:
    mcq_qs: list[int] = []
    for p in paper.parts:
        if p.kind in ("vocab", "cloze", "comprehension", "match") or \
           (p.kind == "words" and p.style == "choice"):
            qs = p.qnos()
            mcq_qs.extend(qs)
    writing_parts = [p for p in paper.parts if p.kind == "writing"]
    if not mcq_qs and not writing_parts:
        return []
    blocks = [page_break(),
              para("PAPER ANSWER SHEET", bold=True, align="center", after=20,
                   sz=28)]
    if mcq_qs:
        blocks.append(para("Tick ( / ) the correct answer for each question.",
                           align="center", after=100))
        rows = [[[para("Q", bold=True, align="center", sz=18)],
                 [para("A", bold=True, align="center", sz=18)],
                 [para("B", bold=True, align="center", sz=18)],
                 [para("C", bold=True, align="center", sz=18)]]]
        for q in mcq_qs:
            rows.append([[para(str(q), align="center", sz=18)],
                         [para("", sz=18)], [para("", sz=18)], [para("", sz=18)]])
        blocks.append(table(rows, grid=[700, 2400, 2400, 2400]))
    if writing_parts:
        blocks.append(para("WRITING", bold=True, align="center", before=240,
                           after=20, sz=24))
        blocks.append(para("Write your answers in the space provided.",
                           align="center", after=80))
        for p in writing_parts:
            qs = p.qnos()
            label = f"PART {p.num}"
            if qs:
                label += f"  (Questions {qs[0]} to {qs[-1]})" \
                    if len(qs) > 1 else f"  (Question {qs[0]})"
            blocks.append(para(label, bold=True, before=120, after=40))
            year = paper.year()
            if p.lines not in (None, 0):
                n_lines = p.lines
            elif p.style in ("letter", "email", "paragraph"):
                n_lines = 16 if year >= 5 else 10
            else:
                n_lines = 9 if year >= 5 else 6
            for _ in range(n_lines):
                blocks.append(para("", sz=22, after=20))
                blocks.append(para("_" * 58, sz=22, after=40))
    return blocks


def _answer_key(paper: Paper) -> list[str]:
    blocks = [page_break(),
              para("ANSWER KEY", bold=True, align="center", after=120, sz=28)]
    for p in paper.parts:
        rows = [[[para(f"PART {p.num}", bold=True, align="center", sz=18)],
                 [para("", sz=18)]]]
        qno = p.qfirst
        for item in p.items:
            if isinstance(item, MCQItem):
                ans = item.ans_text or item.answer_label
                detail = ""
            elif isinstance(item, WordItem):
                ans = item.answer
                detail = ""
            else:
                ans = "(sample answer)"
                detail = f" {item.model[:80]}" if item.model else ""
            rows.append([[para(f"{qno}.", sz=18)],
                         [para(f"{ans}{detail}", sz=18)]])
            qno += 1
        blocks.append(table(rows, grid=[700, 8938]))
    return blocks


def _jsu(paper: Paper) -> list[str]:
    """The Jadual Spesifikasi Ujian, printed after the answer key.

    Round 28: the table is built per paper by :mod:`exam_gen.jsu` -- one row
    per printed question, that question's own skill, text type, theme, learning
    standard, Bloom level and CEFR level -- and the summary the ministry sheet
    closes with (items per level, LOTS:HOTS, total marks) is printed under it.
    """
    from . import jsu as J
    t = J.table(paper)
    L = J.labels(paper)
    blocks = [page_break(),
              para(J.title(paper), bold=True, align="center", after=60,
                   sz=24),
              para(f"{L['source']}: {t['source']}   "
                   f"{L['total_marks']}: {t['total_marks']}   "
                   f"{L['time']}: {paper.duration()}",
                   italic=True, align="center", after=120, sz=16)]
    head = [L["no"], L["skill"], L["focus"], L["theme"], L["standard"],
            L["taxonomy"], L["cefr"], L["marks"]]
    rows = [[[para(h, bold=True, align="center", sz=15)] for h in head]]
    for r in t["rows"]:
        marks = r["marks"]
        mark_text = (f"{marks:g}" if float(marks).is_integer()
                     else f"{marks:.1f}")
        rows.append([
            [para(str(r["qno"]), align="center", sz=15)],
            [para(r["skill"], sz=15)],
            [para(r["focus"], sz=15)],
            [para(r["theme"], sz=15)],
            [para(r["standard"], sz=14)],
            [para(r["taxonomy"], sz=15)],
            [para(r["level"], sz=15)],
            [para(mark_text, align="center", sz=15)],
        ])
    blocks.append(table(rows, grid=[430, 1500, 1450, 1150, 2500, 900, 800,
                                    500]))
    lots, hots = t["lots_hots"]
    tl, th = t.get("target_lots_hots") or (0, 0)
    lots_line = f"LOTS : HOTS = {lots} : {hots}"
    if tl and th:
        lots_line += f"   ({L['target']}: {tl} : {th})"
    blocks.append(para("", after=0, sz=12))
    blocks.append(para(lots_line, bold=True, sz=17))
    mix_line = "   ".join(f"{k}: {v}" for k, v in t["objective_mix"].items())
    blocks.append(para(f"{L['objective_mix']}: {mix_line}", sz=17))
    blocks.append(para(f"{L['questions']}: {len(t['rows'])}   "
                       f"{L['total_marks']}: {t['total_marks']}", sz=17))
    return blocks


def _short(text, n=64) -> str:
    t = " ".join(str(text).split())
    return t if len(t) <= n else t[: n - 1] + "…"


def mark_sheet_doc(paper: Paper) -> bytes:
    """Standalone 'MARKING SHEET' (.docx) for teachers."""
    ms = __import__("exam_gen.bank", fromlist=["mark_sheet"]).mark_sheet(paper)
    meta = paper.meta
    body = _mark_sheet_blocks(meta, ms)
    doc = (XML +
           "<w:document xmlns:w=\"http://schemas.openxmlformats.org/"
           "wordprocessingml/2006/main\"><w:body>" +
           "".join(body) +
           sect_pr() +
           "</w:body></w:document>")
    return _zip(doc, meta.get("school", ""), None)


def _mark_sheet_blocks(meta: dict, ms: dict, school_line: bool = True,
                       student_line: bool = True) -> list[str]:
    """Shared marking-sheet body (used by the single + bundle sheets)."""
    blocks = [para("MARKING SHEET", bold=True, align="center",
                   before=0, after=80, sz=30)]
    if school_line:
        blocks.append(para(f"School: {meta.get('school', '')}", after=20))
        blocks.append(para(f"Teacher: {meta.get('teacher', '')}", after=20))
    blocks.append(para("Student: " if student_line else "",
                       after=120, sz=18 if not student_line else 22))
    for part in ms["parts"]:
        rows = [[[para(f"PART {part['part']}  [{part['marks']} marks]",
                       bold=True, align="center", sz=18)]]]
        rows.append([[para("No.", bold=True, align="center", sz=18)],
                     [para("Brief", bold=True, align="center", sz=18)],
                     [para("Marks", bold=True, align="center", sz=18)]])
        for it in part["items"]:
            rows.append([[para(str(it["q"]), align="center", sz=18)],
                         [para(_short(it["text"]), sz=18)],
                         [para("", align="center", sz=18)]])
        rows.append([[para("Section", bold=True, align="center", sz=18)],
                     [para(str(part["marks"]), bold=True, align="center",
                           sz=18)],
                     [para("", align="center", sz=18)]])
        blocks.append(table(rows, grid=[1100, 6500, 2100],
                            grid_span=[[3]] + [[1, 1, 1]] * (len(rows) - 1)))
    total = ms["total"]
    blocks.append(table(
        [[[para("TOTAL", bold=True, align="center", sz=20)],
          [para(str(total), bold=True, align="center", sz=20)],
          [para("", align="center", sz=20)]]],
        grid=[1100, 2500, 2100]))
    blocks.append(para(f"Total overall:  ______  /  {total}",
                       bold=True, before=160, after=20, sz=22))
    return blocks


def bundle_marksheet_doc(papers, class_label: str = "",
                         rows: int = 24) -> bytes:
    """One merged 'MARKING SHEET' (.docx) covering the whole class bundle.

    A grid row per pupil (enter marks in the P1..P7 columns and TOTAL is
    summed by the teacher); a per-part average row is computed when the first
    grid row already holds marks — the sheet is meant to be filled in, so the
    grid ships empty.
    """
    from . import marks as _marks
    base = papers[0] if papers else None
    cols = _marks.part_columns(papers) if papers else []
    inside = []

    grid = [[[para("No.", bold=True, align="center", sz=16)],
             [para("Pupil", bold=True, align="center", sz=16)],
             *[[para(c, bold=True, align="center", sz=16)] for c, _ in cols],
             [para("Grade", bold=True, align="center", sz=16)]]]
    n_cols = len(cols)                       # P1..P7 + TOTAL
    for i in range(rows):
        row = [[para(str(i + 1), align="center", sz=16)],
               [para("", sz=16)],
               *[[para("", sz=16)] for _ in range(n_cols)],
               [para("", sz=16)]]
        grid.append(row)
    inside.append(para("MARKING SHEET — CLASS BUNDLE", bold=True,
                       align="center", before=0, after=30, sz=28))
    inside.append(para(f"Class: {class_label}", after=20, sz=20))
    for p in (base.parts if base else []):
        qs = p.qnos()
        qtext = "—" if not qs else (
            f"{qs[0]} to {qs[-1]}" if len(qs) > 1 else str(qs[0]))
        inside.append(para(f"PART {p.num} [{p.marks} marks]  "
                           f"Questions {qtext}", after=10, sz=18))
    inside.append(para("", after=40))
    widths = [0.08, 0.26]
    for _ in range(n_cols):
        widths.append(0.072)
    widths.append(0.09)
    inside.append(table(grid, grid=[w * 12000 for w in widths]))
    total = cols[-1][1] if cols else 50
    inside.append(para(f"Total: ______ / {total}", bold=True, before=160,
                       after=20, sz=20))
    base_meta = base.meta if base else {}
    doc = (XML +
           "<w:document xmlns:w=\"http://schemas.openxmlformats.org/"
           "wordprocessingml/2006/main\"><w:body>" +
           "".join(inside) +
           sect_pr() +
           "</w:body></w:document>")
    return _zip(doc, base_meta.get("school", ""), None)


def render_doc(paper: Paper, imgs: dict | None = None,
               allow_fetch: bool = True) -> bytes:
    """Render ``paper`` to a .docx byte blob.

    ``imgs`` may supply pre-resolved ``{topic: (fname, mime, data)}`` entries
    (e.g. from an app-side photo worker); when omitted the renderer resolves
    topics itself.  ``allow_fetch=False`` only consults the on-disk photo cache
    (never the network), which keeps GUI saves instant once the background
    worker has warmed the cache.  Each topic is embedded at most once, so two
    parts sharing a topic reference the same image instead of duplicating it
    (a duplicate media name makes LibreOffice reject the file).
    """
    meta = paper.meta
    lang = meta.get("lang", "bm")
    body: list[str] = []
    img_refs: dict[str, tuple[str, str, bytes]] = {}
    body.extend(_header_block(paper, img_refs))
    body.append(_arahan_block(meta))

    if meta.get("pictures", True) and not imgs:
        from types import SimpleNamespace as _NS
        imgs = {}
        for part in paper.parts:
            if not part.topic or part.topic in imgs:
                continue
            cands = art.photo_candidates(_NS(topic=part.topic,
                                             photo_query=part.photo_query))
            data = None
            for query in cands:
                if not query:
                    continue
                try:
                    data = art.photo_bytes(query, allow_fetch=allow_fetch)
                except Exception:
                    data = None
                if data:
                    break
            if data:
                imgs[part.topic] = (f"photo{len(imgs) + 1}.jpg",
                                    "image/jpeg", data)

    for i, p in enumerate(paper.parts):
        body.extend(_paragraph_blocks(p, meta, imgs, img_refs,
                                      page_break=i > 0, pic_no=i + 1))

    if meta.get("answer_sheet"):
        body.extend(_answer_sheet(paper))
    if meta.get("answer_key"):
        body.extend(_answer_key(paper))
    # The JSU is a teacher's document, so it follows the answer key: a paper
    # exported without the key (a pupil's copy) does not carry it either.
    if meta.get("jsu", meta.get("answer_key", True)):
        body.extend(_jsu(paper))

    doc = (XML +
           "<w:document xmlns:w=\"http://schemas.openxmlformats.org/"
           "wordprocessingml/2006/main\"><w:body>" +
           "".join(body) +
           sect_pr() +
           "</w:body></w:document>")
    return _zip(doc, meta.get("school", ""), img_refs)


def sect_pr() -> str:
    return ('<w:sectPr><w:footerReference w:type="default" r:id="rIdF" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
            'w:header="708" w:footer="708" w:gutter="0"/>'
            "</w:sectPr>")


def _footer_page() -> str:
    return ('<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            "</w:p></w:ftr>")


def _zip(doc: str, school: str,
         img_refs: dict[str, tuple[str, str, bytes]] | list | None = None) -> bytes:
    items = list((img_refs or {}).values()) if isinstance(img_refs, dict) \
        else list(img_refs or [])
    seen: set[str] = set()
    rels = []
    for rid, fname, _data in items:
        if fname in seen:
            continue
        seen.add(fname)
        rels.append(
            f'<Relationship Id="{rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="media/{fname}"/>')
    img_rels = "".join(rels)
    _rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rIdF" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
             'relationships/footer" Target="footer1.xml"/>'
             '<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
             'relationships/styles" Target="styles.xml"/>'
             + img_rels +
             "</Relationships>")
    import io as _io
    fh = _io.BytesIO()
    with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _content_types())
        z.writestr("_rels/.rels", _root_rels())
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", _rels)
        z.writestr("word/styles.xml", _styles())
        z.writestr("word/footer1.xml", _footer_page())
        for _rid, fname, data in items:
            if fname not in seen:
                continue
            seen.discard(fname)
            z.writestr(f"word/media/{fname}", data)
        z.writestr("docProps/core.xml", _core(school))
    return fh.getvalue()

# ---------------------------------------------------------------------------
# Round 31 (F2): standalone teacher marking scheme
# ---------------------------------------------------------------------------
def mark_scheme_rows(paper: Paper) -> list[dict]:
    """One row per question: qno, part, ao, marks, answer, model, note.

    Marks are split evenly across a part's items (``Part.marks_per_q``) so the
    column always sums to the paper total of 50; a teacher marking from this
    sheet can add the marks up as a check on their own arithmetic.

    ``ao`` is the attainment objective the part kind serves (Round 39, see
    ``data.AO_KIND``), so the sheet can be audited against the DSKP by
    objective and not only by part number.
    """
    rows: list[dict] = []
    for p in paper.parts:
        n = len(p.items)
        per = (p.marks / n) if n else 0.0
        ao = D.ao_for_kind(p.kind)
        for i, item in enumerate(p.items):
            qno = p.qfirst + i
            marks = per if n else 0.0
            answer = ""
            model = ""
            note = ""
            if isinstance(item, MCQItem):
                answer = item.ans_text or item.answer_label or ""
                opts = list(getattr(item, "options", []) or [])
                if opts and answer in opts:
                    note = f"option {opts.index(answer) + 1} of {len(opts)}"
            elif isinstance(item, WordItem):
                answer = str(getattr(item, "answer", "") or "")
            else:                                   # WriteItem
                answer = "(sample answer)"
                model = str(getattr(item, "model", "") or "")
            rows.append({
                "qno": qno, "part": p.num, "kind": p.kind, "ao": ao,
                "marks": marks, "answer": answer, "model": model, "note": note,
            })
    return rows


def mark_scheme_ao_totals(paper: Paper) -> list[tuple[str, str, float, str]]:
    """``[(ao, label, marks, parts)]`` for the AO summary table.

    Ordered AO1 first, so the summary reads as a climb from recall to
    production.  Every AO appears even at zero marks, because "nothing was
    assessed here" is itself worth stating in a marking scheme.
    """
    tally: dict[str, float] = {ao: 0.0 for ao in D.AOS}
    where: dict[str, list[int]] = {ao: [] for ao in D.AOS}
    for row in mark_scheme_rows(paper):
        ao = row["ao"]
        tally[ao] = tally.get(ao, 0.0) + row["marks"]
        if row["part"] not in where[ao]:
            where[ao].append(row["part"])
    return [(ao, D.AO_LABEL[ao], tally[ao],
             ", ".join(str(n) for n in where[ao]) or "-")
            for ao in D.AOS]


def mark_scheme_doc(paper: Paper, conf: dict | None = None) -> bytes:
    """Standalone 'MARKING SCHEME' (.docx) for teachers only.

    Deliberately a separate document from the pupil paper, so the paper can be
    handed out while the scheme is held back.
    """
    meta = dict(getattr(paper, "meta", {}) or {})
    if conf:
        meta.update({k: v for k, v in conf.items() if v})
    rows = mark_scheme_rows(paper)
    total = sum(r["marks"] for r in rows)

    blocks = [para("MARKING SCHEME", bold=True, align="center", after=40, sz=30),
              para("Teacher copy - do not distribute to pupils",
                   align="center", after=120, sz=18)]

    head = [meta.get("school", "") or "", meta.get("teacher", "") or "",
            f"Year {paper.year()}",
            f"{paper.duration()}"]
    blocks.append(para("  \u00b7  ".join(x for x in head if x),
                       align="center", after=140, sz=20))

    # -- Round 39: what the paper weighs, by attainment objective ----------
    blocks.append(para("MARKS BY ATTAINMENT OBJECTIVE", bold=True,
                       after=60, sz=22))
    ao_body = [[[para("AO", bold=True, align="center", sz=16)],
                [para("What is assessed", bold=True, sz=16)],
                [para("Parts", bold=True, align="center", sz=16)],
                [para("Marks", bold=True, align="center", sz=16)]]]
    for ao, label, marks, where in mark_scheme_ao_totals(paper):
        mk = (f"{marks:g}" if abs(marks - round(marks)) < 1e-9
              else f"{marks:.1f}")
        ao_body.append([[para(ao, bold=True, align="center", sz=16)],
                        [para(label, sz=16)],
                        [para(where, align="center", sz=16)],
                        [para(mk, align="center", sz=16)]])
    ao_body.append([[para("", sz=16)],
                    [para("Total", bold=True, align="right", sz=16)],
                    [para("", sz=16)],
                    [para(f"{total:g}", bold=True, align="center", sz=16)]])
    blocks.append(table(ao_body, grid=[900, 5338, 1000, 1400]))
    blocks.append(para("", sz=12, after=40))

    for p in paper.parts:
        blocks.append(para(f"PART {p.num}  ({p.marks} marks)", bold=True,
                           after=60, sz=22))
        body = [[[para("Q", bold=True, align="center", sz=16)],
                 [para("AO", bold=True, align="center", sz=16)],
                 [para("Mark", bold=True, align="center", sz=16)],
                 [para("Answer", bold=True, sz=16)]]]
        for r in rows:
            if r["part"] != p.num:
                continue
            mk = (f"{r['marks']:g}" if abs(r["marks"] - round(r["marks"])) < 1e-9
                  else f"{r['marks']:.1f}")
            ans = r["answer"]
            if r["note"]:
                ans = f"{ans}  ({r['note']})"
            if r["model"]:
                ans = f"{ans}  e.g. {r['model']}"
            body.append([[para(str(r["qno"]), align="center", sz=16)],
                         [para(r["ao"], align="center", sz=16)],
                         [para(mk, align="center", sz=16)],
                         [para(ans, sz=16)]])
        blocks.append(table(body, grid=[700, 700, 900, 6338]))
        blocks.append(para("", sz=12, after=40))

    # -- Round 39: performance levels for the produced-writing parts --------
    written = [p for p in paper.parts
               if D.ao_for_kind(p.kind) == "AO3" and p.marks > 0]
    if written:
        blocks.append(para("PERFORMANCE LEVELS FOR THE WRITING PARTS",
                           bold=True, after=60, sz=22))
        blocks.append(para(D.PL_CAVEAT, sz=16, after=80))
        for p in written:
            blocks.append(para(f"Part {p.num} - {p.marks:g} marks", bold=True,
                               after=40, sz=18))
            pl_body = [[[para("Level", bold=True, align="center", sz=16)],
                        [para("Marks", bold=True, align="center", sz=16)],
                        [para("What the response looks like", bold=True,
                              sz=16)]]]
            for code, name, lo, hi, desc in D.pl_bands(p.marks):
                pl_body.append([[para(f"{code}\n{name}", align="center", sz=16)],
                                [para(f"{lo:g}-{hi:g}", align="center", sz=16)],
                                [para(desc, sz=16)]])
            blocks.append(table(pl_body, grid=[1300, 900, 6438]))
            blocks.append(para("", sz=12, after=40))

    blocks.append(para(f"TOTAL: {total:g} marks", bold=True, align="right",
                       after=0, sz=20))
    doc = (XML +
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>' + "".join(blocks) +
           sect_pr() + "</w:body></w:document>")
    return _zip(doc, meta.get("school", ""), None)


# ---------------------------------------------------------------------------
# Round 32 (F1): OMR bubble answer sheet
# ---------------------------------------------------------------------------
def _omr_cell(label: str, shd: bool) -> str:
    """One bubble: the letter above a dark rounded box to fill with a pencil."""
    fill = 'w:shd w:val="solid" w:color="FFFFFF" w:fill="000000"' if shd else ""
    inner = (f'<w:p><w:pPr><w:spacing w:after="0"/><w:jc w:val="center"/></w:pPr>'
             f'<w:r><w:t xml:space="preserve">{label}</w:t></w:r></w:p>'
             f'<w:p><w:pPr><w:spacing w:after="0"/><w:jc w:val="center"/>'
             f'<w:tcBorders></w:tcBorders></w:pPr>'
             f'<w:r><w:rPr><w:sz w:val="18"/></w:rPr>'
             f'<w:t xml:space="preserve">[_]</w:t></w:r></w:p>')
    tcpr = (f'<w:tcPr><w:tcW w:w="500" w:type="dxa"/>'
            f'<w:tcBorders></w:tcBorders>{fill}'
            f'<w:vAlign w:val="center"/></w:tcPr>')
    return f"<w:tc>{tcpr}{inner}</w:tc>"


def omr_sheet_doc(paper: Paper) -> bytes:
    """One-page-per-pupil OMR bubble sheet (.docx).

    Column headers carry the school, pupil name/class boxes and the exam, so a
    stack of these needs nothing else written on them.  Bubbles are drawn as
    letter-over-box rather than true OMR forms so the sheet is printable on a
    plain laser printer with no special stock.
    """
    from . import bank as _bank
    meta = getattr(paper, "meta", {}) or {}
    grid = _bank.omr_grid(paper)
    qs = grid["questions"]

    blocks = [para("ANSWER SHEET", bold=True, align="center", after=40, sz=30),
              para(f"Year {grid['year']}  \u00b7  {paper.duration()}  \u00b7  "
                   f"{grid['total_marks']} marks", align="center", after=100, sz=20)]

    ident = [[para("Name:", sz=18), para("", sz=18)],
             [para("Class:", sz=18), para("", sz=18)]]
    blocks.append(table(ident, grid=[2400, 7238]))
    blocks.append(para("Fill ONE bubble per question with a pencil. "
                       "Leave a row blank if you are not sure.",
                       align="center", after=100, sz=16))

    head = [[para("Q", bold=True, align="center", sz=16)]]
    for lab in ("A", "B", "C", "D"):
        head.append([para(lab, bold=True, align="center", sz=16)])
    head.append([para("Part", bold=True, align="center", sz=16)])
    hdr = [[c[0] for c in head]]
    blocks.append(table(hdr, grid=[700, 1700, 1700, 1700, 1700, 2178],
                        header_shade="DDDDDD"))

    rows = []
    for q in qs:
        row = [[para(str(q["qno"]), align="center", sz=16)]]
        if q["kind"] == "mcq":
            for lab in q["labels"]:
                row.append(_omr_cell(lab, False))
        else:
            row.append(_omr_cell("score", False))
        row.append(para(str(q["part"]), align="center", sz=16))
        rows.append(row)
    blocks.append(table(rows, grid=[700, 1700, 1700, 1700, 1700, 2178]))

    blocks.append(para("", sz=14, after=40))
    total = [[para("TOTAL", bold=True, sz=18),
              para("____ / 50", sz=18),
              para("Teacher:", sz=18),
              para("______________", sz=18),
              para("Date:", sz=18),
              para("__________", sz=18)]]
    blocks.append(table(total, grid=[1200, 1600, 1400, 2600, 900, 1678]))

    doc = (XML +
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>' + "".join(blocks) +
           sect_pr() + "</w:body></w:document>")
    return _zip(doc, meta.get("school", ""), None)
