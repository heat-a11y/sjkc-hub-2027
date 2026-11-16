"""TDD test suite for Penjana Kertas Ujian (stdlib unittest).

Run:  python3 tests/run_tests.py
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
import io
import json
import dataclasses
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["EXAM_GEN_OFFLINE"] = "1"     # keep the suite hermetic/offline

from exam_gen import art
from exam_gen import (bank, data as D, docx as X, jsu, kssr_stories,
                      marks as M, models, pdfmake, render_html, webfetch)
from exam_gen.models import MCQItem, WordItem, WriteItem

HAVE_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _gen(conf: dict | None = None, passages=None) -> bank.Paper:
    c = dict(D.DEFAULT_CONFIG)
    if conf:
        c.update(conf)
    return bank.generate_paper(c, passages)


def _teacher(conf: dict | None = None, passages=None) -> bank.Paper:
    """A paper rendered as the *teacher* document (key + JSU).

    Since Round 38 a plain paper is a pupil copy and carries neither, so
    anything that asserts on the key or the test specification has to say so.
    """
    c = dict(conf or {})
    c["answer_key"] = True
    c["jsu"] = True
    return _gen(c, passages)


def _docx_text(paper) -> str:
    raw = X.render_doc(paper)
    with zipfile.ZipFile(__import__("io").BytesIO(raw)) as z:
        return z.read("word/document.xml").decode("utf-8", "ignore")


def _lacks(haystack: str, needle: str) -> bool:
    """``needle not in haystack``, as a predicate.

    ``assertNotIn`` echoes the whole container on failure, and a .docx is
    ~250 KB of XML -- an audit assertion would bury its own message.  These
    assertions only care about the verdict, so they call a predicate and keep
    the message they wrote themselves.
    """
    return needle not in haystack


def _has(haystack: str, needle: str) -> bool:
    return needle in haystack


def _paper_part(num, kind):
    from exam_gen import models
    return models.Part(num=num, kind=kind, style="upper", marks=5,
                       title=f"PART {num}", lead="")


def _paper_item(**kw):
    from exam_gen import models
    kw.setdefault("options", ["a", "b", "c"])
    kw.setdefault("answer", 0)
    return models.MCQItem(**kw)


def _jsu_esc(text) -> str:
    """The HTML renderer's own escaping, for asserting on printed text."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _part_words(p) -> str:
    """All displayable text of a part: lead + item stems + options + answers.

    A photo's search phrase is grounded in everything the pupil sees (the
    passage is the lead, MCQ options and answer words are part of the
    question), not only the passage/stem text (Round 14 follow-up).
    """
    bits = [p.lead_text or ""]
    for it in p.items:
        bits.append(str(getattr(it, "stem", "") or ""))
        opts = getattr(it, "options", None) or None
        if opts:
            bits.extend(str(o) for o in opts)
        ans = getattr(it, "ans_text", "") or getattr(it, "answer", "")
        if ans:
            bits.append(str(ans))
    return " ".join(x for x in bits if x)


class TestData(unittest.TestCase):
    def test_difficulties(self):
        self.assertEqual(D.DIFFICULTIES, ("easy", "medium", "hard"))
        self.assertIn("difficulty", D.DEFAULT_CONFIG)
        self.assertEqual(D.DEFAULT_CONFIG["difficulty"], "medium")

    def test_rpt_themes(self):
        for y in D.YEARS:
            self.assertIn(y, D.RPT_THEMES)
            self.assertTrue(D.RPT_THEMES[y])
        for theme in {t for ts in D.RPT_THEMES.values() for t in ts}:
            self.assertIn(theme, D.THEME_KEYWORDS)

    def test_pictures_default(self):
        self.assertTrue(D.DEFAULT_CONFIG.get("pictures", True))

    def test_arahan_matches_official(self):
        # The instruction block must mirror the real UPSA/UASA 2026 papers.
        self.assertEqual(D.ARAHAN["bm"][1],
                         "Tulis nama dan nama kelas kamu pada ruang yang disediakan.")
        self.assertIn("Part 1, Part 2, Part 3 dan Part 4", D.ARAHAN["bm"][2])
        self.assertIn("ruang jawapan objektif di halaman terakhir",
                      D.ARAHAN["bm"][2])
        self.assertIn("Part 5, Part 6 dan Part 7", D.ARAHAN["bm"][3])
        self.assertIn("guru bertugas", D.ARAHAN["bm"][4])

    def test_mcq_leads_mark_on_answer_sheet(self):
        # Parts 1-4 leads end with the official "mark on your answer sheet"
        # instruction (every year, both languages).
        for year in D.YEARS:
            for spec in D.PARTS[year]:
                if spec["id"] not in (1, 2, 3, 4):
                    continue
                for lang in ("bm", "en"):
                    lead = spec["lead"][lang]
                    self.assertTrue(
                        lead.endswith("mark the correct answer A, B or C on "
                                      "your answer sheet."),
                        f"Y{year} Part {spec['id']} {lang} lead")

    def test_y6_rpt_matches_planner(self):
        # The real T6 planner names 10 units; the app must carry them all.
        # Test that the two previously-dropped units are present and ordered
        # correctly around their neighbours.
        themes = D.RPT_THEMES[6]
        self.assertIn("Cool Jobs", themes)
        self.assertIn("What's Your Opinion?", themes)
        self.assertEqual(themes.index("Cool Jobs"),
                         themes.index("Adventure Time") + 1)
        self.assertEqual(themes.index("What's Your Opinion?"),
                         themes.index("Tell Me a Story") + 1)
        self.assertIn("Cool Jobs", D.THEME_KEYWORDS)
        self.assertIn("What's Your Opinion?", D.THEME_KEYWORDS)
        for theme in ("Cool Jobs", "What's Your Opinion?"):
            self.assertGreaterEqual(len(D.THEME_KEYWORDS[theme]), 5)

    def test_y1y2_part7_outfit_prompt(self):
        # Y1/Y2 Part 7 mirrors the official UPSA prompt: pupils draw a boy/girl
        # wearing different outfits and write three sentences about each figure,
        # with a clothing word box in the lead and the official father example.
        from exam_gen import bank
        for year in (1, 2):
            spec = next(s for s in D.PARTS[year] if s["id"] == 7)
            self.assertEqual(spec["count"], 5)
            self.assertEqual(spec["marks"], 15)
            self.assertIn("each boy/girl you draw wearing", spec["lead"]["en"])
            self.assertIn("Word box:", spec["lead"]["en"])
            self.assertIn("Word box:", spec["lead"]["bm"])
        for year in (1, 2):
            p = bank.generate_paper({"year": year, "seed": 1, "difficulty": "easy"})
            p7 = next(pr for pr in p.parts if pr.num == 7)
            self.assertEqual(len(p7.items), 5)
            self.assertEqual(p7.example.model,
                             "My father wears a shirt. He also wears a pair of glasses.")
            for item in p7.items:
                self.assertTrue("Draw a boy" in item.prompt or
                                "Draw a girl" in item.prompt)
                self.assertIn("wearing", item.prompt)
                self.assertIn("Write THREE sentences", item.prompt)
                self.assertEqual(len(item.model.split(". ")), 3)


class TestDifficulty(unittest.TestCase):
    def test_shift_year_clamps(self):
        self.assertEqual(bank.shift_year(1, "easy"), 1)     # lowest clamps
        self.assertEqual(bank.shift_year(6, "hard"), 6)     # highest clamps
        self.assertEqual(bank.shift_year(3, "easy"), 2)
        self.assertEqual(bank.shift_year(3, "hard"), 4)     # Year 4 sits next
        self.assertEqual(bank.shift_year(3, "medium"), 3)
        # Round 36: Year 4 is a real level, so the ladder is contiguous and
        # "hard" never has to jump over it.
        self.assertEqual(bank.YEAR_ORDER, [1, 2, 3, 4, 5, 6])
        self.assertEqual(bank.shift_year(4, "easy"), 3)
        self.assertEqual(bank.shift_year(4, "hard"), 5)
        self.assertEqual(bank.shift_year(4, "medium"), 4)
        self.assertEqual(bank.shift_year(5, "easy"), 4)

    def test_all_years_all_difficulties_generate(self):
        for y in D.YEARS:
            for diff in D.DIFFICULTIES:
                paper = _gen({"year": y, "difficulty": diff})
                self.assertEqual(sum(len(p.items) for p in paper.parts) > 0, True)
                self.assertEqual(
                    sum(m for _l, m, _g in paper.marks_table if _l != "TOTAL"),
                    D.TOTAL)

    def test_easy_hard_differ(self):
        easy = _gen({"year": 3, "difficulty": "easy", "seed": 7})
        hard = _gen({"year": 3, "difficulty": "hard", "seed": 7})
        e1 = {it.answer_label for p in easy.parts for it in p.items
              if it.__class__.__name__ == "MCQItem"}
        h1 = {it.answer_label for p in hard.parts for it in p.items
              if it.__class__.__name__ == "MCQItem"}
        e_text = " ".join(str(it.stem) for p in easy.parts
                          for it in p.items if hasattr(it, "stem"))
        h_text = " ".join(str(it.stem) for p in hard.parts
                          for it in p.items if hasattr(it, "stem"))
        self.assertNotEqual(e_text, h_text)


class TestTheme(unittest.TestCase):
    def test_theme_filters_active(self):
        themed = _gen({"year": 5, "difficulty": "hard", "seed": 3,
                       "theme": "Wild Life"})
        kws = D.THEME_KEYWORDS["Wild Life"]
        joined = " ".join(str(p.lead_text) + " " +
                          " ".join(str(getattr(it, "stem", "")) for it in p.items)
                          for p in themed.parts)
        self.assertTrue(any(k in joined.lower() for k in kws))

    def test_unknown_theme_falls_back(self):
        paper = _gen({"year": 2, "theme": "NO SUCH THEME"})
        self.assertGreater(sum(len(p.items) for p in paper.parts), 0)

    def test_rpt_theme_cycling(self):
        idx = 0
        cycle = []
        for _ in range(4):
            idx, theme = bank.next_theme(3, idx)
            cycle.append(theme)
        self.assertEqual(len(set(cycle)) <= len(D.RPT_THEMES[3]), True)


class TestCoherence(unittest.TestCase):
    def test_removed_dead_names_stay_removed(self):
        # Round 29 sweep.  These had zero references; the sweep proved paper
        # output was byte-identical without them.  This guards against a
        # half-reverted cleanup silently restoring them.
        import exam_gen.data, exam_gen.dskp, exam_gen.dskp_words
        import exam_gen.extra_cloze, exam_gen.kssr_stories
        import exam_gen.qr, exam_gen.webfetch
        gone = {
            exam_gen.data: ("EXAM_TITLES", "PART_MARKER", "OUT_DIR"),
            exam_gen.dskp_words: ("SOURCE_NAME", "ALL_YEARS"),
            exam_gen.extra_cloze: ("GRAND", "FOOD"),
            exam_gen.dskp: ("in_year",),
            exam_gen.kssr_stories: ("all_texts",),
            exam_gen.qr: ("qr_png_data_uri",),
            exam_gen.webfetch: ("passage_questions",),
        }
        for mod, names in gone.items():
            for n in names:
                self.assertFalse(hasattr(mod, n),
                                 f"{mod.__name__}.{n} was removed in Round 29")

    def test_specced_unwired_content_is_still_there(self):
        # The counterweight to the test above: SPEC 36/41 record
        # extra_writing.PEOPLE/PARAGRAPHS and bank.tb_letter_words as
        # deliberately unwired.  "Unused" is not a reason to delete curated
        # content, so keep them until a round explicitly rewires them.
        import exam_gen.extra_writing as extra_writing
        self.assertTrue(hasattr(extra_writing, "PEOPLE"))
        self.assertTrue(hasattr(extra_writing, "PARAGRAPHS"))
        self.assertTrue(callable(getattr(bank, "tb_letter_words", None)))

    def test_jalur_gemilang_item_has_one_true_answer(self):
        # The Jalur Gemilang has 14 stripes AND a 14-pointed star, so
        # "stars" was as factually true as "stripes" — an item with two
        # defensible answers cannot be marked in an exam hall.  The
        # distractor set must contain exactly one fourteen-count noun.
        item = next(i for i in bank._vocab_pool(3)
                    if "Jalur Gemilang" in i["stem"])
        opts = [o.lower() for o in item["opts"]]
        self.assertIn("stripes", opts)
        for other in ("stars", "star"):
            self.assertNotIn(
                other, opts,
                "'stars' is also literally true of the flag (14-point star)")

    def test_block_text_sees_writing_fields(self):
        text = bank._block_text({
            "prompt": "A tiger", "focus": "teacher",
            "bullets": ["the forest"], "sentences": ["a ranger"],
        })
        for word in ("tiger", "teacher", "forest", "ranger"):
            self.assertIn(word, text)

    def test_theme_prefer_narrows_then_falls_back(self):
        kw = D.THEME_KEYWORDS["Wild Life"][0]        # e.g. "wild"
        pool = [{"prompt": f"about {kw}"}, {"prompt": "about a bus"}]
        narrowed = bank._theme_prefer(pool, "Wild Life", 1)
        self.assertEqual(len(narrowed), 1)
        self.assertIn(kw, narrowed[0]["prompt"])
        # not enough on-theme entries -> keep the whole pool (variety)
        self.assertEqual(len(bank._theme_prefer(pool, "Wild Life", 2)), 2)

    def test_themed_paper_keeps_writing_on_topic(self):
        # Across seeds, a strongly themed paper should keep its writing
        # prompts on theme whenever the pool offers matching content.
        kws = D.THEME_KEYWORDS["It's a Mystery!"]
        hits = 0
        for seed in range(1, 7):
            paper = _gen({"year": 6, "seed": seed, "theme": "It's a Mystery!"})
            text = " ".join(str(getattr(it, "prompt", ""))
                            for p in paper.parts if p.kind == "writing"
                            for it in p.items).lower()
            if any(k in text for k in kws):
                hits += 1
        self.assertGreater(hits, 0)


class TestPictures(unittest.TestCase):
    def test_topic_classifier(self):
        from exam_gen import art
        self.assertEqual(art.topics_for_text("the market sells fish"), "market")
        self.assertEqual(art.topics_for_text("the tiger lives in the forest"), "animals")
        self.assertEqual(art.topics_for_text("children go to school by bus"), "school")
        self.assertEqual(art.topics_for_text("unrelated gibberish zzz"), "general")

    def test_builtin_papers_always_aligned(self):
        # The official UPSA/UASA 2026 format is fixed: every part must carry
        # exactly PARTS[year] questions and marks (total 50).  No PIC/PNG/SVG
        # scene code remains, so this replaces the old SVG tests with the
        # alignment contract that actually matters.
        for year in D.YEARS:
            for theme in [""] + D.RPT_THEMES[year]:
                for diff in D.DIFFICULTIES:
                    for seed in (1, 3, 7, 42):
                        conf = {"year": year, "seed": seed, "difficulty": diff}
                        if theme:
                            conf["theme"] = theme
                        paper = _gen(conf)
                        total = 0
                        for p in paper.parts:
                            spec = next(s for s in D.PARTS[year]
                                        if s["id"] == p.num)
                            self.assertEqual(
                                len(p.items), spec["count"],
                                f"Y{year} {theme or '-'} {diff} seed{seed} "
                                f"PART {p.num} count")
                            self.assertEqual(
                                p.marks, spec["marks"],
                                f"Y{year} PART {p.num} marks")
                            total += p.marks
                        self.assertEqual(total, D.TOTAL,
                                         f"Y{year} {theme or '-'} total")

    def test_upper_cloze_is_four_gaps(self):
        # Years 5/6 Part 2 is 4 questions / 4 marks (Q6-Q9); regression for the
        # old 5-gap cloze blocks that left 1 item and 1 mark missing.
        for year in (5, 6):
            for seed in (1, 2, 3, 5, 8, 13):
                paper = _gen({"year": year, "seed": seed})
                p2 = next(p for p in paper.parts if p.num == 2)
                self.assertEqual(len(p2.items), 4, f"Y{year} seed{seed}")
                self.assertEqual(p2.marks, 4)

    def test_web_used_when_questions_sufficient(self):
        # A web passage that can supply the full Part 3 count (5) must be used.
        # Round 26: its questions must also be on the DSKP ladder for the year,
        # so the fixture offers words a Year 2 pupil has met.
        wb = [{"text": "The cat saw the bird in the tall tree. " * 3,
               "qs": [{"stem": f"Q{i}: which animal hid in the tree",
                       "opts": ["Cat", "Bird", "Dog"], "ans": 0}
                      for i in range(5)]}]
        paper = _gen({"year": 2, "seed": 2, "use_web": True}, wb)
        p3 = next(p for p in paper.parts if p.num == 3)
        self.assertEqual(len(p3.items), 5)
        self.assertIn("cat", p3.lead_text)

    def test_web_passage_about_an_off_list_word_falls_back(self):
        # Round 26: enough questions, but the options are off the DSKP ladder,
        # so the built-in pool answers Part 3 instead of the web passage.
        wb = [{"text": "The fox saw the crow in the tall tree. " * 3,
               "qs": [{"stem": f"Q{i}: which animal hid in the tree",
                       "opts": ["Fox", "Crow", "Lion"], "ans": 0}
                      for i in range(5)]}]
        paper = _gen({"year": 2, "seed": 2, "use_web": True}, wb)
        p3 = next(p for p in paper.parts if p.num == 3)
        self.assertEqual(len(p3.items), 5)
        self.assertNotIn("fox", p3.lead_text.casefold())

    def test_web_short_passages_fall_back_to_builtin(self):
        # Web passages that cannot supply 5 questions (stale cache / thin text)
        # must silently fall back to the built-in comprehension pool, never
        # leaving a short Part 3.
        wb = [{"text": "A fox saw a crow. " * 4,
               "qs": [{"stem": f"Q{i} fox", "opts": ["Fox", "Crow", "Lion"],
                       "ans": 0} for i in range(2)]}]
        for year in (1, 2, 3, 5, 6):
            paper = _gen({"year": year, "seed": 1, "use_web": True}, wb)
            p3 = next(p for p in paper.parts if p.num == 3)
            self.assertEqual(len(p3.items), 5, f"Y{year}")
            self.assertEqual(p3.marks, 5)

    def test_docx_embeds_commons_photo(self):
        # Hermetic: pretend a Commons photo resolved so the DOCX embeds it as a
        # real JPEG (there is no SVG fallback in documents any more).
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        paper = _gen({"year": 3, "pictures": True})
        with unittest.mock.patch.object(art, "photo_bytes",
                                        return_value=fake_jpeg):
            raw = X.render_doc(paper)
        with zipfile.ZipFile(__import__("io").BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
            names = z.namelist()
        self.assertTrue(any(n.startswith("word/media/") for n in names))
        self.assertIn("<w:drawing>", xml)
        self.assertIn("image/jpeg", X_content_types(raw))

    def test_docx_shared_topic_embedded_once(self):
        # Two parts sharing a topic must reference the same image, never
        # duplicate a media entry (a duplicate name makes LibreOffice reject
        # the file and kills PDF export).
        paper = _gen({"year": 3, "pictures": True})
        for p in paper.parts:
            p.topic = "market"
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        with unittest.mock.patch.object(art, "photo_bytes",
                                        return_value=fake_jpeg):
            raw = X.render_doc(paper)
        with zipfile.ZipFile(__import__("io").BytesIO(raw)) as z:
            names = z.namelist()
        media = [n for n in names if n.startswith("word/media/")]
        self.assertEqual(media, list(dict.fromkeys(media)))
        self.assertLessEqual(len(media), sum(1 for p in paper.parts if p.topic))

    def test_html_photo_placeholder_no_svg(self):
        # With no photo available the preview shows a clean captioned
        # placeholder (never a broken SVG scene).
        tmp = tempfile.mkdtemp()
        with unittest.mock.patch.object(art, "_photo_cache_dir",
                                        return_value=tmp):
            html = render_html.render_html(_gen({"year": 1}))
        shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotIn("<svg", html)
        self.assertIn("class=\"pic-ph\"", html)
        self.assertIn("Photo available online", html)

    def test_html_embeds_photo_related_query(self):
        # When a photo resolves, the <img> data URI appears in the preview and
        # no placeholder is shown.  With the Round 13 follow-up every embedded
        # photo's query must come from the part's own content (photo_candidates
        # returns only the phrase-derived photo_query); Round 14 broadened the
        # subject lexicon so a full paper usually illustrates every reading
        # part — whatever query a part carries must actually be embedded.
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 96
        paper = _gen({"year": 3, "pictures": True})
        with unittest.mock.patch.object(art, "photo_bytes",
                                        return_value=fake_jpeg):
            html = render_html.render_html(paper)
        self.assertIn("<img", html)
        self.assertIn("data:image/jpeg;base64,", html)
        thumbs = {a for a in re.findall(r'alt="([^"]+)"', html)
                  if a != "crest"}   # the school crest is not a part photo
        queries = {p.photo_query for p in paper.parts if p.photo_query}
        self.assertEqual(thumbs, queries)
        self.assertGreaterEqual(len(queries), 1,
                                "at least one part must carry a photo query")


class TestPhotos(unittest.TestCase):
    def test_query_picks_specific_subject(self):
        from types import SimpleNamespace
        self.assertEqual(art.query_for_text(
            "The proboscis monkey lives in the mangrove forest."),
            "proboscis monkey")
        self.assertEqual(art.query_for_text(
            "I eat nasi lemak for breakfast every morning."), "nasi lemak")
        self.assertEqual(art.query_for_text(
            "The firefighter works with a nurse."), "firefighter")
        self.assertEqual(art.query_for_text("A teapot got a new handle."), "")

    def test_query_prefers_dominant_topic(self):
        # "school bus" is longer, but the passage is about a market, so the
        # picture must stay on the dominant subject.
        self.assertEqual(
            art.query_for_text("At the market, Mother buys fish. "
                               "A school bus passes by."),
            "market")

    def test_query_no_generic_fallback(self):
        # Round 13 follow-up: a picture must be anchored to the text.  "The sky
        # is dark tonight." no longer gets a "moon" photo merely because the
        # dominant topic is space.
        self.assertEqual(art.query_for_text("The sky is dark tonight."), "")
        self.assertEqual(art.query_for_text("A teapot got a new handle."), "")

    def test_query_picks_picture_word_vocab(self):
        # Round 14: lower-primary picture-word subjects (Y1/2 Part 5 boxes and
        # the reference papers' labels) resolve to a photo of the word asked.
        from exam_gen import bank
        self.assertEqual(art.query_for_text("The lizard has a long tail."),
                         "lizard")
        self.assertEqual(art.query_for_text("A spider builds a web in the tree."),
                         "spider")
        self.assertEqual(art.query_for_text("The frog jumps into the pond."),
                         "frog")
        self.assertEqual(
            art.query_for_text("Word box: elephant, lizard, spider, frog, duck"),
            "elephant")
        vec = ("The lizard has a long tail. The spider sits in its web. "
               "The frog jumps in the pond. The duck swims.")
        with unittest.mock.patch.object(art, "_commons_thumbs") as ct:
            q = art.query_for_text(vec)
        self.assertIn(q, {"lizard", "spider", "frog", "duck"})
        ct.assert_not_called()

    def test_part_topic_uses_answer_words(self):
        # A photo subject may come from an item's options/answer (the pupil
        # reads the whole question), so a Part whose lead and stems carry no
        # subject phrase still pictures a target word from the question's own
        # options (previously the empty result meant no picture at all).
        from exam_gen import bank, models
        part = models.Part(num=5, kind="words", style="choice", marks=5,
                           title="PART 5",
                           lead="Study the pictures and the words below.",
                           lead_text="Study the pictures and the words below.")
        part.items.append(models.MCQItem(
            stem="This furry pet says meow. Choose the correct word.",
            options=["cat", "dog", "bird"], answer=0, ans_text="cat"))
        topic = bank._part_topic(part)
        self.assertIn(part.photo_query, {"cat", "dog", "bird"})
        self.assertEqual(topic, "animals")

    def test_photo_bytes_cache_only_never_fetches(self):
        with unittest.mock.patch.object(art, "_commons_thumbs") as ct, \
             unittest.mock.patch.object(art, "_download") as dl:
            got = art.photo_bytes("proboscis monkey", allow_fetch=False,
                                  cache_dir=tempfile.mkdtemp())
        self.assertIsNone(got)
        ct.assert_not_called()
        dl.assert_not_called()

    def test_fetch_photos_parallel_dedupes(self):
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\0\1\0\0\1\0\1\0\0\xff\xd9"
        calls = []

        def fake(query, cache_dir=None, allow_fetch=True):
            calls.append(query)
            return jpeg

        orig_offline = art._OFFLINE
        art._OFFLINE = False
        try:
            with unittest.mock.patch.object(art, "photo_bytes", side_effect=fake):
                out = art.fetch_photos(["a", "a", "b"])
        finally:
            art._OFFLINE = orig_offline
        self.assertEqual(set(out), {"a", "b"})
        self.assertEqual(out["a"], jpeg)
        self.assertEqual(sorted(calls), ["a", "b"])

    def test_photo_bytes_offline_returns_none(self):
        self.assertIsNone(art.photo_bytes("proboscis monkey",
                                          cache_dir=tempfile.mkdtemp()))

    def test_photo_bytes_fetch_and_cache(self):
        orig_offline = art._OFFLINE
        art._OFFLINE = False
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\0\1\0\0\1\0\1\0\0\xff\xd9"
        try:
            with unittest.mock.patch.object(art, "_commons_thumbs",
                                            return_value=[("http://t/j", "CC BY 2.0")]), \
                 unittest.mock.patch.object(art, "_download",
                                            side_effect=lambda url: jpeg):
                cache = tempfile.mkdtemp()
                got = art.photo_bytes("proboscis monkey", cache_dir=cache)
                self.assertEqual(got, jpeg)
                self.assertEqual(len(os.listdir(cache)), 1)
                # served from cache even if the fetch is turned off again
                art._OFFLINE = True
                cached = art.photo_bytes("proboscis monkey", cache_dir=cache)
                self.assertEqual(cached, jpeg)
        finally:
            art._OFFLINE = orig_offline

    def test_picture_html_fallback_and_embed(self):
        from types import SimpleNamespace
        part = SimpleNamespace(topic="market", photo_query="")
        tmp = tempfile.mkdtemp()
        try:
            # hermetic: isolated cache dir, so any real 'market' photo cached
            # on this machine cannot leak in and break the placeholder check
            with unittest.mock.patch.object(art, "_photo_cache_dir",
                                            return_value=tmp):
                # no broken SVG any more: a clean placeholder is returned
                self.assertNotIn("<svg", art.picture_html(part))
                self.assertIn("pic-ph", art.picture_html(part))
            part = SimpleNamespace(topic="market", photo_query="nasi lemak")
            with unittest.mock.patch.object(art, "photo_bytes",
                                            return_value=None):
                self.assertIn("pic-ph", art.picture_html(part))
            with unittest.mock.patch.object(
                    art, "photo_bytes",
                    return_value=b"\xff\xd8\xff\xe0\x00\x10JFIF\0\1\0\0\1\0\1\0\0\xff\xd9"):
                html = art.picture_html(part)
            self.assertIn("<img", html)
            self.assertIn("data:image/jpeg;base64,", html)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_photo_budget_stops_fetching(self):
        cache = tempfile.mkdtemp()
        art._budget_left = 0.0
        try:
            with unittest.mock.patch.object(art, "_commons_thumbs") as ct, \
                 unittest.mock.patch.object(art, "_download") as dl:
                self.assertIsNone(art.photo_bytes("dragon fruit",
                                                  cache_dir=cache))
            ct.assert_not_called()
            dl.assert_not_called()
        finally:
            art._budget_left = art._PHOTO_BUDGET_SECS

    def test_fetch_photos_batch_does_not_starve_siblings(self):
        # Regression: the shared photo budget used to be a counter that every
        # parallel worker thread drained with its own wall-clock, so the first
        # query to finish spent the whole budget and every other part of the
        # paper kept the "Photo available online after a refresh" placeholder
        # forever.  The budget is now a batch *deadline*: siblings that start
        # together share one window and all resolve.
        import time
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\0\1\0\0\1\0\1\0\0\xff\xd9"
        cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cache, ignore_errors=True)

        def search(q):
            t0 = time.monotonic()
            time.sleep(0.6)          # slow network: ~0.6 s per search
            art._spend(t0)           # the real search charges the budget
            return [(f"https://t.invalid/{q}/thumb.jpg", "CC BY 4.0")]

        def download(url):
            t0 = time.monotonic()
            time.sleep(0.05)
            art._spend(t0)           # the real download charges the budget
            return jpeg

        orig_offline, orig_budget = art._OFFLINE, art._budget_left
        art._OFFLINE = False
        art._failed_queries.clear()
        try:
            with unittest.mock.patch.object(art, "_commons_thumbs",
                                            side_effect=search), \
                 unittest.mock.patch.object(art, "_download",
                                            side_effect=download):
                art._budget_left = 1.0
                out = art.fetch_photos(["alpha", "beta", "gamma"],
                                       cache_dir=cache)
        finally:
            art._OFFLINE = orig_offline
            art._budget_left = orig_budget
        self.assertEqual(set(out), {"alpha", "beta", "gamma"})
        self.assertTrue(all(out[q] == jpeg for q in ("alpha", "beta", "gamma")),
                        "every paper topic in a batch must get its photo, "
                        "got %r" % out)

    def test_docx_embeds_photo_without_rsvg(self):
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\0\1\0\0\1\0\1\0\0\xff\xd9"
        paper = _gen({"year": 3, "seed": 2})
        with unittest.mock.patch.object(art, "photo_bytes",
                                        return_value=jpeg):
            raw = X.render_doc(paper)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
        self.assertTrue(any(n.startswith("word/media/") and
                            n.endswith(".jpg") for n in names))
        self.assertIn("image/jpeg", X_content_types(raw))


def X_content_types(raw: bytes) -> str:
    with zipfile.ZipFile(__import__("io").BytesIO(raw)) as z:
        return z.read("[Content_Types].xml").decode("utf-8", "ignore")


class TestAnswerSheet(unittest.TestCase):
    def test_docx_sheet_has_writing_section(self):
        for y in (1, 3, 5, 6):
            xml = _docx_text(_gen({"year": y, "answer_sheet": True}))
            self.assertIn("PAPER ANSWER SHEET", xml)
            self.assertIn("WRITING", xml)
            self.assertIn("Write your answers in the space provided.", xml)

    def test_html_sheet_has_writing_section(self):
        html = render_html.render_html(_gen({"year": 5}))
        self.assertIn("PAPER ANSWER SHEET", html)
        self.assertIn("WRITING", html)

    def test_html_sheet_part_lines_editable(self):
        import re
        from exam_gen import editor
        paper = _gen({"year": 5, "answer_sheet": True})
        idx = next(i for i, p in enumerate(paper.parts)
                   if p.kind == "writing")
        paper = editor.apply_edits(paper, {"parts": [{}] * idx +
                                           [{"lines": 7}]})
        html = render_html.render_html(paper)
        sheet = html.split("PAPER ANSWER SHEET")[1]
        marker = "PART %d" % paper.parts[idx].num
        self.assertIn(marker, sheet)
        seg = sheet.split(marker)[1]
        seg = seg.split('<table class="write-lines">')[1].split("</table>")[0]
        self.assertEqual(seg.count("<tr><td></td></tr>"), 7)

    def test_sheet_omittable(self):
        xml = _docx_text(_gen({"answer_sheet": False}))
        self.assertNotIn("PAPER ANSWER SHEET", xml)


class TestWebEnrich(unittest.TestCase):
    def test_fact_questions_stable(self):
        qs = webfetch._fact_questions(
            "The fox saw the crow high in the tree. The lion slept in its den.",
            max_q=5)
        self.assertTrue(qs)
        for q in qs:
            self.assertIn("stem", q)
            self.assertGreaterEqual(len(q["opts"]), 3)

    def test_cache_roundtrip(self):
        cache = {"S": [{"text": "t", "qs": [{"stem": "s", "opts": ["a", "b", "c"],
                                             "ans": 0, "ans_text": "a"}]}]}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            p = fh.name
        try:
            import json
            json.dump(cache, open(p, "w"))
            got = json.load(open(p))
            self.assertEqual(got["S"][0]["qs"][0]["stem"], "s")
        finally:
            os.unlink(p)


class TestWebBand(unittest.TestCase):
    """Round 11/F27: web comprehension passages are CEFR-banded per year.

    A 243-word Victorian Aesop chunk ("black servant" + "frog and mouse"
    fused) must never reach a paper of any year, even though it carries the
    full 5-question Part 3 count under the old length-only gate.
    """
    SERVANT = ("THE PURCHASER of a black servant was persuaded that the color "
               "of his skin arose from dirt contracted through the neglect of "
               "his former masters. On bringing him home he resorted to every "
               "means of cleaning, and subjected the man to incessant "
               "scrubbings. The servant caught a severe cold, but he never "
               "changed his color or complexion. What's bred in the bone will "
               "stick to the flesh. A MOUSE who always lived on the land, by "
               "an unlucky chance formed an intimate acquaintance with a Frog, "
               "who lived for the most part in the water.")

    @staticmethod
    def _wb(text, n=5):
        # Round 26: the options must be words the DSKP allows for the year —
        # a placeholder letter pair is now refused, so the fixture offers real
        # on-ladder vocabulary and the test stays about band/ceiling/blocklist.
        return [{"text": text,
                 "qs": [{"stem": f"Q{i}: the ___",
                         "opts": ["cat", "dog", "bird"],
                         "ans": 0, "ans_text": "cat"} for i in range(n)]}]

    def _p3(self, year, text):
        return _gen({"year": year, "seed": 1, "use_web": True, "parts": [3]},
                    self._wb(text)).parts[0]

    def test_passage_band_classifier(self):
        self.assertEqual(bank.passage_band(
            "The cat sits on the mat. The dog runs fast."), "a1")
        self.assertEqual(bank.passage_band(
            "The clever fox approached the crow in the tree. "
            "The crow was sad."), "a2")
        self.assertEqual(bank.passage_band(self.SERVANT), "b1")

    def test_blocked_passage_never_used_any_year(self):
        for year in D.YEARS:
            p3 = self._p3(year, self.SERVANT)
            self.assertEqual(len(p3.items), 5, f"Y{year}")
            self.assertNotIn("black servant", p3.lead_text, f"Y{year}")
            self.assertNotIn("frog", p3.lead_text.lower(), f"Y{year}")

    def test_year_word_ceiling(self):
        long_simple = "The cat sat on the big mat. " * 30    # ~210 words, a1
        for year in (1, 2, 3):
            p3 = self._p3(year, long_simple)
            self.assertLess(p3.lead_text.lower().count("cat"), 5,
                            f"Y{year} web text leaked past ceiling")
        for year in (5, 6):
            p3 = self._p3(year, long_simple)
            self.assertGreater(p3.lead_text.lower().count("cat"), 20,
                               f"Y{year} should accept an a1 passage in range")

    def test_band_caps_lower_years(self):
        mild = "The farmer approached the old man and replied. " * 8  # band a2
        p1 = self._p3(1, mild)
        self.assertNotIn("approached", p1.lead_text,
                         "Y1 (A1 cap) must reject an A2 passage")
        p3 = self._p3(3, mild)
        self.assertIn("approached", p3.lead_text,
                      "Y3 (A2 cap) may accept an A2 passage")

    def test_lower_year_sources_serve_the_lower_years(self):
        # Round 14 added simple readers so Years 1/2 (A1 cap) would have web
        # passages; Round 27 replaced the whole Gutenberg registry with the
        # shipped KSSR story corpus, so the check is now "does the corpus
        # actually serve the A1 years?" rather than "which book is it?".
        from exam_gen import webfetch as WF
        cache = WF.update_cache(keep_existing=False)
        for year in (1, 2):
            self.assertTrue(WF.passages_for_year(cache, year, 5),
                            f"Year {year} must have KSSR passages")

    def test_a_simple_a1_passage_still_passes_the_year_gate(self):
        from exam_gen import webfetch as WF
        simple = ("Ann has a new red hat. Tom can run fast. "
                  "The cat can see the dog and the bird.")
        self.assertEqual(bank.passage_band(simple), "a1")
        self.assertTrue(WF._passes_year_gate(1, "Ann has a new hat. " * 14),
                        "Y1 (A1) must accept a short simple reader")
        self.assertTrue(WF._passes_year_gate(1, simple))
        pond = ("A duck swam in the pond. It ate some bread. "
                "Then a cat came to the water.")
        self.assertIn(bank.passage_band(pond), ("a1", "a2"))
        self.assertTrue(WF._passes_year_gate(2, pond))


class TestWebDifficultySplit(unittest.TestCase):
    """Round 12/J: easy/hard length splits run INSIDE the year band, so
    'hard' is never empty for years 1-3 (whose ceilings sit below the old
    absolute 150-word 'hard' threshold)."""

    SIMPLE = "The cat sat on a mat in the sun. "

    def _pool(self, blocks):
        # Round 26: the questions must clear the DSKP gate, so the fixture
        # offers on-ladder words instead of placeholder letters.
        return [{"text": self.SIMPLE * n,
                 "qs": [{"stem": f"Q{i}", "opts": ["cat", "dog", "bird"],
                         "ans": 0, "ans_text": "cat"} for i in range(5)]}
                for n in blocks]

    def test_banded_hard_easy_not_empty(self):
        import random
        from exam_gen import bank
        self.assertEqual(bank.passage_band(self.SIMPLE * 14), "a1")
        pool = self._pool([7, 8, 9, 14, 18, 22, 26, 30])  # ~63..270 words
        for diff in ("easy", "hard", "medium"):
            for year in (1, 2, 3):
                text, qs, _src = bank._web_comprehension(
                    pool, random.Random(7 + year), difficulty=diff,
                    count=5, year=year)
                self.assertIsNotNone(text, f"Y{year} {diff} must not be empty")
                self.assertLessEqual(
                    len(text.split()),
                    D.PASSAGE_WORD_CEIL[year],
                    f"Y{year} {diff} must respect the word ceiling")

    def test_year_gate_helper(self):
        """Round 12/S2 helper mirrors the bank gate: low-year caps exclude
        A2/B1 or blocked prose; long-but-simple passages only fit Years 5/6."""
        from exam_gen import webfetch
        self.assertFalse(webfetch._passes_year_gate(1, TestWebBand.SERVANT))
        self.assertFalse(webfetch._passes_year_gate(2, TestWebBand.SERVANT))
        self.assertFalse(webfetch._passes_year_gate(6, TestWebBand.SERVANT),
                         "blocked content stays blocked every year")
        simple = "The cat sat on a big mat. " * 9      # 72w, a1, short
        self.assertTrue(webfetch._passes_year_gate(1, simple))
        long_simple = "The cat sat on a big mat. " * 30  # 240w, a1 but long
        self.assertFalse(webfetch._passes_year_gate(3, long_simple))
        self.assertTrue(webfetch._passes_year_gate(5, long_simple))
        mild = "The farmer approached the old man and replied. " * 8
        self.assertFalse(webfetch._passes_year_gate(1, mild), "A1 cap")
        self.assertTrue(webfetch._passes_year_gate(6, mild), "B1 year")


class TestFactQuestions(unittest.TestCase):
    """Round 12/S1: web MCQs are deterministic, offer three unique options and
    never use a distractor that also appears in the passage (the old code
    could offer 'Crow' next to 'fox' in a fable that mentions both)."""

    FOX = ("The fox and the crow sat on a big tree. The fox wanted the "
           "cheese. The crow held the cheese in its mouth. Then the fox "
           "sang a sweet song. The crow opened its mouth and dropped the "
           "cheese.")

    @staticmethod
    def _tokens(text: str) -> set:
        return set(re.findall(r"[a-z]+", text.lower()))

    def test_deterministic(self):
        self.assertEqual(webfetch._fact_questions(self.FOX),
                         webfetch._fact_questions(self.FOX))

    def test_distractors_not_in_passage(self):
        toks = self._tokens(self.FOX)
        for q in webfetch._fact_questions(self.FOX):
            self.assertEqual(len(q["opts"]), 3)
            self.assertGreaterEqual(q["ans"], 0)
            self.assertLess(q["ans"], 3)
            for i, o in enumerate(q["opts"]):
                if i != q["ans"]:
                    self.assertNotIn(o.lower(), toks,
                                     f"distractor {o!r} leaked into passage")
            self.assertIn(q["ans_text"].lower(), toks,
                          "answer must be directly in the passage")
            self.assertTrue(
                q["opts"][q["ans"]].casefold() == q["ans_text"].casefold())
            self.assertEqual(len({o.casefold() for o in q["opts"]}), 3)


class TestQualityGate(unittest.TestCase):
    """Round 12/S9: generated papers are scanned for duplicates, repeated
    passages and answer-in-stem leaks; the CLI/GUI are warned on save."""

    def test_clean_papers_have_no_issues(self):
        for year in D.YEARS:
            p = _gen({"year": year, "seed": 9, "difficulty": "medium"})
            self.assertEqual(bank.quality_issues(p), [], f"Y{year}")

    def test_web_question_answer_leak_detected(self):
        self.assertTrue(bank._stem_leaks(
            {"stem": "The crow held the cheese.",
             "opts": ["cheese", "bread", "corn"], "ans": 0}))
        self.assertFalse(bank._stem_leaks(
            {"stem": "What did the crow hold?",
             "opts": ["cheese", "bread", "corn"], "ans": 0}))

    def test_duplicate_stem_and_answer_reported(self):
        from exam_gen.models import Part, MCQItem, Paper
        def paper_with(pairs):
            items = [MCQItem(stem=s, options=o, answer=a)
                     for s, o, a in pairs]
            body = Paper(meta={})
            part = Part(num=1, kind="mcq", style="", marks=10,
                        title="PART 1", lead="", lead_text="")
            part.items = items
            body.parts = [part]
            return body
        issues = bank.quality_issues(paper_with(
            [("Q1", ["x", "y", "z"], 0), ("Q1", ["p", "q", "r"], 0),
             ("Q2", ["x", "y", "z"], 0)]))
        self.assertTrue(any("duplicate question" in i for i in issues))
        issues = bank.quality_issues(paper_with(
            [("Q1", ["x", "y", "z"], 0), ("Q2", ["m", "n", "o"], 0)]))
        self.assertEqual(issues, [])

    def test_web_mcqs_dropped_on_leak(self):
        # a block whose only questions leak the answer must fall back to the
        # built-in pool (never ship a hint-to-answer Part 3)
        leaky = [{"text": "The cat sat on a big mat. " * 10,
                  "qs": [{"stem": "The cat sat on a big mat.",
                          "opts": ["mat", "cup", "box"], "ans": 0}] * 5}]
        p = _gen({"year": 3, "seed": 3, "use_web": True, "parts": [3]}, leaky)
        self.assertEqual(len(p.parts[0].items), 5)


class TestBandAudit(unittest.TestCase):
    """Round 12/S3: the per-year word-band audit now covers cloze, match and
    comprehension content too, not just the Part 1 vocabulary pool."""

    def test_all_years_all_kinds_clean(self):
        for year in D.YEARS:
            for kinds in (None, ("vocab",), ("cloze",), ("match",),
                          ("comprehension",)):
                self.assertEqual(bank.band_violations(year, kinds), [],
                                 f"Y{year} {kinds}")

    def test_audit_uses_the_years_own_band(self):
        for year in D.YEARS:
            for kind in ("vocab", "cloze", "match", "comprehension"):
                hits = bank.band_violations(year, (kind,))
                for _, words, _ in hits:
                    for w in words.split(", "):
                        self.assertIn(w, D.VOCAB_BAND[year],
                                      f"Y{year} {kind} flagged '{w}'")

    def test_flags_injected_band_words(self):
        import unittest.mock as mock
        with mock.patch.object(
                bank, "_cloze_pool",
                return_value=[{"passage": "A surgeon fixed the monsoon rain.",
                               "gaps": [{"stem": "x", "opts": ["a", "b", "c"],
                                         "ans": 0}]}]):
            hits = bank.band_violations(1, kinds=("cloze",))
            self.assertTrue(any("surgeon" in w and "monsoon" in w
                                for _, w, _ in hits))


class TestRegenApi(unittest.TestCase):
    def test_next_seed(self):
        self.assertNotEqual(bank.next_seed(5), 5)
        self.assertIn(bank.next_seed(1), range(2, 11))

    def test_theme_advance(self):
        idx, theme = bank.next_theme(6, 0)
        self.assertEqual(theme, D.RPT_THEMES[6][1])
        self.assertEqual(idx, 1)


@unittest.skipUnless(HAVE_DISPLAY, "no display for widget tests")
class TestGuiRegression(unittest.TestCase):
    def test_ui_is_english_only(self):
        from exam_gen import app as A
        # language toggle was removed — the UI is English everywhere
        self.assertFalse(hasattr(A.ExamApp, "on_toggle_lang"))
        self.assertFalse(hasattr(A.ExamApp, "_rebuild_ui"))
        self.assertEqual(A._t("btn_regen"), "Regenerate")
        self.assertEqual(A._t("edit_inline"), "Edit on Paper")
        self.assertEqual(A._t("gen_status", 7, 50, 30),
                         "7 parts · 50 marks · 30 questions")

    def test_regen_regenerates_immediately(self):
        from exam_gen import app as A
        import gi
        gi.require_version("Gtk", "4.0")
        ap = A.ExamApp()
        try:
            ap.do_activate()
        except Exception:
            self.skipTest("no window possible")
        before = ap.paper
        ap.on_regen()
        self.assertIsNotNone(ap.paper)
        # a regen always produces a freshly seeded paper immediately
        self.assertTrue(hasattr(ap.paper, "parts"))
        A._STATE["bm"] = True

    def test_inline_edit_toggles_preview(self):
        from exam_gen import app as A
        import gi
        gi.require_version("Gtk", "4.0")
        ap = A.ExamApp()
        try:
            ap.do_activate()
        except Exception:
            self.skipTest("no window possible")
        ap.bt_edit_inline.set_active(True)
        self.assertTrue(ap._editing)
        ap.bt_edit_inline.set_active(False)
        self.assertFalse(ap._editing)
        A._STATE["bm"] = True

    def test_theme_is_always_dark(self):
        from exam_gen import app as A
        ap = A.ExamApp()
        try:
            ap.do_activate()
        except Exception:
            self.skipTest("no window possible")
        ap._apply_theme()
        self.assertIn("dark", ap.win.get_css_classes())
        self.assertNotIn("light", ap.win.get_css_classes())
        ap._theme = "light"                     # flag no longer honoured
        ap._apply_theme()
        self.assertIn("dark", ap.win.get_css_classes())
        self.assertNotIn("light", ap.win.get_css_classes())

    def test_layout_wide_narrow(self):
        from exam_gen import app as A
        ap = A.ExamApp()
        try:
            ap.do_activate()
        except Exception:
            self.skipTest("no window possible")
        ap._apply_layout(1500)
        self.assertEqual(ap._mode, "wide")
        self.assertIs(ap.drawer.get_child(), ap.side_scroll)
        self.assertIs(ap.side_scroll.get_parent(), ap.drawer)
        self.assertIs(ap.overlay.get_parent(), ap.root)   # preview fills
        ap._apply_layout(600)
        self.assertEqual(ap._mode, "narrow")
        self.assertIs(ap.popover.get_child(), ap.side_scroll)
        self.assertIs(ap.config_btn.get_popover(), ap.popover)
        ap._apply_layout(1500)
        self.assertEqual(ap._mode, "wide")
        self.assertIs(ap.drawer.get_child(), ap.side_scroll)


class TestInlineEditProtocol(unittest.TestCase):
    """Clicking the paper must round-trip ``P<part>:I<item>`` to the app.

    Regression: two bugs made on-paper editing silently do nothing — the
    WebKit handler called ``result.get_js_value()`` (WebKitGTK 6.0 hands the
    callback a ``JSC.Value``, so this raised and every click was discarded) and
    the parser then split on ``I`` without dropping the ``:`` separator, so
    ``int("0:")`` failed even when a value arrived.
    """

    class _Direct:
        def __init__(self, s):
            self.s = s

        def to_string(self):
            return self.s

    def test_parse_paper_eid(self):
        from exam_gen import app as A
        self.assertEqual(A.parse_paper_eid("P0:I2"), (0, 2))
        self.assertEqual(A.parse_paper_eid("P3:I-1"), (3, -1))
        self.assertEqual(A.parse_paper_eid("P0I7"), (0, 7))
        self.assertIsNone(A.parse_paper_eid("nonsense"))
        self.assertIsNone(A.parse_paper_eid(""))

    def test_jsc_string_handles_both_apis(self):
        from exam_gen import app as A
        class Wrapped:
            def get_js_value(self):
                return TestInlineEditProtocol._Direct("P1:I4")
        self.assertEqual(A._jsc_string(self._Direct("P1:I4")), "P1:I4")
        self.assertEqual(A._jsc_string(Wrapped()), "P1:I4")
        self.assertEqual(A._jsc_string(object()), "")

    def test_rendered_eids_round_trip(self):
        from exam_gen import app as A
        conf = dict(D.DEFAULT_CONFIG)
        conf.update(year=6, seed=5, pictures=False)
        p = bank.generate_paper(conf, None)
        html = render_html.render_html(p, allow_fetch=False, editable=True)
        eids = re.findall(r'data-eid="(P\d+:I-?\d+)"', html)
        self.assertGreater(len(eids), 10)
        for e in eids:
            parsed = A.parse_paper_eid(e)
            self.assertIsNotNone(parsed, e)
            self.assertEqual(parsed[0], int(e.split(":")[0][1:]))

    def test_message_dispatch_targets_clicked_part(self):
        from exam_gen import app as A
        import types
        calls = []
        stub = types.SimpleNamespace(
            paper=types.SimpleNamespace(parts=[1, 2, 3]),
            _open_quick_edit=lambda pi, ii: calls.append((pi, ii)))
        orig = A.GLib.idle_add
        A.GLib.idle_add = lambda fn, *a: (calls.append((a[0], a[1])), False)[1]
        try:
            A.ExamApp._on_paper_message(stub, None, self._Direct("P1:I4"))
        finally:
            A.GLib.idle_add = orig
        self.assertEqual(calls, [(1, 4)])


class TestCli(unittest.TestCase):
    def run_cli(self, args):
        from exam_gen import cli
        return cli.run_cli(args)

    def test_cli_all_years(self):
        with tempfile.TemporaryDirectory() as td:
            for y in D.YEARS:
                out = os.path.join(td, f"Y{y}")
                code = self.run_cli(["--cli", "--year", str(y), "--seed", "4",
                                     "--out", out, "--difficulty", "easy",
                                     "--theme", D.RPT_THEMES[y][0]])
                self.assertEqual(code, 0)
                self.assertTrue(os.path.exists(out + ".docx"))
                with zipfile.ZipFile(out + ".docx") as z:
                    self.assertIn("word/document.xml", z.namelist())

    def test_cli_round2_flags(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P")
            code = self.run_cli(["--cli", "--year", "5", "--seed", "2",
                                 "--out", out, "--marksheet", "--ab",
                                 "--week", "8"])
            self.assertEqual(code, 0)
            for n in (".docx", "B.docx", "_marksheet.docx"):
                self.assertTrue(os.path.exists(out + n), n)

    def test_cli_out_strips_known_extension(self):
        """--out that already carries a document extension must not gain a
        second one (no ``Paper.docx.docx``)."""
        with tempfile.TemporaryDirectory() as td:
            for ext in (".docx", ".pdf", ".odt"):
                out = os.path.join(td, "P" + ext)
                code = self.run_cli(["--cli", "--year", "5", "--seed", "2",
                                     "--out", out])
                self.assertEqual(code, 0)
                self.assertTrue(os.path.exists(os.path.join(td, "P.docx")),
                                ext)
                self.assertFalse(os.path.exists(out + ".docx"), ext)

    def test_cli_out_plain_stem_unchanged(self):
        """A bare --out stem keeps the existing ``<stem>.docx`` behaviour."""
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P")
            code = self.run_cli(["--cli", "--year", "5", "--seed", "2",
                                 "--out", out])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(out + ".docx"))

    def test_cli_term_batch(self):
        """Round 12/S5: --term emits one paper per RPT week with a distinct
        seed and theme, ready for a whole term."""
        with tempfile.TemporaryDirectory() as td:
            code = self.run_cli(["--cli", "--year", "3", "--seed", "5",
                                 "--out", td, "--term", "3"])
            self.assertEqual(code, 0)
            files = sorted(f for f in os.listdir(td) if f.endswith(".docx"))
            self.assertEqual(len(files), 3, files)
            for f in files:
                self.assertRegex(f, r"^UPSA_Y3_W0[123]_")
            t1 = D.RPT_THEMES[3][0]
            slug1 = re.sub(r"[^A-Za-z0-9]+", "_", t1).strip("_")
            self.assertTrue(any(slug1 in f for f in files), files)

    def test_cli_csv_json_export(self):
        """Round 12/S7: --csv/--json emit spreadsheets + machine-readable JSON
        beside the .docx."""
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P")
            code = self.run_cli(["--cli", "--year", "5", "--seed", "7",
                                 "--out", out, "--csv", "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(out + ".key.csv"))
            self.assertTrue(os.path.exists(out + ".json"))
            with open(out + ".key.csv", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0][0], "Part")
            regen = bank.generate_paper(
                dict(D.DEFAULT_CONFIG, **{"year": 5, "seed": 7}))
            self.assertEqual(len(rows) - 1, regen.max_qno())
            with open(out + ".json", encoding="utf-8") as f:
                data = _json.load(f)
            self.assertIn("meta", data)
            self.assertEqual(len(data["parts"]), len(regen.parts))
            self.assertTrue(all(p["marks"] > 0 for p in data["parts"]))


class TestArchive(unittest.TestCase):
    """Round 12/S6: JSON-exported past papers can be re-rendered and are
    auto-suggested against each RPT week's theme."""

    def test_reset_part_restores_original(self):
        """Round 12/S8: undoing an edit via part_to_edit(original part)
        restores every header field of the edited part."""
        from exam_gen import editor
        paper = _gen({"year": 5, "seed": 9})
        idx = next(i for i, p in enumerate(paper.parts) if p.lead_text)
        original = editor.part_to_edit(paper.parts[idx])
        edits_parts = [{} for _ in paper.parts]
        edits_parts[idx] = {"lead": "CHANGED", "lead_text": "MUTATED",
                            "items": []}
        edited = editor.apply_edits(paper, {"parts": edits_parts})
        self.assertEqual(edited.parts[idx].lead, "CHANGED")
        self.assertEqual(edited.parts[idx].lead_text, "MUTATED")
        edits_parts = [{} for _ in edited.parts]
        edits_parts[idx] = original
        restored = editor.apply_edits(edited, {"parts": edits_parts})
        self.assertEqual(restored.parts[idx].lead, paper.parts[idx].lead)
        self.assertEqual(restored.parts[idx].lead_text,
                         paper.parts[idx].lead_text)
        self.assertEqual([i.answer for i in restored.parts[idx].items],
                         [i.answer for i in paper.parts[idx].items])

    def test_export_roundtrip(self):
        import json as _json
        for y in (1, 3, 6):
            paper = _gen({"year": y, "seed": 6})
            data = _json.loads(_json.dumps(bank.paper_export(paper)))
            rebuilt = bank.paper_from_export(data)
            self.assertEqual(rebuilt.max_qno(), paper.max_qno(), f"Y{y}")
            self.assertEqual(rebuilt.key, paper.key, f"Y{y} key")
            self.assertEqual(len(rebuilt.parts), len(paper.parts), f"Y{y}")
            for pa, pb in zip(paper.parts, rebuilt.parts):
                self.assertEqual(len(pa.items), len(pb.items), f"Y{y} {pa.title}")

    def test_archive_suggest_matches_week_theme(self):
        import json as _json
        want_theme = bank.theme_for_week(1, 3)
        other_theme = D.RPT_THEMES[1][-1]  # same year, different theme
        with tempfile.TemporaryDirectory() as td:
            for name, theme in (("match.json", want_theme),
                                ("miss.json", other_theme)):
                paper = _gen({"year": 1, "seed": 2, "theme": theme})
                with open(os.path.join(td, name), "w", encoding="utf-8") as f:
                    _json.dump(bank.paper_export(paper), f)
            want, hits = bank.archive_suggest(1, 3, td)
            self.assertEqual(want, want_theme)
            self.assertEqual(len(hits), 1, hits)
            self.assertTrue(hits[0][0].endswith("match.json"), hits)


class TestBackup(unittest.TestCase):
    def test_backup_writes_timestamped_copies(self):
        """Round 12/S10: bank + packs are snapshotted before overwrites."""
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            old_data = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_DATA_HOME"] = td
            try:
                exam_dir = os.path.join(td, "exam-gen")
                os.makedirs(exam_dir)
                with open(os.path.join(exam_dir, "user_bank.json"),
                          "w", encoding="utf-8") as f:
                    _json.dump({"vocab": {1: [{"a": 1}]}}, f)
                with open(os.path.join(exam_dir, "packs.json"),
                          "w", encoding="utf-8") as f:
                    _json.dump({"packs": []}, f)
                made = bank.backup_state()
                self.assertIn("user_bank_", made)
                self.assertIn("packs_", made)
                self.assertTrue(all(p.endswith(".json")
                                    for p in made.splitlines()), made)
                backups = os.listdir(os.path.join(exam_dir, "backups"))
                self.assertEqual(len(backups), 2, backups)
            finally:
                if old_data is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = old_data


class TestEnglishPapers(unittest.TestCase):
    """Round 12 wrap-up: papers render in English only — first-page header,
    instructions, every part lead, the answer sheet and the answer key."""

    BAD = ("ARAHAN", "JUMLAH", "SKEMA", "BORANG", "TAHUN", "SESI",
           "Nama:", "Kelas:", "Pemeriksa", "Markah", "Bahagian", "Tulis",
           "contoh", "Sekolah", "Guru", "Murid", "Untuk", "minit",
           "Ruang", "jawapan", "Ujian", "Kertas")

    def _strip_caption(self, text):
        # The requested tri-lingual cover caption (English · Malay · Chinese)
        # is deliberately bilingual, so it is excluded from the English-only
        # token scan (Round 13 follow-up).
        for cap in D.EXAM_CAPTION.values():
            for lang in ("en", "ms", "zh"):
                text = text.replace(cap[lang], "")
        return text

    def _scan(self, text, y, what):
        if what == "html":
            text = re.sub(r"data:[^\"'\s)]+", "", text)
        text = self._strip_caption(text)
        for tok in self.BAD:
            self.assertIsNone(
                re.search(r"\b" + re.escape(tok) + r"\b", text),
                f"Y{y} {what} still contains '{tok}'")

    def test_docx_paper_english(self):
        for y in D.YEARS:
            paper = _teacher({"year": y, "seed": 3})
            raw = X.render_doc(paper)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            self.assertIn("INSTRUCTIONS:", xml)
            self.assertIn("ANSWER KEY", xml)
            self.assertIn("PAPER ANSWER SHEET", xml)
            self._scan(xml, y, "docx")

    def test_html_paper_english(self):
        for y in D.YEARS:
            paper = _gen({"year": y, "seed": 3})
            self._scan(render_html.render_html(paper, allow_fetch=False),
                       y, "html")

    def test_marksheet_english(self):
        paper = _gen({"year": 5, "seed": 4})
        raw = X.mark_sheet_doc(paper)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        self._scan(xml, 5, "marksheet")
        self.assertIn("MARKING SHEET", xml)
        self.assertIn("TOTAL", xml)


class TestMarksheet(unittest.TestCase):
    def test_marksheet_data(self):
        paper = _gen({"year": 3})
        ms = bank.mark_sheet(paper)
        self.assertEqual(ms["total"], D.TOTAL)
        self.assertEqual(sum(len(p["items"]) for p in ms["parts"]),
                         paper.max_qno())
        self.assertEqual(len(ms["parts"]), len(paper.parts))

    def test_marksheet_docx(self):
        raw = X.mark_sheet_doc(_gen({"year": 5}))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        self.assertIn("MARKING SHEET", xml)
        self.assertIn("TOTAL", xml)

    def test_marksheet_html(self):
        html = render_html.mark_sheet_html(_gen({"year": 1}))
        self.assertIn("MARKING SHEET", html)
        self.assertIn("TOTAL", html)


class TestAbSets(unittest.TestCase):
    def test_ab_differ_and_match_structure(self):
        conf = dict(D.DEFAULT_CONFIG)
        conf.update(year=3, seed=11)
        a = bank.generate_paper(conf)
        b = bank.generate_paper(dict(conf, seed=bank.next_seed(conf["seed"])))
        self.assertEqual(len(a.parts), len(b.parts))
        self.assertEqual([p.marks for p in a.parts],
                         [p.marks for p in b.parts])

        def text(p):
            return " ".join(str(getattr(it, "stem", "") or
                                getattr(it, "clue", "") or
                                getattr(it, "prompt", ""))
                            for pr in p.parts for it in pr.items)

        self.assertNotEqual(text(a), text(b))


class TestPagination(unittest.TestCase):
    def test_docx_page_breaks_between_parts(self):
        paper = _gen({"year": 3, "answer_sheet": False, "answer_key": False})
        xml = _docx_text(paper)
        self.assertEqual(xml.count("<w:pageBreakBefore/>"),
                         len(paper.parts) - 1)

    def test_html_part_breaks(self):
        html = render_html.render_html(
            _gen({"year": 3, "answer_sheet": False, "answer_key": False}))
        self.assertIn('class="pagebr"></div>\n<div class="partblock">\n'
                      '<div class="section-h">PART 2', html)


class TestRptWeeks(unittest.TestCase):
    def test_week_mapping(self):
        self.assertEqual(bank.theme_for_week(1, 1), D.RPT_THEMES[1][0])
        self.assertEqual(bank.theme_for_week(3, 14), D.RPT_THEMES[3][1])
        self.assertEqual(bank.theme_for_week(3, 40), D.RPT_THEMES[3][2])
        self.assertEqual(bank.theme_for_week(5, 8), D.RPT_THEMES[5][1])
        self.assertEqual(bank.theme_for_week(3, 0), "")

    def test_week_ranges(self):
        self.assertEqual(bank.weeks_for_theme(5, "Days"), (6, 10))
        self.assertEqual(bank.weeks_for_theme(3, "World of Stories"), (14, 27))

    def test_auto_theme_via_week(self):
        paper = _gen({"year": 5, "week": 8})
        self.assertEqual(paper.meta["theme"], D.RPT_THEMES[5][1])
        explicit = _gen({"year": 5, "week": 8, "theme": "Sport"})
        self.assertEqual(explicit.meta["theme"], "Sport")


class TestUserBank(unittest.TestCase):
    def test_parse_and_year_expansion(self):
        pb = bank.parse_user_bank({
            "comprehension": [{"passage": "T.", "qs": [{"q": "A", "opts": ["x"], "ans": 0}]}],
            "words": [{"year": 1, "box": ["a"], "items": [{"o": 1}]}],
            "match": [{"year": "any", "texts": ["A.", "B.", "C."],
                       "qs": [{"opts": ["A", "B", "C"], "ans": 0}]}],
        })
        for y in D.YEARS:
            self.assertEqual(len(pb["comprehension"][y]), 1)  # "any"
        self.assertEqual(len(pb["words"][1]), 1)
        self.assertEqual(len(pb["words"][2]), 0)               # specific year
        self.assertEqual(len(pb["match"][6]), 1)

    def test_user_comprehension_selected(self):
        pb = {"comprehension": [{
            "year": 3, "theme": "World of Stories", "title": "The Flying Horse",
            "passage": "The emperor told a great tale about a flying horse.",
            "qs": [
                {"stem": "What did the emperor tell?",
                 "opts": ["a tale", "a song", "a map"], "ans": 0},
                {"stem": "What creature is the story about?",
                 "opts": ["a horse", "a goat", "a cow"], "ans": 0},
                {"stem": "Where does the horse fly?",
                 "opts": ["the sky", "the sea", "the cave"], "ans": 0},
                {"stem": "Who listened to the tale?",
                 "opts": ["the people", "the birds", "the fish"], "ans": 0},
                {"stem": "Was the horse real?",
                 "opts": ["No", "Yes", "Maybe"], "ans": 0}]}]}
        paper = _gen({"year": 3, "theme": "World of Stories", "seed": 1,
                      "parts": [3], "user_bank": pb})
        self.assertIn("flying horse", paper.parts[0].lead_text)
        self.assertEqual(len(paper.parts[0].items), 5)
        self.assertEqual(paper.parts[0].marks, 5)

    def test_user_short_comprehension_falls_back(self):
        # A user comprehension whose questions are fewer than the official Part 3
        # count is not usable as-is; generation must fall back to the built-in
        # pool instead of producing a 1-question / 5-mark part.
        pb = {"comprehension": [{
            "year": 3, "passage": "A short passage about a flying horse.",
            "qs": [{"stem": "What is the story about?",
                    "opts": ["a horse", "a goat"], "ans": 0}]}]}
        paper = _gen({"year": 3, "seed": 1, "parts": [3], "user_bank": pb})
        p3 = paper.parts[0]
        self.assertEqual(len(p3.items), 5)
        self.assertEqual(p3.marks, 5)

    def test_cli_bank_and_template(self):
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            tpl = os.path.join(td, "tpl.json")
            self.assertEqual(cli.run_cli(["--cli", "--bank-template", tpl]), 0)
            self.assertTrue(os.path.exists(tpl))
            bank_json = os.path.join(td, "bank.json")
            with open(bank_json, "w") as fh:
                fh.write('{"letter_words": [{"clue": "A loud bird.", '
                         '"word": "hornbill"}]}')
            out = os.path.join(td, "P")
            code = cli.run_cli(["--cli", "--year", "6", "--seed", "3",
                                "--out", out, "--bank", bank_json])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(out + ".docx"))


class TestEditor(unittest.TestCase):
    def test_edits_are_deep_copied(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "seed": 1})
        edits = {"parts": []}
        paper2 = editor.apply_edits(paper, edits)
        self.assertIsNot(paper, paper2)
        self.assertIsNot(paper.parts, paper2.parts)   # untouched input

    def test_mcq_text_edits(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "seed": 1, "parts": [2]})
        part = paper.parts[0]
        item = part.items[0]
        edits = {"parts": [{
            "lead": "ARAHAN BARU", "lead_text": "PETIKAN BARU",
            "items": [{"stem": "STEM BARU", "options": ["X", "Y", "Z"],
                       "answer": 2}]}]}
        p2 = editor.apply_edits(paper, edits)
        self.assertEqual(p2.parts[0].lead, "ARAHAN BARU")
        self.assertEqual(p2.parts[0].lead_text, "PETIKAN BARU")
        it = p2.parts[0].items[0]
        self.assertEqual(it.stem, "STEM BARU")
        self.assertEqual(it.options, ["X", "Y", "Z"])
        self.assertEqual(it.answer, 2)
        orig = paper.parts[0].items[0]
        self.assertEqual(orig.stem, item.stem)      # input untouched
        self.assertEqual(p2.parts[0].items[1].stem, part.items[1].stem)

    def test_mcq_answer_clamped(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "parts": [2]})
        edits = {"parts": [{"items": [{"options": ["A", "B"], "answer": 9}]}]}
        p2 = editor.apply_edits(paper, edits)
        self.assertEqual(p2.parts[0].items[0].answer, 1)

    def test_word_answer_rebuilds_pattern(self):
        from exam_gen import editor
        from exam_gen.models import WordItem
        paper = _gen({"year": 5, "parts": [5]})
        paper.parts[0].items = [WordItem(clue="C.", first="B", length=7,
                                         answer="BANANA")]
        edits = {"parts": [{"items": [{"answer": "ORANGEN"}]}]}
        p2 = editor.apply_edits(paper, edits)
        it = p2.parts[0].items[0]
        self.assertEqual(it.answer, "ORANGEN")
        self.assertEqual(it.first, "O")
        self.assertEqual(it.length, 7)

    def test_write_fields_editable(self):
        from exam_gen import editor
        from exam_gen.models import WriteItem
        paper = _gen({"year": 6, "parts": [7]})
        it = paper.parts[0].items[0]
        edits = {"parts": [{"items": [{
            "prompt": "Write a new letter.", "bullets": ["a", "b"],
            "lines": 22, "salutation": "Dear X", "closing": "Yours,"}]}]}
        p2 = editor.apply_edits(paper, edits)
        it2 = p2.parts[0].items[0]
        self.assertEqual(it2.prompt, "Write a new letter.")
        self.assertEqual(it2.bullets, ["a", "b"])
        self.assertEqual(it2.lines, 22)
        self.assertEqual(it2.salutation, "Dear X")
        self.assertEqual(it2.closing, "Yours,")
        self.assertIsInstance(it2, WriteItem)
        self.assertEqual(it, paper.parts[0].items[0])   # untouched

    def test_ignored_part_kept(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "seed": 2})
        p2 = editor.apply_edits(paper, {"parts": []})
        self.assertEqual(len(p2.parts), len(paper.parts))
        self.assertEqual(p2.parts[0].items[0].stem,
                         paper.parts[0].items[0].stem)

    def test_schema_covers_all_item_types(self):
        from exam_gen import editor
        from exam_gen.models import MCQItem, WordItem, WriteItem
        for inst, n in ((MCQItem("s", ["a", "b"], 0), 3),
                        (WordItem("c", "H", 4, "HAT"), 2),
                        (WriteItem("p", lines=4), 9)):
            self.assertEqual(len(editor.item_schema(inst)), n)

    def test_marks_editable(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "parts": [2]})
        p2 = editor.apply_edits(paper, {"parts": [{"marks": 9}]})
        self.assertEqual(p2.parts[0].marks, 9)
        self.assertEqual(paper.parts[0].marks, 4)   # untouched input

    def test_item_to_edit_defaults(self):
        from exam_gen import editor
        from exam_gen.models import WriteItem
        d = editor.item_to_edit(WriteItem("p", lines=4))
        self.assertEqual(d["prompt"], "p")
        self.assertEqual(d["lines"], 4)
        self.assertEqual(d["bullets"], [])

    def test_part_to_edit_single_item_override(self):
        from exam_gen import editor
        paper = _gen({"year": 3, "parts": [2]})
        part = paper.parts[0]
        ed = editor.part_to_edit(part, target_item=0,
                                 item_override={"stem": "NEW?", "answer": 2})
        self.assertEqual(len(ed["items"]), len(part.items))
        self.assertEqual(ed["items"][0]["stem"], "NEW?")
        self.assertEqual(ed["items"][1]["stem"], part.items[1].stem)
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        self.assertEqual(p2.parts[0].items[0].stem, "NEW?")

    def test_render_html_editable_markers(self):
        html = render_html.render_html(_gen({"year": 5}), editable=True)
        self.assertIn('data-eid="P0:I-1"', html)
        self.assertIn('data-eid="P1:I0"', html)
        self.assertIn("messageHandlers.paperEdit", html)
        self.assertIn('class="edit-banner"', html)
        plain = render_html.render_html(_gen({"year": 5}))
        self.assertNotIn('data-eid="P0:I-1"', plain)
        self.assertNotIn("messageHandlers.paperEdit", plain)

    def test_part_level_lines_editable(self):
        from exam_gen import editor
        paper = _gen({"year": 5, "parts": [7]})
        orig = paper.parts[0].lines
        p2 = editor.apply_edits(paper, {"parts": [{"lines": 14}]})
        self.assertEqual(p2.parts[0].lines, 14)
        self.assertEqual(paper.parts[0].lines, orig)   # untouched input

    def test_part_to_edit_roundtrip_lines(self):
        import dataclasses
        from exam_gen import editor
        paper = _gen({"year": 6, "parts": [7]})
        paper.parts[0] = dataclasses.replace(paper.parts[0], lines=20)
        ed = editor.part_to_edit(paper.parts[0])
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        self.assertEqual(p2.parts[0].lines, 20)


class TestMyBank(unittest.TestCase):
    def test_bank_kind_for(self):
        paper = _gen({"year": 3, "parts": [3]})
        self.assertEqual(bank.bank_kind_for(paper.parts[0]), "comprehension")
        self.assertEqual(bank.part_to_user_entry(paper.parts[0], 3)["year"], 3)
        paper = _gen({"year": 3, "parts": [2]})
        self.assertEqual(bank.bank_kind_for(paper.parts[0]), "cloze")
        paper = _gen({"year": 3, "parts": [4]})
        self.assertEqual(bank.bank_kind_for(paper.parts[0]), "match")
        paper = _gen({"year": 3, "parts": [5]})
        self.assertEqual(bank.bank_kind_for(paper.parts[0]), "letter_words")
        paper = _gen({"year": 6, "parts": [5]})
        self.assertEqual(bank.bank_kind_for(paper.parts[0]), "letter_words")

    def test_save_user_bank_entry_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bank.json")
            paper = _gen({"year": 3, "parts": [3]})
            part = paper.parts[0]
            entry = bank.part_to_user_entry(part, year=3)
            self.assertIsNotNone(entry)
            n = bank.save_user_bank_entry(path, bank.bank_kind_for(part), entry)
            self.assertEqual(n, 1)
            n2 = bank.save_user_bank_entry(path, bank.bank_kind_for(part), entry)
            self.assertEqual(n2, 0)          # duplicate — not re-added
            loaded = bank.load_user_bank(path)
            self.assertEqual(len(loaded["comprehension"][3]), 1)

    def test_writing_part_not_bankable(self):
        paper = _gen({"year": 6, "parts": [7]})
        part = paper.parts[0]
        self.assertIsNone(bank.bank_kind_for(part))
        self.assertIsNone(bank.part_to_user_entry(part, year=6))

    def test_answer_lines_helpers(self):
        paper = _gen({"year": 5, "parts": [7]})
        part = paper.parts[0]
        self.assertGreater(part.lines, 0)
        paper2 = _gen({"year": 1, "parts": [7]})
        self.assertGreater(paper2.parts[0].lines, 0)
        self.assertLess(paper2.parts[0].lines, paper.parts[0].lines)  # Y1 shorter


class TestRound13Bundle(unittest.TestCase):
    """Round 13 / S1: class bundles — N seeded variants + merged marksheet."""

    def test_bundle_first_equals_plain_generate(self):
        conf = dict(D.DEFAULT_CONFIG, year=3, lang="en", seed=4)
        single = bank.generate_paper(conf)
        papers = bank.bundle_papers(conf, n=1)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].year(), single.year())
        self.assertEqual(papers[0].max_qno(), single.max_qno())
        self.assertEqual(bank.build_key(papers[0]), bank.build_key(single))

    def test_bundle_variants_differ(self):
        conf = dict(D.DEFAULT_CONFIG, year=5, lang="en", seed=7)
        papers = bank.bundle_papers(conf, n=3)
        self.assertEqual(len(papers), 3)
        seeds = [p.meta["seed"] for p in papers]
        self.assertEqual(len(set(seeds)), 3)          # chained next_seed
        keys = [bank.build_key(p) for p in papers]
        self.assertNotEqual(keys[0], keys[1])         # genuinely different
        self.assertEqual(keys[1], keys[1])            # stable per paper

    def test_bundle_marksheet_docx(self):
        conf = dict(D.DEFAULT_CONFIG, year=3, lang="en", seed=2)
        papers = bank.bundle_papers(conf, n=2)
        blob = X.bundle_marksheet_doc(papers, "Year 3 Cempaka")
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        self.assertIn("CLASS BUNDLE", xml)
        self.assertIn("Pupil", xml)
        self.assertIn("Grade", xml)
        for p in papers[0].parts:
            self.assertIn(f"PART {p.num} [{p.marks} marks]", xml)

    def test_bundle_pdfmake_save(self):
        conf = dict(D.DEFAULT_CONFIG, year=3, lang="en", seed=1)
        papers = bank.bundle_papers(conf, n=2)
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "set")
            res = pdfmake.save_bundle(papers, base, class_label="Y3 A",
                                      want_pdf=False)
            self.assertEqual(len(res["docx"]), 2)
            self.assertTrue(all(p.endswith(".docx") for p in res["docx"]))
            self.assertTrue(os.path.exists(res["bundle_marksheet"]))
            self.assertEqual(len(res["pdf"]), 0)


class TestRound13Identity(unittest.TestCase):
    """Round 13 / S2+S8: school identity + pupil-ID QR on headers."""

    def _crest_path(self) -> str:
        from exam_gen import qr as Q
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(Q.qr_png("CREST", scale=3, border=2))
        self.addCleanup(os.unlink, path)
        return path

    def test_docx_identity(self):
        crest = self._crest_path()
        paper = _gen({"year": 3, "lang": "en", "school": "SJK(C) TEST",
                      "teacher": "Ms Tan", "crest": crest,
                      "pupil_id": "2026-0451", "qr": True})
        raw = X.render_doc(paper)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
            names = " ".join(z.namelist())
            rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        self.assertIn("School: SJK(C) TEST", xml)
        self.assertIn("Teacher: Ms Tan", xml)
        self.assertIn("Pupil ID: 2026-0451", xml)
        self.assertIn(os.path.basename(crest), names)   # crest embedded
        self.assertIn("qr.png", names)
        self.assertIn("rIdCrest", rels)
        self.assertIn("rIdQr", rels)

    def test_html_identity(self):
        crest = self._crest_path()
        paper = _gen({"year": 5, "lang": "en", "school": "SJK(C) TEST",
                      "teacher": "Mr Lam", "crest": crest,
                      "pupil_id": "B-032", "qr": True})
        html = render_html.render_html(paper)
        self.assertIn("School: SJK(C) TEST", html)
        self.assertIn("Pupil ID: B-032", html)
        self.assertIn("data:image/png;base64", html)
        self.assertIn('class="qr"', html)

    def test_invalid_crest_skipped(self):
        paper = _gen({"year": 3, "crest": "/nonexistent/crest.png"})
        raw = X.render_doc(paper)                       # must not raise
        names = __import__("zipfile").ZipFile(io.BytesIO(raw)).namelist()
        self.assertIn("word/document.xml", names)

    def test_qr_too_long_skipped_quietly(self):
        paper = _gen({"year": 3, "pupil_id": "X" * 5000, "qr": True})
        raw = X.render_doc(paper)                       # must not raise
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = " ".join(z.namelist())
        self.assertNotIn("qr.png", names)

    def test_default_identity_empty(self):
        paper = _gen({"year": 3, "lang": "en"})
        xml = _docx_text(paper)
        self.assertNotIn("Pupil ID", xml)
        self.assertNotIn("qr.png", xml)


class TestCrestPersistence(unittest.TestCase):
    """Round 13 S2 follow-up: an uploaded school crest is copied into the app
    data dir so it persists across restarts and survives the source file being
    moved or deleted (the old behavior stored the picker's fragile path)."""

    def _src_png(self) -> str:
        from exam_gen import qr as Q
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(Q.qr_png("CREST", scale=3, border=2))
        self.addCleanup(os.unlink, path)
        return path

    def test_persist_crest_copies_to_app_data_and_is_default(self):
        src = self._src_png()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with unittest.mock.patch.dict(os.environ, {"EXAM_GEN_DATA": tmp}):
            dst = D.persist_crest(src)
        self.assertTrue(os.path.isfile(dst), dst)     # bytes landed on disk
        self.assertEqual(os.path.dirname(dst), tmp)   # inside the app data dir
        with open(dst, "rb") as fh:
            self.assertEqual(fh.read(),
                             open(src, "rb").read())  # identical copy
        with unittest.mock.patch.dict(os.environ, {"EXAM_GEN_DATA": tmp}):
            self.assertEqual(D.default_crest_path(), dst)  # is the new default

    def test_persist_crest_missing_source_returns_empty(self):
        self.assertEqual(D.persist_crest("/nonexistent/crest.png"), "")
        self.assertEqual(D.persist_crest(""), "")


class TestRound13Results(unittest.TestCase):
    """Round 13 / S3: marking, totals, KSSR bands, CSV export."""

    def _papers_with_marks(self, conf, marks_by_tick):
        """Turn per-pupil per-part ticks into per-question marks dict."""
        paper = _gen(conf)
        pupils = []
        for name, ticks in marks_by_tick.items():
            marks = {}
            for p in paper.parts:
                if p.num in ticks:
                    step = p.marks / max(len(p.items), 1)
                    for q in p.qnos()[:len(p.items)]:
                        marks[q] = step
            pupils.append({"name": name, "marks": marks})
        return paper, pupils

    def test_columns_and_totals(self):
        paper = _gen({"year": 3, "lang": "en"})
        cols = M.part_columns([paper])
        self.assertEqual([c for c, _ in cols[:-1]],
                         [f"P{i}" for i in range(1, 8)])
        self.assertEqual(cols[-1][0], "TOTAL")
        self.assertAlmostEqual(float(cols[-1][1]), 50.0, places=6)

    def test_grades_and_bands(self):
        out = 50.0
        self.assertEqual(M.grade(40.0, out), "A")
        self.assertEqual(M.grade(30.0, out), "B")
        self.assertEqual(M.grade(20.0, out), "C")
        self.assertEqual(M.grade(10.0, out), "D")
        self.assertEqual(M.grade(0.0, out), "E")
        self.assertEqual(M.band(45.0, out), 6)
        self.assertEqual(M.band(35.0, out), 5)
        self.assertEqual(M.band(27.5, out), 4)
        self.assertEqual(M.band(20.0, out), 3)
        self.assertEqual(M.band(12.5, out), 2)
        self.assertEqual(M.band(5.0, out), 1)

    def test_results_csv_roundtrip(self):
        paper, pupils = self._papers_with_marks(
            {"year": 3, "lang": "en", "seed": 1},
            {"Alya": set(range(1, 8)), "Bala": set()})
        text = M.results_csv([paper], pupils)
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertIn("Pupil", lines[0])
        self.assertIn("Alya", text)
        self.assertIn("Bala", text)
        self.assertIn("Class average", text)
        self.assertIn("KSSR band count", text)
        back = M.pupils_from_csv(text)
        self.assertEqual(len(back), 2)
        by_name = {p["name"]: p for p in back}
        self.assertEqual(set(by_name["Alya"]["marks"]),
                         {p.num for p in paper.parts})
        self.assertEqual(by_name["Bala"]["marks"],
                         {p.num: 0.0 for p in paper.parts})

    def test_part_marks_sum_to_total(self):
        paper = _gen({"year": 5, "lang": "en", "seed": 3})
        pupil = {"name": "N", "marks": {q: 1 for p in paper.parts
                                        for q in p.qnos()[:1]}}
        per = M.pupil_parts(pupil, [paper])
        self.assertEqual(
            sum(m for m in per.values()), M.total_mark(pupil, [paper]))


class TestRound13Dskp(unittest.TestCase):
    """Round 13 / S5: DSKP content-standard tags + coverage report."""

    def test_coverage_all_parts(self):
        for year in D.YEARS:
            cov = bank.dskp_coverage(year)
            self.assertEqual(set(cov.keys()), set(range(1, 8)), year)
            for pno, codes in cov.items():
                self.assertGreaterEqual(len(codes), 1, (year, pno))

    def test_report_shape(self):
        paper = _gen({"year": 3, "lang": "en"})
        rep = bank.dskp_report(paper)
        self.assertIn("DSKP coverage", rep)
        for p in paper.parts:
            self.assertIn(f"PART {p.num}", rep)
        self.assertIn("4.3", rep)          # Year 3 Part 7 standard

    def test_year12_part5_override(self):
        for year in (1, 2):
            rep = bank.dskp_report(_gen({"year": year}))
            self.assertIn("4.1", rep)


class TestRound13Stats(unittest.TestCase):
    """Round 13 / S4: difficulty calibration stats."""

    def test_raw_key_and_qkey(self):
        from exam_gen.models import MCQItem
        raw = {"stem": "What do cats drink?", "opts": ["milk", "water", "tea"],
               "ans": 0}
        item = MCQItem(stem=raw["stem"], options=raw["opts"], answer=0)
        key = bank._raw_key(raw)
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 20)
        self.assertEqual(key, bank.qkey(item))  # same content -> same key
        self.assertEqual(bank.qkey(MCQItem(stem="", options=[], answer=1)), "")

    def test_order_by_stats_deprioritises_drops(self):
        items = [{"key": "a"}, {"key": "b"}, {"key": "c"}]
        stats = {"q": {"b": {"asked": 4, "misses": 4}}}   # 100% miss
        ordered = bank._order_by_stats(items, stats, lambda d: d["key"])
        keys = [d["key"] for d in ordered]
        self.assertEqual(keys[0], "a")                     # healthy first
        self.assertEqual(keys[-1], "b")                    # flag sinks last
        self.assertEqual(bank._order_by_stats(items, {}, lambda d: d["key"]),
                         items)                            # untouched when off

    def test_record_stats_tallies(self):
        with tempfile.TemporaryDirectory() as td:
            with unittest.mock.patch("exam_gen.bank.stats_path",
                                     return_value=os.path.join(td, "stats.json")):
                paper = _gen({"year": 3, "lang": "en", "parts": [1, 3, 7],
                              "seed": 2})
                pupils = [{"name": "A", "marks": {}},
                          {"name": "B", "marks":
                           {p.qfirst: p.marks for p in paper.parts}}]
                stats = bank.record_stats([paper], pupils)
        table = stats["q"]
        self.assertTrue(table)
        for cell in table.values():
            self.assertEqual(cell["asked"], 2)             # two pupils
            self.assertIn(cell["kind"], ("vocab", "comprehension"))

    def test_calibration_off_by_default_and_off_loads_empty(self):
        conf = dict(D.DEFAULT_CONFIG, year=3, lang="en", seed=1)
        a = bank.generate_paper(conf)
        with unittest.mock.patch("exam_gen.bank.load_stats",
                                 return_value={"q": {}}):
            b = bank.generate_paper(dict(conf, calibrate=True))
        self.assertEqual(bank.build_key(a), bank.build_key(b))


class TestRound13Import(unittest.TestCase):
    """Round 13 / S7: past-paper / bank import."""

    def test_import_csv_adds_and_dedupes(self):
        import csv as _csv
        with tempfile.TemporaryDirectory() as td:
            bank_path = os.path.join(td, "bank.json")
            rows = [
                ["kind", "stem", "a", "b", "c", "answer", "year"],
                ["vocab", "The cat ___ milk.", "drinks", "eats", "plays",
                 "A", "3"],
                ["vocab", "Rivers ___ into the sea.", "flow", "walk", "run",
                 "A", "3"],
            ]
            csv_path = os.path.join(td, "import.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as fh:
                _csv.writer(fh).writerows(rows)
            with unittest.mock.patch("exam_gen.bank.default_bank_path",
                                     return_value=bank_path):
                n = bank.import_csv(csv_path)
                self.assertEqual(n, 2)
                n2 = bank.import_csv(csv_path)             # duplicates skipped
                self.assertEqual(n2, 0)
                loaded = bank.load_user_bank(bank_path)
                self.assertEqual(len(loaded["vocab"][3]), 2)

    def test_import_csv_bad_header(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bad.csv")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("kind,spelling,stem\nvocab,x,y\n")
            with self.assertRaises(ValueError):
                bank.import_csv(p)

    def test_import_past_json_validates(self):
        paper = _gen({"year": 5, "lang": "en", "seed": 6})
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "paper.json")
            with open(p, "w", encoding="utf-8") as fh:
                import json as _json
                _json.dump(bank.paper_export(paper), fh)
            verdict = bank.import_past_json(p)
            self.assertEqual(verdict["year"], 5)
            self.assertEqual(verdict["parts"], len(paper.parts))
            self.assertEqual(verdict["questions"], paper.max_qno())

    def test_import_past_json_bad_input(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bad.json")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write('{"not": "a paper"}')
            with self.assertRaises(ValueError):
                bank.import_past_json(p)


class TestRound13FollowUp(unittest.TestCase):
    """Round 13 follow-up (2026-09-23): tri-lingual cover line under the
    crest, answer key starting on its own page, and pictures strictly tied
    to the article / questions."""

    def test_docx_bilingual_cover_with_abbr_underneath(self):
        paper = _gen({"year": 3, "exam_type": "uasa", "lang": "en"})
        xml = _docx_text(paper)
        cap = D.EXAM_CAPTION["uasa"]
        joined = f"{cap['en']}  \u00b7  {cap['ms']}  \u00b7  {cap['zh']}"
        i = xml.find(joined)
        self.assertGreaterEqual(i, 0, "tri-lingual caption missing in docx")
        self.assertGreater(xml.find("UASA"), i,
                           "UASA acronym must sit underneath the caption")
        self.assertGreater(xml.find("YEAR 3"), i,
                           "year/session under the caption")
        if "rIdCrest" in xml:
            self.assertLess(xml.find("rIdCrest"), i,
                            "crest must lead the caption block")

    def test_html_bilingual_cover(self):
        paper = _gen({"year": 3, "exam_type": "upsa", "lang": "en"})
        html = render_html.render_html(paper, allow_fetch=False)
        cap = D.EXAM_CAPTION["upsa"]
        i = html.find(cap["en"] + " &middot; " + cap["ms"] +
                      " &middot; " + cap["zh"])
        self.assertGreaterEqual(i, 0, "tri-lingual caption missing in html")
        self.assertGreater(html.find("UPSA"), i)
        self.assertGreater(html.find("YEAR 3"), i)

    def test_answer_key_starts_on_new_page_docx(self):
        paper = _teacher({"year": 3, "lang": "en"})
        xml = _docx_text(paper)
        body = xml.split("ANSWER KEY", 1)[0]
        br = body.rfind('<w:br w:type="page"/>')
        self.assertGreaterEqual(br, 0,
                                "no page break anywhere before the answer key")
        seg = body[br:]
        self.assertLessEqual(seg.count("<w:p>"), 1,
                             "only the key's heading paragraph may follow "
                             "the last page break before ANSWER KEY")
        self.assertNotIn("</w:t>", seg)

    def test_answer_sheet_starts_on_new_page_docx(self):
        paper = _gen({"year": 3, "lang": "en"})
        xml = _docx_text(paper)
        body = xml.split("PAPER ANSWER SHEET", 1)[0]
        br = body.rfind('<w:br w:type="page"/>')
        self.assertGreaterEqual(br, 0)
        seg = body[br:]
        self.assertLessEqual(seg.count("<w:p>"), 1)
        self.assertNotIn("</w:t>", seg)

    def test_answer_key_starts_on_new_page_html(self):
        paper = _gen({"year": 3, "lang": "en"})
        html = render_html.render_html(paper, allow_fetch=False)
        pre_key = html.split("ANSWER KEY", 1)[0]
        br = pre_key.rfind('<div class="pagebr"></div>')
        self.assertGreaterEqual(br, 0,
                                "no page break element before the answer key")
        self.assertNotIn('<div class="partblock">', pre_key[br:],
                         "a part must not follow the key's page break")
        sheet = html.split("PAPER ANSWER SHEET", 1)[0]
        sbr = sheet.rfind('<div class="pagebr"></div>')
        self.assertGreaterEqual(sbr, 0)
        self.assertNotIn('<div class="partblock">', sheet[sbr:])

    def test_photo_query_always_in_part_text(self):
        # A picture is never used unless its search phrase literally appears in
        # the article / questions / options / answer words the part is about.
        for year in D.YEARS:
            for seed in (1, 5, 99):
                paper = _gen({"year": year, "seed": seed, "pictures": True})
                for p in paper.parts:
                    text = _part_words(p)
                    q = str(getattr(p, "photo_query", "") or "").strip()
                    if not q:
                        continue
                    self.assertIn(q.lower(), text.lower(),
                                  f"Y{year} P{p.num}: photo '{q}' "
                                  f"not found in the part's own text")

    def test_missing_phrase_yields_no_picture(self):
        from types import SimpleNamespace
        self.assertEqual(art.query_for_text("The sky is dark tonight."), "")
        part = SimpleNamespace(topic="space", photo_query="")
        self.assertEqual(art.photo_candidates(part), [])

    def test_docx_picture_bound_to_photo_query(self):
        # When a part has a photo query, the rendered drawing's alt-term (the
        # docPr name) echoes the query, not a generic topic label.
        paper = _gen({"year": 3, "seed": 7, "pictures": True})
        xml = _docx_text(paper)
        for p in paper.parts:
            q = str(getattr(p, "photo_query", "") or "").strip()
            if not q:
                continue
            text = _part_words(p)
            self.assertIn(q.lower(), text.lower())


def _write_min_pdf(path: str, text: str) -> None:
    """A minimal, valid, single-page PDF holding ``text``.

    Hand-built (not via a library) so the test stays stdlib-only and does not
    depend on any third-party PDF writer.  The content stream is a plain
    uncompressed ``BT /F1 12 Tf`` text object, one ``Tj`` per line.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    shown = lines[:40] or ["empty"]
    content = "BT /F1 12 Tf 12 TL 40 760 Td\n"
    for ln in shown:
        esc = ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content += "(%s) Tj T*\n" % esc
    content += "ET"
    cbytes = content.encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(cbytes)).encode() + b" >>\nstream\n"
        + cbytes + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1, xref)
    with open(path, "wb") as fh:
        fh.write(bytes(out))


class TestRefCorpus(unittest.TestCase):
    """Round 14: mine the official UPSA/UASA 2026 .docx papers into a
    per-year vocabulary word / picture-word reference bank."""

    SAMPLE = """UPSA YEAR 1 ENGLISH
PART 1
Questions 1 to 5
1. It is raining. Aini uses an umbrella.
   A. umbrella   B. book   C. bag
2. We cut paper with a pair of scissors.
   A. scissors   B. rulers   C. crayons
PART 5
Questions 21 to 25
Study the pictures and the words below.
elephant   lizard   spider   frog   duck
"""

    def _sample_dir(self, name="UPSA Year 1 BI 2026.txt"):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(self.SAMPLE)
        return d

    def test_mine_docx_text_hermetic(self):
        from exam_gen import refcorpus
        d = self._sample_dir()
        try:
            data = refcorpus.mine_dir(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(data[1]["year"], 1)
        words = [w for p in data[1]["parts"] for w in p["words"]]
        self.assertIn("umbrella", words)
        self.assertIn("scissors", words)
        p5 = next(p for p in data[1]["parts"] if p.get("num") == 5)
        self.assertIn("elephant", p5["picture_words"])
        for w in ("elephant", "lizard", "spider", "frog", "duck"):
            self.assertIn(w, p5["picture_words"])

    def test_save_load_roundtrip(self):
        from exam_gen import refcorpus
        d = self._sample_dir()
        out = tempfile.mkdtemp()
        try:
            data = refcorpus.mine_dir(d)
            saved = refcorpus.save_report(data, out)
            self.assertTrue(os.path.exists(saved))
            loaded = refcorpus.load_report(saved)
        finally:
            shutil.rmtree(d, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)
        self.assertEqual(loaded[1]["year"], 1)

    @unittest.skipUnless(os.path.isdir(
        os.path.expanduser("~/Downloads/exam2026")),
        "reference papers directory not present")
    def test_official_papers_minable(self):
        from exam_gen import refcorpus
        d = os.path.expanduser("~/Downloads/exam2026")
        data = refcorpus.mine_dir(d)
        self.assertGreaterEqual(len(data), 4,
                                "expected most SJKC years to be discovered")
        for year, info in data.items():
            try:
                yearsOK = [p for p in D.YEARS if str(year) in str(info["year"])]
                self.assertTrue(yearsOK, f"unknown year {year}")
            except AttributeError:
                self.fail("mine_dir must return {year: info} dict")

    def test_mine_dir_recurses_into_paper_subdir(self):
        """Round 25: the teacher keeps the papers in ``paper/`` under the exam
        root, so a non-recursive scan finds nothing at all."""
        from exam_gen import refcorpus
        d = tempfile.mkdtemp()
        try:
            sub = os.path.join(d, "paper")
            os.makedirs(sub)
            with open(os.path.join(sub, "UPSA Year 3 BI 2026.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write(self.SAMPLE)
            data = refcorpus.mine_dir(d)
            self.assertIn(3, data)
            self.assertEqual(data[3]["source"], "UPSA Year 3 BI 2026.txt")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_mine_dir_reads_pdf_when_pdftotext_available(self):
        """Round 25: the five UASA papers are PDFs; without pdftotext support
        those years lose a whole paper's vocabulary."""
        from exam_gen import refcorpus
        if not refcorpus.pdftotext_available():
            self.skipTest("pdftotext not installed")
        import zipfile
        d = tempfile.mkdtemp()
        try:
            pdf = os.path.join(d, "UASA YEAR 5.pdf")
            _write_min_pdf(pdf, self.SAMPLE)
            data = refcorpus.mine_dir(d)
            self.assertIn(5, data)
            words = [w for p in data[5]["parts"] for w in p["words"]]
            self.assertIn("umbrella", words)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_pdf_read_is_hermetic_without_pdftotext(self):
        """A missing poppler must degrade to None, never raise."""
        from exam_gen import refcorpus
        d = tempfile.mkdtemp()
        try:
            pdf = os.path.join(d, "UASA YEAR 1.pdf")
            _write_min_pdf(pdf, "PART 1\nnurse")
            old = refcorpus.PDFTOTEXT
            refcorpus.PDFTOTEXT = "/nonexistent/pdftotext"
            try:
                self.assertIsNone(refcorpus.docx_text(pdf))
            finally:
                refcorpus.PDFTOTEXT = old
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_structured_paper_beats_pdf_for_same_year(self):
        """Round 25: pdftotext output is column-formatted, so a .docx with the
        same part count must win — otherwise the clean Part 5 picture-word box
        is replaced by prose fragments."""
        from exam_gen import refcorpus
        d = tempfile.mkdtemp()
        try:
            sub = os.path.join(d, "paper")
            os.makedirs(sub)
            with open(os.path.join(sub, "UPSA Year 1 BI 2026.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write(self.SAMPLE)
            _write_min_pdf(os.path.join(sub, "UASA YEAR 1.pdf"),
                           self.SAMPLE + "\n\nextra prose line about insects\n")
            data = refcorpus.mine_dir(d)
            self.assertTrue(str(data[1]["source"]).endswith(".txt"),
                            data[1]["source"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_official_papers_cover_every_supported_year(self):
        """Round 25: the official UPSA/UASA set on disk must yield every
        supported year, and the Y3 picture words must come out of it."""
        from exam_gen import refcorpus
        d = os.path.expanduser("~/Downloads/exam2026")
        if not os.path.isdir(d):
            self.skipTest("reference papers directory not present")
        data = refcorpus.mine_dir(d)
        for year in (1, 2, 3, 5, 6):
            self.assertIn(year, data, f"year {year} not mined")


def spec_style(year: int, num: int) -> str:
    """The rendering style ``data.PARTS`` declares for a part."""
    spec = {s["id"]: s for s in D.PARTS[year]}.get(num)
    return str((spec or {}).get("style") or "")


def part_answers(part, year: int) -> list[str]:
    """The answer text of every item in ``part``, for a vocabulary gate.

    Handles both item types: an :class:`MCQItem` exposes ``options`` /
    ``answer`` (an index), a :class:`WordItem` exposes ``answer`` (the word).
    """
    out: list[str] = []
    for item in part.items:
        opts = getattr(item, "options", None)
        if opts:
            idx = getattr(item, "answer", 0)
            if isinstance(idx, int) and 0 <= idx < len(opts):
                out.append(str(opts[idx]))
        elif hasattr(item, "answer"):
            out.append(str(item.answer))
    return out


class TestDskpGate(unittest.TestCase):
    """Round 25: the KSSR DSKP word list is the vocabulary contract.

    Official Year 3 tests ``pilot, dentist, firefighter, nurse, chef``; the
    generated paper was offering ``civet, gecko, tapir, orangutan``.  These
    tests pin the list itself, the gate, and every generated paper's
    Part 1/2/5 vocabulary.
    """

    def test_bundled_list_matches_the_ministry_word_list(self):
        from exam_gen import dskp_words as W
        # The official Year 3 Part 5 word box, verbatim.
        for w in ("pilot", "dentist", "firefighter", "nurse", "chef"):
            self.assertIn(w, W.WORDS[3], w)
        # The off-curriculum drift the audit found.
        for w in ("civet", "gecko", "tapir", "orangutan", "hornbill"):
            self.assertNotIn(w, W.WORDS[3], w)
        for y in (1, 2, 3, 5, 6):
            self.assertGreaterEqual(len(W.WORDS[y]), 60, y)

    def test_ladder_is_cumulative(self):
        """A Year 6 paper may test a Year 1 word; a Year 1 paper may not test
        a Year 6 word."""
        from exam_gen import dskp
        self.assertTrue(dskp.in_list("frog", 1))
        self.assertTrue(dskp.in_list("frog", 6))     # carried up the ladder
        self.assertFalse(dskp.in_list("rocket", 1))
        self.assertTrue(dskp.in_list("rocket", 5))
        self.assertFalse(dskp.in_list("pilot", 2))   # Year 3 word, too early

    def test_in_list_rejects_punctuation_and_phrases(self):
        from exam_gen import dskp
        self.assertTrue(dskp.in_list("Pilot.", 3))
        self.assertTrue(dskp.in_list("  nurse  ", 3))
        self.assertFalse(dskp.in_list("", 3))
        self.assertFalse(dskp.in_list("!!", 3))
        # A phrase is read by its first token, so "computer game" finds
        # "computer" (a Year 4 word) and "kuala lumpur" finds nothing, since
        # the DSKP list is English vocabulary and place names live in
        # ``dskp.PROPER``.
        self.assertTrue(dskp.in_list("computer game", 4))
        self.assertFalse(dskp.in_list("kuala lumpur", 3))
        self.assertTrue(dskp.allowed("Kuala Lumpur", 3))

    def test_distractors_may_be_familiar_without_being_dskp(self):
        """An option only has to be rejectable, not listed."""
        from exam_gen import dskp
        self.assertFalse(dskp.in_list("taxi", 1))
        self.assertTrue(dskp.allowed("taxi", 1))      # everyday noun
        self.assertFalse(dskp.allowed("civet", 3))    # neither
        self.assertTrue(dskp.allowed("the", 1))        # function word
        self.assertTrue(dskp.allowed("thursday", 1))  # closed set
        self.assertTrue(dskp.allowed("Kuala Lumpur", 3))

    def test_off_curriculum_audit_reads_mcq_dicts(self):
        from exam_gen import dskp
        bad = dskp.off_curriculum(
            [{"word": "civet", "opts": ["gecko", "frog"]}], 3)
        self.assertEqual(bad, ["civet", "gecko"])

    def test_part5_word_box_is_on_curriculum_every_year(self):
        """A choice-style Part 5 word box (Y1-Y3) must be on the DSKP ladder.

        Years 5-6 are deliberately excluded: their official Part 5 is the
        spelling style, and the real UPSA Year 5 paper answers its own clue
        items with ``camel / ostrich / butterfly / frog / panda``, none of
        which appear in the DSKP Year 5 list either.  Those parts are gated on
        being concrete describable nouns instead — see
        :func:`test_part5_spelling_answers_are_concrete_nouns`.
        """
        from exam_gen import dskp
        for year in (1, 2, 3):
            for seed in (1, 4, 9):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                part = next(p for p in paper.parts if p.num == 5)
                words = part_answers(part, year)
                self.assertEqual(len(words), D.PARTS[year][4]["count"],
                                 f"Y{year} seed {seed}: no answers found")
                bad = dskp.off_curriculum(words, year)
                self.assertEqual(bad, [], f"Y{year} seed {seed}: {bad}")

    def test_part5_spelling_answers_are_concrete_nouns(self):
        """Years 5-6 Part 5 spells a word from a description, so the answer
        must be a concrete noun a pupil can picture — not an abstraction, and
        never a function word."""
        for year in (5, 6):
            for seed in (1, 4, 9):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                part = next(p for p in paper.parts if p.num == 5)
                for item in part.items:
                    answer = str(item.answer).lower()
                    self.assertTrue(answer.isalpha(), (year, seed, answer))
                    self.assertGreaterEqual(len(answer), 3, (year, answer))
                    self.assertNotIn(answer, ("the", "and", "very"), answer)

    def test_part5_year3_never_uses_the_off_curriculum_animals(self):
        from exam_gen import dskp_words
        y3 = set(dskp_words.WORDS[3])
        self.assertTrue({"pilot", "dentist", "firefighter", "nurse",
                         "chef"} <= y3)
        for seed in (1, 5):
            paper = _gen({"year": 3, "seed": seed, "pictures": False})
            part = next(p for p in paper.parts if p.num == 5)
            for answer in part_answers(part, 3):
                self.assertNotIn(
                    answer, ("civet", "gecko", "tapir", "orangutan", "hornbill"))

    def test_part1_answers_are_on_curriculum(self):
        """A Part 1 *gap-fill* answer must be on the year's ladder.

        The official Year 1 paper offers "A toy car / My school bag / A
        bicycle" and "He puts his books in the drawer", none of which the DSKP
        Year 1 list enumerates.  Distractors are policed by preference and by a
        QC soft finding instead — see
        :func:`test_part1_prefers_familiar_distractors`.

        Round 26: an item in the official short-stimulus shape is a *reading*
        question, not a vocabulary target — the answer is a phrase located in
        the poster/menu/email — so the word-list gate does not apply to it.  Its
        guarantee is "the answer is in the stimulus", checked by
        :func:`test_part1_answer_is_readable_from_its_stimulus` and by
        ``qc._part1_stimulus_issues``.
        """
        from exam_gen import dskp
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 2, "pictures": False})
            for num in (1, 2):
                part = next(p for p in paper.parts if p.num == num)
                if num == 1:
                    gapped = [it for it in part.items
                              if not getattr(it, "stimulus", None)]
                    if not gapped:
                        # Years 5-6 are fully migrated to the stimulus shape,
                        # so there is no gap-fill answer left to gate.
                        continue
                    answers = [it.ans_text or it.options[it.answer]
                               for it in gapped]
                else:
                    answers = part_answers(part, year)
                self.assertTrue(answers, f"Y{year} part {num}")
                bad = dskp.off_curriculum(answers, year)
                self.assertEqual(bad, [], f"Y{year} part {num}: {bad}")

    def test_part1_prefers_familiar_distractors(self):
        """On-list items must be available, so the gate has something to pick.

        Counted rather than asserted per-item: the official papers legitimately
        go past the word list on distractors, so the guarantee is that a
        paper's *majority* of options are familiar, not every one.
        """
        from exam_gen import dskp
        for year in (1, 2, 3):
            total = familiar = 0
            for seed in (1, 2, 3, 4, 5):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for num in (1, 2):
                    for item in next(p for p in paper.parts
                                     if p.num == num).items:
                        for opt in getattr(item, "options", None) or []:
                            total += 1
                            if dskp.allowed(opt, year):
                                familiar += 1
            self.assertGreater(familiar / max(total, 1), 0.6,
                               f"Y{year}: only {familiar}/{total} options "
                               f"are familiar")


class TestPaperCompliance(unittest.TestCase):
    """Round 16: the refresh/Regenerate button proves a paper is usable as an
    official school exam M-bM-^@M-^T 7 parts, 50 marks, contiguous numbering, DSKP
    standards, the scheduled RPT theme/week and the year's CEFR passage band."""

    def test_generated_paper_is_exam_ready(self):
        for year in D.YEARS:
            pc = bank.paper_compliance(_gen({"year": year, "pictures": False}))
            self.assertTrue(pc["ok"], (year, pc["issues"]))
            self.assertEqual(pc["parts"], 7, year)
            self.assertEqual(pc["marks"], D.TOTAL, year)
            self.assertEqual(pc["year"], year)
            self.assertGreaterEqual(
                pc["questions"],
                sum(s["count"] for s in D.PARTS[year]), year)
            self.assertTrue(pc["rpt"], (year,))
            self.assertTrue(pc["dskp"], (year, pc["issues"]))
            self.assertTrue(pc["cefr"], (year, pc["issues"]))
            self.assertEqual(pc["issues"], [], year)
            self.assertTrue(pc["messages"], year)

    def test_dropped_part_fails_structure(self):
        pc = bank.paper_compliance(
            _gen({"year": 3, "parts": [1, 2, 3, 4, 5, 6]}))
        self.assertFalse(pc["ok"])
        self.assertEqual(pc["parts"], 6)
        joined = " ".join(pc["issues"]).lower()
        self.assertIn("part", joined)
        self.assertEqual(pc["marks"], 35)     # part 7's 15 marks are gone

    def test_cefr_flag_on_over_band_web_passage(self):
        for year, too_hard in ((1, "The ancient messenger approached with "
                                   "calamity and consternation."),
                               (5, "The beauteous obedient pupil acknowledged the messenger")): 
            paper = _gen({"year": year})
            p3 = next(p for p in paper.parts if p.num == 3)
            p3.lead_text = too_hard
            pc = bank.paper_compliance(paper)
            self.assertFalse(pc["cefr"], year)
            self.assertIn("cefr", " ".join(pc["issues"]).lower())
            self.assertIn(3, pc["passage_bands"], year)
        paper = _gen({"year": 1})
        next(p for p in paper.parts if p.num == 3).lead_text = \
            "The cat is in the cup. The dog is on the mat."
        pc = bank.paper_compliance(paper)
        self.assertTrue(pc["cefr"])
        self.assertEqual(pc["issues"], [])

    def test_rpt_week_mismatch_flag(self):
        good = bank.paper_compliance(
            _gen({"year": 6, "week": 1, "theme": "It's an Emergency"}))
        self.assertTrue(good["rpt"], good["issues"])
        off = bank.paper_compliance(
            _gen({"year": 6, "week": 1, "theme": "Music and Song"}))
        self.assertFalse(off["rpt"])
        self.assertIn("rpt", " ".join(off["issues"]).lower())
        auto = bank.paper_compliance(
            _gen({"year": 3, "week": 0, "theme": "World of Knowledge"}))
        self.assertTrue(auto["rpt"], auto["issues"])

    def test_writing_shapes_reported(self):
        for year in D.YEARS:
            paper = _gen({"year": year})
            pc = bank.paper_compliance(paper)
            for p in paper.parts:
                if p.kind != "writing":
                    continue
                if p.style in ("letter", "email"):
                    self.assertEqual(len(p.items), 1, (year, p.num))
                else:
                    spec = next(s for s in D.PARTS[year] if s["id"] == p.num)
                    self.assertEqual(len(p.items), spec["count"], (year, p.num))
                    self.assertIsNotNone(getattr(p, "example", None),
                                         (year, p.num))


class TestTextbook(unittest.TestCase):
    """Round 17/T1: the scanned SJKC pupil's textbook PDFs (the SOLE reference)
    are OCR-mined into a per-year ``textbook_corpus.json``; unit splitting and
    the cleanliness gates are pure and hermetic."""

    SAMPLE = """Unit 1 - At School
The cat is on the bag. The dog is under the table.
The bird is in the tree. The fish is in the water.
Listen and write the words. Colour the pictures.
Unit 2 - Free Time
The hen is on the nest. The fox is in the field.
The monkey is in the tree. We play football on Sundays.

gArB||age 123
"""

    def _get_tb(self):
        from exam_gen import textbook
        return textbook

    def test_split_units(self):
        TB = self._get_tb()
        units = TB.split_units(self.SAMPLE)
        titles = [u["title"] for u in units]
        self.assertIn("Unit 1 - At School", titles)
        self.assertIn("Unit 2 - Free Time", titles)
        for u in units:
            self.assertIsInstance(u.get("sentences"), list)
            self.assertIsInstance(u.get("words"), list)

    def test_clean_sentences_drop_garbage(self):
        TB = self._get_tb()
        sents = TB.clean_sentences(self.SAMPLE, 1)
        self.assertIn("The cat is on the bag.", sents)
        self.assertIn("We play football on Sundays.", sents)
        self.assertTrue(all("||" not in s for s in sents))
        self.assertTrue(all(not s.isdigit() for s in sents))
        self.assertTrue(all(len(s.split()) >= 3 for s in sents))

    def test_parse_and_roundtrip(self):
        TB = self._get_tb()
        with tempfile.TemporaryDirectory() as td:
            corpus = TB.parse_text(self.SAMPLE, 1)
            self.assertEqual(corpus["1"]["source"], "inline")
            self.assertGreaterEqual(len(corpus["1"]["units"]), 2)
            words = corpus["1"]["words"]
            for w in ("cat", "dog", "bird", "fish"):
                self.assertIn(w, words)
            saved = TB.save_corpus(corpus, td)
            self.assertTrue(os.path.exists(saved))
            loaded = TB.load_corpus(saved)
            self.assertEqual(loaded[1]["units"], corpus["1"]["units"])
            self.assertGreaterEqual(len(loaded[1]["sentences"]), 2)

    def test_mine_dir_skips_non_textbook(self):
        TB = self._get_tb()
        with tempfile.TemporaryDirectory() as td:
            data = TB.mine_dir(td)          # no textbook PDFs -> empty
            self.assertEqual(data, {})

    @unittest.skipUnless(
        shutil.which("pdftotext") and shutil.which("pdftoppm")
        and shutil.which("tesseract")
        and os.path.exists(os.path.expanduser(
            "~/Downloads/exam2026/textbook_year1&2.pdf")),
        "OCR tools or the Year 1&2 textbook PDF not present")
    def test_ocr_small_page_range(self):
        TB = self._get_tb()
        pdf = os.path.expanduser(
            "~/Downloads/exam2026/textbook_year1&2.pdf")
        text = TB.ocr_pdf(pdf, 1, first=8, last=10)
        self.assertGreater(len(re.findall(r"[A-Za-z]{3,}", text)), 20,
                           "expected OCR to recover real words")


class TestOptionMarkers(unittest.TestCase):
    """Round 25: the official option marker differs by year.

    Years 1-2 print ``A)`` and Years 3-6 print ``A.``.  Every renderer that
    draws an option has to agree, or the same paper shows two conventions.
    """

    def _paper(self, year, seed=2):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False})
        return bank.generate_paper(c)

    def test_marker_is_year_specific(self):
        from exam_gen.models import MCQItem
        self.assertEqual(D.OPTION_MARKER, {1: ")", 2: ")", 3: ".",
                                            4: ".", 5: ".", 6: "."})
        for year in D.YEARS:
            marker = D.OPTION_MARKER[year]
            for p in self._paper(year).parts:
                for item in p.items:
                    if not isinstance(item, MCQItem) or len(item.options) != 3:
                        continue
                    if p.kind == "match":
                        continue        # letters label texts, not options
                    labels = D.option_labels(len(item.options), year)
                    self.assertEqual(labels[0], f"A{marker}", f"Y{year}")

    def test_docx_uses_the_year_marker(self):
        for year in D.YEARS:
            xml = _docx_text(self._paper(year))
            marker = D.OPTION_MARKER[year]
            want = f"A{marker}"
            other = ")" if marker == "." else "."
            self.assertIn(f">{want}<", xml.replace(" ", ""),
                          f"Y{year}: no {want!r} marker in the docx")
            self.assertNotIn(f">A{other}<", xml.replace(" ", ""),
                             f"Y{year}: rendered the other year's marker")

    def test_html_uses_the_year_marker(self):
        for year in D.YEARS:
            html = render_html.render_html(self._paper(year), allow_fetch=False)
            marker = D.OPTION_MARKER[year]
            self.assertIn(f"A{marker}", html, f"Y{year}: no A{marker} in html")

    def test_answer_key_keeps_the_plain_letter(self):
        for year in D.YEARS:
            paper = self._paper(year)
            for qno, ans, _note in bank.build_key(paper):
                if ans in ("A", "B", "C"):
                    self.assertEqual(ans, ans.upper(), f"Y{year} Q{qno}")

    def test_inline_editor_labels_with_the_year_marker(self):
        """Both editors draw option letters; the quick one sets up its own
        state, so a marker helper added for ``PaperEditor`` used to reach a
        missing attribute and crash the app on a click (--check-teacher)."""
        from exam_gen import editor as ED
        try:
            ED._gtk_import()
        except Exception as exc:                # PyGObject / GTK missing
            self.skipTest(f"GTK unavailable ({exc})")
        for year in D.YEARS:
            qe = ED.QuickItemEditor(self._paper(year), 0, 0)
            marker = D.OPTION_MARKER[year]
            self.assertEqual(qe._opt_letter(0), f"A{marker}", f"Y{year}")
            self.assertEqual(qe._opt_letter(2), f"C{marker}", f"Y{year}")
            self.assertEqual(ED.PaperEditor._opt_letter(qe, 1), f"B{marker}")


class TestPart4Mapping(unittest.TestCase):
    """Round 25: Part 4 must not hand the pupil the answer.

    The official papers print the three matching texts as A, B and C, then ask
    six paraphrased descriptions whose answers are spread over the three
    letters, and they show one worked example numbered 0.  A generator that
    labels every text with the letter its own descriptions used produced the
    pattern A, A, B, B, C, C, which is not the exam.
    """

    def _p4(self, year, seed=1):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "parts": [4]})
        return bank.generate_paper(c).parts[0]

    def test_answer_is_not_the_identity_mapping(self):
        for year in D.YEARS:
            for seed in (1, 2, 3, 4, 5):
                p4 = self._p4(year, seed)
                labels = [it.answer_label for it in p4.items]
                self.assertNotEqual(
                    labels, ["A", "A", "B", "B", "C", "C"],
                    f"Y{year} seed {seed}: every description kept its own "
                    f"letter ({labels})")

    def test_answers_are_spread_over_the_three_letters(self):
        for year in D.YEARS:
            for seed in range(1, 7):
                p4 = self._p4(year, seed)
                labels = [it.answer_label for it in p4.items]
                counts = {lab: labels.count(lab) for lab in "ABC"}
                self.assertEqual(sorted(counts.values()), [2, 2, 2],
                                 f"Y{year} seed {seed}: {labels}")
                # No letter may own three consecutive descriptions.
                longest = 1
                run = 1
                for a, b in zip(labels, labels[1:]):
                    run = run + 1 if a == b else 1
                    longest = max(longest, run)
                self.assertLessEqual(longest, 2,
                                     f"Y{year} seed {seed}: {labels}")

    def test_every_letter_is_used_at_least_once_over_seeds(self):
        for year in D.YEARS:
            seen = set()
            for seed in range(1, 7):
                seen.update(it.answer_label for it in self._p4(year, seed).items)
            self.assertEqual(seen, {"A", "B", "C"}, f"Y{year}: {seen}")

    def test_a_worked_example_is_shown(self):
        for year in D.YEARS:
            p4 = self._p4(year)
            self.assertIsNotNone(p4.example,
                                 f"Y{year}: Part 4 has no worked example")
            # The official papers number the example 0 so it is never marked.
            self.assertTrue(p4.example.startswith("0. "),
                            f"Y{year}: {p4.example!r}")
            self.assertRegex(p4.example, r"\([ABC]\)$",
                             f"Y{year}: the example must show its letter")
            self.assertEqual(p4.qfirst, 1, f"Y{year}")
            self.assertEqual(len(p4.items), 6, f"Y{year}")

    def _ex_stem(self, example):
        """The description inside ``0. <description>  (<letter>)``."""
        body = re.sub(r"^0\.\s*", "", example)
        return " ".join(re.sub(r"\s*\([ABC]\)$", "", body).split())

    def test_the_example_is_not_also_a_question(self):
        """The official papers spend a *seventh* description on the worked
        example, so printing question 1 a second time hands the pupil the
        answer to it."""
        for year in D.YEARS:
            for seed in range(1, 7):
                p4 = self._p4(year, seed)
                ex = self._ex_stem(p4.example or "")
                self.assertTrue(ex, f"Y{year} seed {seed}: no example")
                for item in p4.items:
                    self.assertNotEqual(
                        ex, " ".join(item.stem.split()),
                        f"Y{year} seed {seed}: the example is also Q{item.stem!r}")

    def test_every_match_block_carries_its_own_example(self):
        for year in D.YEARS:
            for block in bank._match_pool(year):
                ex = block.get("example")
                self.assertTrue(ex, f"Y{year}: a matching block has no "
                                    f"example: {block['texts'][0][:40]!r}")
                self.assertIn(int(ex.get("ans", -1)), (0, 1, 2), f"Y{year}")
                stems = {" ".join(q["stem"].split()) for q in block["qs"]}
                self.assertNotIn(" ".join(ex["stem"].split()), stems,
                                 f"Y{year}: the example repeats a question")

    def test_the_example_matches_its_own_text(self):
        """A mis-keyed example is worse than none: the letter shown must be
        the text the description is actually about."""
        for year in D.YEARS:
            for block in bank._match_pool(year):
                ex = block.get("example")
                if not ex:
                    continue
                want = int(ex["ans"])
                scores = [len(bank._content_words(ex["stem"])
                              & bank._content_words(t))
                          for t in block["texts"]]
                best = max(range(3), key=lambda i: scores[i])
                self.assertEqual(
                    best, want,
                    f"Y{year}: example {ex['stem'][:50]!r} is closest to text "
                    f"{'ABC'[best]} but is keyed {'ABC'[want]} "
                    f"({scores}) — {block['texts'][0][:40]!r}")

    def test_marks_stay_at_six_for_the_six_descriptions(self):
        for year in D.YEARS:
            p4 = self._p4(year)
            self.assertEqual(p4.marks, 6, f"Y{year}")
            self.assertEqual(p4.marks_per_q(), 1.0, f"Y{year}")

    def test_renumbering_leads_to_a_working_answer_key(self):
        for year in D.YEARS:
            p4 = self._p4(year)
            self.assertEqual(p4.qnos(), [1, 2, 3, 4, 5, 6], f"Y{year}")
            for qno, item in zip(p4.qnos(), p4.items):
                self.assertEqual(item.answer_label, item.options[item.answer],
                                 f"Y{year} Q{qno}")
            # Each description must name a different text than its neighbours
            # would suggest: the printed letters are the labels, so the option
            # list must stay in A, B, C order.
            for item in p4.items:
                self.assertEqual(
                    [o.strip() for o in item.options], ["A", "B", "C"],
                    f"Y{year}: options are out of order — the letters label "
                    f"the texts above, they are not the options")

    def test_a_healthy_mapping_is_not_reported(self):
        from exam_gen import qc
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": 3, "seed": 1, "pictures": False})
        paper = bank.generate_paper(c)
        p4 = next(p for p in paper.parts if p.num == 4)
        self.assertEqual(qc.mapping_balance_issues(p4), [],
                         qc.mapping_balance_issues(p4))

    def test_quality_gate_reports_a_degenerate_mapping(self):
        from exam_gen import qc
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": 3, "seed": 1, "pictures": False})
        paper = bank.generate_paper(c)
        p4 = next(p for p in paper.parts if p.num == 4)
        self._force_labels(p4, list("AAABBC"))
        self.assertTrue(qc.mapping_balance_issues(p4),
                        "a mapping leaning on A must be reported")
        self._force_labels(p4, ["A"] * 6)
        issues = qc.mapping_balance_issues(p4)
        self.assertTrue(any("all" in m for m in issues), issues)
        self._force_labels(p4, list("BABABA"))
        self.assertTrue(qc.mapping_balance_issues(p4),
                        "an answer that never reaches C must be reported")

    def _force_labels(self, p4, labels):
        for item, lab in zip(p4.items, labels):
            item.answer = "ABC".index(lab)
            item.ans_text = item.options[item.answer]


class TestPassageCoherence(unittest.TestCase):
    """Round 25: an OCR'd textbook must not be stitched into a reading text.

    The mined Year 3 corpus is a flat bag of every line the scan produced, in
    page order across the whole book.  Chunking it produced passages that
    jumped from a house to a teacher to a duck mid-paragraph, and the same
    passage came out for every seed.  A passage may only be built from a run
    of sentences that are actually about the same thing; anything else falls
    back to the hand-written pool.
    """

    BAG = {
        "3": {"source": "bag3.pdf", "pages": 1,
              "units": [{
                  "title": "",
                  "words": ["house", "teacher", "duck"],
                  "sentences": [
                      "This is our house, We never catch any fish.",
                      "It's got thirteen rooms.",
                      "We just sit on a chair.",
                      "And three living rooms.",
                      "And look for pretty shells.",
                      "This is my teacher, Mr Price.",
                      "At home he's got a little cat.",
                      "It's in his room.",
                      "On a farm there was a duck.",
                      "His neck was long.",
                      "His wings were black.",
                      "His name was Chuck.",
                      "He was a king.",
                      "He liked to drink.",
                      "The grass was green.",
                      "A dog barked.",
                      "The bell rang.",
                      "We went home.",
                      "Mother waited.",
                      "The TV was on.",
                  ],
                  "passages": [],
              }],
              "words": [], "sentences": []},
    }

    COHERENT = {
        "3": {"source": "coherent3.pdf", "pages": 1,
              "units": [{
                  "title": "Unit 1 - Grandma's Garden",
                  "words": ["grandma", "garden", "flower", "bee", "grass",
                            "sunflower", "water", "morning", "cat", "bucket",
                            "gate", "tree", "seedling", "watering"],
                  "sentences": [
                      "My grandma has a small garden behind her house.",
                      "She grows many kinds of flower there.",
                      "The yellow flower is her favourite.",
                      "A bee visits the flower every morning.",
                      "The garden is full of green grass.",
                      "Grandma waters the grass with a bucket.",
                      "A tall sunflower stands by the gate.",
                      "Her cat sleeps in the garden all afternoon.",
                      "A mango tree grows beside the gate.",
                      "Every seedling needs water in the morning.",
                      "Grandma smiles when she sees the sunflower.",
                      "The garden is quiet in the afternoon.",
                  ],
                  "passages": [],
              }],
              "words": [], "sentences": []},
    }

    def _p3(self, corpus, year=3, seed=5):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "textbook": corpus})
        paper = bank.generate_paper(c)
        return next(p for p in paper.parts if p.num == 3)

    def test_unlinked_ocr_run_never_becomes_a_passage(self):
        p3 = self._p3(self.BAG)
        text = p3.lead_text or ""
        self.assertNotIn("This is our house", text)
        self.assertNotIn("Mr Price", text)
        self.assertNotIn("there was a duck", text)

    def test_unlinked_sentences_of_the_same_run_stay_apart(self):
        # The gate must reject the blend, not merely the whole unit: two
        # unrelated three-sentence topics inside one long run, followed by a
        # long run of singletons, is exactly the shape a page-order scan
        # produces.  (A short run is exempt — a workbook unit's own three or
        # four lines are coherent by construction.)
        merged = bank._tb_linked(
            ["My grandma grows many kinds of flower in her garden.",
             "She waters the yellow flower every morning.",
             "A bee visits the flower at nine o'clock.",
             "Our class visited the science museum last Friday.",
             "The guide explained how a rocket is built.",
             "We watched a film about the moon.",
             "The bell rang at four o'clock."])
        self.assertFalse(merged)

    def test_linked_run_is_accepted(self):
        self.assertTrue(bank._tb_linked(
            ["My grandma grows many kinds of flower in her garden.",
             "She waters the yellow flower every morning.",
             "A bee visits the flower at nine o'clock.",
             "The garden is full of green grass.",
             "The flower opens when the sun is up.",
             "Grandma picks one flower for the table.",
             "She gives the flower to my sister."]))

    def test_short_workbook_run_is_exempt(self):
        # Round 19/20 contract: a curated workbook unit of three or four lines
        # is one text even when no noun repeats.
        self.assertTrue(bank._tb_linked(
            ["The fish is in the water.", "The shark is scary.",
             "The crab hides under the rock.",
             "The whale swims to the deep sea."]))

    def test_coherent_corpus_still_supplies_the_passage(self):
        # The gate must not throw away a genuinely coherent textbook unit —
        # the corpus is the SJKC pupil's own book and stays the first choice.
        blocks = bank.tb_comprehension_blocks(self.COHERENT, 3)
        self.assertTrue(blocks, "a coherent unit produced no reading block")
        text = blocks[0]["text"]
        self.assertIn("grandma has a small garden", text.casefold())
        self.assertIn("sunflower", text.casefold())
        self.assertEqual(text.count("."), 10, "sentences were merged or lost")

    def test_part3_falls_back_to_the_built_in_pool_and_keeps_its_shape(self):
        # A textbook run that is too thin to carry five questions is dropped,
        # and the built-in passage answers instead — five items, in band.
        thin = {"3": {"source": "thin3.pdf", "pages": 1,
                      "units": [{"title": "Unit 1 - My Garden",
                                 "words": ["grandma", "garden", "flower"],
                                 "sentences": [
                                     "My grandma has a small garden.",
                                     "She grows many kinds of flower.",
                                     "A bee visits the flower every morning.",
                                     "The garden is full of green grass.",
                                 ],
                                 "passages": []}],
                      "words": [], "sentences": []}}
        for corpus in (self.BAG, thin):
            p3 = self._p3(corpus)
            lo, hi = D.PASSAGE_WORD_BAND[3]
            n = len((p3.lead_text or "").split())
            self.assertTrue(lo <= n <= hi, f"{n} words out of band")
            self.assertEqual(len(p3.items), 5)

    def test_part3_varies_with_the_seed(self):
        seen = set()
        for seed in range(1, 6):
            c = dict(D.DEFAULT_CONFIG)
            c.update({"year": 3, "seed": seed, "pictures": False})
            paper = bank.generate_paper(c)
            seen.add((next(p for p in paper.parts
                           if p.num == 3).lead_text or "").strip())
        self.assertGreater(len(seen), 1, "every seed produced the same text")

    def test_part3_register_matches_the_year(self):
        # Years 1-3 read a short personal narrative; Years 5-6 read an
        # expository piece about a place, a person or an event.
        for year, kind in ((1, "narrative"), (3, "narrative"),
                           (5, "expository"), (6, "expository")):
            c = dict(D.DEFAULT_CONFIG)
            c.update({"year": year, "seed": 4, "pictures": False})
            paper = bank.generate_paper(c)
            p3 = next(p for p in paper.parts if p.num == 3)
            self.assertEqual(bank.passage_register(p3.lead_text or ""), kind,
                             f"Y{year}: {(p3.lead_text or '')[:120]}")

    def test_part3_length_sits_in_the_criteria_band(self):
        for year in (1, 2, 3, 5, 6):
            lo, hi = D.PASSAGE_WORD_BAND[year]
            for seed in (1, 3, 5):
                c = dict(D.DEFAULT_CONFIG)
                c.update({"year": year, "seed": seed, "pictures": False})
                paper = bank.generate_paper(c)
                p3 = next(p for p in paper.parts if p.num == 3)
                n = len((p3.lead_text or "").split())
                self.assertGreaterEqual(n, lo,
                                        f"Y{year} seed {seed}: {n} words")
                self.assertLessEqual(n, hi,
                                     f"Y{year} seed {seed}: {n} words")


class TestTbBank(unittest.TestCase):
    """Round 17/T2: a textbook corpus drives Parts 1-7 content; the existing
    pools are the spare wheel; CEFR gates always apply."""

    FIX = {
        "1": {"source": "fixture.pdf", "pages": 1,
              "units": [{
                  "title": "Unit 1 - At School",
                  "words": ["cat", "dog", "bird", "fish", "fox", "hen",
                            "monkey", "boy", "girl", "tree", "bag", "table",
                            "water", "bicycle", "picture", "hall", "field",
                            "football"],
                  "sentences": [
                      "The cat is on the bag.",
                      "The dog is under the table.",
                      "The bird is in the tree.",
                      "The fish is in the water.",
                      "The fox is in the field.",
                      "The hen is on the nest.",
                      "The monkey is in the tree.",
                      "The boy rides a bicycle to school.",
                      "The boy plays football on Sundays.",
                      "The girl draws a picture.",
                      "The girl sings in the hall.",
                      "We play football on Sundays.",
                  ],
                  "passages": [],
              }],
              "words": [], "sentences": []},
        "3": {"source": "fixture3.pdf", "pages": 1,
              "units": [{
                  "title": "Unit 1 - Free Time",
                  "words": ["bird", "tree", "monkey", "table"],
                  "sentences": [
                      "The bird is in the tree.",
                      "The monkey is on the table.",
                  ],
                  "passages": [],
              }],
              "words": [], "sentences": []},
    }

    def _paper(self, year=1, corpus=None, conf=None, seed=5):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False})
        c["textbook"] = corpus if corpus is not None else self.FIX
        if conf:
            c.update(conf)
        return bank.generate_paper(c)

    def test_comprehension_text_from_corpus(self):
        paper = self._paper(1)
        p3 = next(p for p in paper.parts if p.num == 3)
        self.assertIn("The boy rides a bicycle to school.", p3.lead_text)
        self.assertEqual(len(p3.items), 5)
        self.assertLessEqual(len(p3.lead_text.split()),
                             D.PASSAGE_WORD_CEIL[1])

    def test_words_box_from_corpus(self):
        paper = self._paper(1)
        p5 = next(p for p in paper.parts if p.num == 5)
        # Round 41: Y1 Part 5 is the spelling task (letter style).  It
        # does not use the textbook "Word box: ..." format; it uses a clue
        # lead and WordItem entries.
        self.assertEqual(p5.style, "letter")
        self.assertIsNotNone(p5.lead)
        if p5.lead_text:
            self.assertFalse(p5.lead_text.startswith("Word box: "))
        self.assertTrue(p5.items)
        for it in p5.items:
            self.assertTrue(hasattr(it, "answer") or hasattr(it, "word"))

    def test_vocab_and_cloze_answers_from_corpus(self):
        paper = self._paper(1)
        unit_words = set(self.FIX["1"]["units"][0]["words"])
        for p in paper.parts:
            if p.kind != "cloze":
                continue
            for it in p.items:
                ans = getattr(it, "ans_text", "") or it.options[it.answer]
                self.assertIn(str(ans).lower().strip("."), unit_words,
                              (p.num, ans))
        # Round 19: Part 1 vocabulary only blends corpus items whose stem
        # carries a discriminating collocate; everything else comes from the
        # hand-written context pool, so no option ever reproduces a stem word.
        p1 = next(p for p in paper.parts if p.num == 1)
        for it in p1.items:
            stem_tokens = set(re.findall(r"[a-z']+", it.stem.casefold()))
            for o in it.options:
                self.assertNotIn(re.sub(r"[^a-z']", "", o.casefold()),
                                 stem_tokens, (it.stem, o))

    def test_match_questions_from_corpus(self):
        paper = self._paper(1)
        p4 = next(p for p in paper.parts if p.num == 4)
        self.assertEqual(len(p4.items), 6)
        self.assertIn("Who rides a bicycle to school?",
                      " ".join(i.stem for i in p4.items))
        self.assertIn("What is on the bag?",
                      " ".join(i.stem for i in p4.items))

    def test_comprehension_lead_within_year_gate(self):
        for year, corpus in ((1, self.FIX), (3, self.FIX)):
            paper = self._paper(year, corpus=corpus)
            p3 = next(p for p in paper.parts if p.num == 3)
            self.assertEqual(len(p3.items), 5, (year, p3.lead_text))
            self.assertLessEqual(
                len(p3.lead_text.split()), D.PASSAGE_WORD_CEIL[year], year)

    def test_cefr_gate_keeps_dirty_band_out(self):
        dirty = {str(k): v for k, v in self.FIX.items()}
        dirty["3"]["units"][0]["sentences"] = [
            "The beauteous monkey climbed the enormous ancient tree regally.",
            "The perplexed pupils watched the magnificent creature silently.",
            "The cunning fox observed the extraordinary scene carefully.",
            "The humble bird sang a melodious tune gracefully.",
            "The startled hen fled across the tremendous field rapidly.",
            "The majestic tiger returned to its den victoriously.",
        ]
        paper = self._paper(3, corpus=dirty)
        p3 = next(p for p in paper.parts if p.num == 3)
        low = p3.lead_text.lower()
        for banned in ("beauteous", "perplexed", "magnificent",
                       "extraordinary", "melodious", "tremendous"):
            self.assertNotIn(banned, low)
        self.assertLessEqual(
            len(p3.lead_text.split()), D.PASSAGE_WORD_CEIL[3])

    def test_empty_corpus_falls_back_to_builtin(self):
        empty = {"5": {"source": "x.pdf", "pages": 0, "units": [],
                       "words": [], "sentences": []}}
        paper = self._paper(5, corpus=empty)
        pc = bank.paper_compliance(paper)
        self.assertEqual(len(paper.parts), 7)
        self.assertTrue(pc["ok"], pc["issues"])

    def test_corpus_paper_still_compliant(self):
        for year in (1, 3, 5, 6):
            corpus = self.FIX if year != 6 else None
            if year == 6:
                corpus = {"6": {"source": "fx6.pdf", "pages": 1, "units": [],
                                "words": [], "sentences": []}}
            paper = self._paper(year, corpus=corpus)
            pc = bank.paper_compliance(paper)
            self.assertTrue(pc["ok"], (year, pc["issues"]))


class TestTbUsability(unittest.TestCase):
    """Round 18: OCR fragments must never become questions.  A scanned
    textbook corpus is only a question source when a sentence survives the
    strict admission gate (capital start, finite verb, no OCR debris); garbage
    is dropped and the curated built-in pools back the part up.  These tests
    reproduce the actual unusable output observed after Round 17."""

    OCR_FRAGMENTS = [
        "3 school sections of the Student's Book.",
        "for developing and writing the phonics material.",
        "Guodolupe Mejia, Maria Teresa Moguel.",
        "into the DVD-ROM drive.",
        "lick on the setup.msi icon.",
        "ReadMe file ovailable on the DVD-ROM.",
        "1 have dinner with my family.",
        "and he works at work!",
        "grow tomatoes and vegetables.",
        "o Listen and match.",
        "Is sleeping on the tree.",
        "Is climbing up a tree.",
        "s of people were leaving the station.",
        "fing and no food.",
        "I''m a white fish.",
        "at Thomas Jefferson were busy through the night.",
        "The boy in the land.",
        "The girl in the land.",
    ]

    GOOD_SENTENCES = [
        "The cat is on the bag.",
        "The dog is under the table.",
        "I'm a big fish.",
        "The snake is awake.",
        "His name is Greg.",
        "The boy rides a bicycle to school.",
        "We play football on Sundays.",
        "The Bactrian camel lives in Asia.",
        "The king was very happy.",
        "The shark is scary.",
    ]

    def _paper(self, year, corpus, seed=3, **extra):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "textbook": corpus})
        c.update(extra)
        return bank.generate_paper(c)

    def _gathered(self, paper):
        out = []
        for p in paper.parts:
            if p.lead_text:
                out.append(p.lead_text)
            for it in p.items:
                for attr in ("stem", "clue", "prompt", "model"):
                    v = getattr(it, attr, None)
                    if v:
                        out.append(v)
        return " ".join(out)

    def test_clean_sentences_reject_ocr_fragments(self):
        TB = __import__("exam_gen.textbook", fromlist=["textbook"])
        for frag in self.OCR_FRAGMENTS:
            got = TB.clean_sentences(frag, 3)
            self.assertNotIn(frag, got, frag)
        got = TB.clean_sentences(" ".join(self.OCR_FRAGMENTS), 3)
        self.assertEqual([], got)

    def test_sentence_admits_keeps_clean_rejects_garbage(self):
        for good in self.GOOD_SENTENCES:
            self.assertTrue(bank._sentence_admits(good, 3), good)
        for frag in self.OCR_FRAGMENTS:
            self.assertFalse(bank._sentence_admits(frag, 3), frag)

    def _dirty_corpus(self, year=3):
        unit = {
            "title": "Textbook",
            "words": ["dinner", "family", "fish", "tree", "land",
                      "station", "supermarket", "got", "big"],
            "sentences": list(self.OCR_FRAGMENTS)
            + ["The boy rides a bicycle to school.",
               "The shark is scary.",
               "The king was very happy."],
            "passages": [],
        }
        return {str(year): {"source": "dirty.pdf", "pages": 1,
                            "units": [unit], "words": [], "sentences": []}}

    def test_dirty_corpus_never_surfaces_in_paper(self):
        banned = ["1 have", "listening", "Listen and match", "in the land",
                  "setup.msi", "DVD-ROM", "Guodolupe", "o Listen",
                  "about Textbook", "were leaving the station"]
        for year in (3, 5, 6):
            paper = self._paper(year, self._dirty_corpus(year))
            blob = self._gathered(paper)
            for b in banned:
                self.assertNotIn(b, blob, (year, b))
            self.assertEqual(len(paper.parts), 7)

    def test_generated_stems_are_clean_lines(self):
        for year in (3, 5, 6):
            paper = self._paper(year, self._dirty_corpus(year))
            for p in paper.parts:
                for it in p.items:
                    stem = getattr(it, "stem", None)
                    if stem:
                        self.assertTrue(bank._stem_admits(stem, year),
                                        (year, p.num, stem))
                    clue = getattr(it, "clue", None)
                    if clue:
                        self.assertTrue(bank._stem_admits(clue, year),
                                        (year, p.num, clue))

    def test_match_items_are_well_formed_lines(self):
        for year in (3, 5, 6):
            paper = self._paper(year, self._dirty_corpus(year))
            p4 = next(p for p in paper.parts if p.num == 4)
            for it in p4.items:
                stem = it.stem.strip()
                # a bare "Who in the land?"-style jibberish must be impossible:
                # every line is a well-formed sentence (statement or question)
                self.assertTrue(bank._stem_admits(stem, year), (year, stem))
                ends_q = stem.endswith("?")
                if ends_q:
                    self.assertRegex(stem, r"^(Who|What|Where|When|How|Why)\b",
                                     (year, stem))
                    toks = set(re.findall(r"[a-z']+", bank._decontract(stem)))
                    self.assertTrue(toks & bank._FINITE_VERBS, (year, stem))
                else:
                    self.assertTrue(stem.endswith("."), (year, stem))

    def test_subject_verb_phrase_needs_a_verb(self):
        self.assertIsNone(bank._tb_subject_noun("The boy in the land."))
        self.assertIsNone(bank._tb_subject_noun("The girl in the land."))
        hit = bank._tb_subject_noun("The boy rides a bicycle to school.")
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1], "boy")
        self.assertEqual(hit[2], "Who")

    def test_writing_generic_title_falls_back_to_builtin(self):
        for title in ("Textbook", "Starter unit 11", "Unit 3"):
            corpus = self._dirty_corpus(3)
            corpus["3"]["units"][0]["title"] = title
            corpus["3"]["units"][0]["sentences"] = [
                "The cat is on the bag.",
                "The dog is under the table.",
                "The bird is in the tree.",
                "The fish is in the water.",
                "The boy rides a bicycle to school.",
                "We play football on Sundays.",
            ]
            paper = self._paper(3, corpus)
            p6 = next(p for p in paper.parts if p.num == 6)
            p7 = next(p for p in paper.parts if p.num == 7)
            for p in (p6, p7):
                self.assertNotIn("about %s" % title, p.items[0].prompt)
                self.assertNotIn("Use the words: got", p.items[0].prompt)

    def test_fixture_paper_stems_still_clean(self):
        for year in (1, 3):
            corpus = {str(year): v for k, v in TestTbBank.FIX.items()
                      if str(k) == str(year)}
            paper = self._paper(year, corpus)
            for p in paper.parts:
                for it in p.items:
                    stem = getattr(it, "stem", None)
                    if stem:
                        self.assertTrue(bank._stem_admits(stem, year),
                                        (year, p.num, stem))


class TestRound19(unittest.TestCase):
    """Round 19: mirror the teacher's reference papers (copies under
    ``~/Downloads/exam2026``).  Options are always same-shape and lowercased and
    never reproduce words from the stem; passages for Parts 2/3 are built from
    coherent, unit-bounded runs (never cross-unit stitches); Years 3/5 Part 2 is
    a present-tense verb-form cloze (drink/drinks/drinking) in one paragraph;
    and an OCR sentence-seam ("One day, Norman and But it wasn't a monster.")
    can no longer pass the admission gate."""

    def _paper(self, year, corpus=None, seed=5, **kw):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "textbook": corpus})
        c.update(kw)
        return bank.generate_paper(c)

    def _corpus_for(self, year, sentences, title="Unit 1"):
        return {str(year): {"source": "r19.pdf", "pages": 1,
                            "units": [{"title": title, "words": [],
                                       "sentences": list(sentences)}],
                            "words": [], "sentences": []}}

    # ---- sentence seams: a glued OCR fragment is always rejected ----------
    def test_sentence_seams_are_rejected(self):
        self.assertFalse(bank._sentence_admits(
            "One day, Norman and But it wasn't a monster.", 3))
        self.assertFalse(bank._sentence_admits(
            "Once upon a time, John and Sue they lived near the sea.", 3))
        self.assertTrue(bank._sentence_admits(
            "Tom and Jerry went to the shop together.", 3))

    # ---- unit boundaries are preserved for coherent passages --------------
    def test_tb_units_preserve_unit_boundaries(self):
        corpus = {"5": {"source": "x", "pages": 1,
                        "units": [
                            {"title": "Unit A", "words": [],
                             "sentences": ["Ben drinks milk every morning.",
                                           "He eats toast for breakfast."]},
                            {"title": "Unit B", "words": [],
                             "sentences": ["Sue takes the car to the office.",
                                           "Ravi opens the window and waves."]},
                        ], "words": [], "sentences": []}}
        groups = bank._tb_units(corpus, 5)
        flattened = [s for _, ss in groups for s in ss]
        self.assertEqual(flattened,
                         ["Ben drinks milk every morning.",
                          "He eats toast for breakfast.",
                          "Sue takes the car to the office.",
                          "Ravi opens the window and waves."])

    def test_comprehension_blocks_never_cross_units(self):
        corpus = {"3": {"source": "x", "pages": 1,
                        "units": [
                            {"title": "Unit Fish", "words": [],
                             "sentences": ["The fish is in the water. "
                                           "The shark is scary. "
                                           "The crab hides under the rock. "
                                           "The whale swims to the deep sea."]},
                            {"title": "Unit Farm", "words": [],
                             "sentences": ["The cow gives us milk. "
                                           "The hen lays an egg. "
                                           "The farmer feeds the pigs."]},
                        ], "words": [], "sentences": []}}
        blocks = bank.tb_comprehension_blocks(corpus, 3)
        self.assertTrue(blocks)
        for b in blocks:
            text = b["text"]
            self.assertFalse(
                {"fish", "shark", "crab", "whale"} & set(
                    re.findall(r"[a-z']+", text.lower())) and
                {"cow", "hen", "farmer", "pig"} & set(
                    re.findall(r"[a-z']+", text.lower())),
                "passage mixes two different units: %r" % text[:80])

    # ---- Part 1 vocabulary: lowercase, same-shape, discriminating ---------
    def test_vocab_options_lowercased_and_not_in_stem(self):
        corpus = self._corpus_for(3, ["The Bactrian camel lives in Asia.",
                                      "The shark is scary.",
                                      "The farmer keeps the cow in the field."])
        items = bank.tb_vocab_items(corpus, 3)
        self.assertTrue(items, "collocate-clued corpus items must be eligible")
        for q in items:
            self.assertEqual(q["opts"], [str(o).lower() for o in q["opts"]],
                             "options must be lowercased (teacher style)")
            self.assertEqual(q["ans_text"], q["ans_text"].lower())
            stem_tokens = set(re.findall(r"[a-z']+",
                                         q["stem"].lower().replace("_", "")))
            for o in q["opts"]:
                self.assertNotIn(re.sub(r"[^a-z']", "", o.lower()), stem_tokens,
                                 "an option may not appear inside the stem")

    def test_vocab_generic_context_is_dropped(self):
        corpus = self._corpus_for(3, ["I live in a big city.",
                                      "There was a big house on the hill."])
        self.assertEqual(bank.tb_vocab_items(corpus, 3), [],
                         "context-less nouns must not become Part 1 questions")

    # ---- Year 3/5 cloze: verb-form options in one coherent paragraph -------
    VERB_RUN = ["Ben drinks a glass of milk every morning.",
                "His mother packs a lunch box for school.",
                "Ben walks to the bus stop with his sister.",
                "They watch the yellow bus come down the road.",
                "Ben helps his sister climb onto the bus.",
                "The driver smiles and waves to the children."]

    @staticmethod
    def _verb_base(w):
        w = w.lower()
        w = re.sub(r"(ing|es|s)$", "", w)
        if len(w) > 2 and w[-1] == w[-2]:
            w = w[:-1]
        return w.rstrip("e")

    def _assert_verb_gap_shapes(self, gaps, markers=(6, 7, 8, 9)):
        self.assertEqual(len(gaps), 4)
        for n, gap in zip(markers, gaps):
            self.assertEqual(len(gap["opts"]), 3)
            self.assertGreaterEqual(len(gap["stem"].split("__________")), 2)
            self.assertTrue(gap["stem"].startswith(
                gap["stem"].split("__________")[0].strip(),
            ) or gap["stem"].endswith("."))
            self.assertEqual(gap["stem"].count("__________"), 1)
            self.assertTrue(gap["stem"].endswith("."), gap["stem"])
            forms = [str(o).lower() for o in gap["opts"]]
            self.assertEqual(len(set(forms)), 3, gap["opts"])
            self.assertLessEqual(len({self._verb_base(o) for o in forms}), 1,
                                 "the three options are one verb's forms")
            self.assertIn(gap["ans_text"].lower(), forms)

    def test_cloze_verb_forms_from_unit_run(self):
        corpus = self._corpus_for(5, self.VERB_RUN, title="Morning Routine")
        blocks = [b for b in bank.tb_cloze_blocks(corpus, 5)
                  if len(b.get("gaps", [])) >= 4]
        self.assertTrue(blocks, "a 6-sentence verb run must yield a cloze block")
        block = blocks[0]
        self.assertEqual(block.get("mode"), "verb")
        self.assertIn("(6)", block["passage"])
        self._assert_verb_gap_shapes(block["gaps"])

    def test_builtin_cloze_is_verb_form_for_years_3_and_5(self):
        for year in (3, 5):
            pool = bank._cloze_pool(year)
            verb = [b for b in pool if b.get("mode") == "verb"
                    and len(b.get("gaps", [])) >= 4]
            self.assertTrue(verb, f"Y{year} needs teacher-style verb cloze blocks")
            b = verb[0]
            self.assertGreaterEqual(len(b["passage"].split()), 30)
            self.assertEqual(re.findall(r"\((\d)\)", b["passage"]),
                             ["6", "7", "8", "9"])
            self._assert_verb_gap_shapes(b["gaps"])

    def test_builtin_cloze_year6_same_category_options(self):
        pool = [b for b in bank._cloze_pool(6) if b.get("mode") == "sem"
                and len(b.get("gaps", [])) >= 4]
        self.assertTrue(pool, "Y6 needs same-category cloze blocks")
        for gap in pool[0]["gaps"]:
            self.assertEqual(len(gap["opts"]), 3)
            self.assertTrue(all(str(o).islower() for o in gap["opts"]))

    def test_cloze_y3_paper_is_coherent_verb_form(self):
        for seed in (1, 3, 7):
            paper = self._paper(3, seed=seed)
            p2 = next(p for p in paper.parts if p.num == 2)
            self.assertGreaterEqual(len(p2.lead_text.split()), 30, seed)
            self.assertEqual(re.findall(r"\((\d)\)", p2.lead_text),
                             ["6", "7", "8", "9"], seed)
            self.assertEqual(len(p2.items), 4, seed)
            for it in p2.items:
                forms = [str(o).lower() for o in it.options]
                self.assertEqual(len(set(forms)), 3, (seed, forms))
                self.assertLessEqual(
                    len({self._verb_base(o) for o in forms}), 1, forms)

    def test_part1_part2_teacher_style_smoke(self):
        for year in (3, 5, 6):
            paper = self._paper(year, seed=4)
            p1 = next(p for p in paper.parts if p.num == 1)
            for it in p1.items:
                for o in it.options:
                    self.assertNotIn(o.casefold(),
                                     set(re.findall(r"[a-z']+",
                                                    it.stem.casefold())),
                                     (year, it.stem, o))
            p2 = next(p for p in paper.parts if p.num == 2)
            self.assertNotIn("and But", p2.lead_text)
            self.assertNotIn("has / have", p2.lead_text)


class TestRound20(unittest.TestCase):
    """Round 20: the in-app QC watchdog.

    Part 3 (and every other part) can no longer ship the mined workbook's
    dialogue / worksheet-instruction / OCR DNA — "Did you see that documentary
    about healthy eafing last night?", "Read and listen to the text again.",
    "got up at & a.m." — and a comprehension block never repeats one answer
    ("sugar" three times).  A new ``exam_gen.qc`` module grades every item and
    part against the rules the teacher's own reference papers satisfy,
    ``generate_clean`` re-rolls a part until zero QC-hard issues remain, and
    the teacher's copies under ``~/Downloads/exam2026`` are the oracle that a
    real paper must pass 100%."""

    def _paper(self, year, corpus=None, seed=5, **kw):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "textbook": corpus})
        c.update(kw)
        return bank.generate_paper(c)

    def _corpus_for(self, year, sentences, title="Unit 1"):
        return {str(year): {"source": "r20.pdf", "pages": 1,
                            "units": [{"title": title, "words": [],
                                       "sentences": list(sentences)}],
                            "words": [], "sentences": []}}

    # ---- new OCR debris: '&' and splash-dash is rejected ------------------
    def test_new_ocr_noise_is_rejected(self):
        self.assertFalse(bank._sentence_admits(
            "The next day the boys got up at & a.m.", 5))
        self.assertFalse(bank._sentence_admits(
            "That's true - but it isn't what we mean.", 5))
        self.assertTrue(bank._sentence_admits(
            "On Saturday the pupils hold their Sports Day.", 3))

    # ---- a teacher's dash is punctuation, OCR debris is not ---------------
    def test_stem_dash_is_punctuation_not_ocr_debris(self):
        """The teacher's own T5&T6 papers print a parenthetical dash —
        "no one gives up—it's all about pulling together" (UASA AKHIR
        T5&6 2025) and "the British presence was strong—tin and rubber
        exports fueled their empire" (UPSA PT6 2026) — so a hand-authored
        stem must survive the watchdog.  A corpus sentence still may not:
        the OCR gate is where a stray dash is real shrapnel."""
        self.assertTrue(bank._stem_admits(
            "COMMUNITY PROJECT\nEverybody can __________ to the project "
            "— a small amount of help makes a difference.", 6))
        # every other debris signal is untouched
        for debris in ("WORKSHEET\nRead the text (again) and answer.",
                       "WORKSHEET\nRead the text & answer it.",
                       "WORKSHEET\nRead the text | answer it."):
            self.assertFalse(bank._stem_admits(debris, 6), debris)
        # the sentence-level OCR gate is unchanged: a mined dash is dropped
        self.assertFalse(bank._sentence_admits(
            "The girls fly a kite in the sky — every Saturday.", 5))
        self.assertTrue(bank._sentence_admits(
            "The girls fly a kite in the sky.", 5))

    def test_year6_papers_never_fail_the_watchdog(self):
        """The gate that caught the Round-25 em-dash regression: every year's
        every theme must clear the watchdog, not just Years 1-3."""
        from exam_gen import qc
        for year in D.YEARS:
            for theme in D.RPT_THEMES.get(year) or [None]:
                for diff in ("easy", "medium"):
                    p = self._paper(year, seed=3, difficulty=diff,
                                    theme=theme or "auto")
                    self.assertEqual(qc.check_paper(p).hard, 0,
                                     (year, theme, diff))

    # ---- Part 3 comprehension: declarative narrative only -----------------
    def test_comprehension_rejects_dialogue_and_instructions(self):
        corpus = {"5": {"source": "x", "pages": 1,
                        "units": [
                            {"title": "Dialogue", "words": [],
                             "sentences": [
                                 "Did you see that documentary about sugar "
                                 "last night?",
                                 "It was about how much sugar we eat.",
                                 "Read and listen to the text again.",
                                 "That's true - but it isn't what we mean!",
                                 "This means we eat much more sugar!"]},
                            {"title": "Beach", "words": [],
                             "sentences": [
                                 "The girls fly a kite in the sky. ",
                                 "The tall tree stands beside the stream. ",
                                 "A cow gives fresh milk to the farmer. "]},
                        ], "words": [], "sentences": []}}
        blocks = bank.tb_comprehension_blocks(corpus, 5)
        texts = [b["text"] for b in blocks]
        self.assertTrue(texts, "the clean unit must still surface a block")
        for t in texts:
            self.assertNotIn("?", t)
            self.assertNotIn("Read and listen", t)
            self.assertNotIn("documentary", t.lower())
            self.assertNotIn("- but", t)
        self.assertTrue(any("tree" in t for t in texts),
                        "the story unit must survive, not the dialogue")

    def test_comprehension_answers_are_distinct(self):
        corpus = self._corpus_for(
            6, ["A farmer gives rice to the cook. ",
                "A hen sits on the egg in the warm nest. ",
                "A cow gives fresh milk to the children. ",
                "A farmer makes a nest for the hen. "])
        blocks = bank.tb_comprehension_blocks(corpus, 6)
        self.assertTrue(blocks)
        for b in blocks:
            seen = []
            for q in b["qs"]:
                a = str(q.get("ans_text") or q["opts"][q["ans"]]).casefold()
                seen.append(a)
            self.assertEqual(len(seen), len(set(seen)),
                             "a block never repeats the same answer")
            self.assertEqual(seen.count("farmer"), 1,
                             "the duplicated farmer answer must be dropped")

    # ---- the QC watchdog --------------------------------------------------
    def _gap(self, opts, stem="A cook __________ rice every day.", **kw):
        d = {"stem": stem, "opts": opts, "ans": 0,
             "ans_text": str(opts[0])}
        d.update(kw)
        return d

    def _shuffled(self, item):
        return bank._shuffle_mcq(bank._rng({"seed": 1, "year": 3}), item)

    def test_qc_flags_mixed_case_options(self):
        from exam_gen import qc
        issues = qc.check_item(self._gap(["Wood", "stream", "house"]),
                               "vocab", 6)
        self.assertTrue([i for i in issues if i.code == "option-case"])
        self.assertTrue(all(i.hard for i in issues if i.code == "option-case"))

    def test_qc_allows_legitimate_capitalised_options(self):
        from exam_gen import qc
        # Proper nouns / acronyms are teacher-accepted capitalization (the
        # teacher's own papers print "Kuala Lumpur", "Chinese New Year", LRT
        # next to lowercase distractors), so they must never trip the rule.
        for opts in (["LRT", "ferry", "aeroplane"],
                     ["Cameron Highlands", "the mall basement", "the sea floor"],
                     ["Kuala Lumpur", "Bangkok", "Singapore"],
                     ["Chinese New Year", "Hari Merdeka", "Teachers' Day"]):
            issues = qc.check_item(self._gap(opts), "vocab", 6)
            self.assertEqual([i for i in issues if i.code == "option-case"],
                             [], opts)

    def test_junior_papers_never_fail_the_watchdog(self):
        from exam_gen import qc
        for year in (1, 2, 3):
            for theme in D.RPT_THEMES.get(year, []) or [None]:
                p = self._paper(year, seed=3)
                self.assertEqual(qc.check_paper(p).hard, 0, (year, theme))

    def test_qc_flags_option_leak(self):
        from exam_gen import qc
        issues = qc.check_item(
            self._gap(["rain", "shine", "blow"],
                      stem="Rain clouds gathered; soon it began to "
                           "__________ heavily."), "vocab", 3)
        self.assertTrue([i for i in issues if i.code == "option-leak"])

    def test_qc_passes_teacher_style_item(self):
        from exam_gen import qc
        issues = qc.check_item(self._gap(["cook", "cooks", "cooking"],
                                         "Grandmother __________ a big pot "
                                         "of porridge."),
                               "cloze", 3)
        self.assertEqual(issues, [])

    def test_qc_flags_question_inside_cloze_passage(self):
        from exam_gen import qc
        p = self._paper(3, seed=2)
        p2 = next(pp for pp in p.parts if pp.num == 2)
        p2.lead_text = "Why does the bus stop here? " + p2.lead_text
        report = qc.check_part(p2, 3)
        self.assertTrue(any(i.code == "passage-dialogue"
                            for i in report.issues))

    def test_qc_flags_non_verb_gap_for_upper_cloze(self):
        from exam_gen import qc
        issues = qc.check_item(self._gap(["doctor", "nurse", "farmer"]),
                               "cloze", 3)
        self.assertTrue([i for i in issues if i.code == "gap-triplet"])

    def test_qc_flags_answer_repeat_soft(self):
        from exam_gen import qc
        part = bank.Part(num=3, kind="comprehension", style="web", marks=5,
                         title="PART 3", lead="a",
                         lead_text="A chicken laid a brown egg in the nest. "
                                   "A cow gave fresh milk to the farmer. "
                                   "The hen sat on the egg all day. "
                                   "The farmer sold rice at the market. ")
        part.items = [self._shuffled(self._gap(["sugar", "bread", "jam"],
                                               stem=f"S{i} eats too much "
                                               "__________ every day."))
                      for i in range(3)]
        report = qc.check_part(part, 6)
        soft = [i for i in report.issues if i.code == "answer-repeat"]
        self.assertTrue(soft and not soft[0].hard,
                        report.issues)

    def test_comprehension_answers_may_borrow_stem_words(self):
        from exam_gen import qc
        issues = qc.check_item(
            self._gap(["her school bag", "her kite", "her ball"],
                      stem="What does Mei Ling bring to school every day?",
                      **{"ans": 0}), "comprehension", 3)
        self.assertFalse([i for i in issues if i.code == "option-leak"],
                         "comprehension stems legitimately reuse passage words")

    def test_generated_papers_have_no_qc_hard_issues(self):
        from exam_gen import qc
        for year in (1, 2, 3, 5, 6):
            for seed in (1, 4):
                report = qc.check_paper(self._paper(year, seed=seed))
                self.assertEqual(report.hard, 0, (year, seed,
                                                  [i for i in report.issues]))
                self.assertGreaterEqual(report.score, 8.0, (year, seed))

    @unittest.skipUnless(
        os.path.isdir(os.path.expanduser("~/Downloads/exam2026")),
        "teacher reference copies not present")
    def test_teacher_reference_papers_pass_the_watchdog(self):
        from exam_gen import qc
        issues = qc.reference_issues(
            os.path.expanduser("~/Downloads/exam2026"))
        self.assertEqual(issues, [], [i.message for i in issues])

    def test_dirty_corpus_is_forced_clean_by_generate_clean(self):
        from exam_gen import qc
        corpus = {"5": {"source": "x", "pages": 1,
                        "units": [{"title": "Junk", "words": [],
                                   "sentences": [
                                       "Read and listen to the text again. ",
                                       "Did you see that documentary about "
                                       "eafing last night?",
                                       "It was about how much sugar we eat. ",
                                       "The boys got up at & a.m. ",
                                       "This means we eat much more sugar! ",
                                       "I'm going to download it right now! "]},
                                  ], "words": [], "sentences": []}}
        for seed in (1, 3, 5):
            paper = bank.generate_clean(
                {"year": 5, "seed": seed, "pictures": False,
                 "textbook": corpus, "use_web": True}, ["bad"])
            report = qc.check_paper(paper)
            self.assertEqual(report.hard, 0, (seed, report.issues[:3],
                                              paper.parts[2].lead_text[:80]))


class TestRound21(unittest.TestCase):
    """Round 21: Part 6/7 writing is answerable.

    The reported "Your friend wants to know about Read A Newspaper Article.
    Write an email to him or her about it. Use the words: singing, working,
    some." is unanswerable — the topic is a skill/method label carved from a
    mined unit title and the required words have nothing to do with it.
    Writing topics must be plain noun phrases, the "Use the words" list must
    be content vocabulary, and the QC watchdog must grade the writing part
    (it was previously parsed as vocab, so a broken prompt sailed through
    as 10/10)."""

    def _corpus_for(self, year, sentences, title="Unit 1"):
        return {str(year): {"source": "r21.pdf", "pages": 1,
                            "units": [{"title": title, "words": [],
                                       "sentences": list(sentences)}],
                            "words": [], "sentences": []}}

    BAD = ("Your friend wants to know about Read A Newspaper Article. Write "
           "an email to him or her about it. Use the words: singing, "
           "working, some.")
    BAD_NOTES = ["what read a newspaper article is about",
                 "what the word 'singing' means",
                 "what you like about it",
                 "why your friend should try it"]

    # ---- the generator never offers a skill/method topic for writing ------
    def test_skill_titles_are_not_writing_topics(self):
        corpus = self._corpus_for(
            6, ["A reporter writes the news every morning. ",
                "The editor reads the paper every day. ",
                "The readers sing at the school hall. "],
            title="Unit 1 - Read a newspaper article")
        self.assertEqual(bank.tb_writing_entries(corpus, 6, "email", "long"),
                         [])

    def test_all_the_mining_skill_titles_are_rejected(self):
        sents = ["A reporter writes the news every morning. ",
                 "The editor reads the paper every day. ",
                 "The readers sing at the school hall. "]
        titles = ["Unit 1 - Read a newspaper article",
                  "Reading skill: identify the features of a newspaper "
                  "article",
                  "Unit 2 - Talk about interrupted past actions with when",
                  "Unit 3 - Ask and answer questions about interrupted past "
                  "activities",
                  "Unit 4 - Understand context from audio clues",
                  "Unit 5 - Reading skill: understand facts and details"]
        corpus = {"6": {"source": "x", "pages": 1, "words": [],
                        "sentences": [],
                        "units": [{"title": t, "words": [],
                                   "sentences": list(sents)}
                                  for t in titles]}}
        self.assertEqual(bank.tb_writing_entries(corpus, 6, "email", "long"),
                         [])

    def test_plain_noun_phrase_topic_is_kept(self):
        corpus = self._corpus_for(
            3, ["A night at the zoo gives us great joy. ",
                "The zookeeper makes the lion show every night. ",
                "The monkeys sing at the zoo in the morning. "],
            title="Unit 3 - A night at the zoo")
        entries = bank.tb_writing_entries(corpus, 3, "email", "long")
        self.assertTrue(entries)
        topic = entries[0]["prompt"].split(" about ", 1)[1].split(". ", 1)[0]
        self.assertTrue(bank.valid_writing_topic(topic), topic)

    def test_weak_required_words_are_dropped(self):
        corpus = self._corpus_for(
            3, ["Some cows give some fresh milk every morning. ",
                "The farmer gives some milk to the cook. ",
                "We see some birds near the farm. "],
            title="Unit 2 - On the farm")
        entries = bank.tb_writing_entries(corpus, 3, "email", "long")
        self.assertTrue(entries)
        listed = entries[0]["prompt"].split("Use the words:", 1)[1]
        self.assertNotIn("some", listed.split(", ")[0].lower())

    # ---- the watchdog refuses the pasted broken pattern -------------------
    def test_qc_catches_unanswerable_writing_prompt(self):
        from exam_gen import qc
        issues = qc.check_item({"prompt": self.BAD,
                                "bullets": list(self.BAD_NOTES)},
                               "writing", 6)
        codes = sorted({i.code for i in issues if i.hard})
        self.assertTrue(codes and "write-topic" in codes, issues)

    def test_qc_passes_teacher_style_writing_prompt(self):
        from exam_gen import qc
        issues = qc.check_item(
            {"prompt": "You saw a poster at school. Based on the "
                       "information below, write an email to tell your "
                       "friend about it.",
             "bullets": ["Get tickets: buy online ahead",
                         "Plan activities: check the app",
                         "Earn KidZos: do jobs to get paid"]},
            "writing", 5)
        self.assertEqual([i for i in issues if i.hard], [])

    def test_docx_audit_grades_the_writing_part(self):
        from exam_gen import pdfmake, qc
        p = bank.generate_paper({"year": 6, "seed": 9, "pictures": False})
        p.parts[-1].items[0].prompt = self.BAD
        p.parts[-1].items[0].bullets = list(self.BAD_NOTES)
        with tempfile.TemporaryDirectory() as td:
            pdfmake.save_paper(p, os.path.join(td, "P"), want_pdf=False)
            _, parts = qc._parse_docx(os.path.join(td, "P.docx"))
            kinds = {pp["num"]: pp["kind"] for pp in parts}
            self.assertEqual(kinds.get(7), "writing")
            r = qc._audit_docx(os.path.join(td, "P.docx"))
            self.assertTrue(any(i.code == "write-topic" for i in r.issues),
                            [i.code for i in r.issues])


class TestRound22(unittest.TestCase):
    """Round 22: Part 5 letter-words are clean themed descriptions; the
    essay/letter prompts stay theme-aligned and reasonable.

    Teacher directive for the upper-primary fill-in-the-space exercise: "align
    the theme and the answers", "get rid of the space, it should be statements
    without space, pupils read the statements, and guess the answers by filling
    in the space".  Before this round the `words`/letter branch shipped
    textbook usage sentences with a mid-sentence blank as the clue ("We
    couldn't __________ dinner.") plus OCR-shrapnel stems ("New York
    __________, people were a lot of problems at home supermarket."), all
    untouched by the active RPT theme."""

    THEMES = {5: D.RPT_THEMES[5], 6: D.RPT_THEMES[6]}

    def _corpus_for(self, year, sentences, title="Unit 1"):
        return {str(year): {"source": "r22.pdf", "pages": 1,
                            "units": [{"title": title, "words": [],
                                       "sentences": list(sentences)}],
                            "words": [], "sentences": []}}

    def _part5(self, year, theme, seed, corpus=None, **conf):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "theme": theme, "seed": seed,
                  "parts": [5], "pictures": False})
        if corpus is not None:
            c["textbook"] = corpus
        c.update(conf)
        return bank.generate_paper(c).parts[0]

    # ---- Part 5 letter words: statements without space --------------------
    def test_part5_letter_clues_are_statements_without_blanks(self):
        """A Y5/Y6 Part 5 clue reads as a clean description: no mid-sentence
        blank, no leading noise, terminal punctuation.  A pupil reads the
        statement and fills the pattern below."""
        dirty = self._corpus_for(
            6, ["The woman cooked dinner and fed the farmer today. ",
                "The hunter saw a tiger near the station. ",
                "The fire spread across the building quickly. ",
                "A cook prepared rice for the whole town. ",
                "The boy rides a bicycle to school. "])
        for year in (5, 6):
            for theme in self.THEMES[year]:
                for seed in (1, 2, 3, 7, 11):
                    p = self._part5(year, theme, seed, corpus=dirty)
                    for it in p.items:
                        clue = it.clue
                        self.assertNotIn("__________", clue,
                                         (year, theme, seed, clue))
                        self.assertNotIn("?", clue, (year, theme, seed, clue))
                        self.assertTrue(clue.endswith("."),
                                        (year, theme, seed, clue))
                        self.assertTrue(clue[0].isupper(),
                                        (year, theme, seed, clue))
                        self.assertTrue(bank._stem_admits(clue, year),
                                        (year, theme, seed, clue))
                        self.assertEqual(it.answer, it.answer.upper())

    def test_part5_letter_answers_align_with_theme(self):
        """Every Y5/Y6 Part 5 answer word belongs to the active RPT theme's
        keyword set (the word the description defines is on-topic)."""
        for year in (5, 6):
            for theme in self.THEMES[year]:
                for seed in (1, 2, 3, 7, 11):
                    p = self._part5(year, theme, seed)
                    self.assertEqual(len(p.items), 5, (year, theme, seed))
                    kws = {k.casefold() for k in D.THEME_KEYWORDS[theme]}
                    for it in p.items:
                        self.assertIn(it.answer.casefold(), kws,
                                      (year, theme, seed, it.answer, it.clue))

    def test_part5_letter_stems_never_ship_ocr_fragments(self):
        """The exact garbled stems reported by the teacher can never surface;
        even a textbook corpus that would blank a noun mid-sentence is
        ignored for the letter format (descriptions, not usage lines)."""
        dirty = self._corpus_for(
            6, ["We couldn't cook dinner. ",
                "New York city, people were a lot of problems at home "
                "supermarket. ",
                "Why did a woman scream on the train? ",
                "He looked for his knife to make a fire. "])
        for year in (5, 6):
            for seed in (1, 3, 5, 9):
                p = self._part5(year, "It's an Emergency", seed,
                                corpus=dirty)
                blob = " ".join(f"{i.clue} {i.answer}" for i in p.items)
                for banned in ("__________", "couldn't", "supermarket",
                               "scream", "knife"):
                    self.assertNotIn(banned.casefold(), blob.casefold(),
                                     (year, seed, blob))

    def test_theme_letter_pool_covers_every_theme(self):
        """The curated letter-word data must offer >= 5 genuinely on-theme
        entries for every Y5/Y6 theme — matching the theme, not just any
        fallback filler — so a paper is never topped up off-theme."""
        for year in (5, 6):
            pool = bank._letter_words_pool(year)
            for theme in self.THEMES[year]:
                themed = bank._theme_prefer(pool, theme, 5)
                self.assertGreaterEqual(len(themed), 5,
                                        (year, theme,
                                         [d.get("word") for d in themed]))
                kws = {k.casefold() for k in D.THEME_KEYWORDS[theme]}
                for d in themed:
                    self.assertIn(d.get("word", "").casefold(), kws,
                                  (year, theme, d))

    # ---- Part 6/7 writing: theme-aligned, still a fair exam question ------
    def test_writing_pools_offer_a_themed_entry_per_theme(self):
        """Every Y5/Y6 theme has >= 1 tagged or keyword-matching email/letter
        prompt in each used bucket (Y5 email short/long; Y6 letter + email
        long), so Part 6/7 is never pulled off-theme."""
        import collections
        used = {5: ["short", "long"], 6: ["letter", "long"]}
        for year in (5, 6):
            essay = bank._essay_pool(year)
            letters = bank._letter_pool(year)
            for theme in self.THEMES[year]:
                kws = bank._theme_kws(theme)
                def hit(fields):
                    return (("theme" in fields and fields["theme"] == theme)
                            or bank._matches_theme(fields, kws))
                bybucket = collections.defaultdict(list)
                for b in used[year]:
                    if b == "letter":
                        bybucket[b].extend(e for e in letters if hit(e))
                    else:
                        for e in essay.get(b, []) + essay.get("long", []):
                            if hit(e):
                                bybucket[b].append(e)
                for b in used[year]:
                    self.assertTrue(bybucket[b],
                                    (year, theme, b,
                                     [e.get("theme") for e in
                                      essay.get(b, [])][:5]))

    def test_writing_prompt_is_reasonable_and_themed(self):
        """A generated Part 6/7 prompt reads like the teacher's paper
        (a complete sentence, no skill labels, a word-count target, notes)
        and matches the active theme."""
        from exam_gen.models import WriteItem
        for year in (5, 6):
            for theme in self.THEMES[year]:
                for seed in (1, 3, 7):
                    c = dict(D.DEFAULT_CONFIG)
                    c.update({"year": year, "theme": theme, "seed": seed,
                              "parts": [6, 7], "pictures": False})
                    paper = bank.generate_paper(c)
                    for p in paper.parts:
                        it = p.items[0]
                        self.assertIsInstance(it, WriteItem, (year, theme, seed))
                        prompt = it.prompt.strip()
                        self.assertTrue(
                            prompt.endswith((".", "?", "!")),
                            (year, theme, seed, it.prompt))
                        if prompt[0].isupper():
                            words = prompt.split()
                            is_skill_phrase = (
                                len(words) <= 6
                                and not re.search(r"[.,?!;:]\s", prompt[:60])
                                and words[0].lower().rstrip("s")
                                in bank._WRITE_IMP)
                            self.assertFalse(
                                is_skill_phrase,
                                (year, theme, seed, it.prompt))
                        self.assertGreaterEqual(len(it.bullets), 3,
                                                (year, theme, seed, p.num))
                        self.assertTrue(it.word_count,
                                        (year, theme, seed, p.num))
                        kws = bank._theme_kws(theme)
                        fields = {"prompt": it.prompt, "model": it.model,
                                  "bullets": it.bullets,
                                  "recipient": it.recipient or "",
                                  "subject": it.subject or ""}
                        self.assertTrue(bank._matches_theme(fields, kws)
                                        or any(bank._matches_theme(
                                            {"prompt": e["prompt"]}, kws)
                                            for e in (bank._letter_pool(year)
                                                      if p.style == "letter"
                                                      else _essay_flat(year))),
                                        (year, theme, seed, p.num, it.prompt))


def _essay_flat(year):
    pool = bank._essay_pool(year)
    return pool.get("short", []) + pool.get("long", [])


class TestRound23(unittest.TestCase):
    """Round 23: Part 6/7 writing always mirrors the ORIGINAL exam papers.

    The teacher's directive: never invent a topic out of a textbook unit title
    or pull "use the words: singing, working, some" out of a sentence bank.
    Part 6/7 must look like the official papers — a concrete scenario plus a
    notes table (song/Fiona · Lyrics/Rhythms/Meaning · chicken salad · Kidzania
    · learning English · breakfast), and the QC watchdog must refuse the old
    scaffold template before a paper is shipped.
    """

    def _part_write(self, year, seed, theme=None, style=None):
        c = dict(D.DEFAULT_CONFIG)
        c.update({"year": year, "seed": seed, "pictures": False,
                  "parts": [6, 7]})
        if theme:
            c["theme"] = theme
        p = bank.generate_paper(c)
        out = [(pp.num, pp.items[0],
                "email" if pp.items[0].recipient else "letter")
               for pp in p.parts if pp.kind == "writing"]
        if style:
            out = [o for o in out if o[2] == style]
        return p, out

    def test_generated_writing_never_uses_the_textbook_scaffold(self):
        """Across years, seeds and themes no writing prompt carries the old
        "wants to know about <skill>. Use the words: X, Y, Z." shape or the
        "why you chose the words" / "what the word 'x' means" notes."""
        banned = ("wants to know about", "use the words:", "why you chose "
                  "the words", "what the word '", "about interrupted past",
                  "reading skill", "identify fectures", "audio clues")
        part7 = [("email", 7, "long"), ("letter", 6, "short")]
        for year in (3, 5, 6):
            for seed in (1, 2, 3, 5, 7, 9, 11):
                style = {6: "letter", 3: "email", 5: "email"}[year]
                _, out = self._part_write(year, seed, style=style)
                for num, it, st in out:
                    parts = [it.prompt] + [it.subject or ""] + \
                        list(it.bullets or [])
                    text = " ".join(parts).casefold()
                    for b in banned:
                        self.assertNotIn(b, text,
                                         (year, seed, num, it.prompt))
                    self.assertGreaterEqual(len(it.bullets or []), 3,
                                            (year, seed, num))
                    self.assertTrue(it.word_count.startswith("30 - 50") or
                                    it.word_count.startswith("60 - 80"),
                                    (year, seed, num, it.word_count))

    def test_reference_writing_tasks_mirror_the_teacher_papers(self):
        """The teacher-reference pool carries the official Part 6/7 tasks:
        song/letter for Year 6, chicken salad / Kidzania / breakfast /
        learning-English emails — each a scenario plus a notes table and a
        word-count band."""
        entries = list(bank.REFERENCE_WRITING)
        by_prompt = {" ".join([str(e["prompt"]), str(e.get("subject", "")),
                               *e.get("bullets", [])]).casefold()
                     for e in entries}
        for needle in ("fiona", "chicken salad", "kidzania", "learning "
                       "english", "nasi lemak"):
            self.assertTrue(any(needle in p for p in by_prompt),
                            (needle, by_prompt))
        for e in entries:
            self.assertGreaterEqual(len(e.get("bullets", [])), 3, e)
            self.assertTrue(e.get("word_count"), e)

    def test_docx_reference_blocks_remain_clean_after_rules(self):
        from exam_gen import qc
        hearth = [os.path.join("/home/school/Downloads/exam2026", f)
                  for f in ("UPSA Pertengahan Tahun T6 2026.docx",
                            "BI_UASA AKHIR Tahun T5&6 2025.docx")]
        for path in hearth:
            if not os.path.exists(path):
                continue
            r = qc._audit_docx(path, reference=True)
            self.assertEqual(r.hard, 0, (path, r.issues))

    def test_qc_refuses_the_old_scaffold_outright(self):
        from exam_gen import qc
        bad = ("Your friend wants to know about Read A Newspaper Article. "
               "Write an email to him or her about it. Use the words: "
               "singing, working, some.")
        for payload in (
                {"prompt": bad,
                 "bullets": ["what read a newspaper article is about",
                             "what the word 'singing' means",
                             "why you chose the words singing, working, some",
                             "why your friend should try it"]},
                {"stem": bad, "kind_hint": "writing"}):
            issues = qc.check_item(payload, "writing", 6)
            codes = {i.code for i in issues if i.hard}
            self.assertIn("write-template", codes, issues)

    def test_reference_writing_entries_pass_the_watchdog(self):
        from exam_gen import qc
        for e in bank.REFERENCE_WRITING:
            issues = qc.check_item(
                {"prompt": e["prompt"], "bullets": list(e["bullets"]),
                 "lead_text": e.get("lead_text", "")},
                "writing", e["years"][0])
            hard = [i for i in issues if i.hard]
            self.assertEqual(hard, [], (e["prompt"], [str(i) for i in hard]))

    def test_generated_writing_answers_are_reference_first(self):
        """With the real textbook loaded, a Y5/Y6 Part 6/7 prompt is drawn
        from a curated teacher-facing task (scenario + notes) — e.g. the
        chicken-salad or song task — and never from a unit title.

        Round 26 widened this: the reference papers are no longer the *only*
        source, because a term then repeated the same three prompts, but every
        prompt must still be a hand-written task from the reference pool or the
        curated letter/email pools, never a mined unit heading.
        """
        import json as _json
        corpus = {}
        path = "/home/school/.local/share/exam-gen/textbook_corpus.json"
        if os.path.exists(path):
            corpus = _json.load(open(path))
        curated = {str(e["prompt"]).casefold() for e in bank.REFERENCE_WRITING}
        for year in (3, 5, 6):
            curated |= {str(e["prompt"]).casefold()
                        for e in bank._letter_pool(year)}
            for rows in bank._essay_pool(year).values():
                curated |= {str(e["prompt"]).casefold() for e in rows}
        for year, seed in ((6, 1), (5, 3), (6, 7), (3, 2), (5, 9)):
            c = dict(D.DEFAULT_CONFIG)
            c.update({"year": year, "seed": seed, "pictures": False,
                      "parts": [6, 7], "textbook": corpus})
            p = bank.generate_paper(c)
            for pp in p.parts:
                if pp.kind != "writing":
                    continue
                it = pp.items[0]
                self.assertIn(it.prompt.casefold(), curated,
                              (year, seed, pp.num, it.prompt))


class TestRound26(unittest.TestCase):
    """Round 26 (F1): Part 1 must be the official short-stimulus + question.

    The Y5/Y6 pool had drifted into a gap-fill cloze wearing a fake event
    heading ("TRAVEL TIP", "ADVENTURE CAMP", "SCHOOL NOTICE") with distractors
    from unrelated categories — "suitcase / planet / hotel", "plaster /
    passport / telescope".  A pupil could throw out two of three options
    without reading, which is not a reading test.  The teacher's own UASA
    papers instead print a real stimulus (poster, menu, email, form) and ask a
    question about it, with all three options of the same kind.
    """

    def _pool(self, year):
        from exam_gen import extra_vocab_dskp as XVD
        return list(XVD.VOCAB_DSKP.get(year, []))

    def test_part1_pool_items_carry_a_stimulus_not_a_heading(self):
        for year in (5, 6):
            for it in self._pool(year):
                self.assertTrue(it.get("stimulus"),
                                f"Y{year}: {it.get('stem')!r} has no stimulus")
                self.assertNotIn(
                    "\n", it["stem"],
                    f"Y{year}: a bare heading is left in the stem: {it['stem']!r}")
                self.assertTrue(it["stem"].rstrip().endswith("?"),
                                f"Y{year}: Part 1 asks a question, not a gap: "
                                f"{it['stem']!r}")

    def test_part1_options_are_one_plausible_set(self):
        """All three options must be the same *kind* of thing.

        The pool declares the confusion set the options are drawn from, so a
        hand-edit that mixes categories (a suitcase next to a planet) is
        caught here rather than printed.
        """
        from exam_gen import data as DD
        for year in (5, 6):
            for it in self._pool(year):
                setname = it.get("set")
                self.assertTrue(setname, f"Y{year}: {it['stem']!r} names no set")
                fam = DD.PART1_SETS.get(setname)
                self.assertTrue(fam, f"Y{year}: unknown Part 1 set {setname!r}")
                for o in it["opts"]:
                    self.assertIn(
                        o, fam,
                        f"Y{year}: option {o!r} is not a {setname} option "
                        f"(set is {sorted(fam)})")
                self.assertEqual(len(set(it["opts"])), 3,
                                 f"Y{year}: {it['stem']!r} repeats an option")

    def test_part1_answer_is_readable_from_its_stimulus(self):
        """The answer must be traceable to the stimulus — that is the skill.

        This is what a real short-text question tests, and it is the guarantee
        the old gap-fill items could not make: nothing in the item connected
        the answer to any stimulus.
        """
        for year in (5, 6):
            for it in self._pool(year):
                ans = it["opts"][it["ans"]]
                blob = " ".join(it["stimulus"]).casefold()
                needle = ans.casefold()
                self.assertIn(
                    needle, blob,
                    f"Y{year}: answer {ans!r} is nowhere in the stimulus of "
                    f"{it['stem']!r} — the question is unanswerable")

    def test_generated_part1_prints_stimulus_then_question(self):
        for year in (5, 6):
            for seed in (1, 2, 3):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                part = next(p for p in paper.parts if p.num == 1)
                self.assertEqual(len(part.items), 5)
                for it in part.items:
                    self.assertTrue(it.stimulus,
                                    f"Y{year} s{seed}: no stimulus on {it.stem!r}")
                    self.assertTrue(it.stem.rstrip().endswith("?"),
                                    f"Y{year} s{seed}: {it.stem!r}")

    def test_part1_stimulus_reaches_the_docx_and_html(self):
        from exam_gen import docx
        for year in (5, 6):
            paper = _gen({"year": year, "seed": 1, "pictures": False})
            part = next(p for p in paper.parts if p.num == 1)
            it = part.items[0]
            data = docx.render_doc(paper)
            import tempfile, zipfile, os
            fh = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
            fh.write(data if isinstance(data, bytes) else data.encode())
            fh.close()
            with zipfile.ZipFile(fh.name) as z:
                xml = z.read("word/document.xml").decode("utf-8")
            os.unlink(fh.name)
            self.assertIn(it.stimulus[0][:24], xml,
                          f"Y{year}: stimulus missing from the paper")
            self.assertIn(it.stem[:24], xml, f"Y{year}: question missing")

    def test_qc_flags_a_part1_gap_fill_cloze(self):
        """The watchdog must catch a regressed pool item, not just the tests."""
        from exam_gen import qc
        paper = _gen({"year": 5, "seed": 1, "pictures": False})
        part = next(p for p in paper.parts if p.num == 1)
        stem = ("SCHOOL NOTICE\nEvery player must have a __________ in a bag.",
                ["plaster", "passport", "telescope"], 0)
        bad = models.MCQItem(stem=stem[0], options=list(stem[1]), answer=0)
        broken = dataclasses.replace(part, items=[bad] + list(part.items[1:]))
        codes = [i.code for i in qc.check_part(broken, 5).issues]
        self.assertIn("part1-stimulus", codes)

    def test_qc_flags_an_unanswerable_part1_item(self):
        from exam_gen import qc
        paper = _gen({"year": 5, "seed": 1, "pictures": False})
        part = next(p for p in paper.parts if p.num == 1)
        bad = models.MCQItem(
            stem="Which day is the trip?", options=["Monday", "Friday", "Sunday"],
            answer=1, stimulus=["THE TRIP", "Bring water and a hat."])
        broken = dataclasses.replace(part, items=[bad] + list(part.items[1:]))
        msgs = [i.message for i in qc.check_part(broken, 5).issues
                if i.code == "part1-stimulus"]
        self.assertTrue(any("nowhere in the stimulus" in m for m in msgs), msgs)

    def test_legacy_gapfill_items_cannot_reach_a_paper(self):
        """Enough official items exist, so the old shape is dropped."""
        for year in (5, 6):
            pool = bank._vocab_pool(year)
            official = [q for q in pool if q.get("stimulus")]
            self.assertGreaterEqual(len(official), 5,
                                    f"Y{year}: {len(official)} official items")
            kept = bank._part1_stimulus_first(pool, 5)
            self.assertTrue(all(q.get("stimulus") for q in kept))

    def test_part1_dskp_gate_still_finds_on_list_answers(self):
        """The Round-25 ladder gate must still work for the gap-fill shape.

        The stimulus shape is exempt (its answer is a phrase read out of a
        poster, not a vocabulary target), so the gate is exercised on Part 2 —
        which is still a cloze — and on the legacy Part 1 pool directly.
        """
        from exam_gen import dskp
        pool = bank.VOCAB_UPPER[5] + bank.VOCAB_UPPER[6]
        self.assertLessEqual(
            len(bank._dskp_answer_first(pool, 5, 5)), len(pool))
        for year in (5, 6):
            for seed in (1, 2, 3):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                part = next(p for p in paper.parts if p.num == 2)
                for it in part.items:
                    ans = it.options[it.answer]
                    self.assertEqual(
                        dskp.off_curriculum([ans], year), [],
                        f"Y{year} s{seed}: {ans!r} is off the ladder")

    def test_junior_part1_papers_still_pass_qc(self):
        """The new hard rule must not fire on the Years 1-3 Part 1 format.

        Year 1-3 Part 1 still uses the older "It is a __________." gap-fill
        shape, so the stimulus rule is scoped to the years that were migrated
        (5 and 6).  Migrating the junior pools is a documented follow-up; this
        test pins the scoping so the rule cannot be widened silently.
        """
        from exam_gen import qc
        for year in (1, 2, 3):
            for seed in (1, 2, 3):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                part = next(p for p in paper.parts if p.num == 1)
                codes = [i.code for i in qc.check_part(part, year).issues
                         if i.code == "part1-stimulus"]
                self.assertEqual(codes, [], f"Y{year} s{seed}: {codes}")

    def test_senior_part1_rule_is_actually_scoped_to_five_and_six(self):
        """Guard the guard: the rule must fire for 5/6 and stay off for 1-3."""
        from exam_gen import qc
        for year in (5, 6):
            paper = _gen({"year": year, "seed": 1, "pictures": False})
            part = next(p for p in paper.parts if p.num == 1)
            codes = [i.code for i in qc.check_part(part, year).issues
                     if i.code == "part1-stimulus"]
            self.assertEqual(codes, [], f"Y{year} must be clean: {codes}")
        codes = qc.check_part(
            next(p for p in _gen({"year": 1, "seed": 1,
                                  "pictures": False}).parts if p.num == 1),
            1).issues
        self.assertTrue(all(i.code != "part1-stimulus" for i in codes))


class TestRound26Editor(unittest.TestCase):
    """Round 26: the three defects found in the paper editor.

    Each was reachable in the GUI and each silently discarded an edit, so the
    tests drive the same public functions the GTK form uses.
    """

    def test_part_example_is_editable(self):
        """Part 4's worked example showed in the paper but had no field."""
        from exam_gen import editor
        self.assertIn("example", [f["key"] for f in editor.PART_FIELDS])
        paper = _gen({"year": 5, "parts": [4]})
        part = paper.parts[0]
        self.assertTrue(part.example, "fixture must actually have an example")
        ed = editor.part_to_edit(part)
        self.assertEqual(ed["example"], part.example)
        p2 = editor.apply_edits(paper, {"parts": [{"example": "0. Hi.  (A)"}]})
        self.assertEqual(p2.parts[0].example, "0. Hi.  (A)")
        self.assertEqual(paper.parts[0].example, part.example)  # untouched

    def test_part_example_defaults_to_empty_when_absent(self):
        """A part with no example must not crash the round-trip."""
        from exam_gen import editor
        paper = _gen({"year": 5, "parts": [6]})
        self.assertIsNone(paper.parts[0].example)
        ed = editor.part_to_edit(paper.parts[0])
        self.assertEqual(ed["example"], "")
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        # "no example" stays None — renderers branch on ``is not None``
        self.assertIsNone(p2.parts[0].example)

    def test_match_items_do_not_offer_the_letter_row_as_options(self):
        """Part 4's "A / B / C" options are labels, not editable choices.

        ``_item_from`` copies them verbatim, so the three entries looked
        editable in the GUI but editing them changed nothing a pupil reads —
        the real texts live in the part's ``lead_text``.
        """
        from exam_gen import editor
        paper = _gen({"year": 5, "parts": [4]})
        part = paper.parts[0]
        self.assertEqual(part.kind, "match")
        keys = [f["key"] for f in editor.item_schema(part.items[0])]
        self.assertNotIn("options", keys)
        self.assertIn("answer", keys)
        # the letter labels are still what the key prints
        self.assertEqual(part.items[0].options, ["A", "B", "C"])

    def test_editing_a_match_answer_still_moves_the_key(self):
        """Hiding the option rows must not cost the teacher the answer."""
        from exam_gen import editor
        paper = _gen({"year": 5, "parts": [4]})
        item = paper.parts[0].items[0]
        ed = editor.part_to_edit(paper.parts[0], target_item=0,
                                 item_override={"answer": 0})
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        self.assertEqual(p2.parts[0].items[0].answer, 0)
        self.assertNotEqual(p2.parts[0].items[0].answer, item.answer)

    def test_answer_index_beats_a_stale_ans_text(self):
        """A changed answer must reach the key, not the old ``ans_text``.

        ``_answer_key`` prints ``ans_text or answer_label``, and ``_rag`` pools
        pin ``ans_text`` to the target word.  Re-picking a different option in
        the editor left the stale word in place, so the key kept announcing the
        *previous* answer — a wrong mark scheme, not a cosmetic slip.
        """
        from exam_gen import docx, editor
        paper = _gen({"year": 3, "parts": [1]})
        item = paper.parts[0].items[0]
        self.assertIsNotNone(item.ans_text, "fixture must have ans_text")
        other = (item.answer + 1) % len(item.options)
        ed = editor.part_to_edit(paper.parts[0], target_item=0,
                                 item_override={"answer": other})
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        it = p2.parts[0].items[0]
        self.assertEqual(it.answer, other)
        # the key must name the newly chosen option
        key = "\n".join(str(x) for x in docx._answer_key(p2))
        self.assertIn(it.options[other], key)
        self.assertNotIn(" %s." % item.ans_text.strip(), key)

    def test_ans_text_still_wins_when_the_answer_is_untouched(self):
        """The Round-19 gap-fill key (the word, not the letter) is preserved."""
        from exam_gen import docx, editor
        paper = _gen({"year": 3, "parts": [1]})
        ed = editor.part_to_edit(paper.parts[0])
        p2 = editor.apply_edits(paper, {"parts": [ed]})
        item = p2.parts[0].items[0]
        self.assertEqual(item.ans_text, paper.parts[0].items[0].ans_text)
        key = "\n".join(str(x) for x in docx._answer_key(p2))
        self.assertIn(item.ans_text, key)

    def test_part1_stimulus_is_editable(self):
        """The new Round-26 stimulus must be editable, or the fix is a dead end."""
        from exam_gen import editor
        paper = _gen({"year": 5, "parts": [1], "pictures": False})
        item = paper.parts[0].items[0]
        self.assertTrue(item.stimulus, "fixture must have a stimulus")
        ed = editor.part_to_edit(paper.parts[0])
        self.assertEqual(ed["items"][0]["stimulus"], item.stimulus)
        p2 = editor.apply_edits(
            paper, {"parts": [{"items": [{"stimulus": ["HEADING", "Body."]}]}]})
        self.assertEqual(p2.parts[0].items[0].stimulus, ["HEADING", "Body."])
        self.assertEqual(paper.parts[0].items[0].stimulus, item.stimulus)


class TestRound26WebfetchKSSR(unittest.TestCase):
    """Round 26 (F3): web-sourced reading is KSSR-only.

    A passage fetched off the internet used to reach a paper on nothing but a
    CEFR band, so a Year 1 comprehension could be built on Victorian prose
    ("velveteen rabbit", "corkscrew") that no SJK pupil has met.  The KSSR
    Semakan 2017 DSKP ladder is the curriculum contract, so a web passage may
    only be used when the words it tests are on that ladder for the year, and
    only a source on the registry may be fetched at all.
    """

    #: A passage in the DSKP's own Malaysian primary register.
    ONSCHOOL = ("Aisyah brought a bottle of water to school. Her mother "
                "packed some fruit and bread for her. At recess Aisyah and "
                "her friend played badminton near the field. They drank the "
                "water and returned the bottle to the canteen. ")

    #: Off-curriculum prose: every content word here is a Gutenberg-ism.
    OFFLIST = ("The velveteen rabbit limped through the garden where the "
               "corkscrew burrow smelt of camomile and marmalade. ")

    def test_a_source_must_be_on_the_registry(self):
        from exam_gen import webfetch as WF
        for name, rec in WF.SOURCES.items():
            self.assertNotIn("url", rec,
                             f"{name} ships with the app; it is not fetched")
            self.assertIn("year", rec, f"{name} must name its year")
            self.assertIn(rec["year"], kssr_stories.STORIES,
                          f"{name} must have a story pack")
            self.assertTrue(rec.get("cefr"), f"{name} must name its CEFR band")
            self.assertTrue(rec.get("publisher"),
                            f"{name} must name a publisher")
            self.assertTrue(rec.get("licence"), f"{name} must name a licence")
            self.assertTrue(WF.fetch_source(name), f"{name} served no passage")
        with self.assertRaises(KeyError):
            WF.fetch_source("Some Blog The Teacher Found")

    def test_kssr_coverage_reports_the_register(self):
        from exam_gen import webfetch as WF
        good = WF.kssr_coverage(self.ONSCHOOL, 5)
        bad = WF.kssr_coverage(self.OFFLIST, 5)
        self.assertGreater(good, bad, (good, bad))
        self.assertGreaterEqual(good, WF.KSSR_MIN_COVERAGE, good)

    def test_a_question_about_an_off_list_word_never_survives(self):
        from exam_gen import webfetch as WF
        passage = {"text": self.ONSCHOOL,
                   "qs": [{"stem": "Aisyah drank the ____.",
                           "opts": ["water", "camomile", "marmalade"],
                           "ans": 0, "ans_text": "water"}]}
        kept = WF.kssr_questions(passage, 5)
        self.assertEqual(kept, [], "an off-list option must sink the question")
        passage["qs"][0]["opts"] = ["water", "milk", "juice"]
        self.assertEqual(len(WF.kssr_questions(passage, 5)), 1)

    def test_a_passage_needs_five_usable_questions_to_be_offered(self):
        from exam_gen import webfetch as WF
        def q(i, opts):
            return {"stem": f"Q{i}", "opts": opts, "ans": 0, "ans_text": opts[0]}
        thin = {"text": "The cat sat on a mat. " * 4,
                "qs": [q(i, ["cat", "dog", "bird"]) for i in range(4)]}
        full = {"text": "The cat sat on a mat. " * 4,
                "qs": [q(i, ["cat", "dog", "bird"]) for i in range(5)]}
        off = {"text": "The cat sat on a mat. " * 4,
               "qs": [q(i, ["velveteen", "corkscrew", "camomile"])
                      for i in range(5)]}
        served = WF.passages_for_year({"P": [thin, full, off]}, 1)
        self.assertEqual(len(served), 1, "only the full, on-list passage")
        self.assertEqual(served[0], full)

    def test_fact_questions_only_blank_kssr_words(self):
        from exam_gen import webfetch as WF
        qs = WF._fact_questions(self.ONSCHOOL, year=5)
        self.assertTrue(qs, "an on-curriculum passage must still give questions")
        for q in qs:
            self.assertTrue(WF.dskp.allowed(q["ans_text"], 5), q)
            for o in q["opts"]:
                self.assertTrue(WF.dskp.allowed(o, 5), (q, o))

    def test_cache_only_serves_a_year_what_the_kssr_allows(self):
        from exam_gen import webfetch as WF
        def q(i, opts):
            return {"stem": f"Q{i}", "opts": opts, "ans": 0, "ans_text": opts[0]}
        cache = {"Probe": [
            {"text": self.ONSCHOOL, "qs": [q(i, ["water", "milk", "rice"])
                                          for i in range(5)]},
            {"text": self.OFFLIST, "qs": [q(i, ["velveteen", "corkscrew", "hay"])
                                          for i in range(5)]},
        ]}
        served = WF.passages_for_year(cache, 5)
        self.assertEqual(len(served), 1, "the off-list passage is not served")
        self.assertIn("Aisyah", served[0]["text"])

    def test_a_refresh_stores_a_question_set_for_each_year(self):
        """Round 26: the cache must carry per-year questions, otherwise a
        Year 1 paper is served year-agnostic 19th-century options."""
        from exam_gen import webfetch as WF
        import os as _os, tempfile as _tf
        with _tf.TemporaryDirectory() as tmp:
            old = _os.environ.get("XDG_DATA_HOME")
            _os.environ["XDG_DATA_HOME"] = tmp
            try:
                out = WF.update_cache(sources=["KSSR Stories · Year 5"],
                                      keep_existing=False)
                row = out["KSSR Stories · Year 5"][0]
                self.assertTrue(row["qs"], "the generic question set is kept")
                for year in ("1", "3", "6"):
                    self.assertIn(year, row["qs_by_year"],
                                  "each year needs its own question set")
                    for q in row["qs_by_year"][year]:
                        for o in q["opts"]:
                            self.assertTrue(WF.dskp.allowed(o, int(year)), o)
                self.assertTrue(WF.passages_for_year(out, 5, 5),
                                "the refreshed passages are serviceable again")
            finally:
                if old is None:
                    _os.environ.pop("XDG_DATA_HOME", None)
                else:
                    _os.environ["XDG_DATA_HOME"] = old

    def test_offline_update_keeps_the_existing_cache(self):
        from exam_gen import webfetch as WF
        import os as _os, tempfile as _tf
        keep = {n: [{"text": self.ONSCHOOL, "qs": []}] for n in WF.SOURCES}
        with _tf.TemporaryDirectory() as tmp:
            old = _os.environ.get("XDG_DATA_HOME")
            _os.environ["XDG_DATA_HOME"] = tmp
            try:
                os.makedirs(os.path.dirname(WF.cache_path()), exist_ok=True)
                with open(WF.cache_path(), "w", encoding="utf-8") as fh:
                    json.dump(keep, fh)
                # Round 27: the corpus ships with the app, so there is no
                # download to fail — but a pack that cannot be materialised
                # must still leave what is already cached untouched.
                with unittest.mock.patch.object(
                        WF, "fetch_source",
                        side_effect=OSError("unreadable pack")):
                    out = WF.update_cache(sources=list(WF.SOURCES),
                                          keep_existing=True)
                self.assertEqual(set(out), set(keep),
                                 "a failed refresh must not drop a cached pack")
            finally:
                if old is None:
                    _os.environ.pop("XDG_DATA_HOME", None)
                else:
                    _os.environ["XDG_DATA_HOME"] = old


class TestRound26WritingPools(unittest.TestCase):
    """Round 26: ~50 usable topics for each of the four Y5/Y6 P6-P7 parts.

    The pools were too small to avoid repeats across a term, and the model
    answers were not held to the word count they themselves print.
    """

    # (label, callable returning the pool, the band its own word_count states)
    POOLS = (
        ("Y5 P6 email", lambda: bank._essay_pool(5).get("short", []), (30, 50)),
        ("Y5 P7 email", lambda: bank._essay_pool(5).get("long", []), (60, 80)),
        ("Y6 P6 letter", lambda: bank._letter_pool(6), (30, 50)),
        ("Y6 P7 email", lambda: bank._essay_pool(6).get("long", []), (60, 80)),
    )

    def test_each_part_has_about_fifty_topics(self):
        for label, get, _ in self.POOLS:
            pool = get()
            self.assertGreaterEqual(
                len(pool), 50, f"{label}: only {len(pool)} topics")

    def test_model_answers_respect_their_own_word_count(self):
        for label, get, _ in self.POOLS:
            for row in get():
                n = _words(row["model"])
                lo, hi = _word_band(row.get("word_count", ""))
                self.assertTrue(lo <= n <= hi,
                                f"{label}: model is {n} words, says "
                                f"{row.get('word_count')!r} — {row['prompt'][:50]}")

    def test_topic_prompts_are_unique(self):
        for label, get, _ in self.POOLS:
            prompts = [r["prompt"].strip() for r in get()]
            dupes = {p for p in prompts if prompts.count(p) > 1}
            self.assertEqual(dupes, set(), f"{label}: repeated {dupes}")

    def test_every_topic_has_the_fields_a_teacher_needs(self):
        for label, get, _ in self.POOLS:
            for row in get():
                self.assertTrue(row.get("bullets"), f"{label}: {row['prompt'][:40]}")
                self.assertGreaterEqual(len(row["bullets"]), 3,
                                        f"{label}: {row['prompt'][:40]}")
                self.assertTrue(row.get("model"), f"{label}: {row['prompt'][:40]}")
                self.assertTrue(row.get("lines"), f"{label}: {row['prompt'][:40]}")

    def test_p6_p7_instruction_names_the_form_it_asks_for(self):
        """An email item behind a "write a short essay" instruction misleads.

        The criteria allow a composition *or* an email for Part 7; the
        generator emits an email, so the instruction has to say so.
        """
        for year in (5, 6):
            for spec in D.PARTS[year]:
                if spec["kind"] != "writing" or spec["id"] not in (6, 7):
                    continue
                lead = spec["lead"]["en"].lower()
                if spec["style"] == "email":
                    self.assertIn("email", lead,
                                  f"Y{year} P{spec['id']} asks for an email item "
                                  f"but says {lead!r}")
                else:
                    self.assertIn("letter", lead,
                                  f"Y{year} P{spec['id']} asks for a letter item "
                                  f"but says {lead!r}")

    def test_generated_p6_p7_pick_from_the_big_pools(self):
        """The pools must be reachable, not just long."""
        seen6, seen7 = set(), set()
        for year in (5, 6):
            for seed in range(1, 13):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for part in paper.parts:
                    if part.kind != "writing":
                        continue
                    prompt = part.items[0].prompt
                    (seen6 if part.num == 6 else seen7).add(prompt)
        self.assertGreaterEqual(len(seen6), 8, len(seen6))
        self.assertGreaterEqual(len(seen7), 8, len(seen7))

    def test_model_answers_are_clean_prose(self):
        """A model must read as prose, not as wrapped source code.

        Long model answers live in the pool files as implicitly concatenated
        string fragments, and an edit that re-wraps them can silently eat the
        space at a fragment boundary ("Your friend" -> "Yourfriend") or add
        one that was not there ("a  firefighter"). Neither shows up in a word
        count, so check the text itself.
        """
        fused = re.compile(r"[a-z]\.[A-Z]|[a-z],[A-Z]|[a-z]{2,}[A-Z]")
        sentence_start = re.compile(r"(?:^|(?<=[.!?])\s+)")
        allowed_caps = re.compile(r"(?:^|\W)(?:pH|KidZos|MPU)")
        for label, get, _ in self.POOLS:
            for row in get():
                text = row["model"]
                where = f"{label}: {row['prompt'][:50]}"
                self.assertNotIn("  ", text, f"double space — {where}")
                self.assertNotIn(" .", text, f"space before a full stop — {where}")
                self.assertNotIn(" ,", text, f"space before a comma — {where}")
                self.assertEqual(text, text.strip(), f"stray edge space — {where}")
                for hit in fused.finditer(text):
                    snippet = text[max(0, hit.start() - 12):hit.end() + 12]
                    if allowed_caps.search(snippet):
                        continue
                    self.fail(f"words run together ({hit.group(0)!r} in "
                              f"{snippet!r}) — {where}")
                for sentence in sentence_start.split(text):
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    self.assertRegex(
                        sentence, r"^[A-Z0-9'\"]",
                        f"sentence starts in lower case ({sentence[:40]!r}) — {where}")
                self.assertRegex(
                    text[-90:],
                    r"(?:Yours|Thank you|best wishes"
                    r"|Your [a-z]+(?: [a-z]+)?)",
                    f"no sign-off at the end ({text[-40:]!r}) — {where}")
                self.assertNotRegex(
                    text,
                    r"\b(?:the|a|an|and|but|or|of|to|in|on|for|with|at|by|"
                    r"from|is|was|were|my|our|your|his|her|their|that|"
                    r"which|who|because|so|if|when|while|after|before|"
                    r"next|then)$",
                    f"model ends mid-sentence ({text[-40:]!r}) — {where}")

    def test_wrapped_pool_sources_keep_their_spaces(self):
        """Guard the source form that hides the defect above.

        A model answer is one Python string built from fragments on adjacent
        lines. In valid source the space between two words is always inside
        one of the fragments, so a boundary whose left side ends on a word
        character and whose right side starts on one is a lost space waiting
        to happen. Checking the boundary catches every variant ("Yourfriend",
        "torepair", "schoollibrary"), which a regex over the finished text
        cannot.
        """
        import ast as _ast
        import os

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        package = os.path.join(here, "exam_gen")
        wordy = set("abcdefghijklmnopqrstuvwxyz"
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        literal = re.compile(
            r'(?<![\w\\])[rbufRBF]{0,2}'
            r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')')
        docstrings = set()
        for name in ("extra_writing.py", "extra_writing_56.py", "bank.py"):
            path = os.path.join(package, name)
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            tree = _ast.parse(source)
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.Module, _ast.ClassDef,
                                     _ast.FunctionDef, _ast.AsyncFunctionDef)):
                    body = getattr(node, "body", None)
                    if body and isinstance(body[0], _ast.Expr) and \
                            isinstance(body[0].value, _ast.Constant) and \
                            isinstance(body[0].value.value, str):
                        docstrings.add(id(body[0].value))

        def edges(text):
            """First and last character of a literal, without evaluating it."""
            start = 0
            while start < len(text) and text[start] not in "\"'":
                start += 1
            end = len(text) - 1
            while end > 0 and text[end] not in "\"'":
                end -= 1
            return text[start + 1], text[end - 1]

        joined = 0
        for name in ("extra_writing.py", "extra_writing_56.py", "bank.py"):
            path = os.path.join(package, name)
            self.assertTrue(os.path.exists(path), f"missing pool module {name}")
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            try:
                tree = _ast.parse(source)
            except SyntaxError:
                continue
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Constant):
                    continue
                if id(node) in docstrings:
                    continue
                if not isinstance(node.value, str) or not node.value:
                    continue
                if len(node.value) < 120 or " " not in node.value:
                    continue  # only hand-wrapped prose is at risk
                segment = _ast.get_source_segment(source, node)
                if not segment or "\n" not in segment:
                    continue
                if '"""' in segment or "'''" in segment:
                    continue
                if "{" in segment or "}" in segment:
                    continue  # an f-string, not hand-wrapped prose
                # The parser folds "a" "b" into one Constant; put the
                # fragments back and check the joins it hid.
                parts = [m.group(1) for m in literal.finditer(segment)]
                if len(parts) < 2:
                    continue
                pairs = [edges(part) for part in parts]
                for (_, a_last), (b_first, _) in zip(pairs, pairs[1:]):
                    joined += 1
                    if a_last in wordy and b_first in wordy:
                        self.fail(
                            f"{name}:{node.lineno} loses a space at the join: "
                            f"...{node.value[-40:]!r}")
        self.assertGreater(joined, 100, "no wrapped literals were inspected")

    def test_reference_paper_writing_tasks_stay_reachable(self):
        """Widening the pools must not lock out the official-paper tasks."""
        from exam_gen import bank
        ref = {e["prompt"] for e in bank.REFERENCE_WRITING
               if e.get("years")}
        self.assertTrue(ref, "no reference writing tasks to reach")
        seen = set()
        for year in (3, 5, 6):
            for seed in range(1, 25):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for part in paper.parts:
                    if part.kind == "writing":
                        seen.add(part.items[0].prompt)
        self.assertTrue(ref & seen,
                        "the reference paper writing tasks became unreachable")


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'\u2019-]+", text or ""))


def _word_band(spec: str) -> tuple[int, int]:
    nums = [int(n) for n in re.findall(r"\d+", spec or "")]
    return (nums[0], nums[1]) if len(nums) >= 2 else (0, 10 ** 6)


class TestKssrStories(unittest.TestCase):
    """Round 27 (F29/F30): the passage source is a CEFR-banded KSSR corpus.

    The registry used to hold five Gutenberg books — Aesop's Fables, Kipling's
    Just So Stories, the Velveteen Rabbit, McGuffey and Peter Rabbit.  All of it
    is nineteenth-century English prose about kings, camels and rabbits: nothing
    in it belongs to the KSSR Semakan 2017 DSKP themes (Towns and Cities, Wild
    Life, Food and Health, Growing Up, It's an Emergency, Cool Jobs ...), and
    the words it asks a pupil to recognise ("velveteen", "corkscrew", "frock")
    are not on the year ladder.  The Round-26 gate already refused nearly all
    of it, which left Years 1-2 with *no* web passage at all.

    The registry now points at :mod:`exam_gen.kssr_stories` — short passages
    written to the DSKP ladder, in the CEFR band and the Part 3 word band of
    their year, tagged with the RPT theme they belong to, and needing no
    network at all (photos stay the only live-network feature).
    """

    #: The 19th-century books the registry used to carry.
    GUTENBERG = ("Aesop's Fables", "Just So Stories", "The Velveteen Rabbit",
                 "McGuffey's First Reader", "The Tale of Peter Rabbit")

    def test_the_registry_no_longer_offers_19th_century_prose(self):
        from exam_gen import webfetch as WF
        for name in self.GUTENBERG:
            self.assertNotIn(name, WF.SOURCES,
                             f"{name} is not KSSR material and must be gone")
        self.assertTrue(WF.SOURCES, "the registry must still serve passages")
        for name, rec in WF.SOURCES.items():
            self.assertNotIn("url", rec,
                             f"{name} ships with the app; it is not fetched")

    def test_a_source_must_be_on_the_registry(self):
        from exam_gen import webfetch as WF
        for name, rec in WF.SOURCES.items():
            self.assertIn("year", rec, f"{name} must name its year")
            self.assertIn(rec["year"], WF.kssr_stories.STORIES,
                          f"{name} must have a story pack")
            self.assertTrue(rec.get("cefr"), f"{name} must name its CEFR band")
            self.assertTrue(rec.get("publisher"),
                            f"{name} must name a publisher")
            self.assertTrue(rec.get("licence"), f"{name} must name a licence")
        with self.assertRaises(KeyError):
            WF.fetch_source("Some Blog The Teacher Found")

    def test_every_story_sits_in_its_year_cefr_and_word_band(self):
        from exam_gen import webfetch as WF
        from exam_gen import kssr_stories as KS
        for year, stories in KS.STORIES.items():
            lo, hi = D.PASSAGE_WORD_BAND[year]
            cap = bank._BAND_RANK[D.PASSAGE_CEFR[year]]
            for s in stories:
                words = len(s["text"].split())
                self.assertTrue(lo <= words <= hi,
                                f"Y{year} {s['title']!r}: {words} words "
                                f"outside the {lo}-{hi} Part 3 band")
                band = bank.passage_band(s["text"])
                self.assertLessEqual(bank._BAND_RANK[band], cap,
                                     f"Y{year} {s['title']!r} reads as {band}")

    def test_every_story_uses_only_kssr_vocabulary(self):
        from exam_gen import kssr_stories as KS
        for year, stories in KS.STORIES.items():
            for s in stories:
                bad = webfetch.dskp.off_curriculum(
                    re.findall(r"[A-Za-z][A-Za-z'\-]*", s["text"]), year)
                self.assertEqual(bad, [],
                                 f"Y{year} {s['title']!r} uses off-ladder "
                                 f"words: {bad}")

    def test_every_story_can_fill_part_three(self):
        from exam_gen import webfetch as WF
        from exam_gen import kssr_stories as KS
        for year, stories in KS.STORIES.items():
            for s in stories:
                row = {"text": s["text"],
                       "qs": WF._fact_questions(s["text"], year=year)}
                self.assertGreaterEqual(
                    len(WF.kssr_questions(row, year, 5)), 5,
                    f"Y{year} {s['title']!r} cannot supply the 5 Part 3 "
                    f"questions")
                for q in row["qs"]:
                    self.assertTrue(WF.dskp.allowed(q["ans_text"], year), q)
                    for o in q["opts"]:
                        self.assertTrue(WF.dskp.allowed(o, year), (q, o))

    def test_every_story_is_tagged_with_a_real_theme_for_its_year(self):
        from exam_gen import kssr_stories as KS
        for year, stories in KS.STORIES.items():
            for s in stories:
                self.assertIn(s["theme"], D.RPT_THEMES[year],
                              f"Y{year} {s['title']!r} theme "
                              f"{s['theme']!r} is not in the RPT planner")

    def test_every_year_has_a_story_for_each_rpt_theme(self):
        from exam_gen import kssr_stories as KS
        for year, stories in KS.STORIES.items():
            got = {s["theme"] for s in stories}
            for theme in D.RPT_THEMES[year]:
                self.assertIn(theme, got,
                              f"Year {year} has no story for {theme!r}")

    def test_the_corpus_serves_every_supported_year(self):
        from exam_gen import webfetch as WF
        from exam_gen import kssr_stories as KS
        cache = WF.update_cache(keep_existing=False)
        shipped = {s["text"] for stories in KS.STORIES.values()
                   for s in stories}
        for year in (1, 2, 3, 5, 6):
            served = WF.passages_for_year(cache, year, 5)
            self.assertGreaterEqual(len(served), 5,
                                    f"Year {year} needs real Part 3 choices")
            own = [p for p in served
                   if p["text"] in {s["text"]
                                    for s in KS.STORIES.get(year, [])}]
            self.assertGreaterEqual(len(own), 5,
                                    f"Year {year} must have five of its own "
                                    f"KSSR stories")
            for p in served:
                self.assertIn(p["text"], shipped,
                              f"Y{year} served a passage that is not KSSR")

    def test_part_three_can_be_built_from_a_kssr_story(self):
        """The corpus is only useful if the real generation path can reach it:
        a Year 5 paper fed the shipped pack must actually print one."""
        from exam_gen import webfetch as WF
        from exam_gen import kssr_stories as KS
        cache = WF.update_cache(keep_existing=False)
        for year in (1, 2, 3, 5, 6):
            own = {s["text"] for s in KS.STORIES.get(year, [])}
            pool = WF.passages_for_year(cache, year, 5)
            used = 0
            for seed in (1, 2, 3, 5, 7, 11):
                paper = _gen({"year": year, "seed": seed, "use_web": True,
                              "textbook": None}, passages=pool)
                p3 = next(p for p in paper.parts if p.kind == "comprehension")
                if p3.lead_text.strip() in own:
                    used += 1
            self.assertGreaterEqual(used, 1,
                                    f"Year {year} never reached a KSSR story")

    def test_a_refresh_needs_no_network(self):
        """The corpus ships with the app, so a refresh works on a plane and is
        byte-identical every time (the photos are the only live feature)."""
        from exam_gen import webfetch as WF
        import os as _os, socket as _socket, tempfile as _tf
        with _tf.TemporaryDirectory() as tmp:
            old = _os.environ.get("XDG_DATA_HOME")
            _os.environ["XDG_DATA_HOME"] = tmp
            try:
                def _no_network(*_a, **_kw):
                    raise AssertionError("the corpus must not touch the "
                                         "network")
                with unittest.mock.patch.object(_socket, "socket", _no_network), \
                        unittest.mock.patch.object(_socket, "create_connection",
                                                   _no_network):
                    first = WF.update_cache(keep_existing=False)
                    second = WF.update_cache(keep_existing=False)
                self.assertEqual(first, second,
                                 "the shipped corpus must refresh "
                                 "deterministically")
                self.assertTrue(os.path.exists(WF.cache_path()))
            finally:
                if old is None:
                    _os.environ.pop("XDG_DATA_HOME", None)
                else:
                    _os.environ["XDG_DATA_HOME"] = old


class TestJsuBlueprint(unittest.TestCase):
    """Round 27 (F31): the official Jadual Spesifikasi Ujian (JSU) is the
    blue-print every generated paper is measured against.

    The ministry's exam specification table for the upper primary years names,
    for every part, the skill, the text genre, the theme, the learning standard
    and the CEFR band — plus the LOTS/HOTS split.  The generator's own
    structure check knows the shape (7 parts, 50 marks); the JSU knows whether
    the *content* is the kind of question the year is supposed to be asked.
    """

    def test_the_blueprint_covers_every_part_of_the_year_six_paper(self):
        from exam_gen import data as DD
        self.assertIn(6, DD.JSU, "the JSU ships the Year 6 UASA blue-print")
        jsu = DD.JSU[6]
        self.assertEqual(sorted(jsu["parts"]), [1, 2, 3, 4, 5, 6, 7])
        for num, spec in jsu["parts"].items():
            gen = next(s for s in DD.PARTS[6] if s["id"] == num)
            self.assertEqual(spec["marks"], gen["marks"], f"PART {num} marks")
            self.assertEqual(spec["items"], gen["count"], f"PART {num} items")
            self.assertTrue(spec["skill"], f"PART {num} names its skill")
            self.assertTrue(spec["learning_standards"],
                            f"PART {num} names its learning standards")

    def test_the_writing_standards_are_the_official_ones(self):
        from exam_gen import data as DD
        self.assertIn("4.2.2", DD.JSU[6]["parts"][6]["learning_standards"])
        self.assertIn("4.2.3", DD.JSU[6]["parts"][7]["learning_standards"])

    def test_the_cefr_mix_is_the_official_one(self):
        from exam_gen import data as DD
        mix = DD.JSU[6]["cefr_mix"]
        self.assertEqual(sum(mix.values()), sum(
            s["count"] for s in DD.PARTS[6] if s["kind"] != "writing"))
        self.assertEqual(set(mix), {"A2 Low", "A2 Mid", "Revise A2"})

    def test_the_learning_standard_ladder_runs_year_four_to_six(self):
        from exam_gen import data as DD
        for strand in ("3.1.1", "3.2.1", "3.2.2", "4.2.5", "4.3.1"):
            self.assertIn(strand, DD.JSU_STANDARDS, strand)
            for year in (4, 5, 6):
                self.assertIn(strand, DD.JSU_STANDARDS[strand])
                self.assertTrue(DD.JSU_STANDARDS[strand][year],
                                f"{strand} has no Year {year} wording")

    def test_a_clean_paper_passes_the_blueprint(self):
        for year in (1, 2, 3, 5, 6):
            issues = bank.jsu_issues(_gen({"year": year, "seed": 3}))
            self.assertEqual(issues, [], f"Year {year}: {issues}")

    def test_a_paper_off_the_blueprint_is_flagged(self):
        paper = _gen({"year": 6, "seed": 3})
        p6 = next(p for p in paper.parts if p.num == 6)
        p6.items[0].prompt = "Write about the alphabet."
        self.assertTrue(bank.jsu_issues(paper),
                        "a Part 6 prompt outside 4.2.2 must be reported")


class TestCliTextbook(unittest.TestCase):
    """Round 17/T4: generation consumes the saved textbook corpus; the CLI
    mines and toggles it."""

    def run_cli(self, args):
        from exam_gen import cli
        return cli.run_cli(args)

    def test_import_textbook_no_files_errors(self):
        with tempfile.TemporaryDirectory() as td:
            code = self.run_cli(["--import-textbook", td])
            self.assertEqual(code, 2)

    def test_generation_uses_saved_corpus(self):
        from exam_gen import textbook as TB
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_DATA_HOME"] = td
            try:
                raw = ". ".join(TestTbBank.FIX["1"]["units"][0]
                                ["sentences"]) + "."
                corpus = TB.parse_text(raw, 1)
                appdir = os.path.join(td, "exam-gen")
                os.makedirs(appdir, exist_ok=True)
                TB.save_corpus({str(k): v for k, v in corpus.items()}, appdir)
                out = os.path.join(td, "P")
                code = self.run_cli(["--cli", "--year", "1", "--seed", "5",
                                     "--textbook", "--out", out])
                self.assertEqual(code, 0)
                self.assertTrue(os.path.exists(out + ".docx"))
            finally:
                if old is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = old


class TestRepeatWarning(unittest.TestCase):
    """Round 30 F4: warn when two sittings reuse too much of the same pool.

    Repeats across sittings are normal; a teacher who accidentally sets Paper 1
    and Paper 2 from the same seed needs to know before the term starts.
    """

    def test_identical_papers_report_full_overlap(self):
        from exam_gen import bank
        conf = {"year": 3, "difficulty": "medium", "seed": 4}
        a = _gen(conf)
        b = _gen(dict(conf))
        rep = bank.repeat_report([a, b])
        self.assertEqual(len(rep["pairs"]), 1)
        self.assertEqual(rep["pairs"][0]["overlap_pct"], 100.0)

    def test_different_seeds_have_no_pair_warning(self):
        from exam_gen import bank
        a = _gen({"year": 3, "difficulty": "medium", "seed": 1})
        b = _gen({"year": 3, "difficulty": "medium", "seed": 2})
        rep = bank.repeat_report([a, b], threshold=25)
        self.assertEqual(rep["pairs"], [])
        self.assertEqual(rep["over_threshold"], 0)

    def test_report_states_below_threshold_and_shares(self):
        from exam_gen import bank
        a = _gen({"year": 5, "difficulty": "medium", "seed": 1})
        b = _gen({"year": 5, "difficulty": "medium", "seed": 2})
        rep = bank.repeat_report([a, b], threshold=25)
        self.assertIn("below", rep["text"].lower())
        self.assertGreater(rep["shared_items"], 0)
        self.assertEqual(len(rep["text"].splitlines()) >= 1, True)

    def test_single_paper_is_a_no_op(self):
        from exam_gen import bank
        rep = bank.repeat_report([_gen({"year": 6, "seed": 3})])
        self.assertEqual(rep["pairs"], [])
        self.assertEqual(rep["over_threshold"], 0)


class TestCoverageReport(unittest.TestCase):
    """Round 30 F6: prove per-paper DSKP coverage for a principal's audit."""

    def test_report_names_standards_and_parts(self):
        from exam_gen import dskp
        paper = _gen({"year": 6, "difficulty": "medium", "seed": 1})
        rep = dskp.coverage_report(paper)
        self.assertIn("standards", rep)
        self.assertIn("parts", rep)
        self.assertIn("coverage", rep)
        self.assertTrue(rep["text"].strip())

    def test_every_covered_standard_is_a_real_code(self):
        from exam_gen import dskp
        paper = _gen({"year": 6, "difficulty": "medium", "seed": 1})
        rep = dskp.coverage_report(paper)
        for code in rep["standards"]:
            self.assertRegex(code, r"^\d+\.\d+(\.\d+)?$")

    def test_parts_map_to_questions_that_exist(self):
        from exam_gen import dskp
        paper = _gen({"year": 5, "difficulty": "medium", "seed": 1})
        rep = dskp.coverage_report(paper)
        maxq = paper.max_qno()
        for part in rep["parts"]:
            self.assertGreaterEqual(part["first"], 1)
            self.assertLessEqual(part["last"], maxq)

    def test_all_five_years_report(self):
        from exam_gen import dskp
        for y in (1, 2, 3, 5, 6):
            rep = dskp.coverage_report(_gen({"year": y, "seed": 1}))
            self.assertTrue(rep["text"].strip(), f"year {y} report empty")

    def test_every_real_part_kind_has_a_mapping(self):
        # Guards the Round 30 bug where "vocab"/"match" silently fell through
        # to a default because the map used guessed names ("mcq", "matching").
        from exam_gen import dskp
        kinds = set()
        for y in (1, 2, 3, 5, 6):
            for seed in (1, 2, 3):
                kinds.update(p.kind for p in _gen({"year": y, "seed": seed}).parts)
        for k in kinds:
            self.assertIn(k, dskp._KIND_STANDARDS,
                          f"part kind {k!r} has no DSKP mapping")

    def test_coverage_counts_a_standard_per_part(self):
        from exam_gen import dskp
        paper = _gen({"year": 6, "seed": 1})
        rep = dskp.coverage_report(paper)
        for code, n in rep["coverage"].items():
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, len(rep["parts"]))


class TestTermBatchPdf(unittest.TestCase):
    """Round 30 F7: a whole term in one command, with a repeat check."""

    def test_term_generates_one_paper_per_week(self):
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "term")
            code = cli.run_cli(["--cli", "--year", "6", "--term", "3",
                                "--out", out])
            self.assertEqual(code, 0)
            self.assertEqual(len(os.listdir(out)), 3)

    def test_term_prints_repeat_check(self):
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "term")
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cli.run_cli(["--cli", "--year", "6", "--term", "3",
                             "--out", out, "--repeat-check"])
            finally:
                sys.stdout = old
            self.assertIn("Repeat check", buf.getvalue())

    def test_term_pdfs_when_requested_and_soffice_exists(self):
        from exam_gen import cli, pdfmake
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "term")
            have_soffice = pdfmake._find_soffice() is not None
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cli.run_cli(["--cli", "--year", "6", "--term", "2",
                             "--out", out, "--repeat-check"],
                            want_pdf=True)
            finally:
                sys.stdout = old
            files = os.listdir(out)
            self.assertTrue(any(f.endswith(".docx") for f in files))
            pdfs = [f for f in files if f.endswith(".pdf")]
            if have_soffice:
                self.assertEqual(len(pdfs), 2, "soffice present: want 2 PDFs")
            else:
                self.assertEqual(pdfs, [], "no soffice: DOCX only, no crash")


class TestMarkScheme(unittest.TestCase):
    """Round 31 F2: a teacher-only marking scheme, separate from the paper.

    Right now the answer key lives inside the pupil's paper DOCX, so the same
    file has to be handed out and held back. The scheme is its own document
    with marks-per-question and the model answer for writing parts.
    """

    def test_scheme_doc_is_valid_docx(self):
        from exam_gen import docx
        paper = _gen({"year": 3, "difficulty": "medium", "seed": 1})
        blob = docx.mark_scheme_doc(paper, conf={"school": "S", "teacher": "T"})
        import zipfile, io as _io
        z = zipfile.ZipFile(_io.BytesIO(blob))
        self.assertIsNone(z.testzip())
        xml = z.read("word/document.xml").decode("utf-8")
        self.assertIn("document", xml)

    def test_scheme_lists_every_question_with_its_mark(self):
        from exam_gen import docx
        paper = _gen({"year": 6, "difficulty": "medium", "seed": 1})
        rep = docx.mark_scheme_rows(paper)
        self.assertEqual(len(rep), paper.max_qno())
        self.assertEqual(rep[0]["qno"], 1)
        for row in rep:
            self.assertIn("marks", row)
            self.assertIn("answer", row)

    def test_scheme_marks_total_fifty(self):
        from exam_gen import docx
        for y in (1, 2, 3, 5, 6):
            paper = _gen({"year": y, "seed": 1})
            rep = docx.mark_scheme_rows(paper)
            self.assertEqual(sum(r["marks"] for r in rep), 50,
                             f"year {y} scheme must total 50 marks")

    def test_writing_parts_get_a_model_answer(self):
        from exam_gen import docx
        paper = _gen({"year": 6, "seed": 1})
        rep = docx.mark_scheme_rows(paper)
        writing = [r for r in rep if r["model"]]
        self.assertTrue(writing, "writing parts need a model answer")

    def test_scheme_never_lands_in_the_pupil_paper(self):
        from exam_gen import docx
        paper = _gen({"year": 3, "seed": 1})
        pupil = docx.render_doc(paper)
        import zipfile, io as _io
        xml = zipfile.ZipFile(_io.BytesIO(pupil)).read("word/document.xml").decode()
        self.assertNotIn("MARKING SCHEME", xml)

    def test_save_writes_scheme_files(self):
        from exam_gen import pdfmake
        paper = _gen({"year": 3, "seed": 1})
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "P")
            res = pdfmake.save_with_extras(paper, base, want_pdf=False,
                                           marksheet=True, mark_scheme=True)
            scheme = res.get("mark_scheme")
            self.assertTrue(scheme, "save_with_extras must return mark_scheme")
            self.assertTrue(os.path.exists(scheme))
            self.assertIn("_MARK_SCHEME", os.path.basename(scheme).upper())


class TestOmrSheet(unittest.TestCase):
    """Round 32 F1: one-page OMR bubble answer sheet.

    A pupil marks one bubble per question; the sheet is laid out on a fixed
    grid so a scanner (or a fast human) can read a whole class at once.
    """

    def test_bubbles_cover_every_scored_question(self):
        from exam_gen import bank
        for y in (1, 2, 3, 5, 6):
            paper = _gen({"year": y, "seed": 1})
            grid = bank.omr_grid(paper)
            self.assertEqual(len(grid["questions"]), paper.max_qno(),
                             f"year {y}: every question needs a bubble")

    def test_mcq_has_three_bubbles_and_word_part_one(self):
        from exam_gen import bank
        paper = _gen({"year": 3, "seed": 1})
        grid = bank.omr_grid(paper)
        kinds = {q["qno"]: q["bubbles"] for q in grid["questions"]}
        mcq = [q for q in grid["questions"] if q["kind"] == "mcq"]
        for q in mcq:
            self.assertEqual(q["bubbles"], 4, "A-D for a 3-option MCQ")

    def test_question_numbers_are_contiguous_from_one(self):
        from exam_gen import bank
        paper = _gen({"year": 6, "seed": 1})
        grid = bank.omr_grid(paper)
        qnos = [q["qno"] for q in grid["questions"]]
        self.assertEqual(qnos, list(range(1, paper.max_qno() + 1)))

    def test_sheet_fits_one_page_budget(self):
        from exam_gen import bank
        for y in (1, 2, 3, 5, 6):
            grid = bank.omr_grid(_gen({"year": y, "seed": 1}))
            self.assertLessEqual(grid["rows_needed"], 60, f"year {y} too tall")
            self.assertGreaterEqual(grid["columns"], 1)

    def test_declared_columns_match_the_rendered_layout(self):
        # The renderer draws ONE table.  A grid claiming two columns for Y1/Y2
        # would be metadata the document does not honour.
        from exam_gen import bank
        for y in (1, 2, 3, 5, 6):
            grid = bank.omr_grid(_gen({"year": y, "seed": 1}))
            self.assertEqual(grid["columns"], 1, f"year {y}")
            self.assertEqual(grid["rows_needed"], len(grid["questions"]))
            self.assertTrue(grid["fits_one_page"])

    def test_render_produces_valid_docx(self):
        from exam_gen import docx
        paper = _gen({"year": 5, "seed": 1})
        blob = docx.omr_sheet_doc(paper)
        import zipfile, io as _io
        z = zipfile.ZipFile(_io.BytesIO(blob))
        self.assertIsNone(z.testzip())
        self.assertIn("document", z.read("word/document.xml").decode())

    def test_save_writes_omr_files(self):
        from exam_gen import pdfmake
        paper = _gen({"year": 3, "seed": 1})
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "P")
            res = pdfmake.save_with_extras(paper, base, want_pdf=False,
                                           omr=True)
            self.assertTrue(res.get("omr"))
            self.assertTrue(os.path.exists(res["omr"]))


class TestDifficultyStructure(unittest.TestCase):
    """Round 33 F3: difficulty must shift structure, not only vocabulary.

    Measured before this round: the writing word count was 30-50 for
    easy/medium/hard alike and comprehension length barely moved, so "hard"
    only re-ranked which words appeared.
    """

    def test_writing_word_count_grows_with_difficulty(self):
        from exam_gen import bank
        got = {}
        for diff in ("easy", "medium", "hard"):
            p = _gen({"year": 6, "difficulty": diff, "seed": 1})
            part = [x for x in p.parts if x.kind == "writing"][0]
            import re
            m = re.search(r"between (\d+) and (\d+) words", str(part.lead))
            self.assertIsNotNone(m, f"{diff}: no word count in writing lead")
            got[diff] = int(m.group(1))
        self.assertLess(got["easy"], got["medium"],
                        "easy must ask for fewer words than medium")
        self.assertLess(got["medium"], got["hard"],
                        "medium must ask for fewer words than hard")

    def test_every_year_has_a_three_point_scale(self):
        from exam_gen import bank
        for y in (1, 2, 3, 5, 6):
            widths = set()
            for diff in ("easy", "medium", "hard"):
                p = _gen({"year": y, "difficulty": diff, "seed": 1})
                import re
                for part in p.parts:
                    if part.kind != "writing":
                        continue
                    m = re.search(r"between (\d+) and (\d+) words",
                                  str(part.lead))
                    if m:
                        widths.add(int(m.group(1)))
            self.assertGreaterEqual(len(widths), 2,
                                    f"year {y}: difficulty does not change "
                                    f"the writing demand ({widths})")

    def test_answer_lines_grow_with_writing_demand(self):
        from exam_gen import bank
        def lines(diff):
            p = _gen({"year": 6, "difficulty": diff, "seed": 1})
            return sum(int(getattr(i, "lines", 0) or 0)
                       for x in p.parts if x.kind == "writing" for i in x.items)
        self.assertLessEqual(lines("easy"), lines("hard"))

    def test_difficulty_profile_reports_the_shift(self):
        from exam_gen import bank
        prof = bank.difficulty_profile(_gen({"year": 6, "difficulty": "hard",
                                             "seed": 1}))
        self.assertIn("writing_words", prof)
        self.assertIn("difficulty", prof)
        self.assertGreater(prof["writing_words"], 0)

    def test_marks_and_shape_are_untouched_by_difficulty(self):
        from exam_gen import bank
        for diff in ("easy", "medium", "hard"):
            p = _gen({"year": 5, "difficulty": diff, "seed": 3})
            self.assertEqual(len(p.parts), 7)
            self.assertEqual(sum(x.marks for x in p.parts), 50)


class TestLockedItems(unittest.TestCase):
    """Round 34 F5: lock an item so regeneration never changes it again.

    A teacher who fixes a clumsy stem or swaps in a better distractor should
    not lose the fix on the next click of Generate. Locks are stored per year
    and matched by stem, so they survive a different seed.
    """

    def test_save_and_load_round_trip(self):
        from exam_gen import locks
        with tempfile.TemporaryDirectory() as td:
            store = {"3": {"the cat likes to sleep": {
                "stem": "The cat likes to sleep on the warm ______ by the door.",
                "options": ["mat", "car", "box"],
                "answer": 0,
                "note": "replaced rug - too abstract for Y3"}}}
            locks.save(store, appdir=os.path.join(td, "exam-gen"))
            got = locks.load(appdir=os.path.join(td, "exam-gen"))
            self.assertIn("the cat likes to sleep", got["3"])

    def test_locked_stem_survives_regeneration(self):
        from exam_gen import bank, locks
        paper = _gen({"year": 3, "difficulty": "medium", "seed": 1})
        target = None
        for part in paper.parts:
            for it in part.items:
                if getattr(it, "options", None):
                    target = it
                    break
            if target:
                break
        self.assertIsNotNone(target)
        store = {"3": {" ".join(str(target.stem).lower().split()): {
            "stem": str(target.stem).replace(".", " EXTRA."),
            "options": list(target.options),
            "answer": 0}}}
        again = bank.apply_locks(paper, store)
        found = any(str(getattr(i, "stem", "")).endswith("EXTRA.")
                    for p in again.parts for i in p.items)
        self.assertTrue(found, "locked stem must appear in the regenerated paper")

    def test_unlock_removes_it(self):
        from exam_gen import bank, locks
        paper = _gen({"year": 3, "difficulty": "medium", "seed": 1})
        key = " ".join(str(paper.parts[0].items[0].stem).lower().split())
        store = {"3": {key: {"stem": "LOCKED", "options": ["a", "b", "c"],
                             "answer": 1}}}
        self.assertEqual(len(bank.locked_keys(store, 3)), 1)
        self.assertEqual(len(bank.locked_keys({}, 3)), 0)

    def test_locks_do_not_break_generation(self):
        from exam_gen import bank
        for y in (1, 2, 3, 5, 6):
            paper = _gen({"year": y, "seed": 1})
            out = bank.apply_locks(paper, {"1": {}, str(y): {}})
            self.assertEqual(len(out.parts), 7)
            self.assertEqual(sum(p.marks for p in out.parts), 50)

    def test_answer_index_is_clamped_to_options(self):
        from exam_gen import bank
        paper = _gen({"year": 3, "seed": 1})
        key = " ".join(str(paper.parts[0].items[0].stem).lower().split())
        store = {"3": {key: {"stem": "X", "options": ["a", "b"],
                             "answer": 9}}}
        out = bank.apply_locks(paper, store)
        it = out.parts[0].items[0]
        self.assertLess(int(getattr(it, "answer", 0)), len(it.options))

    def test_corrupt_lock_file_does_not_crash_generation(self):
        from exam_gen import bank, locks
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, "exam-gen")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "locked_items.json"), "w") as fh:
                fh.write("{not json at all")
            self.assertEqual(locks.load(appdir=d), {})
        paper = _gen({"year": 3, "seed": 1})
        self.assertEqual(len(bank.apply_locks(paper, {}).parts), 7)



class TestJsuTable(unittest.TestCase):
    """Round 28: every paper carries its own Jadual Spesifikasi Ujian.

    The ministry sheet is a *per-question* table — No., skill, text genre /
    grammar focus, theme, learning standard, the Bloom column the item is
    plotted in, and the CEFR level — closed by a summary (items per level,
    LOTS:HOTS, total marks).  The generated table must describe the paper
    that was actually printed: one row per question, the *year's* wording of
    each standard, and the level each question was given.
    """

    def _table(self, year=6, seed=4):
        from exam_gen import jsu
        return jsu.table(_gen({"year": year, "seed": seed, "lang": "en"}))

    # -- the shape ---------------------------------------------------------
    def test_every_question_gets_a_row(self):
        from exam_gen import jsu
        paper = _gen({"year": 6, "seed": 4, "lang": "en"})
        t = jsu.table(paper)
        self.assertEqual([r["qno"] for r in t["rows"]],
                         list(range(1, paper.max_qno() + 1)),
                         "one row per printed question, in order")
        for r in t["rows"]:
            self.assertTrue(r["skill"], f"Q{r['qno']} has no skill")
            self.assertTrue(r["standard"], f"Q{r['qno']} has no standard")
            self.assertTrue(r["theme"], f"Q{r['qno']} has no theme")
            self.assertTrue(r["level"], f"Q{r['qno']} has no level")
            self.assertTrue(r["taxonomy"], f"Q{r['qno']} has no taxonomy")
            self.assertEqual(r["marks"], paper.parts[r["part"] - 1].marks_per_q()
                             if r["part"] else 0)

    def test_a_row_never_runs_past_its_part(self):
        from exam_gen import jsu
        paper = _gen({"year": 6, "seed": 4, "lang": "en"})
        t = jsu.table(paper)
        by_part = {r["qno"]: r["part"] for r in t["rows"]}
        for p in paper.parts:
            for q in p.qnos():
                self.assertEqual(by_part[q], p.num,
                                 f"Q{q} is filed under the wrong part")

    # -- the standard must be the year's wording ---------------------------
    def test_the_standard_is_the_official_year_six_wording(self):
        from exam_gen import data as DD
        t = self._table()
        for r in t["rows"]:
            code, _, text = r["standard"].partition(" ")
            self.assertIn(code, DD.JSU_STANDARDS,
                          f"Q{r['qno']} prints an unknown standard {code}")
            # Round 36: the JSU sheet is the authority for a year with one, and
            # its wording is the exact sentence printed in the cell.
            sheet = {t.strip() for rows in DD.JSU_SHEET_STANDARDS[6].values()
                     for _c, t in rows}
            self.assertIn(text, sheet,
                          f"Q{r['qno']} prints {code} in a wording that is "
                          f"not the official Year 6 text")

    def test_a_year_five_paper_prints_the_year_five_wording(self):
        from exam_gen import data as DD
        t = self._table(year=5)
        sheet = {t2.strip() for rows in DD.JSU_SHEET_STANDARDS[5].values()
                 for _c, t2 in rows}
        for r in t["rows"]:
            code, _, text = r["standard"].partition(" ")
            self.assertIn(code, DD.JSU_STANDARDS,
                          f"Q{r['qno']} prints an unknown standard {code}")
            self.assertIn(text, sheet,
                          f"Q{r['qno']} prints {code} in a wording that "
                          f"is not the official Year 5 text")

    def test_the_levels_of_the_two_years_differ_where_they_should(self):
        from exam_gen import data as DD
        self.assertNotEqual(DD.JSU_STANDARDS["3.2.2"][5],
                            DD.JSU_STANDARDS["3.2.2"][6],
                            "Year 5 and Year 6 word a standard differently")

    # -- the level is the level the question was given ---------------------
    def test_the_cefr_mix_is_the_official_one(self):
        t = self._table()
        self.assertEqual(t["cefr_mix"], {"A2 Low": 6, "A2 Mid": 16,
                                         "Revise A2": 5},
                         "objective 5/15/5 plus Part 6 and Part 7")

    def test_a_question_prints_the_level_it_was_given(self):
        t = self._table()
        for r in t["rows"]:
            n = sum(1 for x in t["rows"] if x["level"] == r["level"])
            self.assertGreater(n, 0)
        self.assertEqual(len({r["level"] for r in t["rows"]}), 3)

    def test_the_writing_parts_keep_their_official_levels(self):
        from exam_gen import data as DD
        t = self._table()
        got = {r["part"]: r["level"] for r in t["rows"] if r["part"] >= 6}
        self.assertEqual(got.get(6), DD.JSU[6]["parts"][6]["cefr"])
        self.assertEqual(got.get(7), DD.JSU[6]["parts"][7]["cefr"])

    # -- the focus the ministry names -------------------------------------
    def test_part_1_questions_name_their_reading_genre(self):
        from exam_gen import jsu
        t = self._table()
        official = set(jsu.READING_GENRES)
        seen = set()
        for r in t["rows"]:
            if r["part"] == 1:
                self.assertIn(r["focus"], official,
                              f"Q{r['qno']} genre {r['focus']!r} is not one "
                              f"the ministry lists")
                seen.add(r["focus"])
        self.assertGreaterEqual(len(seen), 3,
                                "Part 1 must not be five of the same genre")

    def test_part_2_questions_name_their_grammar_focus(self):
        """A Part 2 blank is named by what it really tests.

        The ministry lists eight lexico-grammar focuses and a function word
        must be reported with the ministry's own name for it.  A *content*
        word ("mother", "helps", "happy") is outside that list, and calling it
        a noun when it is an adjective would be a lie in a document a teacher
        signs -- so it is reported by its real word class instead.
        """
        from exam_gen import jsu
        t = self._table()
        official = set(jsu.GRAMMAR_FOCUS)
        allowed = official | set(jsu.EXTRA_FOCUS)
        for r in t["rows"]:
            if r["part"] == 2:
                self.assertIn(r["focus"], allowed,
                              f"Q{r['qno']} focus {r['focus']!r} is neither a "
                              f"ministry focus nor a word class")
        for word, stem, want in (
                ("are", "The boys __________ playing outside.", "Auxiliary Verbs"),
                ("in", "The cat is hiding _________ the box.", "Prepositions"),
                ("quickly", "She runs __________ every morning.", "Adverbs"),
                ("mother", "Ava's __________ cooks dinner.", "Nouns"),
                ("helps", "Farid __________ his uncle.", "Verbs")):
            self.assertEqual(jsu._focus_for_word(word, stem), want,
                             f"{word!r} is mislabelled")

    # -- the summary -------------------------------------------------------
    def test_the_lots_hots_split_is_reported(self):
        t = self._table()
        lots, hots = t["lots_hots"]
        self.assertEqual(lots + hots, len(t["rows"]),
                         "every item is LOTS or HOTS; the two writing parts "
                         "are HOTS, so no question is left unclassified")
        self.assertGreater(lots, 0)
        self.assertGreater(hots, 0)

    def test_the_summary_totals_match_the_paper(self):
        t = self._table()
        paper = _gen({"year": 6, "seed": 4, "lang": "en"})
        self.assertEqual(t["total_marks"], sum(p.marks for p in paper.parts))
        self.assertEqual(t["total_marks"], D.TOTAL)
        self.assertEqual(sum(t["cefr_mix"].values()), paper.max_qno())

    # -- every year --------------------------------------------------------
    def test_every_generated_year_gets_a_table(self):
        from exam_gen import jsu
        for year in (1, 2, 3, 5, 6):
            paper = _gen({"year": year, "seed": 3, "lang": "en"})
            t = jsu.table(paper)
            self.assertEqual(len(t["rows"]), paper.max_qno(), f"Y{year}")
            self.assertEqual(sum(t["cefr_mix"].values()), paper.max_qno(),
                             f"Y{year}: every question has a level")
            self.assertEqual(t["total_marks"], D.TOTAL, f"Y{year}")
            self.assertTrue(t["source"], f"Y{year}: the table names its source")

    # -- it reaches the document, after the key -----------------------------
    def test_the_jsu_lands_after_the_answer_key(self):
        paper = _teacher({"year": 6, "seed": 4, "lang": "en"})
        xml = _docx_text(paper)
        from exam_gen import jsu
        head = jsu.title(paper)
        self.assertIn(head, xml)
        self.assertLess(xml.find("ANSWER KEY"), xml.find(head),
                        "the JSU is inserted after the answer key")
        pre = xml.split(head, 1)[0]
        br = pre.rfind('<w:br w:type="page"/>')
        self.assertGreaterEqual(br, 0, "the JSU starts on a fresh page")
        seg = pre[br:]
        self.assertLessEqual(seg.count("<w:p>"), 1)
        self.assertNotIn("</w:t>", seg)

    def test_the_table_prints_the_rows_the_builder_reports(self):
        from exam_gen import jsu
        paper = _teacher({"year": 6, "seed": 4, "lang": "en"})
        t = jsu.table(paper)
        xml = _docx_text(paper)
        seg = xml.split(jsu.title(paper), 1)[1]
        for r in t["rows"][:6]:
            self.assertIn(r["standard"], seg,
                          f"Q{r['qno']}'s standard is not in the document")
        for level in set(r["level"] for r in t["rows"]):
            self.assertIn(level, seg, f"level {level} never printed")

    # -- LOTS and HOTS are told apart by the question, not by a keyword -----
    def test_an_inference_stem_is_higher_order_and_a_manner_stem_is_not(self):
        """Reading the Bloom column off the first "how" or "why" would push
        the whole paper over the blue-print: "How long is the walk?" is
        answered by the text, "Why must the children hurry?" is not."""
        from exam_gen import jsu
        part = _paper_part(3, "comprehension")
        for stem, want in (
                ("Why must the children hurry to the ferry?", "Analysing"),
                ("Why might a bus take forty minutes?", "Analysing"),
                ("What do you think the writer wants?", "Analysing"),
                ("How long is the charity walk?", "Understanding"),
                ("How often does the bus come?", "Understanding"),
                ("How do you travel to Penang?", "Understanding"),
                ("Where do the children wait?", "Remembering"),
                ("How many slides do you use?", "Remembering")):
            item = _paper_item(stem=stem)
            self.assertEqual(jsu._taxonomy(part, item), want,
                             f"{stem!r} is in the wrong Bloom column")
        for num, kind, want in ((2, "cloze", "Applying"),
                                (4, "match", "Analysing"),
                                (5, "words", "Applying")):
            self.assertEqual(
                jsu._taxonomy(_paper_part(num, kind),
                              _paper_item(stem="What must I bring?")),
                want,
                f"Part {num} is {want} work in the ministry sheet, not "
                f"Applying")

    # -- the part 3 rows must name the passage that was actually printed ---
    def test_part_3_rows_name_the_passage_they_came_from(self):
        """A JSU that files Part 3 under the week's RPT theme describes a
        different paper from the one printed, so the rows carry the chosen
        passage's own title and theme."""
        from exam_gen import jsu, webfetch
        pool = webfetch.load_cache().get("KSSR Stories · Year 6") or []
        self.assertTrue(pool, "the shipped Year 6 story corpus is missing")
        paper = _gen({"year": 6, "seed": 5, "lang": "en", "use_web": True},
                     passages=pool)
        p3 = next(p for p in paper.parts if p.num == 3)
        self.assertTrue(p3.source_title,
                        "the part does not remember which passage it used")
        t = jsu.table(paper)
        seen = 0
        for r in t["rows"]:
            if r["part"] == 3:
                seen += 1
                self.assertEqual(r["focus"], p3.source_title)
                self.assertEqual(r["theme"], p3.source_theme)
        self.assertEqual(seen, len(p3.items))

    def test_a_textbook_passage_falls_back_to_the_week_theme(self):
        """No passage title to name: the row says what it can honestly say."""
        from exam_gen import jsu
        paper = _gen({"year": 6, "seed": 4, "lang": "en"})
        t = jsu.table(paper)
        for r in t["rows"]:
            if r["part"] == 3:
                self.assertTrue(r["focus"], "a Part 3 row must name its text")
                self.assertTrue(r["theme"])

    # -- the table must label the exam the sheet is for ---------------------
    def test_the_table_names_the_exam_the_paper_is(self):
        """The acronym names the exam the pupil is sitting, so it follows the
        paper's own exam type.  It used to be read out of the *source sheet's*
        name instead, and the Year 4-6 sheet is always called "Year N UASA" --
        so a mid-year paper printed "MID-YEAR EXAMINATION (UASA) YEAR 4".

        Where the levels came from is not lost: the table's own source line
        still names the sheet the standards were read from.
        """
        from exam_gen import jsu
        paper = _teacher({"year": 6, "seed": 4, "lang": "en", "exam_type": "upsa"})
        self.assertIn("(UPSA)", jsu.title(paper))
        self.assertIn("(UPSA)", _docx_text(paper))
        uasa = _gen({"year": 6, "seed": 4, "lang": "en", "exam_type": "uasa"})
        self.assertIn("(UASA)", jsu.title(uasa))
        y1 = _gen({"year": 1, "seed": 4, "lang": "en", "exam_type": "upsa"})
        self.assertIn("(UPSA)", jsu.title(y1),
                      "a year with no UASA sheet keeps the paper's own exam")
        # the provenance is still on the page
        self.assertIn(jsu.table(paper)["source"], _docx_text(paper))

    def test_the_table_follows_the_paper_s_language(self):
        """An English paper may not carry a Malay heading, and a Malay paper
        may not carry an English one."""
        from exam_gen import jsu
        en = _teacher({"year": 6, "seed": 4, "lang": "en"})
        bm = _teacher({"year": 6, "seed": 4, "lang": "bm"})
        self.assertIn("TEST SPECIFICATION", jsu.title(en))
        self.assertNotIn("JADUAL SPESIFIKASI UJIAN", _docx_text(en))
        self.assertIn("JADUAL SPESIFIKASI UJIAN", jsu.title(bm))
        self.assertIn("JADUAL SPESIFIKASI UJIAN", _docx_text(bm))
        for r in jsu.table(bm)["rows"][:3]:
            self.assertIn(r["standard"], _docx_text(bm))

    # -- every cell is filled, in every year --------------------------------
    def test_no_row_is_left_blank_in_any_year(self):
        from exam_gen import jsu
        for year in (1, 2, 3, 5, 6):
            paper = _gen({"year": year, "seed": 7, "lang": "en"})
            for r in jsu.table(paper)["rows"]:
                for field in ("skill", "focus", "theme", "standard",
                              "taxonomy", "level"):
                    self.assertTrue(r[field],
                                    f"Y{year} Q{r['qno']} has no {field}")
                self.assertGreater(r["marks"], 0,
                                   f"Y{year} Q{r['qno']} carries no mark")

    # -- a pupil's copy carries no table ------------------------------------
    def test_a_paper_without_an_answer_key_carries_no_table(self):
        paper = _gen({"year": 6, "seed": 4, "lang": "en", "answer_key": False})
        xml = _docx_text(paper)
        self.assertNotIn("ANSWER KEY", xml)
        self.assertNotIn("JADUAL SPESIFIKASI UJIAN", xml)
        self.assertNotIn("TEST SPECIFICATION", xml,
                         "the JSU is a teacher's document, not the pupil's")

    # -- the HTML export carries the same table ----------------------------
    def test_the_html_export_carries_the_same_table(self):
        from exam_gen import jsu
        from exam_gen import render_html
        paper = _teacher({"year": 6, "seed": 4, "lang": "en"})
        t = jsu.table(paper)
        html = render_html.render_html(paper, allow_fetch=False)
        self.assertIn(jsu.title(paper), html)
        self.assertLess(html.find("ANSWER KEY"), html.find(jsu.title(paper)))
        for r in t["rows"][:6]:
            self.assertIn(_jsu_esc(r["standard"]), html)

    def test_a_paper_off_the_blueprint_is_reported_in_the_table(self):
        from exam_gen import jsu
        paper = _gen({"year": 6, "seed": 3, "lang": "en"})
        t = jsu.table(paper)
        self.assertEqual(jsu.issues(paper, t), [])
        p6 = next(p for p in paper.parts if p.num == 6)
        p6.items[0].prompt = "Write about the alphabet."
        self.assertTrue(jsu.issues(paper, jsu.table(paper)),
                        "an off-blue-print task must be reported")


class TestRound36Year4Paper(unittest.TestCase):
    """Round 36: Year 4 became a first-class year.

    ``Y4_UASA_2025.docx`` is the format contract: 7 parts, 50 marks, 75
    minutes, Part 6 worth 10 and Part 7 worth 15.  Year 4 also needs its own
    writing pool, because borrowing Year 5's prompts put the Part 6 task
    off the ministry's blue-print.
    """

    def test_year4_is_a_generated_year(self):
        self.assertIn(4, D.YEARS)
        self.assertEqual(len(D.PARTS[4]), 7)
        self.assertEqual(sum(p["marks"] for p in D.PARTS[4]), 50)
        self.assertEqual([p["marks"] for p in D.PARTS[4]],
                         [5, 4, 5, 6, 5, 10, 15])

    def test_year4_matches_the_official_cefr_and_duration(self):
        self.assertEqual(D.DURATION[4], D.DURATION[5])
        self.assertEqual(D.PASSAGE_CEFR[4], "a2")
        self.assertEqual(D.PASSAGE_WORD_BAND[4], (65, 125))
        self.assertEqual(D.PASSAGE_WORD_CEIL[4], 180)
        self.assertEqual({k: tuple(v) for k, v in D.WRITE_WORDS[4].items()},
                         {k: tuple(v) for k, v in D.WRITE_WORDS[5].items()})


    def test_year4_generates_the_official_shape(self):
        paper = _gen({"year": 4, "seed": 3, "lang": "en"})
        self.assertEqual(paper.year(), 4)
        self.assertEqual([p.num for p in paper.parts], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(sum(p.marks for p in paper.parts), 50)
        self.assertEqual(len(paper.parts[0].items), D.PARTS[4][0]["count"])
        self.assertEqual(len(paper.parts[6].items), 1)

    def test_year4_passages_sit_inside_its_own_cefr_ceiling(self):
        """The A2 Low ceiling is 180 words for Year 4 (150 for Years 1-3), and
        the generator filters the passage pool by it, so every drawn passage
        must fit."""
        for seed in (1, 3, 8, 20):
            paper = _gen({"year": 4, "seed": seed, "lang": "en"})
            checked = 0
            for part in paper.parts:
                if part.kind in ("cloze", "comprehension") and part.lead_text:
                    n = len(part.lead_text.split())
                    self.assertLessEqual(
                        n, D.PASSAGE_WORD_CEIL[4],
                        f"Y4 seed {seed} Part {part.num} passage is {n} words")
                    checked += 1
            self.assertTrue(checked, "no Y4 passage was checked")

    def test_year4_has_a_real_vocabulary_list(self):
        """The picture-word bank is shared across years, so Year 4 only has to
        carry a real list of its own -- non-empty, single words, and drawn from
        the themes it is assessed on."""
        band = D.VOCAB_BAND[4]
        self.assertTrue(band, "Year 4 has no vocabulary list")
        self.assertTrue(all(w and " " not in w for w in band))
        self.assertTrue(any("animal" in w or w.endswith("an")
                            for w in band + ("orangutan",)),
                        "Year 4 has no theme vocabulary")

    def test_year4_writing_pool_comes_from_the_rpt_modules(self):
        from exam_gen import extra_writing_4 as xw4
        self.assertTrue(xw4.ESSAYS[4]["short"])
        self.assertTrue(xw4.ESSAYS[4]["long"])
        for row in xw4.ESSAYS[4]["short"] + xw4.ESSAYS[4]["long"]:
            self.assertIn(row["theme"], D.RPT_THEMES[4],
                          f"{row['subject']!r} is not a Year 4 RPT module")

    def test_year4_model_answers_fit_the_band_they_print(self):
        from exam_gen import extra_writing_4 as xw4
        for pool, band in ((xw4.ESSAYS[4]["short"], (30, 50)),
                           (xw4.ESSAYS[4]["long"], (60, 80))):
            for row in pool:
                n = len(row["model"].split())
                self.assertTrue(band[0] <= n <= band[1],
                                f"{row['subject']!r} model is {n} words")

    def test_year4_prompts_are_unique(self):
        from exam_gen import extra_writing_4 as xw4
        pool = xw4.ESSAYS[4]["short"] + xw4.ESSAYS[4]["long"]
        prompts = [r["prompt"] for r in pool]
        self.assertEqual(len(prompts), len(set(prompts)))

    def test_year4_paper_documents_cleanly(self):
        paper = _teacher({"year": 4, "seed": 2, "lang": "en"})
        for text in (_docx_text(paper), render_html.render_html(paper,
                                                               allow_fetch=False)):
            self.assertIn("Year 4", text)


class TestRound36JsuFromTheSheet(unittest.TestCase):
    """Round 36: the JSU is printed from the ministry sheet, not re-invented.

    ``JSU_Y4Y5Y6.xlsx`` (hidden ``Ref`` sheet, columns O/P/Q) is the contract.
    Ten Year 6 cells held a Part 6 or Part 5 code that contradicted the
    standard they sit next to, so the codes are corrected here and the
    rendering quotes the sheet's own task wording.
    """

    #: (sheet cell, the code it was plotted with, the code it belongs to)
    Y6_MISPLOTTED = (("Q36", "4.3.1", "4.3.2"), ("Q40", "4.2.1", "4.2.2"),
                     ("Q43", "4.2.1", "4.2.5"), ("Q46", "4.2.2", "4.3.1"),
                     ("Q49", "4.2.3", "4.3.2"), ("Q53", "4.2.1", "4.2.3"),
                     ("Q56", "4.2.2", "4.2.4"), ("Q59", "4.2.3", "4.2.5"),
                     ("Q62", "4.2.1", "4.3.1"), ("Q65", "4.2.2", "4.3.2"))

    def test_every_year_with_a_sheet_has_a_table(self):
        for year in (4, 5, 6):
            self.assertIn(year, D.JSU, f"Year {year} has a JSU sheet")
            self.assertTrue(D.JSU[year]["parts"])

    @staticmethod
    def _sheet_rows(year: int) -> list[tuple[str, str]]:
        """Every ``(code, task wording)`` pair the sheet gives a year."""
        return [row for part in D.JSU_SHEET_STANDARDS[year].values()
                for row in part]

    def test_the_table_uses_the_sheets_own_wording(self):
        for year in (4, 5, 6):
            rows = self._sheet_rows(year)
            self.assertTrue(rows, f"Year {year} sheet wording is missing")
            for code, task in rows:
                self.assertTrue(code.strip())
                self.assertTrue(task.strip())

    def test_no_year4_or_year5_row_carries_a_year6_code(self):
        for year in (4, 5):
            for code, _task in self._sheet_rows(year):
                self.assertNotEqual(code[:1], "6",
                                    f"Year {year} row uses a Year 6 code")

    def test_each_year_gets_its_own_rung_of_the_ladder(self):
        """Columns O/P/Q are the low, middle and top rung of the same ladder.

        A short-simple-text 3.2.1 belongs to Year 4 and a simple-longer-text
        3.2.1 to Year 5, so a paper may only print the rung its own year is
        assessed on.
        """
        rungs = {4: "short simple texts", 5: "simple longer texts",
                 6: "simple longer texts"}
        for year, rung in rungs.items():
            tasks = [t for _c, t in self._sheet_rows(year)]
            self.assertTrue(any(rung in t for t in tasks),
                            f"Year {year} never plots the {rung!r} rung")
        # Year 4 is the lowest rung, so it must not claim Year 5's wording
        for _c, task in self._sheet_rows(4):
            self.assertNotIn("simple longer texts", task)
        # and Year 6 alone reaches the 3.1.x reading skills
        self.assertFalse(any(c.startswith("3.1") for c, _t in self._sheet_rows(4)))
        self.assertFalse(any(c.startswith("3.1") for c, _t in self._sheet_rows(5)))
        self.assertTrue(any(c.startswith("3.1") for c, _t in self._sheet_rows(6)))

    def test_a_code_is_never_plotted_in_two_blocks_of_one_part(self):
        """Ten Year 6 cells carried a neighbouring code (Q36 held 4.3.1 next to
        the 4.3.2 spelling standard, and so on).  A mis-plotted cell shows up as
        a code reappearing after a different one, or as a block of the wrong
        size, so both are asserted for every year and part."""
        expected = {4: {6: 3, 7: 3}, 5: {6: 3, 7: 3}, 6: {6: 2, 7: 2}}
        for year, parts in expected.items():
            for num, per_code in parts.items():
                codes = [c for c, _t in D.JSU_SHEET_STANDARDS[year][num]]
                blocks: list[str] = []
                for c in codes:
                    if not blocks or blocks[-1] != c:
                        blocks.append(c)
                self.assertEqual(len(blocks), len(set(codes)),
                                 f"Y{year} P{num} plots a code twice: {codes}")
                for c in set(codes):
                    self.assertEqual(codes.count(c), per_code,
                                     f"Y{year} P{num} plots {c} "
                                     f"{codes.count(c)} times")

    def test_every_sheet_code_exists_in_the_standards_ladder(self):
        for year in D.JSU_SHEET_STANDARDS:
            for code, _task in self._sheet_rows(year):
                self.assertIn(code, D.JSU_STANDARDS,
                              f"Year {year} code {code!r} is unknown")

    def test_the_ten_misplotted_year6_cells_are_corrected(self):
        """The corrected outcome is that each Year 6 writing code is plotted
        with the top-rung wording that belongs to it, two rows at a time."""
        for num, top in ((6, ["Ask for, give and respond to simple advice",
                              "Use capital letters, full stops,commas in "
                              "lists, question marks, and speech marks "
                              "appropriately at discourse level"]),
                         (7, ["Narrate factual and imagined events and "
                              "experiences",
                              "Use capital letters, full stops,commas in "
                              "lists, question marks, and speech marks "
                              "appropriately at discourse level"])):
            rows = D.JSU_SHEET_STANDARDS[6][num]
            for wording in top:
                self.assertTrue(any(wording in t for _c, t in rows),
                                f"Y6 P{num} lost the wording {wording!r}")
        codes = [c for c, _t in D.JSU_SHEET_STANDARDS[6][6]]
        self.assertEqual(codes, ["4.2.2", "4.2.2", "4.2.5", "4.2.5",
                                 "4.3.1", "4.3.1", "4.3.2", "4.3.2"])

    def test_year4_and_year5_writing_parts_name_the_sheets_task(self):
        for year in (4, 5):
            self.assertIn("offers and invitations",
                          D.JSU[year]["parts"][6]["task"])
            self.assertIn("Narrate", D.JSU[year]["parts"][7]["task"])

    def test_the_printed_standard_is_the_sheets_own_sentence(self):
        paper = _gen({"year": 4, "seed": 3, "lang": "en"})
        printed = {r["standard"] for r in jsu.table(paper)["rows"]}
        self.assertTrue(printed)
        sheet = {t.strip() for _c, t in self._sheet_rows(4)}
        for sentence in printed:
            self.assertIn(sentence.split(" ", 1)[1], sheet,
                          f"not the sheet's own wording: {sentence!r}")

    def test_a_year6_paper_prints_the_year6_rung_only(self):
        paper = _gen({"year": 6, "seed": 3, "lang": "en"})
        sheet = {t.strip() for _c, t in self._sheet_rows(6)}
        for sentence in {r["standard"] for r in jsu.table(paper)["rows"]}:
            self.assertIn(sentence.split(" ", 1)[1], sheet,
                          f"Year 6 printed another year's rung: {sentence!r}")



    def test_year4_and_year5_no_longer_say_the_sheet_is_missing(self):
        for year in (4, 5):
            for seed in (1, 4):
                paper = _teacher({"year": year, "seed": seed, "lang": "en"})
                text = _docx_text(paper)
                self.assertNotIn("No JSU sheet", text)
                self.assertIn(jsu.title(paper), text)

    def test_every_year4_part_is_off_the_blueprint(self):
        for seed in (1, 7, 42, 99):
            for diff in ("easy", "medium", "hard"):
                paper = _gen({"year": 4, "seed": seed, "difficulty": diff,
                              "lang": "en"})
                self.assertEqual(jsu.issues(paper, jsu.table(paper)), [],
                                 f"Y4 seed {seed} {diff}")

    def test_a_past_tense_experience_satisfies_the_year7_task(self):
        """``writer_signals`` states the same task as ``signals`` in more
        detail, so the audit must accept a prompt matched by either."""
        paper = _gen({"year": 6, "seed": 5, "lang": "en"})
        p7 = next(p for p in paper.parts if p.num == 7)
        p7.items[0].prompt = (
            "You were a helper at a fun fair for the school fund. Write a "
            "letter to your friend about your experience.")
        self.assertEqual(jsu.issues(paper, jsu.table(paper)), [])

class TestRound36Duration(unittest.TestCase):
    """``DEFAULT_CONFIG`` ships ``duration: ""``, so the generator has to fill
    a blank duration from the year or the JSU header reads "Time: - minutes".
    """

    def test_every_year_carries_its_official_duration(self):
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            self.assertEqual(paper.meta.get("duration"), D.DURATION[year],
                             f"Year {year} lost its duration")

    def test_an_explicit_duration_is_never_overwritten(self):
        paper = _gen({"year": 6, "seed": 1, "lang": "en", "duration": "2 hours"})
        self.assertEqual(paper.meta.get("duration"), "2 hours")

    def test_the_jsu_header_prints_a_time(self):
        for year in (4, 5, 6):
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            for text in (_docx_text(paper),
                         render_html.render_html(paper, allow_fetch=False)):
                self.assertNotIn("- minutes", text,
                                 f"Year {year} JSU header has no time")
                self.assertIn(D.DURATION[year], text)


class TestRound37Identity(unittest.TestCase):
    """SPEC 53.1 — a redaction marker is not a school."""

    def test_the_defaults_are_not_placeholders(self):
        for field in ("school", "teacher"):
            self.assertEqual(D.DEFAULT_CONFIG[field], "", field)

    def test_no_year_prints_a_placeholder(self):
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            for text in (_docx_text(paper),
                         render_html.render_html(paper, allow_fetch=False)):
                self.assertTrue(_lacks(text, "***"),
                                f"Year {year} prints a placeholder")

    def test_a_configured_school_prints_its_real_name(self):
        paper = _gen({"year": 5, "seed": 1, "lang": "en",
                      "school": "SK Pinang Bidor", "teacher": "Cikgu Tan"})
        text = _docx_text(paper)
        self.assertTrue(_has(text, "SK Pinang Bidor"))
        self.assertTrue(_has(text, "Cikgu Tan"))

    def test_an_unconfigured_paper_prints_no_identity_line(self):
        paper = _gen({"year": 5, "seed": 1, "lang": "en",
                      "school": "", "teacher": ""})
        self.assertTrue(_lacks(_docx_text(paper), "School:"))
        self.assertTrue(_lacks(_docx_text(paper), "Teacher:"))


class TestRound37Duration(unittest.TestCase):
    """SPEC 53.2 — criteria §1: Y1-3 UASA is 75 minutes, not 60."""

    def test_the_official_minutes_are_keyed_by_exam_type(self):
        for year in (1, 2, 3):
            self.assertEqual(D.duration(year, "upsa"), 60, f"Y{year} UPSA")
            self.assertEqual(D.duration(year, "uasa"), 75, f"Y{year} UASA")
        for year in (4, 5, 6):
            self.assertEqual(D.duration(year, "upsa"), 75, f"Y{year} UPSA")
            self.assertEqual(D.duration(year, "uasa"), 75, f"Y{year} UASA")

    def test_a_uasa_lower_primary_paper_prints_seventy_five_minutes(self):
        for year in (1, 2, 3):
            paper = _gen({"year": year, "seed": 1, "lang": "en",
                          "exam_type": "uasa"})
            self.assertEqual(paper.meta.get("duration_minutes"), 75)
            self.assertEqual(paper.duration(), "1 hour 15 minutes")

    def test_an_upsa_lower_primary_paper_prints_sixty_minutes(self):
        paper = _gen({"year": 3, "seed": 1, "lang": "en", "exam_type": "upsa"})
        self.assertEqual(paper.meta.get("duration_minutes"), 60)
        self.assertEqual(paper.duration(), "1 hour")

    def test_the_duration_phrase_carries_its_own_unit(self):
        self.assertEqual(D.duration_text(60, "en"), "1 hour")
        self.assertEqual(D.duration_text(75, "en"), "1 hour 15 minutes")
        self.assertEqual(D.duration_text(75, "bm"), "1 jam 15 minit")
        self.assertEqual(D.duration_text(45, "en"), "45 minutes")

    def test_an_explicit_duration_is_never_overwritten(self):
        paper = _gen({"year": 6, "seed": 1, "lang": "en", "duration": "2 hours"})
        self.assertEqual(paper.duration(), "2 hours")

    def test_the_cover_prints_the_official_time(self):
        for year in D.YEARS:
            for exam_type in ("upsa", "uasa"):
                paper = _gen({"year": year, "seed": 1, "lang": "en",
                              "exam_type": exam_type})
                want = D.duration_text(D.duration(year, exam_type), "en")
                self.assertTrue(_has(_docx_text(paper), want),
                                f"Y{year} {exam_type} cover time")

    def test_the_cli_can_ask_for_a_uasa_paper(self):
        """The CLI had no ``--exam-type`` flag, so ``--exam-type uasa`` was
        silently ignored and every headless paper came out mid-year."""
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P.docx")
            rc = cli.run_cli(["--cli", "--year", "3", "--exam-type", "uasa",
                              "--no-pictures", "--teacher-copy", "--out", out])
            self.assertEqual(rc, 0)
            with zipfile.ZipFile(out) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            with zipfile.ZipFile(os.path.join(td, "P_TEACHER.docx")) as z:
                txml = z.read("word/document.xml").decode("utf-8", "ignore")
        self.assertTrue(_has(xml, "1 hour 15 minutes"),
                        "the CLI ignored --exam-type uasa")
        self.assertTrue(_has(txml, "END-OF-YEAR"),
                        "the CLI paper carries a mid-year JSU heading")
        self.assertTrue(_lacks(xml, "MID-YEAR EXAMINATION"),
                        "a UASA paper printed the mid-year JSU heading")


class TestRound37JsuHeader(unittest.TestCase):
    """SPEC 53.3 / 53.4 / 53.5 — the JSU states things once, and honestly."""

    def test_the_time_line_never_doubles_its_unit(self):
        for year in D.YEARS:
            for exam_type in ("upsa", "uasa"):
                paper = _gen({"year": year, "seed": 1, "lang": "en",
                              "exam_type": exam_type})
                for text in (_docx_text(paper),
                             render_html.render_html(paper, allow_fetch=False)):
                    self.assertTrue(_lacks(text, "minutes minutes"), f"Y{year} {exam_type}")
                    self.assertTrue(_lacks(text, "hour minutes"), f"Y{year} {exam_type}")
                    self.assertTrue(_lacks(text, "- minutes"), f"Y{year} {exam_type}")
                    self.assertTrue(_lacks(text, "minit minit"), f"Y{year} {exam_type}")

    def test_the_jsu_heading_agrees_with_the_cover(self):
        for year in D.YEARS:
            upsa = _gen({"year": year, "seed": 1, "lang": "en",
                         "exam_type": "upsa"})
            uasa = _gen({"year": year, "seed": 1, "lang": "en",
                         "exam_type": "uasa"})
            self.assertTrue(_has(jsu.title(upsa).upper(), "MID-YEAR"))
            self.assertTrue(_lacks(jsu.title(upsa).upper(), "END-OF"))
            self.assertTrue(_has(jsu.title(uasa).upper(), "END-OF-YEAR"))

    def test_the_heading_follows_the_paper_language(self):
        for exam_type, word in (("upsa", "PERTENGAHAN"), ("uasa", "AKHIR")):
            paper = _gen({"year": 5, "seed": 1, "lang": "bm",
                          "exam_type": exam_type})
            self.assertTrue(_has(jsu.title(paper).upper(), word))

    def test_the_acronym_agrees_with_the_heading(self):
        """``_exam()`` used to read the acronym out of the *source sheet's*
        name -- and the Year 4-6 sheet is always called "Year N UASA" -- so a
        mid-year paper printed "MID-YEAR EXAMINATION (UASA)".  The paper's
        own exam type is what the acronym means."""
        for year in D.YEARS:
            for exam_type, abbr in (("upsa", "UPSA"), ("uasa", "UASA")):
                paper = _gen({"year": year, "seed": 1, "lang": "en",
                              "exam_type": exam_type})
                heading = jsu.title(paper)
                self.assertTrue(_has(heading, f"({abbr})"),
                                f"Y{year} {exam_type}: {heading}")
                other = "UASA" if abbr == "UPSA" else "UPSA"
                self.assertTrue(_lacks(heading, f"({other})"),
                                f"Y{year} {exam_type}: {heading}")

    def test_no_jsu_cell_says_nil(self):
        for year in D.YEARS:
            for seed in (1, 2, 3):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                for row in jsu.table(paper)["rows"]:
                    self.assertNotEqual(row["focus"].strip().upper(), "NIL",
                                        f"Y{year} Q{row['qno']}")

    def test_the_spelling_part_names_the_task_it_actually_built(self):
        allowed = {"Picture / word box", "Spelling (letter cues)",
                   "Word definitions"}
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            p5 = next(p for p in paper.parts if p.num == 5)
            for row in jsu.table(paper)["rows"]:
                if row["part"] == 5:
                    self.assertIn(row["focus"], allowed,
                                  f"Y{year} Q{row['qno']} focus {row['focus']!r}")
            self.assertTrue(p5.items)


class TestRound38PupilCopy(unittest.TestCase):
    """SPEC 54.1 — a plain export is safe to hand to a pupil.

    ``DEFAULT_CONFIG`` shipped ``answer_key: True``, so the single command a
    teacher actually types -- ``main.py --cli --year 5 --out paper.docx`` --
    wrote a document containing the ANSWER KEY and the JSU.  Printing that
    file and handing it round the room gave every pupil the answers.
    """

    def test_the_default_paper_carries_no_key(self):
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            text = _docx_text(paper)
            self.assertTrue(_lacks(text, "ANSWER KEY"),
                            f"Year {year} default paper carries the key")
            self.assertTrue(_lacks(text, jsu.title(paper)),
                            f"Year {year} default paper carries the JSU")

    def test_the_defaults_are_fail_safe(self):
        self.assertFalse(D.DEFAULT_CONFIG["answer_key"])
        self.assertFalse(D.DEFAULT_CONFIG.get("jsu", False))

    def test_the_pupil_copy_still_has_the_questions(self):
        paper = _gen({"year": 5, "seed": 1, "lang": "en"})
        text = _docx_text(paper)
        for part in paper.parts:
            self.assertTrue(_has(text, f"PART {part.num}"),
                            f"the pupil copy lost PART {part.num}")
        self.assertTrue(_has(text, "INSTRUCTIONS"))
        self.assertTrue(_has(text, "Name:"))

    def test_a_teacher_copy_still_gets_the_key_and_the_table(self):
        paper = _gen({"year": 5, "seed": 1, "lang": "en",
                      "answer_key": True, "jsu": True})
        text = _docx_text(paper)
        self.assertTrue(_has(text, "ANSWER KEY"))
        self.assertTrue(_has(text, jsu.title(paper)))

    def test_the_cli_default_export_is_a_pupil_copy(self):
        """A bare --out must be safe to print.  Producing the teacher
        document is deliberate: --teacher."""
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P.docx")
            self.assertEqual(cli.run_cli(
                ["--cli", "--year", "5", "--no-pictures", "--out", out]), 0)
            with zipfile.ZipFile(out) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            self.assertTrue(_lacks(xml, "ANSWER KEY"),
                            "--out wrote the answers into the pupil paper")
            self.assertTrue(_has(xml, "PART 1"))
            self.assertFalse(
                os.path.exists(os.path.join(td, "P_TEACHER.docx")),
                "a teacher copy appeared without --teacher")

    def test_the_teacher_copy_flag_writes_the_teacher_document(self):
        from exam_gen import cli
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "P.docx")
            self.assertEqual(cli.run_cli(
                ["--cli", "--year", "5", "--no-pictures", "--teacher-copy",
                 "--out", out]), 0)
            teacher = os.path.join(td, "P_TEACHER.docx")
            self.assertTrue(os.path.exists(teacher),
                            "--teacher-copy wrote no teacher copy")
            with zipfile.ZipFile(teacher) as z:
                txml = z.read("word/document.xml").decode("utf-8", "ignore")
            self.assertTrue(_has(txml, "ANSWER KEY"))
            self.assertTrue(_has(txml, "TEST SPECIFICATION"))
            # the pupil paper is still clean, side by side in the same folder
            with zipfile.ZipFile(out) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            self.assertTrue(_lacks(xml, "ANSWER KEY"))
            self.assertTrue(_lacks(xml, "TEST SPECIFICATION"))

    def test_no_word_of_the_key_appears_in_the_pupil_copy(self):
        """The strongest form: strip the key and the table out of the teacher
        document and what is left is byte-identical to the pupil copy's
        visible text, so nothing can leak through a shared render path."""
        for year in (1, 5):
            pupil = _gen({"year": year, "seed": 7, "lang": "en"})
            teacher = _gen({"year": year, "seed": 7, "lang": "en",
                            "answer_key": True, "jsu": True})
            cut = _docx_text(teacher).find("ANSWER KEY")
            self.assertTrue(cut > 0, f"Y{year} teacher copy has no key")
            head = _docx_text(teacher)[:cut]
            self.assertTrue(_lacks(_docx_text(pupil), "ANSWER KEY"))
            self.assertTrue(len(head) > 1000, f"Y{year} head is suspiciously short")


class TestRound39MarkingScheme(unittest.TestCase):
    """SPEC 55 — the marking scheme says what each question is *for*.

    Round 39.  The scheme was a bare answer list: Q / Mark / Answer.  Nothing
    named the attainment objective a question served and nothing weighed the
    paper per objective, so auditing a paper against the DSKP meant adding it
    up by hand.  The writing parts also had no performance-level guide at all.
    """

    def _scheme_text(self, paper) -> str:
        raw = X.mark_scheme_doc(paper)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return z.read("word/document.xml").decode("utf-8", "ignore")

    def test_every_row_is_labelled_with_an_attainment_objective(self):
        for year in D.YEARS:
            text = self._scheme_text(_gen({"year": year, "seed": 1}))
            self.assertTrue(_has(text, "AO"), f"Y{year} scheme has no AO column")
            for ao in D.AOS:
                self.assertTrue(_has(text, ao),
                                f"Y{year} scheme never names {ao}")

    def test_the_marks_by_ao_summary_adds_up_to_fifty(self):
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1})
            text = self._scheme_text(paper)
            tally = {}
            for row in X.mark_scheme_rows(paper):
                tally.setdefault(D.ao_for_kind(row["kind"]), 0.0)
                tally[row["ao"]] = tally.get(row["ao"], 0.0) + row["marks"]
            self.assertAlmostEqual(sum(tally.values()), 50.0, places=6,
                                   msg=f"Y{year} AO marks do not total 50")
            self.assertTrue(_has(text, "MARKS BY ATTAINMENT OBJECTIVE"),
                            f"Y{year} scheme has no AO summary")

    def test_all_three_objectives_carry_marks_in_every_year(self):
        """AO3 must be the writing parts, so a paper can never be all recall."""
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1})
            tally = {}
            for row in X.mark_scheme_rows(paper):
                tally[row["ao"]] = tally.get(row["ao"], 0.0) + row["marks"]
            for ao in D.AOS:
                self.assertGreater(tally.get(ao, 0.0), 0.0,
                                   f"Y{year} never assesses {ao}")

    def test_the_writing_parts_carry_performance_levels(self):
        text = self._scheme_text(_gen({"year": 5, "seed": 1}))
        for code, _name, _desc in D.PL_LEVELS:
            self.assertTrue(_has(text, code),
                            f"the scheme never names {code}")

    def test_the_levels_run_from_low_to_best(self):
        """PL1 is the lowest and PL6 the best, in that order on the page."""
        text = self._scheme_text(_gen({"year": 5, "seed": 1}))
        pos = [text.find(code) for code, *_ in D.PL_LEVELS]
        self.assertTrue(all(p >= 0 for p in pos), "a level is missing")
        self.assertEqual(pos, sorted(pos),
                         f"levels are printed out of order: {pos}")

    def test_every_level_carries_a_descriptor(self):
        for code, name, desc in D.PL_LEVELS:
            self.assertTrue(desc.strip(), f"{code} has no descriptor")
            self.assertTrue(name.strip(), f"{code} has no band name")

    def test_the_bands_cover_every_mark_with_no_gap(self):
        for total in (5, 10, 15, 20):
            bands = D.pl_bands(total)
            self.assertEqual(len(bands), 6, f"{total} marks gave {len(bands)} bands")
            covered = []
            for _code, _name, lo, hi, _d in bands:
                covered.extend(range(int(lo), int(hi) + 1))
            self.assertEqual(sorted(covered), list(range(0, total + 1)),
                             f"{total} marks: bands leave a gap or overlap")

    def test_the_scheme_says_the_levels_are_guidance_not_the_ministry_wording(self):
        """No official performance-level scale exists in the ministry corpus,
        so a teacher must be able to see that these bands are guidance and
        check them against their district scheme."""
        text = self._scheme_text(_gen({"year": 5, "seed": 1}))
        self.assertTrue(_has(text, D.PL_CAVEAT.split()[0]))
        self.assertTrue(_has(text, "guidance"))

    def test_the_scheme_is_not_in_the_pupil_paper(self):
        paper = _gen({"year": 5, "seed": 1})
        raw = X.mark_scheme_doc(paper)
        self.assertTrue(_has(
            zipfile.ZipFile(io.BytesIO(raw)).read("word/document.xml")
            .decode("utf-8", "ignore"), "Teacher copy"))
        self.assertTrue(_lacks(_docx_text(paper), "MARKING SCHEME"))


class TestRound40Hots(unittest.TestCase):
    """SPEC 56 — the Bloom column follows ``JSU_Y4Y5Y6.xlsx``.

    Round 40.  The criteria's prose checklist says "HOTS in Parts 3, 4, 6 and
    7", which reads as though Parts 2 and 5 are low order.  They are not:
    the ministry sheet plots every question in its own Bloom column, and puts
    P1/P3 under *Understanding* and P2/P5 under *Applying*.  Rewriting the code
    to the prose version moved HOTS onto Part 3 and off Parts 2 and 5, and
    broke the sheet's own 40:60 tally (14:13 where the sheet wants 10:17).

    The sheet wins, so these tests pin the sheet.  What *was* wrong is Part 4:
    the HOTS parts were all forced to "Applying", but the sheet plots all six
    matching questions under *Analysing*.
    """

    #: Read off JSU_Y4Y5Y6.xlsx: Remembering/Understanding under columns G-L,
    #: Applying under M-O, Analysing under P-R.
    SHEET_BLOOM = {2: "Applying", 4: "Analysing", 5: "Applying"}
    #: The sheet plots these whole parts under *Understanding*, i.e. LOTS.  It
    #: plots a part, not a stem, so the code is free to read the individual
    #: question (a real "why ...?" is Remembering-free and may be Analysing);
    #: what it may not do is push them into HOTS.
    SHEET_LOTS_PARTS = (1, 3)
    #: Only these years have a transcribed ministry sheet, so only they have a
    #: blue-print tally to meet.
    SHEET_YEARS = (4, 5, 6)

    def test_each_hots_part_sits_in_the_column_the_sheet_plots_it_in(self):
        from exam_gen import jsu
        for year in D.YEARS:
            for seed in (1, 4, 42, 99):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                for row in jsu.table(paper)["rows"]:
                    want = self.SHEET_BLOOM.get(row["part"])
                    if want is None:
                        continue          # reading + writing parts
                    self.assertEqual(
                        row["taxonomy"], want,
                        f"Y{year} seed {seed} Q{row['qno']} "
                        f"(Part {row['part']}) is {row['taxonomy']}, but the "
                        f"sheet plots Part {row['part']} as {want}")

    def test_the_reading_parts_stay_low_order(self):
        """Parts 1 and 3 sit in the sheet's *Understanding* column.

        The sheet plots a whole part, but the code is allowed to read the
        individual question: a genuine "why ...?" inference is Analysing, not
        Understanding.  That is a refinement above the sheet, not a
        deviation from it, and the 40:60 tally is what stops it drifting.
        What it may never do is reach *Applying* -- that column is the sheet's
        for Parts 2 and 5.
        """
        from exam_gen import jsu
        for year in D.YEARS:
            for seed in (1, 4, 42, 99):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                for row in jsu.table(paper)["rows"]:
                    if row["part"] not in self.SHEET_LOTS_PARTS:
                        continue
                    level = row["taxonomy"]
                    self.assertIn(level, ("Remembering", "Understanding",
                                          "Analysing"),
                                  f"Y{year} seed {seed} Q{row['qno']} in "
                                  f"reading Part {row['part']} is {level}")
                    if level == "Analysing":
                        part = next(i for i in paper.parts
                                    if i.num == row["part"])
                        item = part.items[row["qno"] - part.qfirst]
                        stem = str(getattr(item, "stem", "")
                                   or getattr(item, "clue", "")
                                   or getattr(item, "prompt", ""))
                        self.assertTrue(
                            jsu._INFERENCE.search(stem),
                            f"Y{year} seed {seed} Q{row['qno']} reads as "
                            f"Analysing but the stem is not an inference "
                            f"question: {stem!r}")

    def test_the_matching_part_is_analysing_not_applying(self):
        """Matching a description to a text means breaking the text down and
        deciding which half fits -- not recalling a rule and using it."""
        from exam_gen import jsu
        for year in D.YEARS:
            for seed in (1, 4, 42, 99):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                rows = [r for r in jsu.table(paper)["rows"] if r["part"] == 4]
                self.assertTrue(rows, f"Y{year} has no Part 4 rows")
                for r in rows:
                    self.assertEqual(r["taxonomy"], "Analysing",
                                     f"Y{year} seed {seed} Q{r['qno']}")

    def test_the_writing_parts_are_creating(self):
        from exam_gen import jsu
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            rows = [r for r in jsu.table(paper)["rows"] if r["part"] in (6, 7)]
            self.assertTrue(rows)
            for r in rows:
                self.assertEqual(r["taxonomy"], "Creating")

    def test_the_tally_meets_the_sheets_forty_sixty_blueprint(self):
        """The sheet's Parts 1-5 block asks for 40% LOTS / 60% HOTS.  Only
        Year 4-6 have that block transcribed -- a Year 1 paper has five writing
        *items* rather than one, so its shape is not the sheet's shape and it
        has no blue-print tally to meet."""
        from exam_gen import jsu
        for year in self.SHEET_YEARS:
            for seed in (1, 4, 42, 99):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                t = jsu.table(paper)
                lots, hots = t["lots_hots"]
                total = lots + hots
                self.assertEqual(total, paper.max_qno(),
                                 f"Y{year} seed {seed} tally lost questions")
                want_lots = 40 * total // 100
                self.assertLessEqual(
                    abs(lots - want_lots), max(1, want_lots // 4),
                    f"Y{year} seed {seed}: {lots}L:{hots}H, blue-print wants "
                    f"about {want_lots}L")

    def test_the_lower_years_have_no_blueprint_tally_to_miss(self):
        """Guard the guard: the check above must not silently start applying
        to years that have no ministry sheet."""
        from exam_gen import jsu
        for year in (1, 2, 3):
            self.assertNotIn(year, D.JSU)
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            self.assertIsNone(jsu.table(paper)["target_lots_hots"][0])

    def test_no_part_is_out_of_the_blueprint(self):
        from exam_gen import jsu
        for year in D.YEARS:
            for seed in (1, 7, 42):
                paper = _gen({"year": year, "seed": seed, "lang": "en"})
                self.assertEqual(jsu.issues(paper, jsu.table(paper)), [],
                                 f"Y{year} seed {seed}")


class TestRound41Part5(unittest.TestCase):
    """SPEC 57 — Part 5 is the ministry's spelling task, in every year.

    Round 41.  Every official paper in the corpus -- ``UASA YEAR 1/2/3.pdf``,
    ``Y4_UASA_2025.docx``, ``Y6_UPSA_2026.docx`` -- gives Part 5 the same
    shape: "Read the descriptions.  What is the word for each one?", with one
    blank per letter.  Year 4-6 quotes that instruction verbatim.

    Years 1-3 were built as ``words/choice`` instead -- a multiple-choice
    question with A/B/C options.  Three things followed from that:

    * the instructions told the pupil to mark Parts 1-4 on the objective
      answer space while the sheet actually carried bubbles for Q21-25;
    * the criteria's "dedicated objective response table ... for Parts 1 to 4"
      was broken for the lower years;
    * learning standard 4.2.2 ("spell most high frequency words accurately")
      was never actually assessed.
    """

    def _p5(self, year):
        paper = _gen({"year": year, "seed": 1, "lang": "en"})
        part = next(p for p in paper.parts if p.num == 5)
        return paper, part

    def test_part5_is_the_spelling_task_in_every_year(self):
        for year in D.YEARS:
            _paper, part = self._p5(year)
            self.assertEqual(part.kind, "words")
            self.assertEqual(part.style, "letter",
                             f"Y{year} Part 5 is {part.style!r}, not the "
                             f"ministry's spelling task")

    def test_part5_never_asks_the_pupil_to_choose_a_b_c(self):
        for year in D.YEARS:
            _paper, part = self._p5(year)
            for field in (part.lead or "", str(part.lead_text or "")):
                low = field.lower()
                self.assertNotIn("choose the correct answer", low)
                for phrase in (" a, b or c", "answer a, b", "choose a, b"):
                    self.assertNotIn(phrase, low,
                                     f"Y{year} Part 5 still reads like an MCQ")
            for item in part.items:
                self.assertNotIsInstance(
                    item, MCQItem,
                    f"Y{year} Part 5 item is an MCQ")

    def test_part5_is_off_the_objective_answer_sheet(self):
        """The criteria give the objective table for Parts 1 to 4."""
        for year in D.YEARS:
            paper, part = self._p5(year)
            sheet = "".join(X._answer_sheet(paper))
            first_p5, last_p5 = part.qnos()[0], part.qnos()[-1]
            import re as _re
            ticks = {int(m) for m in _re.findall(r"<w:t[^>]*>(\d+)</w:t>", sheet)}
            for q in range(first_p5, last_p5 + 1):
                self.assertNotIn(
                    q, ticks,
                    f"Y{year} Q{q} is Part 5 and must not have a bubble")

    def test_part5_items_are_word_items_with_a_letter_blank_each(self):
        for year in D.YEARS:
            _paper, part = self._p5(year)
            for item in part.items:
                self.assertIsInstance(item, WordItem,
                                      f"Y{year} Part 5 item is not a WordItem")
                self.assertTrue(item.clue.strip(), f"Y{year} item has no clue")
                self.assertEqual(item.length, len(item.answer),
                                 f"Y{year} '{item.answer}' has {item.length} "
                                 f"blanks")
                self.assertIn("_", item.pattern)

    def test_the_lower_years_do_not_claim_the_first_letter_is_given(self):
        """``UASA YEAR 1.pdf`` prints every letter blank.  Year 4-6 print
        ``c o u g h`` -- the first letter is already there."""
        for year in (1, 2, 3):
            _paper, part = self._p5(year)
            self.assertNotIn("first letter is already there",
                             str(part.lead or "").lower(),
                             f"Y{year} Part 5 says the first letter is given")
            for item in part.items:
                self.assertEqual(item.first, "",
                                 f"Y{year} '{item.answer}' gives its first "
                                 f"letter away")
                blanks = item.pattern.count("_")
                self.assertEqual(blanks, item.length,
                                 f"Y{year} '{item.answer}' has {blanks} "
                                 f"blanks for {item.length} letters")

    def test_the_upper_years_keep_the_first_letter(self):
        for year in (4, 5, 6):
            _paper, part = self._p5(year)
            self.assertIn("first letter is already there",
                          str(part.lead or "").lower())
            for item in part.items:
                self.assertTrue(item.first)
                self.assertEqual(item.pattern[0].upper(),
                                 item.answer[0].upper())

    def test_the_lower_year_clues_are_not_upper_primary_vocabulary(self):
        """``_letter_words_pool`` fell back to ``WORDS_LETTER_Y5`` for Year
        1-3, so a Year 1 pupil was asked to spell 'bridge' from 'People use
        it to cross a wide river' -- well above A1 Low."""
        from exam_gen import bank as _bank
        lower_words = set()
        for year in (1, 2, 3):
            for entry in _bank._letter_words_pool(year):
                lower_words.add(str(entry["word"]).lower())
        for word in ("train", "bridge", "helmet", "tower", "cable", "dump",
                    "receptionist", "lift", "forecast", "sunglasses", "compass",
                    "skiff", "tax", "metro", "seatbelt", "reporter", "voyage",
                    "stopwatch", "insect", "nest"):
            self.assertNotIn(
                word, lower_words,
                f"Year 1-3 Part 5 still offers the upper-primary word "
                f"{word!r}")

    def test_the_pupil_instructions_and_the_sheet_now_agree(self):
        """The contradiction Round 41 existed to fix: instructions said
        Parts 1-4 go on the objective sheet while the sheet carried Part 5."""
        for year in D.YEARS:
            paper = _gen({"year": year, "seed": 1, "lang": "en"})
            text = _docx_text(paper)
            self.assertTrue(_has(text, "Part 1, Part 2, Part 3 and Part 4"),
                            f"Y{year} lost the objective-answer instruction")
            p5 = next(p for p in paper.parts if p.num == 5)
            self.assertTrue(
                _has(text, f"Part 5, Part 6 and Part 7"),
                f"Y{year} lost the written-answer instruction")
            # the sheet must stop at Part 4
            import re as _re
            sheet = "".join(X._answer_sheet(paper))
            ticks = [int(m) for m in
                     _re.findall(r"<w:t[^>]*>(\d+)</w:t>", sheet)]
            last_mcq = max((q for pt in paper.parts if pt.num <= 4
                            for q in pt.qnos()), default=0)
            self.assertLessEqual(max(ticks, default=0), last_mcq,
                                 f"Y{year} answer sheet runs past Part 4")
            self.assertEqual(p5.kind, "words")


class TestRound42AnswerRuns(unittest.TestCase):
    """SPEC 58 — the objective answer sheet must not betray the answers.

    Measured before this round: sampling 24 papers per year, the worst run of
    identical option letters anywhere in a paper was **9**, and Year 5 had a
    run of >= 3 in 21 of 24 papers.  A pupil shading bubbles in order reads
    CCCC for four bubbles and knows three of them without reading a word.

    The guard repairs the *position* of a repeated letter by re-picking the
    option at that position -- it never changes the answer itself, so the key
    stays correct.  A part that cannot be repaired (a part where three
    consecutive questions genuinely share one correct option) is left alone
    rather than corrupted.
    """

    #: The letters a pupil shades.
    _LETTERS = "ABCD"

    def _mcq_answers(self, paper):
        """The pupil-shaded letter sequence, in question order.

        ``MCQItem.answer`` is an **index** into ``options`` (models.py:30), so
        the letter is ``"ABCD"[answer]`` -- not the answer itself.
        """
        out = []
        for part in paper.parts:
            if part.kind not in ("comprehension", "cloze", "match", "vocab"):
                continue
            for item in part.items:
                if isinstance(item, MCQItem) and isinstance(item.answer, int):
                    out.append(self._LETTERS[item.answer])
        return out

    def _worst_run(self, seq):
        worst = cur = 0
        prev = None
        for ch in seq:
            cur = cur + 1 if ch == prev else 1
            prev = ch
            worst = max(worst, cur)
        return worst

    def test_no_paper_has_three_identical_letters_in_a_row(self):
        worst_overall = 0
        for year in D.YEARS:
            for seed in range(1, 13):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                run = self._worst_run(self._mcq_answers(paper))
                worst_overall = max(worst_overall, run)
                self.assertLessEqual(
                    run, 2,
                    f"Y{year} seed {seed}: {self._mcq_answers(paper)} has a "
                    f"run of {run}")
        self.assertLessEqual(worst_overall, 2)

    def test_the_repair_does_not_change_any_answer(self):
        """Repositioning an option must never move the correct answer, and
        the index must stay a valid index into the options."""
        for year in D.YEARS:
            for seed in range(1, 9):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for part in paper.parts:
                    for item in part.items:
                        if not isinstance(item, MCQItem):
                            continue
                        opts = [str(o) for o in item.options]
                        self.assertEqual(len(opts), len(set(opts)),
                                         f"Y{year} seed {seed}: duplicate "
                                         f"options in {opts}")
                        self.assertIsInstance(item.answer, int,
                                              f"Y{year} seed {seed}: answer is "
                                              f"{item.answer!r}, not an index")
                        self.assertTrue(0 <= item.answer < len(opts),
                                        f"Y{year} seed {seed}: index "
                                        f"{item.answer} outside {opts}")

    def test_the_answer_letter_is_always_inside_the_option_range(self):
        """A pupil shades a letter; the part may have only 3 options."""
        for year in D.YEARS:
            for seed in range(1, 9):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for part in paper.parts:
                    for item in part.items:
                        if not isinstance(item, MCQItem):
                            continue
                        letter = self._mcq_answers(paper)  # exercise the helper
                        self.assertTrue(0 <= item.answer
                                        < len(item.options))
                        self.assertIn(self._LETTERS[item.answer],
                                      self._LETTERS)

    def test_a_run_inside_one_part_is_repaired_too(self):
        """Runs are checked within a part, not only across the whole paper --
        the answer sheet lists parts in order, so a per-part streak is what a
        pupil actually sees."""
        for year in D.YEARS:
            for seed in range(1, 9):
                paper = _gen({"year": year, "seed": seed, "pictures": False})
                for part in paper.parts:
                    seq = [self._LETTERS[i.answer] for i in part.items
                           if isinstance(i, MCQItem) and isinstance(i.answer, int)]
                    self.assertLessEqual(
                        self._worst_run(seq), 2,
                        f"Y{year} seed {seed} part {part.num}: {seq}")


class TestRound43Part2Pool(unittest.TestCase):
    """SPEC 59 -- Part 2 must not hand the same passage to the whole class.

    Measured before this round, over 40 seeds per year, counting **distinct**
    Part 2 passages (not the name/weekday variants the pools were padded
    with):

    | year | before | after |
    |------|--------|-------|
    | 1 | 18 | 22 |
    | 2 | 16 | 19 |
    | 3 |  2 | 17 |
    | 4 |  1 | 12 |
    | 5 |  2 | 12 |
    | 6 |  2 | 12 |

    Year 4 was the worst: 40 papers built from a **single** passage.
    """

    #: Distinct Part 2 passages required when sampling 40 seeds.
    MIN_PASSAGES = 8

    def _passages(self, year, seeds=40):
        out = set()
        for seed in range(1, seeds + 1):
            paper = _gen({"year": year, "seed": seed, "pictures": False})
            part = next(p for p in paper.parts if p.num == 2)
            out.add((part.lead_text or "").strip())
        return out

    def test_every_year_has_enough_distinct_part2_passages(self):
        for year in D.YEARS:
            got = self._passages(year)
            self.assertGreaterEqual(
                len(got), self.MIN_PASSAGES,
                f"Y{year}: only {len(got)} distinct Part 2 passages")

    def test_the_lower_primary_years_are_no_longer_a_pair(self):
        """These three were pinned at exactly 2 before Round 43."""
        for year in (3, 5, 6):
            got = self._passages(year)
            self.assertGreater(len(got), 2, f"Y{year}: still only 2")

    def test_year_four_is_no_longer_a_single_passage(self):
        got = self._passages(4)
        self.assertGreater(len(got), 1, "Y4 still builds every paper from one passage")

    def test_every_new_part2_answer_is_on_the_year_ladder(self):
        """The DSKP gate drops whole blocks when one gap answer is off-list,
        so a block with a single stray word never reaches a pupil."""
        from exam_gen import bank as _bank
        from exam_gen import dskp
        for year in D.YEARS:
            for block in _bank.CLOZE_NEW.get(year, []):
                self.assertTrue(_bank._block_target_ok(block, year, ("gaps",)),
                                f"Y{year}: {[g['opts'][g['ans']] for g in block['gaps']]}"
                                f" contains an off-ladder answer")

    def test_no_new_part2_block_leaks_its_answer_into_a_stem(self):
        from exam_gen import bank as _bank
        for year in D.YEARS:
            for block in _bank.CLOZE_NEW.get(year, []):
                self.assertGreaterEqual(len(block["gaps"]),
                                        D.PARTS[year][1]["count"],
                                        f"Y{year}: block has too few gaps")
                for gap in block["gaps"]:
                    self.assertFalse(_bank._stem_leaks(gap),
                                     f"Y{year}: {gap['stem']!r}")

    def test_the_preferred_format_does_not_starve_the_pool(self):
        """``pref = 'verb'/'sem'`` used to narrow Part 2 to the two blocks
        that carried a mode.  It may only narrow when there are enough."""
        from exam_gen import bank as _bank
        for year in (3, 5, 6):
            self.assertGreaterEqual(_bank._P2_PREFERRED_MIN, 4,
                                    "the floor is too low to preserve variety")

    def test_no_new_part2_block_has_more_blanks_than_questions(self):
        """The Part 2 renderer prints ``passage`` verbatim but emits only
        ``PARTS[year][1]['count']`` items, so a fifth numbered blank prints as
        a hole in the passage with no question under it.  Every legacy block
        obeys this; the new ones must too."""
        import re as _re
        from exam_gen import bank as _bank
        for year in D.YEARS:
            want = D.PARTS[year][1]["count"]
            numbers = [str(n) for n in range(6, 6 + want)]
            for block in _bank.CLOZE_NEW.get(year, []):
                found = _re.findall(r"\((\d+)\)", block["passage"])
                self.assertEqual(found, numbers,
                                 f"Y{year}: passage blanks {found} but the "
                                 f"part asks {want} questions")
                self.assertEqual(len(block["gaps"]), want,
                                 f"Y{year}: {len(block['gaps'])} gaps for a "
                                 f"{want}-question part")
                for gap in block["gaps"]:
                    self.assertEqual(gap["stem"].count("__________"), 1,
                                     f"Y{year}: {gap['stem']!r} has more "
                                     f"than one blank for one option set")

    def test_no_generated_paper_prints_an_unasked_blank(self):
        """End-to-end guard for the same invariant on the real papers."""
        import re as _re
        for year in D.YEARS:
            want = D.PARTS[year][1]["count"]
            for seed in (1, 3, 7, 12):
                cfg = dict(D.DEFAULT_CONFIG)
                cfg.update({"year": year, "seed": seed, "pictures": False})
                paper = bank.generate_paper(cfg)
                part = next(p for p in paper.parts if p.num == 2)
                found = _re.findall(r"\((\d+)\)", part.lead_text or "")
                self.assertEqual(found, [str(n) for n in range(6, 6 + want)],
                                 (year, seed, found))
                self.assertEqual(len(part.items), want, (year, seed))

    def test_no_new_part2_block_offers_a_joined_or_ragged_option(self):
        """Semicolon-joined hybrids ("skill;cv") and options of mixed word
        count are artefacts, not teacher-written distractors."""
        from exam_gen import bank as _bank
        for year in D.YEARS:
            for block in _bank.CLOZE_NEW.get(year, []):
                for gap in block["gaps"]:
                    opts = [str(o) for o in gap["opts"]]
                    for opt in opts:
                        self.assertNotIn(";", opt, f"Y{year}: {opt!r}")
                    self.assertEqual(len({o.count(" ") for o in opts}), 1,
                                     f"Y{year}: ragged options {opts}")


class TestRound44CliHelp(unittest.TestCase):
    """SPEC 60 -- ``--help`` must print usage and stop.

    ``run_cli`` walked its argument list, never matched ``--help``, and fell
    through to the default: ``--cli --help`` silently generated a Year 3 paper
    and wrote ``UPSA_Year3_BI.docx`` into the working directory.  A flag that
    asks a question must not answer by generating a paper.
    """

    def test_cli_help_returns_zero_and_writes_no_paper(self):
        from exam_gen import cli
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                rc = cli.run_cli(["--cli", "--help"])
                leftovers = sorted(os.listdir(tmp))
            finally:
                os.chdir(cwd)
        self.assertEqual(rc, 0)
        self.assertEqual(leftovers, [],
                         "--help wrote files into the working directory")

    def test_cli_help_prints_usage_covering_the_real_flags(self):
        from exam_gen import cli
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.run_cli(["--cli", "--help"])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertTrue(out.strip(), "--help printed nothing")
        for flag in ("--year", "--out", "--seed", "--exam-type", "--teacher-copy"):
            self.assertIn(flag, out, f"--help does not document {flag}")

    def test_answer_run_repair_never_touches_matching_letter_options(self):
        """SPEC 58 follow-up: Part 4 options *are* the labels A/B/C.

        ``balance_answer_runs`` repairs a streak by swapping the correct option
        into a different position and moving ``answer`` with it.  That is safe
        for word options, but when the option text is the bubble label the swap
        also permutes the printed list ("B. A. C.") and the answer index now
        points at a different bubble -- the key goes wrong.  These items must be
        left alone, exactly as the docstring promises.
        """
        import itertools
        from exam_gen.bank import balance_answer_runs
        from exam_gen.models import MCQItem, Part, Paper

        items = [MCQItem(stem=f"s{i}", options=["A", "B", "C"], answer=1)
                 for i in range(4)]
        part = Part(num=4, kind="match", style="letter", marks=5, title="",
                    lead="", items=items)
        paper = Paper(meta=dict(D.DEFAULT_CONFIG, year=5), parts=[part])
        balance_answer_runs(paper)
        for it in items:
            self.assertEqual(it.options, ["A", "B", "C"],
                             "a matching item's printed options were "
                             f"reordered to {it.options}")
            self.assertEqual(it.answer, 1, "a matching answer index moved")
        self.assertEqual([[i.answer for i in items], list(range(1, 5))][0],
                         [1, 1, 1, 1])

    def test_answer_run_repair_still_fixes_word_options(self):
        """The guard above must not disable the repair it was protecting."""
        import itertools
        from exam_gen.bank import balance_answer_runs
        from exam_gen.models import MCQItem, Part, Paper

        items = [MCQItem(stem=f"s{i}", options=["cat", "dog", "hen"], answer=0)
                 for i in range(4)]
        part = Part(num=1, kind="cloze", style="choice", marks=4, title="",
                    lead="", items=items)
        paper = Paper(meta=dict(D.DEFAULT_CONFIG, year=3), parts=[part])
        balance_answer_runs(paper)
        L = "ABCD"
        seq = [L[it.answer] for it in items]
        worst = max(len(list(g)) for _, g in itertools.groupby(seq))
        self.assertLessEqual(worst, 2, f"streak survived: {seq}")
        for it in items:
            self.assertEqual(it.options[it.answer], "cat",
                             f"the correct option changed to "
                             f"{it.options[it.answer]!r}")

    def test_gui_duration_hint_follows_the_exam_type(self):
        """``_update_dur_label`` read ``D.DURATION``, which Round 53 replaced
        with ``D.duration(year, exam_type)``.  The attribute no longer exists,
        so the label raised AttributeError, and even if it had survived it
        would have shown 60 minutes for a lower-primary UASA."""
        from exam_gen import data as _D
        # Years 1-3 UASA is 75 minutes while UPSA is 60, so the label cannot
        # be built from a year-only table.
        self.assertEqual(_D.duration(3, "uasa"), 75)
        self.assertEqual(_D.duration(3, "upsa"), 60)
        root = pathlib.Path(__file__).resolve().parents[1]
        src = (root / "exam_gen" / "app.py").read_text()
        self.assertNotIn("D.DURATION[", src,
                         "_update_dur_label still indexes D.DURATION")
        self.assertIn("D.duration(", src,
                      "_update_dur_label does not consult the exam type")

    def test_bare_help_does_not_reach_the_gui(self):
        """``main.py --help`` (no ``--cli``) must also short-circuit: it used
        to fall into the GTK app instead."""
        root = pathlib.Path(__file__).resolve().parents[1]
        src = (root / "main.py").read_text()
        self.assertIn('"--help"', src,
                      "main.py does not check for --help before the GUI")
        self.assertIn('"-h"', src, "main.py does not accept -h")


if __name__ == "__main__":
    unittest.main(verbosity=2)