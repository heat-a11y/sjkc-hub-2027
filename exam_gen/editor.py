"""In-app structured paper editor.

The generated Paper model is edited through a simple field schema instead of
touching the raw HTML preview, so whatever the user types in the app is exactly
what the DOCX/PDF exporters render — nothing is lost in a HTML round-trip.

Two layers:
  * pure editing   — :func:`apply_edits` maps an ``edits`` dict back onto a
                     Paper (deep-copied, no mutation) — fully unit-testable
                     without a display.
  * GTK form       — :class:`PaperEditor` builds editable widgets for each
                     part/item from the schema and :meth:`collect` reads them
                     back into the same ``edits`` dict.
"""

from __future__ import annotations

from dataclasses import replace

from . import data as D
from .models import MCQItem, WordItem, WriteItem, Paper, Part

# field kinds used by both the schema and the GTK form
FIELD_ENTRY = "entry"          # single-line text
FIELD_MULTI = "multiline"      # multi-line text (passage, prompt, model)
FIELD_OPTIONS = "options"      # list of single-line texts
FIELD_BULLETS = "bullets"      # multi-line text, one bullet per line
FIELD_ANSWER = "answer"        # dropdown of the option letters
FIELD_LINES = "lines"          # integer spin (ruled writing lines)
FIELD_SKIP = "skip"

_SKIP = FIELD_SKIP


def _word_editable() -> list[dict]:
    return [
        {"kind": FIELD_ENTRY, "key": "clue",  "label": "Clue"},
        {"kind": FIELD_ENTRY, "key": "answer", "label": "Word (answer)"},
    ]


def _mcq_editable(item=None) -> list[dict]:
    out: list[dict] = []
    if getattr(item, "stimulus", None):
        # Round 26: Part 1 reads a short text, so the text itself is a field —
        # a teacher who cannot edit the stimulus cannot fix a bad item.
        out.append({"kind": FIELD_BULLETS, "key": "stimulus",
                    "label": "Stimulus (one line per row)"})
    out.append({"kind": FIELD_MULTI, "key": "stem", "label": "Question"})
    if getattr(item, "options", None) and not _is_label_options(item.options):
        out.append({"kind": FIELD_OPTIONS, "key": "options", "label": "Choices"})
    out.append({"kind": FIELD_ANSWER, "key": "answer", "label": "Correct answer"})
    return out


def _is_label_options(options) -> bool:
    """True for Part 4's ``["A", "B", "C"]`` letter labels.

    They are not choices the pupil picks between — they name the three texts
    printed in the part's ``lead_text`` — so offering them as editable rows let
    a teacher retype them and change nothing a pupil reads.
    """
    opts = [str(o or "").strip() for o in (options or [])]
    return bool(opts) and opts == ["A", "B", "C"][:len(opts)]


def _write_editable() -> list[dict]:
    return [
        {"kind": FIELD_MULTI, "key": "prompt", "label": "Prompt"},
        {"kind": FIELD_BULLETS, "key": "bullets", "label": "Bullets (one per line)"},
        {"kind": FIELD_MULTI, "key": "model", "label": "Contoh jawapan (model)"},
        {"kind": FIELD_ENTRY, "key": "salutation", "label": "Salutation"},
        {"kind": FIELD_ENTRY, "key": "subject", "label": "Email subject"},
        {"kind": FIELD_ENTRY, "key": "recipient", "label": "Email recipient"},
        {"kind": FIELD_ENTRY, "key": "closing", "label": "Letter closing"},
        {"kind": FIELD_ENTRY, "key": "word_count", "label": "Word-count instruction"},
        {"kind": FIELD_LINES, "key": "lines", "label": "Ruled lines"},
    ]


#: ordered list of editable part-group fields
PART_FIELDS = [
    {"kind": FIELD_MULTI, "key": "lead", "label": "Instructions (arahan)"},
    {"kind": FIELD_MULTI, "key": "lead_text", "label": "Passage / word box / texts"},
    # Round 26: Part 4 prints a worked example ("0. The prefects stand ... (C)")
    # straight from this field, but it had no editor row, so a teacher could
    # read it and never change it.
    {"kind": FIELD_MULTI, "key": "example", "label": "Worked example"},
]


def item_schema(item) -> list[dict]:
    """Editable-field schema for one item."""
    if isinstance(item, MCQItem):
        return _mcq_editable(item)
    if isinstance(item, WordItem):
        return _word_editable()
    if isinstance(item, WriteItem):
        return _write_editable()
    return []


def _as_int(v, fallback: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return fallback


def _lines(value, fallback) -> list[str] | None:
    """Normalise a multi-line field to ``list[str]`` (or ``None`` if empty).

    The form hands a stimulus back as one newline-joined string, the bank and
    the model hold a list, so both shapes have to be accepted.
    """
    if value is None:
        return fallback
    if isinstance(value, (list, tuple)):
        out = [str(v).strip() for v in value if str(v).strip()]
    else:
        out = [ln.strip() for ln in str(value).splitlines() if ln.strip()]
    return out or None


def _item_from(item, ie: dict):
    if isinstance(item, MCQItem):
        options = list(ie.get("options", item.options))
        ans = _as_int(ie.get("answer", item.answer), item.answer)
        ans = min(max(ans, 0), max(len(options) - 1, 0))
        # Round 26: the key prints ``ans_text or answer_label`` and every pool
        # pins ``ans_text`` to the chosen option, so leaving it alone after the
        # teacher re-picks an answer made the key keep announcing the *old*
        # one — a wrong mark scheme.  Re-derive it whenever the answer or the
        # option list moved.
        ans_text = ie.get("ans_text", item.ans_text)
        if ans != item.answer or options != list(item.options):
            ans_text = options[ans] if 0 <= ans < len(options) else None
        return replace(item,
                       stem=str(ie.get("stem", item.stem)),
                       options=options,
                       answer=ans,
                       ans_text=ans_text,
                       stimulus=_lines(ie.get("stimulus"), item.stimulus))
    if isinstance(item, WordItem):
        ans = str(ie.get("answer", item.answer)).strip()
        if not ans:
            ans = item.answer
        return replace(item,
                       clue=str(ie.get("clue", item.clue)),
                       answer=ans,
                       first=ans[:1].upper(),
                       length=len(ans))
    if isinstance(item, WriteItem):
        bullets = [str(b).strip() for b in ie.get("bullets", item.bullets)
                   if str(b).strip()]
        return replace(item,
                       prompt=str(ie.get("prompt", item.prompt)),
                       bullets=bullets,
                       model=str(ie.get("model", item.model)),
                       salutation=str(ie.get("salutation", item.salutation)),
                       subject=str(ie.get("subject", item.subject)),
                       recipient=str(ie.get("recipient", item.recipient)),
                       closing=str(ie.get("closing", item.closing)),
                       word_count=str(ie.get("word_count", item.word_count)),
                       lines=_as_int(ie.get("lines", item.lines), item.lines))
    return item


def apply_edits(paper: Paper, edits: dict) -> Paper:
    """Return a new Paper with the user's edits applied (input untouched).

    ``edits`` mirrors the widget form::

        {"parts": [
            {"lead": str, "lead_text": str,
             "items": [{"stem": str, "options": [...], "answer": int, ...}]},
            ...
        ]}

    Keys that are absent or unchanged simply keep their old values; ``answer``
    is clamped to the (possibly edited) option list.
    """
    parts: list[Part] = []
    for i, part in enumerate(paper.parts):
        ed = edits.get("parts", [])[i] if i < len(edits.get("parts", [])) else {}
        if not ed:
            parts.append(part)
            continue
        items = []
        for j, item in enumerate(part.items):
            ie = (ed.get("items") or [])[j] if j < len((ed.get("items") or [])) else {}
            items.append(_item_from(item, ie))
        parts.append(replace(part,
                             lead=str(ed.get("lead", part.lead)),
                             lead_text=str(ed.get("lead_text", part.lead_text)),
                             # keep the model's None for "no example" rather
                             # than storing "", which renderers test with
                             # ``is not None``
                             example=str(ed.get(
                                 "example", getattr(part, "example", "")
                                 or "")) or None,
                             marks=_as_int(ed.get("marks", part.marks), part.marks),
                             lines=_as_int(ed.get("lines", part.lines), part.lines),
                             items=items))
    return replace(paper, parts=parts)


# ---------------------------------------------------------------------------
# GTK form
# ---------------------------------------------------------------------------

def _gtk_import():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    return Gtk


def item_to_edit(item) -> dict:
    """Default ``edits`` value for one item (its current values, schema keys)."""
    out: dict = {}
    for f in item_schema(item):
        key, kind = f["key"], f["kind"]
        if kind == FIELD_ANSWER:
            out[key] = getattr(item, "answer", 0)
        elif kind == FIELD_OPTIONS:
            out[key] = list(getattr(item, "options", []))
        elif kind == FIELD_BULLETS:
            out[key] = list(getattr(item, key, []))
        else:
            out[key] = getattr(item, key, "")
            if kind == FIELD_LINES:
                out[key] = _as_int(out[key], 0)
    return out


def part_to_edit(part: Part, target_item: int | None = None,
                 item_override: dict | None = None) -> dict:
    """``edits`` value for a whole part (all items), so a single-item change
    can be merged into a self-contained part edit for :func:`apply_edits`.

    When ``target_item`` and ``item_override`` are given, only that item's
    entry is replaced; every other item keeps its current values.
    """
    items = [item_to_edit(it) for it in part.items]
    if target_item is not None and item_override and 0 <= target_item < len(items):
        merged = dict(items[target_item])
        merged.update(item_override)
        items[target_item] = merged
    return {"lead": str(part.lead),
            "lead_text": str(part.lead_text or ""),
            "example": str(getattr(part, "example", "") or ""),
            "marks": int(getattr(part, "marks", 0) or 0),
            "lines": int(getattr(part, "lines", 0) or 0),
            "items": items}


class PaperEditor:
    """Scrolled GTK form that edits every part/item of a Paper.

    Use :meth:`collect` to read the widget values back into an ``edits`` dict
    accepted by :func:`apply_edits`.
    """

    def __init__(self, paper: Paper):
        Gtk = _gtk_import()
        self._Gtk = Gtk
        self._rows: dict[str, object] = {}
        self._items: list[dict[str, object]] = []
        self._part_edits: list[dict] = []
        self.on_save_to_bank = None
        # Option markers differ by year ("A)" in Years 1-2, "A." from
        # Year 3), so the editor must label them the way the paper will.
        self._opt_labels = D.option_labels(8, paper.year())

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.root = box

        for i, part in enumerate(paper.parts):
            pf = self._part_group(part, i)
            self._part_edits.append(pf)
            box.append(pf["widget"])
        scrolled.set_child(box)
        self.scrolled = scrolled

    # -- widget builders ----------------------------------------------------
    def _part_group(self, part: Part, idx: int) -> dict:
        Gtk = self._Gtk
        frame = Gtk.Frame()
        frame.set_label(f"PART {part.num} — {part.kind} / {part.style}")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_top(10)
        inner.set_margin_bottom(10)
        inner.set_margin_start(12)
        inner.set_margin_end(12)
        frame.set_child(inner)

        fields = {}
        for f in PART_FIELDS:
            value = getattr(part, f["key"], None)
            if f["kind"] == FIELD_MULTI:
                # Round 26: the worked-example row only appears for the parts
                # that print one (Part 4), so the other six do not each gain an
                # empty box.
                if f["key"] == "example" and not value:
                    continue
                w = self._text_view(str(value or ""))
                inner.append(self._row(f["label"], w))
                fields[f["key"]] = w
            else:
                fields[f["key"]] = None

        marks = Gtk.SpinButton.new_with_range(1, 100, 1)
        marks.set_value(float(part.marks))
        marks.set_tooltip_text("Marks for this part")
        inner.append(self._row("Marks", marks))
        fields["marks"] = marks

        if getattr(part, "kind", "") == "writing":
            lines = Gtk.SpinButton.new_with_range(0, 40, 1)
            lines.set_value(float(int(getattr(part, "lines", 0) or 0)))
            lines.set_tooltip_text("Ruled lines on the answer sheet for THIS part")
            inner.append(self._row("Ruled lines", lines))
            fields["lines"] = lines

        if getattr(part, "kind", "") != "writing":
            save = Gtk.Button(label="Save to My Bank…")
            save.set_tooltip_text("Copy this part into your own question bank")
            ci = idx
            save.connect("clicked", lambda *_: self._save_part(ci))
            inner.append(save)

        for j, item in enumerate(part.items):
            gw = self._item_group(part, item, j)
            inner.append(gw["widget"])
            fields.setdefault("items", []).append(gw)

        return {"widget": frame, "fields": fields}

    def _item_group(self, part: Part, item, j: int) -> dict:
        Gtk = self._Gtk
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        qnos = part.qnos()
        qno = qnos[j] if j < len(qnos) else j + 1
        lab = Gtk.Label(label=f"Q{qno} — {type(item).__name__}", xalign=0.0,
                        css_classes=["overline"])
        box.append(lab)
        widgets: dict[str, object] = {}
        for f in item_schema(item):
            w = self._widget_for(f, item)
            widgets[f["key"]] = w
            box.append(self._row(f["label"], w))
        return {"widget": box, "widgets": widgets}

    def _widget_for(self, f: dict, item) -> object:
        Gtk = self._Gtk
        kind, key = f["kind"], f["key"]
        if kind == FIELD_MULTI:
            value = getattr(item, key, "")
            return self._text_view(str(value or ""))
        if kind == FIELD_BULLETS:
            value = getattr(item, key, [])
            return self._text_view("\n".join(str(v) for v in value))
        if kind == FIELD_OPTIONS:
            value = list(getattr(item, key, []))
            rows = []
            for o in value:
                rows.append(self._entry(str(o)))
            return {"type": "options", "rows": rows}
        if kind == FIELD_ANSWER:
            opts = list(getattr(item, "options", []))
            drop = Gtk.DropDown.new_from_strings(
                [self._opt_letter(i) + " " + (o or "")
                 for i, o in enumerate(opts)])
            drop.set_selected(min(getattr(item, "answer", 0),
                                  max(len(opts) - 1, 0)))
            return {"type": "answer", "drop": drop}
        if kind == FIELD_LINES:
            sp = Gtk.SpinButton.new_with_range(0, 40, 1)
            sp.set_value(float(getattr(item, key, 0)))
            return sp
        # FIELD_ENTRY
        value = getattr(item, key, "")
        return self._entry(str(value or ""))

    def _entry(self, text: str):
        e = self._Gtk.Entry()
        e.set_text(text)
        return e

    def _text_view(self, text: str):
        Gtk = self._Gtk
        tv = Gtk.TextView()
        tv.set_wrap_mode(Gtk.WrapMode.WORD)
        tv.set_hexpand(True)
        tv.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        buf = tv.get_buffer()
        buf.set_text(text, -1)
        tv.set_size_request(-1, 74)
        return tv

    def _opt_letter(self, i: int) -> str:
        if i < len(self._opt_labels):
            return self._opt_labels[i]
        return str(i + 1) + D.option_marker(0)

    def _row(self, label: str, widget) -> Gtk.Widget:
        Gtk = self._Gtk
        if isinstance(widget, dict):
            if widget["type"] == "options":
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                for i, e in enumerate(widget["rows"]):
                    r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    letter = Gtk.Label(
                        label=self._opt_letter(i), xalign=0.0)
                    r.append(letter)
                    r.append(e)
                    inner.append(r)
            elif widget["type"] == "answer":
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                inner.append(widget["drop"])
            else:  # pragma: no cover - defensive
                inner = Gtk.Box()
            widget = inner
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lab = Gtk.Label(label=label, xalign=0.0, hexpand=True, wrap=True,
                        css_classes=["muted"])
        row.append(lab)
        row.append(widget)
        return row

    # -- read-back -----------------------------------------------------------
    def _text(self, widget) -> str:
        buf = widget.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True) or ""

    def _entry_text(self, widget) -> str:
        return widget.get_text() or ""

    def collect(self) -> dict:
        """Read every widget into the ``edits`` structure for apply_edits."""
        edits: list[dict] = []
        for pf in self._part_edits:
            fields = pf["fields"]
            pe: dict = {
                "lead": self._text(fields["lead"]),
                "lead_text": self._text(fields["lead_text"]),
                "items": [],
            }
            if "example" in fields:
                pe["example"] = self._text(fields["example"])
            if "marks" in fields:
                pe["marks"] = int(fields["marks"].get_value())
            if "lines" in fields:
                pe["lines"] = int(fields["lines"].get_value())
            for gw in fields.get("items", []):
                wd: dict = {}
                for key, w in gw["widgets"].items():
                    if isinstance(w, dict):
                        if w["type"] == "options":
                            wd[key] = [self._entry_text(e) for e in w["rows"]]
                        elif w["type"] == "answer":
                            wd[key] = int(w["drop"].get_selected())
                    elif isinstance(w, self._Gtk.TextView):
                        wd[key] = self._text(w)
                    elif isinstance(w, self._Gtk.Entry):
                        wd[key] = self._entry_text(w)
                    elif isinstance(w, self._Gtk.SpinButton):
                        wd[key] = int(w.get_value())
                pe["items"].append(wd)
            edits.append(pe)
        return {"parts": edits}

    def _save_part(self, part_idx: int):
        """Collect one part's edits and hand them to ``on_save_to_bank``.

        ``part_idx`` is the position within the editor's part list; the paper
        index is the same for the full editor but the quick editor shows only
        one part, so ``self.part_idx`` holds the real paper index there.
        """
        if self.on_save_to_bank is None:
            return
        try:
            parts = self.collect()["parts"]
        except Exception:
            parts = []
        if not (0 <= part_idx < len(parts)):
            return
        paper_idx = getattr(self, "part_idx", part_idx)
        self.on_save_to_bank(paper_idx, parts[part_idx])


class QuickItemEditor(PaperEditor):
    """Compact editor for one part's header fields plus a single question.

    Inline "click on the paper" editing: the live preview is marked up with
    ``data-eid`` anchors and clicking a part or question opens this small form
    for only that element — no scrolling to find the question.
    """

    def __init__(self, paper: Paper, part_idx: int, item_idx: int | None):
        part = paper.parts[part_idx]
        Gtk = _gtk_import()
        self._Gtk = Gtk
        self._part_edits: list[dict] = []
        self._items: list[dict[str, object]] = []
        # this editor builds its own state instead of calling super().__init__,
        # so it must repeat the option-marker setup _row/_item_group read
        self._opt_labels = D.option_labels(8, paper.year())

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.root = box
        self.scrolled = scrolled
        self.part_idx = part_idx
        self.item_idx = item_idx
        self.on_save_to_bank: callable | None = None

        pf = self._quick_group(part, item_idx)
        self._part_edits.append(pf)
        box.append(pf["widget"])
        scrolled.set_child(box)

    def _quick_group(self, part: Part, item_idx: int | None) -> dict:
        Gtk = self._Gtk
        frame = Gtk.Frame()
        if item_idx is None:
            frame.set_label(f"PART {part.num} — {part.kind} / {part.style}")
        else:
            qnos = part.qnos()
            q = qnos[min(item_idx, len(qnos) - 1)] if qnos else "?"
            frame.set_label(f"PART {part.num} · Q{q}")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_top(10)
        inner.set_margin_bottom(10)
        inner.set_margin_start(12)
        inner.set_margin_end(12)
        frame.set_child(inner)

        fields: dict = {}
        for f in PART_FIELDS:
            value = getattr(part, f["key"], None)
            if f["kind"] == FIELD_MULTI:
                # Round 26: the worked-example row only appears for the parts
                # that print one (Part 4), so the other six do not each gain an
                # empty box.
                if f["key"] == "example" and not value:
                    continue
                w = self._text_view(str(value or ""))
                inner.append(self._row(f["label"], w))
                fields[f["key"]] = w
            else:
                fields[f["key"]] = None

        marks = Gtk.SpinButton.new_with_range(1, 100, 1)
        marks.set_value(float(getattr(part, "marks", 0) or 0))
        inner.append(self._row("Marks", marks))
        fields["marks"] = marks

        if item_idx is not None and part.items:
            i = min(item_idx, len(part.items) - 1)
            gw = self._item_group(part, part.items[i], i)
            inner.append(gw["widget"])
            fields["items"] = [gw]

        if part.kind == "writing":
            lines = Gtk.SpinButton.new_with_range(0, 40, 1)
            lines.set_value(float(int(getattr(part, "lines", 0) or 0)))
            lines.set_tooltip_text("Ruled lines on the answer sheet for this part")
            inner.append(self._row("Ruled lines", lines))
            fields["lines"] = lines
        else:
            save = Gtk.Button(label="Save to My Bank…")
            save.set_tooltip_text("Copy this part into your own question bank")
            ci = self.part_idx
            save.connect("clicked", lambda *_: self._save_part(ci))
            inner.append(save)

        return {"widget": frame, "fields": fields}