"""Serverless + local API endpoint for SJKC Exam Paper Generator (UPSA / UASA).

Compatible with:
1. Vercel Python Serverless Runtime (`handler(BaseHTTPRequestHandler)`)
2. Local unified server (`server.py` calling `handle_exam_request(payload)`)
"""

from __future__ import annotations

import base64
import copy
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from exam_gen import bank, data as D, docx as X, dskp, jsu, render_html


def handle_exam_request(payload: dict) -> dict:
    """Generate an exam paper + HTML preview + JSU + QC + DOCX buffers."""
    os.environ.setdefault("EXAM_GEN_OFFLINE", "1")

    year = int(payload.get("year") or 3)
    if year not in (1, 2, 3, 4, 5, 6):
        year = 3
    exam_type = str(payload.get("exam_type") or "upsa").lower()
    if exam_type not in ("upsa", "uasa"):
        exam_type = "upsa"
    difficulty = str(payload.get("difficulty") or "medium").lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    seed = int(payload.get("seed") or 1)
    week = int(payload.get("week") or 0)
    theme = str(payload.get("theme") or "").strip()
    if week > 0 and not theme:
        theme = bank.theme_for_week(year, week)

    school = str(payload.get("school") or "SJK(C) PIN MIN, BIDOR").strip()
    teacher = str(payload.get("teacher") or "").strip()
    session = str(payload.get("session") or "2027").strip()
    pictures = bool(payload.get("pictures", True))
    answer_sheet = bool(payload.get("answer_sheet", True))
    answer_key = bool(payload.get("answer_key", True))
    include_jsu = bool(payload.get("jsu", True))
    include_marksheet = bool(payload.get("marksheet", True))
    want_docx = bool(payload.get("want_docx", True))
    ab_set = bool(payload.get("ab_set", False))

    conf = dict(D.DEFAULT_CONFIG)
    conf.update({
        "year": year,
        "exam_type": exam_type,
        "difficulty": difficulty,
        "seed": seed,
        "week": week,
        "theme": theme,
        "school": school,
        "teacher": teacher,
        "session": session,
        "pictures": pictures,
        "answer_sheet": answer_sheet,
        "answer_key": answer_key,
        "jsu": include_jsu,
    })

    paper = bank.generate_clean(conf, [])
    compliance = bank.paper_compliance(paper)
    jsu_table = jsu.table(paper)
    dskp_cov = dskp.coverage_report(paper)
    ms_data = bank.mark_sheet(paper)

    # Render separate views for the interactive web tabs
    pupil_paper = copy.copy(paper)
    pupil_paper.meta = dict(paper.meta, answer_key=False, jsu=False, answer_sheet=False)
    paper_html = render_html.render_html(pupil_paper, allow_fetch=False)

    sheet_only_html = render_html._answer_sheet_html(paper)
    key_only_html = render_html._answer_key_html(paper)
    jsu_only_html = render_html._jsu_html(paper)
    marksheet_html = render_html.mark_sheet_html(paper)

    qc_obj = getattr(paper, "_qc", None)
    qc_summary = {
        "score": getattr(qc_obj, "score", 10),
        "hard": getattr(qc_obj, "hard", 0),
        "soft": getattr(qc_obj, "soft", 0),
        "ok": bool(compliance.get("ok", True)),
        "dskp": bool(compliance.get("dskp", True)),
        "cefr": bool(compliance.get("cefr", True)),
        "marks": compliance.get("marks", 50),
        "questions": compliance.get("questions", paper.max_qno()),
        "theme": paper.meta.get("theme") or theme or "Auto",
        "duration": paper.duration(),
    }

    result = {
        "ok": True,
        "meta": {
            "year": year,
            "exam_type": exam_type.upper(),
            "difficulty": difficulty,
            "seed": seed,
            "week": week,
            "theme": qc_summary["theme"],
            "session": session,
            "school": school,
            "teacher": teacher,
            "duration": paper.duration(),
            "themes_for_year": list(D.RPT_THEMES.get(year, ())),
        },
        "qc": qc_summary,
        "dskp_coverage": dskp_cov,
        "jsu": jsu_table,
        "marksheet": ms_data,
        "html": {
            "paper": paper_html,
            "answer_sheet": sheet_only_html,
            "answer_key": key_only_html,
            "jsu": jsu_only_html,
            "marksheet": marksheet_html,
        },
        "docx": {},
    }

    if want_docx:
        # Pupil paper + answer sheet
        p_doc = copy.copy(paper)
        p_doc.meta = dict(paper.meta, answer_key=False, jsu=False, answer_sheet=answer_sheet)
        result["docx"]["paper_b64"] = base64.b64encode(
            X.render_doc(p_doc, allow_fetch=False)
        ).decode("ascii")

        # Teacher copy (with Answer Key + JSU)
        t_doc = copy.copy(paper)
        t_doc.meta = dict(paper.meta, answer_key=True, jsu=True, answer_sheet=answer_sheet)
        result["docx"]["teacher_b64"] = base64.b64encode(
            X.render_doc(t_doc, allow_fetch=False)
        ).decode("ascii")

        if include_marksheet:
            result["docx"]["marksheet_b64"] = base64.b64encode(
                X.mark_sheet_doc(paper)
            ).decode("ascii")
            result["docx"]["mark_scheme_b64"] = base64.b64encode(
                X.mark_scheme_doc(paper, conf=conf)
            ).decode("ascii")

        if ab_set:
            conf_b = dict(conf, seed=bank.next_seed(seed))
            paper_b = bank.generate_clean(conf_b, [])
            p_doc_b = copy.copy(paper_b)
            p_doc_b.meta = dict(paper_b.meta, answer_key=False, jsu=False, answer_sheet=answer_sheet)
            result["docx"]["paper_b_b64"] = base64.b64encode(
                X.render_doc(p_doc_b, allow_fetch=False)
            ).decode("ascii")

    return result


class handler(BaseHTTPRequestHandler):
    """Vercel Python Serverless Function entrypoint."""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            res = handle_exam_request({"year": 3, "exam_type": "upsa", "seed": 1, "want_docx": False})
            body = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            err = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(err)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw or "{}")
            res = handle_exam_request(payload)
            body = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            err = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(err)
