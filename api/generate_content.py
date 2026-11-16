"""Serverless + local endpoint for KSSR AI RPH Content Generator.

Uses OpenRouter (`OPENROUTER_API_KEY`) when configured, and falls back to a
deterministic DSKP + RPT + KSSR 5-phase pedagogical generator when offline or
when no API key is set.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request


def _offline_generate(req: dict) -> dict:
    subj = str(req.get("subject") or "BI").upper()
    year = int(req.get("year") or 3)
    lang = str(req.get("language") or ("bm" if subj in ("BM", "PK", "PI") else "en" if subj == "BI" else "zh")).lower()
    theme = str(req.get("theme") or "Topic").strip()
    unit = str(req.get("unit") or "Unit").strip()
    sk_list = [str(x).strip() for x in (req.get("sk") or []) if str(x).strip()]
    sp_list = [str(x).strip() for x in (req.get("sp") or []) if str(x).strip()]
    sp_core = sp_list[0] if sp_list else f"{unit} ({theme})"

    if lang == "en":
        objectives = [
            f"🎯 By the end of the lesson, pupils will be able to understand and apply key vocabulary from '{unit}' ({theme}).",
            f"✅ Pupils will be able to demonstrate mastery of {sp_core} through guided pair and group tasks.",
            f"✅ At least 80% of Year {year} pupils can complete the formative assessment accurately.",
        ]
        criteria = [
            f"✅ I can identify and use at least 4 target words from '{unit}'.",
            f"✅ I can answer comprehension and oral prompts related to {theme}.",
            "✅ I can complete the post-lesson worksheet and explain my answer to a partner.",
        ]
        activities = {
            "setInduction": f"🎯 Visual Hook ({theme}): Teacher displays stimulus cards for '{unit}'. Pupils brainstorm prior knowledge and predict today's focus. [Dif: A - Justify predictions in full sentences, B - Name key items, C - Point and match]",
            "preLesson": f"📚 Vocabulary & Modeling: Teacher introduces target structures aligned to {sp_core}. Pupils practise pronunciation and sentence frames on mini whiteboards.",
            "development": f"📖 Guided & Cooperative Practice: Pupils work in differentiated stations on '{unit}' tasks (reading stimulus, matching, and guided sentence building) while teacher facilitates.",
            "postLesson": f"💡 Formative Check (Mini-UPSA): Pupils complete a 5-item quick check on '{unit}' and conduct peer checking with the answer key.",
            "closure": "🎯 3-2-1 Reflection: Pupils share 3 new words learned, 2 sentence examples, and rate their confidence (1–3 stars).",
        }
        remedial = [
            f"🧑‍🏫 Guided Phonics & Word Bank: One-to-one syllable/word blending for '{unit}' using picture flashcards.",
            f"📝 Scaffolded Sentence Frames: Fill-in-the-blank prompts with word boxes for TP 1–2 pupils.",
            "🤝 Peer Buddy Reading: Pair TP 1–2 pupils with TP 5–6 buddies to read and match 5 core words.",
        ]
        tp_interventions = {
            "low": "Bimbingan berfokus menggunakan kad imbasan bergambar dan latihan klos berpandu (TP 1–2).",
            "medium": "Latihan pengukuhan kemahiran mendengar, bertutur, membaca dan menulis secara berpasangan (TP 3–4).",
            "high": "Aktiviti pengayaan KBAT dan pembinaan ayat/perenggan lanjutan secara kendiri (TP 5–6).",
        }
        reflection = (
            f"Lesson on '{unit}' ({theme}) for Year {year} went smoothly. "
            f"Pupils actively engaged in the 5-phase KSSR activities aligned with {sp_core}. "
            "Remedial pupils received scaffolded word-bank support while high achievers completed enrichment extension prompts."
        )
    elif lang == "zh":
        objectives = [
            f"🎯 在课堂结束时，{year}年级学生能够理解并运用“{unit}”（{theme}）的核心概念与词汇。",
            f"✅ 学生能够在引导下完成与 {sp_core} 相关的听说读写/探究活动。",
            "✅ 至少80%的学生能够独立完成课后巩固练习。",
        ]
        criteria = [
            f"✅ 我能说出并正确使用“{unit}”中的关键内容。",
            f"✅ 我能与组员合作完成“{theme}”课堂任务。",
            "✅ 我能正确完成评估练习并与同学核对答案。",
        ]
        activities = {
            "setInduction": f"🎯 导入（{theme}）：教师展示与“{unit}”相关的图片或实物，引导学生观察并猜出今日课题。[分层：A组完整叙述，B组说出关键词，C组指认图片]",
            "preLesson": f"📚 课前活动：教师讲解 {sp_core} 的重点概念，学生通过字卡与思维图进行热身练习。",
            "development": f"📖 主要教学：学生分组进行“{unit}”分层学习站活动，结合具体实例与互动任务深化理解，教师巡视指导。",
            "postLesson": f"💡 课后巩固：学生完成针对“{unit}”的分级练习题，并进行同伴互评与订正。",
            "closure": "🎯 总结反思：师生共同完成概念总结图，学生说出今日所学重点并自评掌握程度。",
        }
        remedial = [
            f"🧑‍🏫 一对一结构化辅导：针对“{unit}”基础概念，使用图卡与分步示范引导 TP 1–2 学生。",
            "📝 分步填空工作纸：提供附示例与提示词的简化练习，逐步建立信心。",
            "🤝 同伴互助：安排优秀生（TP 5–6）与辅导生结对完成基础配对练习。",
        ]
        tp_interventions = {
            "low": "Bimbingan berperingkat menggunakan kad visual dan lembaran kerja asas (TP 1–2).",
            "medium": "Latihan pengukuhan berstruktur untuk memantapkan penguasaan konsep (TP 3–4).",
            "high": "Aktiviti pengayaan aras tinggi (KBAT) dan bimbingan rakan sebaya (TP 5–6).",
        }
        reflection = (
            f"今日{year}年级“{unit}”（{theme}）教学顺利进行。大部分学生积极参与活动并达成 {sp_core} 学习目标；"
            "尚需辅导的学生已通过图卡与分步练习获得个别指导。"
        )
    else:
        objectives = [
            f"🎯 Pada akhir PdP, murid Tahun {year} dapat memahami dan mengaplikasikan konsep '{unit}' ({theme}).",
            f"✅ Murid dapat menguasai kemahiran berdasarkan {sp_core} melalui aktiviti berkumpulan dan berpasangan.",
            "✅ Sekurang-kurangnya 80% murid dapat melengkapkan latihan formatif dengan tepat.",
        ]
        criteria = [
            f"✅ Saya boleh menyatakan dan menggunakan isi penting dalam '{unit}'.",
            f"✅ Saya boleh menjawab soalan pemahaman dan latihan berkaitan {theme}.",
            "✅ Saya boleh menerangkan semula perkara yang dipelajari kepada rakan.",
        ]
        activities = {
            "setInduction": f"🎯 Set Induksi ({theme}): Guru menayangkan rangsangan visual berkaitan '{unit}'. Murid bersoal jawab dan mengaitkan dengan pengalaman sedia ada. [Dif: A - Huraian ayat lengkap, B - Sebut kata kunci, C - Padanan gambar]",
            "preLesson": f"📚 Pra-PdP: Guru menerangkan fokus pembelajaran ({sp_core}) menggunakan peta minda dan kad imbasan.",
            "development": f"📖 Perkembangan PdP: Murid menjalankan aktiviti stesen pembelajaran bertema '{unit}' secara kolaboratif mengikut aras keupayaan.",
            "postLesson": f"💡 Pasca-PdP: Murid menjawab kuiz pantas / lembaran kerja bergradien dan membuat semakan bersama guru.",
            "closure": "🎯 Penutup: Murid membuat rumusan 3-2-1 tentang perkara yang dipelajari pada hari ini.",
        }
        remedial = [
            f"🧑‍🏫 Bimbingan Individu: Bimbingan langkah demi langkah bagi topik '{unit}' menggunakan bahan maujud dan kad bergambar.",
            "📝 Lembaran Kerja Berpandu: Latihan klos dan padanan mudah untuk murid TP 1–2.",
            "🤝 Rakan Pembimbing: Murid TP 5–6 membantu rakan TP 1–2 membaca dan menyiapkan tugasan asas.",
        ]
        tp_interventions = {
            "low": "Bimbingan rapi secara individu dan latihan asas berpandukan gambar (TP 1–2).",
            "medium": "Latihan pengukuhan kemahiran mendengar, bertutur, membaca dan menulis (TP 3–4).",
            "high": "Aktiviti pengayaan KBAT dan cabaran penulisan lanjutan (TP 5–6).",
        }
        reflection = (
            f"PdP bagi tajuk '{unit}' ({theme}) Tahun {year} berjalan lancar. "
            f"Majoriti murid mencapai objektif {sp_core} melalui aktiviti berpusatkan murid, manakala murid TP 1–2 diberikan bimbingan pemulihan berfokus."
        )

    return {
        "ok": True,
        "source": "offline-kssr-engine",
        "objectives": objectives,
        "successCriteria": criteria,
        "activities": activities,
        "remedial": remedial,
        "reflection": reflection,
        "tpInterventions": tp_interventions,
        "creditsUsed": 0,
    }


def handle_ai_content(req: dict) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return _offline_generate(req)
    try:
        subj = str(req.get("subject") or "BI").upper()
        year = int(req.get("year") or 3)
        lang = str(req.get("language") or "bm").lower()
        theme = str(req.get("theme") or "").strip()
        unit = str(req.get("unit") or "").strip()
        sk = req.get("sk") or []
        sp = req.get("sp") or []
        prompt_sys = (
            "You are an expert Malaysian KSSR primary school teacher at SJKC Pin Min, Bidor. "
            "Respond with strict JSON only containing keys: objectives (array of 3 strings), "
            "successCriteria (array of 3 strings), activities ({setInduction, preLesson, development, postLesson, closure}), "
            "remedial (array of 3 strings), reflection (string), tpInterventions ({low, medium, high})."
        )
        prompt_user = (
            f"Subject: {subj}, Year: {year}, Language: {lang}, Theme: {theme}, Unit: {unit}, "
            f"SK: {', '.join(sk)}, SP: {', '.join(sp)}"
        )
        body = json.dumps({
            "model": req.get("model") or "inclusionai/ling-3.0-flash-sante:free",
            "messages": [
                {"role": "system", "content": prompt_sys},
                {"role": "user", "content": prompt_user},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        http_req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://erph-pm.vercel.app",
                "X-Title": "SJKC-Hub-2027",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"].strip()
        content = content.removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(content)
        parsed["ok"] = True
        parsed["source"] = "openrouter"
        parsed["creditsUsed"] = 1
        return parsed
    except Exception:
        return _offline_generate(req)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            payload = {}
        res = handle_ai_content(payload)
        body = json.dumps(res).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
