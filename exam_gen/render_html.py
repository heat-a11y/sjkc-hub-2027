"""HTML preview of a generated paper (rendered inside WebKitGTK).

Mirrors the .docx layout as closely as practicality allows so the on-screen
preview matches the exported document.
"""

from __future__ import annotations

import html

from . import art, data as D
from .models import MCQItem, WordItem, WriteItem, Paper


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _page_css() -> str:
    return """
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 24px; background: #eceff4;
           font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; }
    .paper { max-width: 210mm; margin: 0 auto; background: #ffffff;
             color: #000; padding: 14mm 14mm 16mm; box-shadow: 0 4px 24px rgba(0,0,0,.18);
             font-size: 12.5pt; line-height: 1.45; }
    .center { text-align: center; }
    .exam-title { font-weight: 800; font-size: 17pt; margin: 2px 0; }
    .exam-year { font-weight: 700; font-size: 16pt; margin: 2px 0; }
    .exam-subj { font-weight: 700; font-size: 12pt; margin: 3px 0; }
    .exam-dur { font-size: 12pt; margin: 3px 0 14px; }
    table { border-collapse: collapse; width: 100%; }
    .hdr { margin-bottom: 12px; }
    .hdr td, .hdr th { border: 1px solid #000; padding: 6px 8px; vertical-align: top; }
    .marks th, .marks td { border: 1px solid #000; padding: 3px 6px;
                           text-align: center; font-size: 10.5pt; }
    .section-h { font-weight: 800; margin: 18px 0 2px; font-size: 13pt; }
    .q-range { margin: 2px 0; }
    .lead { font-style: italic; margin: 4px 0 10px; }
    .topic-hint { font-weight: 700; margin: 2px 0 6px; }
    .passage { border: 1px solid #333; padding: 10px 12px; margin: 8px 0 12px;
               text-align: justify; background: #fafafa; }
    .q { margin: 10px 0 2px; }
    .q .n { font-weight: 700; }
    .opts { margin: 0 0 4px 22px; }
    .opts div { margin: 1px 0; }
    .opt-l { font-weight: 700; }
    .stimulus { border-left: 2px solid #555; padding: 4px 0 4px 12px;
                margin: 8px 0 2px 22px; }
    .wordbox { border: 1px solid #333; padding: 6px 10px; margin: 6px 0 10px;
               background: #fafafa; }
    .pattern { letter-spacing: 5px; font-size: 13pt; margin: 2px 0 6px 22px; }
    .bullets { margin: 2px 0 4px 22px; }
    .write-lines { border-top: none; margin: 6px 0 14px; }
    .write-lines td { border: 0; border-bottom: 1px solid #000; height: 26px; }
    .example { font-style: italic; color: #333; margin: 4px 0; }
    .pagebr { page-break-before: always; }
    .key-table td, .key-table th { border: 1px solid #000; padding: 3px 8px;
                                   font-size: 11pt; }
    .key-table td.part { font-weight: 700; text-align: center; background: #eee; }
    .askey td, .askey th { border: 1px solid #000; padding: 3px 10px;
                           text-align: center; font-size: 11pt; }
    .note { font-size: 9.5pt; color: #555; }
    .pic { margin: 8px auto 12px; text-align: center; }
    .pic svg { width: 100%; max-width: 380px; height: auto; border: 1px solid #ccc;
               border-radius: 6px; background: #fff; display: inline-block; }
    .pic img { max-width: 380px; max-height: 320px; border: 1px solid #ccc;
               border-radius: 6px; display: inline-block; }
    .pic-ph { max-width: 380px; margin: 0 auto; border: 1px dashed #999;
              border-radius: 6px; padding: 14px 10px; background: #f6f6f6;
              color: #777; text-align: center; }
    .pic-ph-topic { font-weight: 700; color: #555; text-transform: capitalize; }
    .pic-ph-note { font-size: 9pt; margin-top: 2px; }
    .edit-banner { position: sticky; top: 0; z-index: 5; background: #0b57d0;
                   color: #fff; font-weight: 700; padding: 8px 12px;
                   border-radius: 6px; margin-bottom: 12px; text-align: center; }
    .editable [data-eid] { cursor: pointer; border-radius: 4px; }
    .editable [data-eid]:hover { outline: 2px dashed #0b57d0;
                                 background: #eaf1fd; }
    .partblock { position: relative; }
    span.src { display: block; font-size: 8pt; color: #777; margin-top: 2px; }
    @media (prefers-color-scheme: dark) {
      body { background: #1c1b1f; }
      .paper { background: #fff; }
    }
    """


def _header(paper: Paper) -> str:
    m = paper.meta
    lang = m.get("lang", "en")
    exam_type = m.get("exam_type", "upsa")
    crest = _crest_html(m)
    out = []
    if crest:
        # The school crest sits above everything, centred (Round 13/S2).
        out.append(f'<div class="center" style="margin-bottom:6px">{crest}</div>')
    cap = D.EXAM_CAPTION.get(exam_type, D.EXAM_CAPTION["upsa"])
    out.append('<div class="center" style="font-size:12pt;margin-bottom:4px">' +
               " &middot; ".join(_e(cap[l]) for l in ("en", "ms", "zh")) + "</div>")
    out += [f'<div class="center"><div class="exam-title">{_e(D.EXAM_ABBR.get(exam_type, "UP SA"))}</div>'
            f'<div class="exam-year">YEAR {_e(m["year"])} SESSION {_e(m["session"])}</div>'
            f'<div class="exam-subj">{_e(m.get("subject", "English Language"))} '
            f'({_e(m.get("subject_code", "013"))})</div>'
            f'<div class="exam-dur">{_e(paper.duration())}</div></div>']

    identity = []
    school = str(m.get("school") or "").strip()
    teacher = str(m.get("teacher") or "").strip()
    pupil = str(m.get("pupil_id") or "").strip()
    if school or teacher:
        identity.append("  •  ".join(
            p for p in ((f"School: {school}" if school else ""),
                        (f"Teacher: {teacher}" if teacher else "")) if p))
    if pupil:
        identity.append(f"Pupil ID: {pupil}")
    if identity:
        out.append('<div class="center" style="font-size:10.5pt">' +
                   "<br>".join(_e(x) for x in identity) + "</div>")

    marks = "".join(f"<tr><td>{_e(l)}</td><td>{v}</td><td></td></tr>"
                    for l, v, _g in paper.marks_table)
    right = ('<table class="marks"><tr><th colspan="3">For Examiner Use</th></tr>'
             '<tr><td colspan="3">Examiner\'s Name :</td></tr>'
             '<tr><th>Part</th><th>Full Marks</th><th>Marks Obtained</th></tr>'
             f"{marks}</table>")
    left = ('<div>Name:</div>'
            '<div style="margin:10px 0 8px">'
            '<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u></div>'
            '<div>Class:</div>')
    out.append('<table class="hdr"><tr>'
               f'<td style="width:50%">{left}</td>'
               f'<td style="width:50%">{right}</td></tr></table>')

    qr = _qr_html(m)
    if qr:
        out.append(f'<div class="pic" style="margin:6px auto">{qr}</div>'
                   f'<div class="center" style="font-size:10pt">Pupil ID: '
                   f'{_e(pupil)}</div>')
    return "\n".join(out)


def _crest_html(m: dict) -> str:
    import os
    path = str(m.get("crest") or "").strip() or D.default_crest_path()
    if not path or not os.path.exists(path):
        return ""
    try:
        data = open(path, "rb").read()
    except Exception:
        return ""
    if not art.image_dims(data):
        return ""
    import base64
    b64 = base64.b64encode(data).decode("ascii")
    mime = ("image/svg+xml" if data[:4] in (b"<svg", b"<SVG", b"<?xm")
            else "image/jpeg")
    if mime == "image/jpeg" and data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    return (f'<img class="crest" style="max-width:110px;max-height:110px" '
            f'src="data:{mime};base64,{b64}" alt="crest"/>')


def _qr_html(m: dict) -> str:
    pupil = str(m.get("pupil_id") or "").strip()
    if not pupil or not m.get("qr"):
        return ""
    try:
        from . import qr as _qr
        return (f'<img class="qr" style="width:88px;height:88px" '
                f'src="{_qr.qr_svg_data_uri(pupil)}" alt="QR"/>')
    except (ValueError, ImportError):
        return ""


def _arahan(paper: Paper) -> str:
    lang = paper.meta.get("lang", "en")
    items = "".join(f"<div>{i}. {_e(t)}</div>" for i, t in
                    enumerate(D.ARAHAN.get(lang, D.ARAHAN["en"]), 1))
    head = "INSTRUCTIONS:"
    return f'<div class="section-h">{head}</div>{items}'


def _part_html(p, pictures: bool = True, allow_fetch: bool = True,
               editable: bool = False, pidx: int = 0, year=None) -> str:
    def eid(i: int) -> str:
        return f' data-eid="P{pidx}:I{i}"' if editable else ""

    opt_labels = D.option_labels(8, year)

    out = [f'<div class="section-h"{eid(-1)}>PART {p.num} [{p.marks} marks]</div>']
    qs = p.qnos()
    if qs:
        lab = "Questions " if len(qs) > 1 else "Question "
        out.append(f'<div class="q-range">{lab}{qs[0]}{" to " + str(qs[-1]) if len(qs) > 1 else ""}</div>')
    out.append(f'<div class="lead"{eid(-1)}>{_e(p.lead)}</div>')
    if pictures and p.topic:
        out.append(f'<div class="pic">'
                   f'{art.picture_html(p, allow_fetch=allow_fetch)}</div>')
    if p.kind in ("cloze", "comprehension") and p.lead_text:
        hint = art.hint_for_topic(getattr(p, "topic", "") or "")
        if hint:
            out.append(f'<div class="topic-hint">{_e(hint)}</div>')
    if p.lead_text:
        lines = str(p.lead_text).split("\n")
        if p.kind == "match" or p.kind == "comprehension" or p.kind == "cloze" or \
           (p.kind == "words" and p.style == "choice"):
            out.append('<div class="passage">' +
                       "".join(f"<div>{_e(ln)}</div>" for ln in lines) +
                       "</div>")

    if p.kind == "writing" and p.style in ("sentences", "paragraph", "email"):
        ex = getattr(p, "example", None)
        # Round 26: ``Part.example`` is a plain string; the prompt/model pair
        # only exists on some pools, so guard instead of assuming the shape.
        if ex is not None and getattr(ex, "prompt", None) is not None:
            out.append(f'<div class="example">Example: <b>{_e(ex.prompt)}</b> '
                       f'&#8594; {_e(ex.model)}</div>')
    elif getattr(p, "example", None):
        out.append(f'<div class="example">{_e(p.example)}</div>')

    qno = p.qfirst
    for j, item in enumerate(p.items):
        if isinstance(item, MCQItem):
            if p.kind == "cloze":
                rows = []
                for i, o in enumerate(item.options):
                    lab = f'<span class="opt-l">{opt_labels[i]}</span>'
                    if i == 0:
                        rows.append(f'<div><span class="n">{qno}.</span> '
                                    f'{lab} {_e(o)}</div>')
                    else:
                        rows.append(f'<div>{lab} {_e(o)}</div>')
                out.append(f'<div class="opts"{eid(j)}>{"".join(rows)}</div>')
            else:
                if p.kind == "vocab" and item.stimulus:
                    # Part 1: stimulus, then the question about it.
                    head, *rest = item.stimulus
                    out.append(f'<div class="stimulus"{eid(j)}>'
                               f'<b>{_e(head)}</b>'
                               + "".join(f"<div>{_e(x)}</div>" for x in rest)
                               + "</div>")
                out.append(f'<div class="q"><span class="n">{qno}.</span> {_e(item.stem)}</div>')
                if p.kind != "match":
                    # Part 4's letters label the texts printed above, so a
                    # shuffled option list under the description would
                    # mislabel them.
                    opts = "".join(f'<div><span class="opt-l">{opt_labels[i]}</span> '
                                   f'{_e(o)}</div>' for i, o in enumerate(item.options))
                    out.append(f'<div class="opts">{opts}</div>')
        elif isinstance(item, WordItem):
            out.append(f'<div class="q"{eid(j)}>{qno}. {_e(item.clue)}</div>')
            out.append(f'<div class="pattern">{_e(item.pattern)}</div>')
        elif isinstance(item, WriteItem):
            out.append(f'<div class="q"{eid(j)}><span class="n">{qno}.</span> {_e(item.prompt)}</div>')
            if item.bullets:
                bs = "".join(f"<div>{i}. {_e(b)}</div>" for i, b in enumerate(item.bullets, 1))
                out.append(f'<div class="bullets">{bs}</div>')
            if item.word_count:
                kind_word = "email" if p.style == "email" else "letter"
                out.append(f'<div class="note">The {kind_word} should be between '
                           f'{_e(item.word_count)}.</div>')
            if p.style == "email":
                if item.recipient:
                    out.append(f'<div class="q"><b>To:</b> {_e(item.recipient)}</div>')
                if item.subject:
                    out.append(f'<div class="q"><b>Subject:</b> {_e(item.subject)}</div>')
            elif p.style == "letter" and item.salutation:
                out.append(f'<div class="q"><b>{_e(item.salutation)}</b></div>')
            if item.lines:
                rows = "".join("<tr><td></td></tr>" for _ in range(item.lines))
                out.append(f'<table class="write-lines">{rows}</table>')
            if p.style == "letter" and item.closing:
                out.append(f'<div class="q" style="margin-top:10px"><b>{_e(item.closing)}</b></div>')
                out.append('<div class="q">_____________</div>')
        qno += 1
    return "\n".join(out)


def _answer_sheet_html(paper: Paper) -> str:
    qs = []
    for p in paper.parts:
        if p.kind in ("vocab", "cloze", "comprehension", "match") or \
           (p.kind == "words" and p.style == "choice"):
            qs.extend(p.qnos())
    writing_parts = [p for p in paper.parts if p.kind == "writing"]
    if not qs and not writing_parts:
        return ""
    blocks = ['<div class="pagebr"></div>',
              '<div class="center" style="font-weight:800;font-size:15pt;margin-bottom:6px">'
              "PAPER ANSWER SHEET</div>"]
    if qs:
        blocks.append('<div class="center note" style="margin-bottom:12px">Tick ( / ) the '
                      'correct answer for each question.</div>')
        rows = ["<tr><th>Q</th><th>A</th><th>B</th><th>C</th></tr>"] + \
               [f"<tr><td>{q}</td><td></td><td></td><td></td></tr>" for q in qs]
        blocks.append(f'<table class="askey">{"".join(rows)}</table>')
    if writing_parts:
        blocks.append('<div class="center" style="font-weight:800;font-size:14pt;'
                      'margin:24px 0 4px">WRITING</div>')
        blocks.append('<div class="center note" style="margin-bottom:10px">'
                      "Write your answers in the space provided.</div>")
        for p in writing_parts:
            pq = p.qnos()
            label = f"PART {p.num}"
            if pq:
                label += f" (Q{pq[0]})" if len(pq) == 1 else f" (Q{pq[0]}\u2013{pq[-1]})"
            blocks.append(f'<div class="q-range" style="margin-top:12px"><b>{_e(label)}</b></div>')
            year = paper.year()
            n_lines = p.lines if p.lines not in (None, 0) else \
                ((16 if year >= 5 else 10)
                 if p.style in ("letter", "email", "paragraph")
                 else (9 if year >= 5 else 6))
            rows_l = "".join("<tr><td></td></tr>" for _ in range(n_lines))
            blocks.append(f'<table class="write-lines">{rows_l}</table>')
    return "\n".join(blocks)


def _answer_key_html(paper: Paper) -> str:
    out = ['<div class="pagebr"></div>'
           '<div class="center" style="font-weight:800;font-size:15pt;margin-bottom:14px">'
           "ANSWER KEY</div>"]
    for p in paper.parts:
        rows = [f'<tr><td class="part" colspan="2">PART {p.num}</td></tr>']
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
                detail = f'<span class="note"> {_e(item.model[:90])}</span>' if item.model else ""
            rows.append(f"<tr><td style='width:8%'>{qno}.</td>"
                        f"<td>{_e(ans)}{detail}</td></tr>")
            qno += 1
        out.append(f'<table class="key-table">{"".join(rows)}</table>')
    return "\n".join(out)


def _jsu_html(paper: Paper) -> str:
    """The same per-paper JSU the .docx carries, in the HTML export."""
    from . import jsu as J
    t = J.table(paper)
    L = J.labels(paper)
    lots, hots = t["lots_hots"]
    tl, th = t.get("target_lots_hots") or (0, 0)
    summary = (f"LOTS : HOTS = {lots} : {hots}"
               + (f"  ({L['target']}: {tl} : {th})" if tl and th else ""))
    mix = "   ".join(f"{k}: {v}" for k, v in t["objective_mix"].items())
    rows = ["<tr>" + "".join(f"<th>{h}</th>" for h in
                             (L["no"], L["skill"], L["focus"], L["theme"],
                              L["standard"], L["taxonomy"], L["cefr"],
                              L["marks"])) + "</tr>"]
    for r in t["rows"]:
        marks = r["marks"]
        mark = f"{marks:g}" if float(marks).is_integer() else f"{marks:.1f}"
        rows.append("<tr>" + "".join(
            f"<td>{_e(v)}</td>" for v in
            (r["qno"], r["skill"], r["focus"], r["theme"], r["standard"],
             r["taxonomy"], r["level"], mark)) + "</tr>")
    return ('<div class="pagebr"></div>'
            '<div class="center" style="font-weight:800;font-size:14pt;'
            'margin-bottom:6px">' + _e(J.title(paper)) + "</div>"
            f'<div class="center note" style="margin-bottom:12px">'
            f"{L['source']}: {_e(t['source'])}   {L['total_marks']}: "
            f"{t['total_marks']}   {L['time']}: {_e(paper.duration())}"
            "</div>"
            f'<table class="key-table jsu-table">{"".join(rows)}</table>'
            f'<div style="font-weight:700;margin-top:10px">{_e(summary)}</div>'
            f'<div>{L["objective_mix"]}: {_e(mix)}</div>'
            f'<div>{L["questions"]}: {len(t["rows"])}'
            f"   {L['total_marks']}: {t['total_marks']}</div>")


def render_html(paper: Paper, allow_fetch: bool = True,
                editable: bool = False) -> str:
    pictures = bool(paper.meta.get("pictures", True))
    frags = []
    for i, p in enumerate(paper.parts):
        if i:
            frags.append('<div class="pagebr"></div>')
        eid = f' data-eid="P{i}:I-1"' if editable else ""
        frags.append(f'<div class="partblock"{eid}>')
        frags.append(_part_html(p, pictures, allow_fetch, editable, i,
                                paper.year()))
        frags.append("</div>")
    parts = "\n".join(frags)
    body = _header(paper) + _arahan(paper) + parts
    if paper.meta.get("answer_sheet"):
        body += _answer_sheet_html(paper)
    if paper.meta.get("answer_key"):
        body += _answer_key_html(paper)
    if paper.meta.get("jsu", paper.meta.get("answer_key", True)):
        body += _jsu_html(paper)
    extra = ""
    if editable:
        banner = ('<div class="edit-banner">Edit mode — click any part or '
                  'question to change it. Click “Done Editing” when finished.</div>')
        js = ('<script>document.addEventListener("click",function(e){'
              "var el=e.target.closest('[data-eid]');if(!el)return;"
              "if(window.webkit&&window.webkit.messageHandlers&&"
              "window.webkit.messageHandlers.paperEdit)"
              "window.webkit.messageHandlers.paperEdit.postMessage("
              "el.getAttribute('data-eid'));});</script>")
        extra = banner + js
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{_page_css()}</style></head>"
            f"<body class='{'editable' if editable else ''}'>"
            f"<div class='paper'>{body}</div>{extra}</body></html>")


def mark_sheet_html(paper: Paper) -> str:
    """Standalone MARKING SHEET page."""
    from .bank import mark_sheet
    ms = mark_sheet(paper)
    css = _page_css() + """
    .ms { width: 100%; border-collapse: collapse; margin: 10px 0 18px; }
    .ms th, .ms td { border: 1px solid #000; padding: 4px 8px;
                     text-align: center; font-size: 10.5pt; }
    .ms td.l { text-align: left; }
    .ms th.part { background: #eee; font-size: 11.5pt; }
    """
    blocks = ['<div class="center"><div class="exam-title">'
              "MARKING SHEET</div>"
              f'<div class="exam-subj">{_e(paper.meta.get("school", ""))}'
              f'&nbsp;&nbsp;·&nbsp;&nbsp;Teacher: {_e(paper.meta.get("teacher", ""))}'
              "</div></div>",
              '<div class="exam-dur">Student: &nbsp;'
              '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
              '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Class: &nbsp;'
              '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</div>']
    for part in ms["parts"]:
        rows = [f'<tr><th class="part" colspan="3">'
                f"PART {part['part']} &nbsp;[{part['marks']} marks]</th></tr>",
                "<tr><th style='width:8%'>No.</th><th>Brief</th>"
                "<th style='width:14%'>Marks</th></tr>"]
        for it in part["items"]:
            rows.append(f"<tr><td>{it['q']}</td><td class='l'>{_e(it['text'])}"
                        "</td><td></td></tr>")
        rows.append(f"<tr><td><b>Section</b></td><td></td><td>"
                    f"<b>{part['marks']}</b></td></tr>")
        blocks.append(f'<table class="ms">{"".join(rows)}</table>')
    blocks.append(f'<table class="ms"><tr><th>TOTAL</th>'
                  f'<th style="text-align:left">{ms["total"]}</th>'
                  f'<th></th></tr></table>')
    blocks.append(f'<div style="font-weight:800;margin-top:14px">'
                  f"Total overall: ______ / {ms['total']}</div>")
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{css}</style></head><body>"
            f"<div class='paper'>{''.join(blocks)}</div></body></html>")